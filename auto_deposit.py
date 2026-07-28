# auto_deposit.py
"""Motor de selección del modo auto de depósito (Task B).

Funciones puras de selección de cuentas/tarjetas + planner que toca la BD.
Los imports de módulos del repo (deposits, jwt_keeper, account_refresh, app)
son SIEMPRE lazy dentro de función — patrón del repo para evitar imports
circulares (app → auto_deposit → deposits → app).

La lógica de filtros de `select_accounts_for_auto` replica
`jwt_keeper.select_refresh_candidates` (jwt_keeper.py:75-129) con tweaks
para depósito: exige JWT VIVO (> now + 60, no por expirar) y cap 24h
suficiente para amount × count.
"""
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

THREEDS_RECENT_H = 24  # 3DS en las últimas N horas → BIN penalizado


# ── helpers internos ─────────────────────────────────────────────────────────
def _now_epoch() -> int:
    return int(time.time())


def _grade_rank(grade: Any) -> int:
    from jwt_keeper import _GRADE_RANK
    return _GRADE_RANK.get(grade or "", 9)


def _sa_tokens() -> set:
    """Tokens que identifican al SA en locked_by (excepción RESERVADA_SA).

    Lazy + defensivo: las funciones puras deben seguir siendo puras aunque
    account_refresh no sea importable en el contexto del caller.
    """
    try:
        from account_refresh import _sa_lock_tokens
        return {str(t).lower() for t in (_sa_lock_tokens() or [])}
    except Exception:
        return set()


def _cd_active(cd: Any, now: int) -> bool:
    """cooldown_until (epoch) activo, vía deposits._cooldown_active.

    Fallback a la semántica epoch de jwt_keeper si la firma no acepta el
    valor crudo (no enmascara otros errores — solo TypeError/AttributeError).
    """
    if cd in (None, ""):
        return False
    try:
        import deposits as dep
        return bool(dep._cooldown_active(cd))
    except (TypeError, AttributeError):
        try:
            return int(cd) > now
        except (TypeError, ValueError):
            return False


def _exp_int(v: Any) -> int:
    if v in (None, ""):
        return 0
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _bin_of(card: Dict[str, Any]) -> str:
    # BIN = card_number[:6] (deposits.py:236)
    return str(card.get("card_number") or "")[:6]


def _approval_rate(stats: Optional[Dict[str, Any]]) -> float:
    """approval_rate COMPUTADO (total_approved/total_attempts) — NO es columna."""
    stats = stats or {}
    att = stats.get("total_attempts") or 0
    if not att:
        return 0.0
    return (stats.get("total_approved") or 0) / att


def _threeds_recent(stats: Optional[Dict[str, Any]]) -> bool:
    """True si el BIN tuvo 3DS en las últimas THREEDS_RECENT_H horas."""
    stats = stats or {}
    if not (stats.get("total_3ds") or 0):
        return False
    last = stats.get("last_3ds_at")
    if not last:
        return False
    try:
        dt = datetime.fromisoformat(str(last).replace(" ", "T").replace("Z", "+00:00"))
    except ValueError:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - dt < timedelta(hours=THREEDS_RECENT_H)


def _rank_key(card: Dict[str, Any], bin_stats_map: Dict[str, Any]):
    """Peor primero si 3DS reciente; luego mejor approval_rate primero."""
    st = (bin_stats_map or {}).get(_bin_of(card)) or {}
    return (1 if _threeds_recent(st) else 0, -_approval_rate(st))


def _pipe_str(card: Dict[str, Any]) -> str:
    return "{}|{}|{}".format(
        card.get("card_number") or "",
        card.get("card_expiry") or "",
        card.get("card_cvv") or "",
    )


# ── B1 — selección de cuentas (pura) ─────────────────────────────────────────
MM_ACCOUNT_RECENT_DECLINE_LIMIT = 2  # >= N declines en 12h → cuenta fuera de selección (Robert 2026-07-28)


def select_accounts_for_auto(
    rows: List[Dict[str, Any]],
    amount: float,
    count: int,
    window_map: Dict[str, Dict[str, Any]],
    decline_map: Optional[Dict[str, int]] = None,
    meta_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Filtra + ordena + limita cuentas candidatas al depósito auto.

    Filtros en orden (replica jwt_keeper.select_refresh_candidates con tweaks):
      1. status == 'LIVE'
      2. grade IN ('A+','A','B')
      3. published_to_pool == 1 (o excepción RESERVADA_SA: pool=0 + locked_by
         del SA — igual que jwt_keeper:85-95)
      4. locked_by IS NULL
      5. cooldown_until no activo (epoch, vía deposits._cooldown_active)
      6. jwt_expires_at > now + 60 (aquí se exige JWT VIVO, no por expirar)
      7. window_map[email]["available"] >= amount * count (cap 24h alcanza;
         email ausente del map → sin restricción, el caller decide)
      8. decline_map[email] < MM_ACCOUNT_RECENT_DECLINE_LIMIT (Robert 2026-07-28:
         cuenta con >=2 declines en las últimas 12h no se taladra de nuevo;
         decline_map=None → sin restricción, backward-compat)

    Orden (Reglas de priorización Robert 2026-07-28):
      1. 3DS reciente / Grade 'A+' (bonificación top)
      2. Ponderación de declines por antigüedad (recientes pesan más que viejos)
      3. Recuencia de intentos/movimientos recientes (penaliza cuentas intentadas recientemente)
      4. Cantidad de tarjetas asociadas en dashboard (>=3 tarjetas bajan de prioridad)
      5. Grade rank y score base.

    Corta en `count`.
    """
    now = _now_epoch()
    sa = _sa_tokens()
    out: List[Dict[str, Any]] = []
    meta_map = meta_map or {}

    for r in rows:
        email = r.get("email")
        if (r.get("status") or "") != "LIVE":
            continue
        if (r.get("grade") or "") not in ("A+", "A", "B"):
            continue
        locked_by = r.get("locked_by")
        # RESERVADA_SA (pool=0 + locked_by del SA) → candidata.
        is_sa_reserved = (
            not r.get("published_to_pool")
            and str(locked_by).lower() in sa
        )
        if not is_sa_reserved:
            if not r.get("published_to_pool"):
                continue
            if locked_by is not None:
                continue
        if _cd_active(r.get("cooldown_until"), now):
            continue
        if _exp_int(r.get("jwt_expires_at")) <= now + 60:
            continue
        win = (window_map or {}).get(email) or {}
        avail = win.get("available")
        if avail is not None and float(avail) < amount * count:
            continue
        if decline_map is not None:
            if (decline_map.get(email) or 0) >= MM_ACCOUNT_RECENT_DECLINE_LIMIT:
                continue
        out.append(r)

    def _calc_rank_score(r: Dict[str, Any]) -> float:
        email = r.get("email")
        meta = meta_map.get(email) or {}

        # 1. 3DS / Grade A+ (Prioridad superior -> menor score en la tupla de sort)
        grade = r.get("grade") or ""
        is_3ds = 1 if grade == "A+" else 0

        # 2. Declines acumulados con peso por antigüedad
        # weighted_declines: recs <2h (1.0), 2-12h (0.4), >12h (0.1)
        w_declines = meta.get("weighted_declines", 0.0)

        # 3. Recuencia de intento / movimiento reciente (minutos desde el último intento)
        # Menos minutos (muy reciente) -> mayor penalización
        last_min = meta.get("mins_since_last_attempt", 99999)
        recency_penalty = 50.0 / (last_min + 1)  # recientísimo = penalty ~50

        # 4. Tarjetas asociadas en dashboard (>=3 bajan prioridad)
        card_count = meta.get("card_count", 0)
        card_penalty = 20.0 if card_count >= 3 else 0.0

        # Tupla de ordenamiento: menor score global va primero
        # -is_3ds (-1 primero), luego peso acumulado de penalización, luego grade base
        total_penalty = (w_declines * 15.0) + recency_penalty + card_penalty + (_grade_rank(grade) * 5.0) - (r.get("grade_score") or 0) * 0.1
        return (-is_3ds, total_penalty)

    # Estratificación en 3 Tiers (Top, Mid, Low) + Selección Intercalada (Round-Robin)
    # Robert 2026-07-28: No agotar solo las A+, intercalar 1 Top, 1 Mid, 1 Low...
    # Excepción: si se piden <= 3 cuentas (ej. count=1, 2 o 3), prioriza las mejores absolutas (Top first).
    out.sort(key=_calc_rank_score)

    if count <= 3 or len(out) <= 3:
        return out[:count]

    # Dividir en 3 estratos
    n = len(out)
    t1_end = max(1, n // 3)
    t2_end = max(t1_end + 1, (2 * n) // 3)

    tier_top = out[:t1_end]
    tier_mid = out[t1_end:t2_end]
    tier_low = out[t2_end:]

    stratified = []
    i_top, i_mid, i_low = 0, 0, 0

    while len(stratified) < count and (i_top < len(tier_top) or i_mid < len(tier_mid) or i_low < len(tier_low)):
        if i_top < len(tier_top):
            stratified.append(tier_top[i_top])
            i_top += 1
            if len(stratified) == count: break
        if i_mid < len(tier_mid):
            stratified.append(tier_mid[i_mid])
            i_mid += 1
            if len(stratified) == count: break
        if i_low < len(tier_low):
            stratified.append(tier_low[i_low])
            i_low += 1
            if len(stratified) == count: break

    return stratified


# ── B2 — selección de tarjeta (pura) ─────────────────────────────────────────
def select_card_for_account(
    account_email: str,
    cards_married: List[Dict[str, Any]],
    bin_stats_map: Dict[str, Dict[str, Any]],
    amount: float,
) -> Optional[str]:
    """Prioridad: (1) tarjeta casada ACTIVE de la cuenta (fila account_cards
    con account_email=? AND status='ACTIVE' — no hay columna married ni bin),
    (2) BIN con mejor approval_rate COMPUTADO (approved/attempts) y sin 3DS
    reciente (total_3ds > 0 y last_3ds_at reciente → penalizado),
    (3) None si no hay viable.

    Retorna pipe "number|expiry|cvv" o None.
    """
    cands = [
        c for c in (cards_married or [])
        if c.get("account_email") == account_email
        and (c.get("status") or "ACTIVE") == "ACTIVE"
    ]
    if not cands:
        return None
    cands.sort(key=lambda c: _rank_key(c, bin_stats_map))
    return _pipe_str(cands[0])


# ── B3 — planner (toca la BD) ────────────────────────────────────────────────
def _max_accounts_for_cards(num_cards: int) -> int:
    """Robert 2026-07-28: 3 cuentas para la 1a tarjeta + 1 extra por tarjeta
    adicional — evita taladrar todo el pool para lograr el match, con rango
    suficiente cuando hay más tarjetas para probar."""
    return 3 + max(0, num_cards - 1)


def plan_auto_mission(
    db_path,
    card_pipes: List[str],
    amount: float = 150,
    target_count: int = 9,
    max_accounts: Optional[int] = None,
) -> Dict[str, Any]:
    """Plan de misión auto: cuentas elegibles + tarjeta asignada a cada una.

    Retorna {accounts: [{id, email, grade, card_pipe}], total_estimated,
    feasible, reason}.

    - Cuentas: select_accounts_for_auto sobre `accounts` de la BD; el
      window_map se computa desde deposit_attempts con la misma semántica de
      deposits._window_status (available = max(0, DEP_MAX_24H - used 24h)).
      decline_map (Robert 2026-07-28) cuenta declines en las últimas 12h por
      cuenta — >=2 la saca de la selección (cuenta ya "quemada" reciente).
    - Tarjeta: married ACTIVE de la cuenta si existe; si no, pool de
      card_pipes rankeado por approval_rate computado / 3DS reciente.
    - max_accounts: si no se pasa explícito, se escala con el número de
      tarjetas pegadas (`_max_accounts_for_cards`).
    - feasible = hay cuentas Y todas tienen tarjeta viable.
    """
    import sqlite3
    import deposits as dep

    if max_accounts is None:
        max_accounts = _max_accounts_for_cards(len(card_pipes or []))

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in con.execute("SELECT * FROM accounts").fetchall()]
        window_map: Dict[str, Dict[str, Any]] = {}
        decline_map: Dict[str, int] = {}
        meta_map: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            email = r.get("email")
            used = con.execute(
                "SELECT COALESCE(SUM(amount),0) AS s FROM deposit_attempts "
                "WHERE account_email=? AND UPPER(status)='APPROVED' "
                "AND created_at >= datetime('now','-24 hours')",
                (email,),
            ).fetchone()["s"]
            window_map[email] = {
                "available": max(0.0, float(dep.DEP_MAX_24H) - float(used or 0))
            }
            declines = con.execute(
                "SELECT COUNT(*) AS n FROM deposit_attempts "
                "WHERE account_email=? AND UPPER(status)='REJECTED' "
                "AND created_at >= datetime('now','-12 hours')",
                (email,),
            ).fetchone()["n"]
            decline_map[email] = int(declines or 0)

            # Métricas avanzadas para la fórmula de priorización
            # 1. Ponderación de declines por antigüedad
            d_recent = con.execute(
                "SELECT created_at FROM deposit_attempts "
                "WHERE account_email=? AND UPPER(status)='REJECTED' "
                "ORDER BY created_at DESC LIMIT 20",
                (email,),
            ).fetchall()
            now_dt = datetime.now(timezone.utc)
            w_declines = 0.0
            for d_row in d_recent:
                try:
                    dt = datetime.fromisoformat(str(d_row["created_at"]).replace(" ", "T").replace("Z", "+00:00"))
                    if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
                    hrs = (now_dt - dt).total_seconds() / 3600.0
                    if hrs < 2: w_declines += 1.0
                    elif hrs < 12: w_declines += 0.4
                    else: w_declines += 0.1
                except Exception:
                    w_declines += 0.2

            # 2. Minutos desde el último intento/movimiento (evita taladrar recientemente intentadas)
            last_att = con.execute(
                "SELECT created_at FROM deposit_attempts "
                "WHERE account_email=? ORDER BY created_at DESC LIMIT 1",
                (email,),
            ).fetchone()
            mins_since = 99999
            if last_att and last_att["created_at"]:
                try:
                    dt = datetime.fromisoformat(str(last_att["created_at"]).replace(" ", "T").replace("Z", "+00:00"))
                    if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
                    mins_since = int((now_dt - dt).total_seconds() / 60.0)
                except Exception:
                    pass

            # 3. Tarjetas asociadas en dashboard (>=3 bajan prioridad)
            card_cnt = con.execute(
                "SELECT COUNT(*) AS c FROM account_cards WHERE account_email=? AND status='ACTIVE'",
                (email,),
            ).fetchone()["c"]

            meta_map[email] = {
                "weighted_declines": w_declines,
                "mins_since_last_attempt": mins_since,
                "card_count": int(card_cnt or 0),
            }

        try:
            bin_stats_map = {
                str(s["bin"]): dict(s)
                for s in con.execute("SELECT * FROM bin_stats").fetchall()
            }
        except sqlite3.OperationalError:
            bin_stats_map = {}

        selected = select_accounts_for_auto(
            rows, amount, target_count, window_map, decline_map=decline_map, meta_map=meta_map
        )[:max_accounts]

        pool: List[Dict[str, Any]] = []
        for p in (card_pipes or []):
            parts = str(p).split("|")
            if parts and parts[0]:
                pool.append({
                    "card_number": parts[0],
                    "card_expiry": parts[1] if len(parts) > 1 else "",
                    "card_cvv": parts[2] if len(parts) > 2 else "",
                })
        pool.sort(key=lambda c: _rank_key(c, bin_stats_map))

        accounts_out: List[Dict[str, Any]] = []
        pool_i = 0
        for r in selected:
            email = r.get("email")
            married = [
                dict(c) for c in con.execute(
                    "SELECT * FROM account_cards "
                    "WHERE account_email=? AND status='ACTIVE'",
                    (email,),
                ).fetchall()
            ]
            pipe = select_card_for_account(email, married, bin_stats_map, amount)
            if pipe is None and pool:
                pipe = _pipe_str(pool[pool_i % len(pool)])
                pool_i += 1
            accounts_out.append({
                "id": r.get("id"), "email": email,
                "grade": r.get("grade"), "card_pipe": pipe,
            })
    finally:
        con.close()

    feasible = bool(accounts_out) and all(a["card_pipe"] for a in accounts_out)
    if feasible:
        reason = ""
    elif not accounts_out:
        reason = "sin cuentas elegibles"
    else:
        reason = "cuentas sin tarjeta viable"
    return {
        "accounts": accounts_out,
        "total_estimated": amount * target_count * len(accounts_out),
        "feasible": feasible,
        "reason": reason,
    }


# ════════════════════════════════════════════════════════════════════════════
# Task D — Orquestador de misión auto (matchmaking probe $10 + scheduled 9×$150)
#
# Reglas duras (plan v2, auditado por Claude):
#  1. Siempre r.get("jwt")/r.get("used_proxy") — returns tempranos no las traen.
#  2. Match sin JWT → Fase 2 arranca con session_jwt=None y captura en su 1er éxito.
#  3. Totales incrementales en auto_missions tras CADA intento (anti-zombie).
#  4. Cancel cooperativo: chequeo de status en BD entre iteraciones → unlock + salir.
#  5. 1 slot de _mission_sem para TODA la misión (cuentas secuenciales). Fail-fast.
#  6. NUNCA proxyless (lo garantiza _run_deposit_with_phases internamente).
#  7. Lock SOLO antes del 1er intento con tarjeta candidata; unlock si ninguna jala
#     y al cerrar la misión (el lock SA es perpetuo — no dejar cuentas reservadas).
#  8. _record_attempt tras CADA intento (patrón scheduled deposits.py:2486-2492).
#  9. Captcha pool vía _load_deps; stop cuando nadie más necesita login.
# 10. Imports cross-módulo SIEMPRE lazy dentro de función.
# 11. Reuso de sesión entre tarjetas de la MISMA cuenta (_mm_session_* :1782-1798).
# ════════════════════════════════════════════════════════════════════════════
import asyncio
import json
import logging
import os
import uuid

logger = logging.getLogger("betmexico.dashboard.auto_deposit")

PROBE_AMOUNT = 10.0          # D1: probe de matchmaking (dinero real, queda en la cuenta)
MATCH_TRANSIENT_RETRIES = 4  # = MM_MAX_PAIR_TRANSIENT (nuestro lado, no quema tarjeta)

# Regla Robert 2026-07-28 (anti-rafagueo):
#  - MISMA cuenta, otra tarjeta: esperar dep.MM_COOLDOWN (60s) antes de reintentar.
#  - Cuenta DISTINTA: basta un respiro de MM_CROSS_ACCOUNT_GAP (5s).
#  - Tope de declines reales por cuenta EN ESTA CORRIDA antes de abandonarla
#    (independiente del límite histórico de 12h aplicado en la selección).
MM_CROSS_ACCOUNT_GAP = 5
MM_MAX_ACCOUNT_DECLINES_PER_RUN = 2


# ── seams de BD/app (los tests los monkeypatchean; producción usa app.db) ─────
def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _m_load(mission_id: str) -> Optional[Dict[str, Any]]:
    """Fila de la misión (amount, target_count, card_pipes, status)."""
    from app import db
    with db() as c:
        row = c.execute(
            "SELECT * FROM auto_missions WHERE mission_id=?", (mission_id,)
        ).fetchone()
    return dict(row) if row else None


def _m_status(mission_id: str) -> Optional[str]:
    m = _m_load(mission_id)
    return m.get("status") if m else None


def _m_update(mission_id: str, **fields) -> None:
    """UPDATE incremental — SIEMPRE toca updated_at (regla 3, anti-zombie)."""
    from app import db
    fields["updated_at"] = _iso()
    cols = ", ".join(f"{k}=?" for k in fields)
    with db(write=True) as c:
        c.execute(
            f"UPDATE auto_missions SET {cols} WHERE mission_id=?",
            (*fields.values(), mission_id),
        )


def _fetch_account(account_id: int) -> Optional[Dict[str, Any]]:
    from app import db
    with db() as c:
        row = c.execute(
            "SELECT id, email, password FROM accounts WHERE id=?", (account_id,)
        ).fetchone()
    return dict(row) if row else None


def _unlock(account_id: int) -> None:
    """Unlock explícito (reglas 4 y 7). El lock SA es perpetuo (locked_until NULL)
    — sin esto la cuenta queda RESERVADA_SA para siempre tras la misión."""
    from app import db
    with db(write=True) as c:
        c.execute(
            "UPDATE accounts SET locked_by=NULL, locked_until=NULL WHERE id=?",
            (account_id,),
        )


def _broadcast_mission(mission_id: str, status: str, user: dict, **extra) -> None:
    from app import _broadcast, _resolve_who
    try:
        _broadcast({
            "type": "activity", "kind": "auto_mission",
            "mission_id": mission_id, "status": status, "ts": _iso(),
            **_resolve_who(user.get("telegram_id")), **extra,
        })
    except Exception as e:
        logger.warning(f"[Auto {mission_id}] broadcast falló ({status}): {e}")


async def _stop_pool(pool, mission_id: str) -> None:
    if pool is None:
        return
    try:
        await pool.stop()
        logger.info(f"[Auto {mission_id}] captcha pool detenido")
    except Exception as e:
        logger.warning(f"[Auto {mission_id}] no pude detener pool: {e}")


# ── orquestador ──────────────────────────────────────────────────────────────
async def run_auto_mission(mission_id: str, plan: Dict[str, Any], user: dict) -> None:
    """Orquesta Fase 1 (matchmaking probe $10) + Fase 2 (scheduled N×amount/60s)
    + Fase 3 (cierre). Lee amount/target_count/card_pipes de la fila de la misión
    (self-sufficient: no depende del shape exacto de `plan`)."""
    import deposits as dep

    operator_id = user.get("telegram_id")

    # Regla 5: fail-fast si el semáforo está lleno (el endpoint ya devolvió 429,
    # pero la misión pudo encolarse antes de que se llenara).
    if dep._mission_sem.locked():
        _m_update(mission_id, status="failed",
                  phase_detail="misiones activas — semáforo lleno", completed_at=_iso())
        return

    async with dep._mission_sem:
        make_pool = dep._load_deps()
        if make_pool is None:
            _m_update(mission_id, status="failed",
                      phase_detail="módulo de depósitos no disponible",
                      completed_at=_iso())
            return
        mission = _m_load(mission_id) or {}
        amount = float(mission.get("amount") or 150)
        target_count = int(mission.get("target_count") or 9)
        try:
            card_pipes = json.loads(mission.get("card_pipes") or "[]")
        except (TypeError, ValueError):
            card_pipes = []

        cap_key = os.environ.get("CAPMONSTER_KEY", "") or os.environ.get("BMX_CAPMONSTER_KEY", "")
        pool = make_pool(cap_key, size=2, workers=1)
        await pool.start_factory()
        asyncio.create_task(pool.prefetch(2))

        sessions: Dict[str, Any] = {}     # email -> (jwt, proxy) — regla 11
        matches: List[Dict[str, Any]] = []
        locked_ids: set = set()
        deposited = 0.0
        approved = 0
        failed = 0
        cancelled = False

        def _cancelled() -> bool:
            return _m_status(mission_id) == "cancelled"

        async def _attempt(email, password, pipe, amt, sj, sp):
            """Un intento de depósito + persistencia (regla 8). Retorna (r, ok, code)."""
            import deposits as _d
            num, exp, cvv = _d._parse_pipe(pipe)
            t0 = asyncio.get_event_loop().time()
            r = await _d._run_deposit_with_phases(
                email, password, num, exp, cvv, amt, user, pool, None,
                session_jwt=sj, session_proxy=sp,
                persist_login_data=(sj is None),
            )
            ok = bool(r.get("success"))
            code = r.get("result_code", "UNKNOWN")
            reason = r.get("error") or code
            duration = r.get("duration_ms") or int((asyncio.get_event_loop().time() - t0) * 1000)
            _d._record_attempt(
                uuid.uuid4().hex, email, amt,
                _d.classify_deposit_status(code, ok),
                reason, duration, operator_id, card_pipe=pipe,
            )
            return r, ok, code

        try:
            # ── FASE 1 — MATCHMAKING (probe $10 real, D1) ────────────────────
            _m_update(mission_id, status="matching",
                      phase_detail="buscando pares cuenta×tarjeta")
            _broadcast_mission(mission_id, "matching", user,
                               accounts=len(plan.get("accounts", [])))
            accounts_list = plan.get("accounts", [])
            for acc_idx, acc in enumerate(accounts_list):
                if _cancelled():
                    cancelled = True
                    break
                account_id, email = acc.get("id"), acc.get("email")
                acct = _fetch_account(account_id)
                if not acct:
                    continue

                # Emitir evento SSE de feedback: obteniendo datos/sesión de la cuenta
                _broadcast_mission(
                    mission_id,
                    "logging_in",
                    user,
                    email=email,
                    current=acc_idx + 1,
                    total=len(accounts_list),
                )

                # Tarjetas candidatas: la asignada (married si había) + pool (regla 7:
                # si no hay ninguna, siguiente cuenta SIN lockear)
                candidates = [p for p in [acc.get("card_pipe"), *card_pipes] if p]
                candidates = list(dict.fromkeys(candidates))  # dedup, orden estable
                if not candidates:
                    continue
                matched = False
                locked = False
                code = None
                account_declines = 0  # regla Robert 2026-07-28: tope por cuenta EN ESTA CORRIDA
                for pipe_idx, pipe in enumerate(candidates):
                    if matched or _cancelled():
                        break
                    if account_declines >= MM_MAX_ACCOUNT_DECLINES_PER_RUN:
                        break  # ya declinó 2 veces esta corrida — no taladrar más, siguiente cuenta
                    if not locked:  # regla 7: lock justo antes del 1er intento real
                        dep._auto_lock_for_deposit(account_id, operator_id, user, hours=4)
                        locked = True
                        locked_ids.add(account_id)
                    transient = 0
                    while True:  # reintentos transitorios del PAR (nuestro lado)
                        sj, sp = dep._mm_session_get(sessions, email)
                        r, ok, code = await _attempt(email, acct["password"], pipe,
                                                     PROBE_AMOUNT, sj, sp)
                        dep._mm_session_update(sessions, email, r)  # regla 11
                        if ok:
                            matched = True
                            deposited += PROBE_AMOUNT
                            approved += 1
                            matches.append({
                                "account_id": account_id, "email": email,
                                "card_pipe": pipe,
                                "jwt": r.get("jwt"), "proxy": r.get("used_proxy"),
                            })
                            _m_update(mission_id, matches=json.dumps(matches),
                                      total_deposited=deposited, total_approved=approved,
                                      phase_detail=f"match {email}")
                            _broadcast_mission(mission_id, "match", user,
                                               email=email, card_tail=f"···{pipe[:6]}")
                            break
                        if code in dep.MM_THREEDS_RC:
                            # 3DS → cuenta premium A+ (no es decline) — patrón :2541-2549
                            try:
                                from app import db as _adb
                                with _adb(write=True) as cdb:
                                    cdb.execute("UPDATE accounts SET grade='A+' WHERE email=?",
                                                (email,))
                            except Exception as ex:
                                logger.error(f"[Auto {mission_id}] no pude marcar A+ {email}: {ex}")
                            break  # siguiente tarjeta
                        if code == "RATE_LIMITED":
                            # Cuarentena instantánea + aviso SSE
                            dep._set_account_cooldown(email)
                            _broadcast_mission(
                                mission_id,
                                "cooldown",
                                user,
                                email=email,
                                reason="rate_limited",
                            )
                            break  # siguiente cuenta inmediatamente (0 espera)
                        if dep._mm_is_real_decline(code) or dep._mm_is_ambiguous_charge(code):
                            failed += 1
                            account_declines += 1
                            break  # siguiente tarjeta (decline real o cargo ambiguo: terminal)
                        if code in dep.MM_DEAD_RC:
                            failed += 1
                            account_declines += 1
                            break  # cuenta muerta — siguiente cuenta
                        # TRANSITORIO (nuestro lado) → reintentar el par
                        transient += 1
                        if transient > MATCH_TRANSIENT_RETRIES:
                            failed += 1
                            break
                        await asyncio.sleep(25)
                    if code and (code == "RATE_LIMITED" or code in dep.MM_DEAD_RC):
                        break  # siguiente cuenta inmediatamente
                    # Regla Robert 2026-07-28: 60s SOLO si vamos a reintentar OTRA
                    # tarjeta en la MISMA cuenta (no al salir hacia la siguiente cuenta).
                    has_more_candidates = pipe_idx < len(candidates) - 1
                    if (not matched and code is not None and has_more_candidates
                            and account_declines < MM_MAX_ACCOUNT_DECLINES_PER_RUN):
                        await asyncio.sleep(dep.MM_COOLDOWN)
                if locked and not matched:
                    _unlock(account_id)  # regla 7: no dejar 4h/perpetuo sin match
                    locked_ids.discard(account_id)
                # Regla Robert 2026-07-28: 5s de respiro entre CUENTAS distintas
                # (no 60s — ese piso es solo para reintentar en la misma cuenta).
                if not _cancelled() and acc_idx < len(accounts_list) - 1:
                    await asyncio.sleep(MM_CROSS_ACCOUNT_GAP)

            if not matches:
                _m_update(mission_id, status="failed" if not cancelled else "cancelled",
                          phase_detail="sin matches" if not cancelled else "cancelada por el operador",
                          total_deposited=deposited, total_approved=approved,
                          total_failed=failed, completed_at=_iso())
                _broadcast_mission(mission_id, "failed" if not cancelled else "cancelled",
                                   user, reason="sin matches")
                return

            # Si TODOS los matches capturaron sesión, el pool ya no se necesita (regla 9)
            if all(m.get("jwt") for m in matches):
                await _stop_pool(pool, mission_id)
                pool = None

            # ── FASE 2 — SCHEDULED por match (N×amount cada 60s, SP-2) ───────
            _m_update(mission_id, status="scheduling",
                      phase_detail=f"{len(matches)} matches — {target_count}×${amount:.0f}/60s")
            _broadcast_mission(mission_id, "scheduling", user, matches=len(matches))
            for m in matches:
                if _cancelled():
                    cancelled = True
                    break
                email = m["email"]
                acct = _fetch_account(m["account_id"])
                if not acct:
                    continue
                session_jwt, session_proxy = m.get("jwt"), m.get("proxy")  # regla 2
                completed = 0
                retries = 0
                while completed < target_count:
                    if _cancelled():
                        cancelled = True
                        break
                    r, ok, code = await _attempt(email, acct["password"], m["card_pipe"],
                                                 amount, session_jwt, session_proxy)
                    if ok:
                        completed += 1
                        retries = 0
                        deposited += amount
                        approved += 1
                        if session_jwt is None and r.get("jwt"):  # SP-2 verbatim (:2475)
                            session_jwt = r.get("jwt")
                            session_proxy = r.get("used_proxy")
                            m["jwt"], m["proxy"] = session_jwt, session_proxy
                            if all(mm.get("jwt") for mm in matches) and pool is not None:
                                await _stop_pool(pool, mission_id)
                                pool = None
                        _m_update(mission_id, total_deposited=deposited,
                                  total_approved=approved,
                                  phase_detail=f"{email} {completed}/{target_count}")
                        _broadcast_mission(mission_id, "scheduling", user,
                                           email=email, completed=completed,
                                           total=target_count)
                        if completed < target_count:
                            await asyncio.sleep(60)
                        continue
                    # Terminal para ESTA cuenta (no las demás) — misma ley que scheduled
                    if (code == "RATE_LIMITED" or code in dep.MM_THREEDS_RC
                            or dep._mm_is_real_decline(code) or code in dep.MM_DEAD_RC
                            or code == "PENDING_NOT_APPLIED" or dep._mm_is_ambiguous_charge(code)):
                        if code == "RATE_LIMITED":
                            dep._set_account_cooldown(email)
                        failed += 1
                        _m_update(mission_id, total_failed=failed,
                                  phase_detail=f"{email} abortada ({code})")
                        _broadcast_mission(mission_id, "scheduling", user,
                                           email=email, aborted=code)
                        break
                    # Transitorio → retry (SCHED_MAX_TRANSIENT_RETRIES=4, backoff 25s)
                    low = str(r.get("error") or "").lower()
                    if session_jwt and ("sesión rechazada" in low or "401" in low
                                        or "redirectlogin" in low):
                        session_jwt = session_proxy = None  # patrón :2594-2605
                        if pool is None:
                            pool = make_pool(cap_key, size=2, workers=1)
                            await pool.start_factory()
                            asyncio.create_task(pool.prefetch(1))
                    retries += 1
                    if retries > dep.SCHED_MAX_TRANSIENT_RETRIES:
                        failed += 1
                        _m_update(mission_id, total_failed=failed,
                                  phase_detail=f"{email} sin éxito tras {retries - 1} reintentos")
                        break
                    await asyncio.sleep(dep.SCHED_RETRY_BACKOFF_SEC)

            # ── FASE 3 — CIERRE ──────────────────────────────────────────────
            final = "cancelled" if cancelled else "completed"
            _m_update(mission_id, status=final,
                      phase_detail=("cancelada por el operador" if cancelled
                                    else f"${deposited:.0f} en {len(matches)} cuentas"),
                      total_deposited=deposited, total_approved=approved,
                      total_failed=failed, completed_at=_iso())
            _broadcast_mission(mission_id, final, user,
                               deposited=deposited, approved=approved, failed=failed,
                               accounts=len(matches))
        finally:
            await _stop_pool(pool, mission_id)
            for aid in locked_ids:  # regla 7: la misión no deja cuentas reservadas
                try:
                    _unlock(aid)
                except Exception as e:
                    logger.warning(f"[Auto {mission_id}] unlock {aid} falló: {e}")

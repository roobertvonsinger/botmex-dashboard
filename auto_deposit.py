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

import json
import logging
import os
import sqlite3
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


def _extract_card_number(p: str) -> str:
    """Extrae únicamente los dígitos del número de tarjeta (PAN, 15-16 dígitos)."""
    if not p:
        return ""
    parts = [part.strip() for part in str(p).replace(" ", "").split("|") if part.strip()]
    if not parts:
        return ""
    return "".join(filter(str.isdigit, parts[0]))


def _parse_card_pipe(p: str) -> Optional[Dict[str, Any]]:
    parts = [part.strip() for part in str(p).replace(" ", "").split("|") if part.strip()]
    if not parts or not parts[0]:
        return None
    card_num = "".join(filter(str.isdigit, parts[0]))
    if not card_num:
        return None
    if len(parts) == 3:
        exp_raw = parts[1].replace("/", "").strip()
        if len(exp_raw) == 6:  # MMYYYY -> MMYY
            exp = f"{exp_raw[:2]}{exp_raw[4:]}"
        elif len(exp_raw) == 4:
            exp = exp_raw
        elif len(exp_raw) == 3:  # MYY -> 0MYY
            exp = f"0{exp_raw}"
        else:
            exp = exp_raw
        return {
            "card_number": card_num,
            "card_expiry": exp,
            "card_cvv": parts[2],
        }
    if len(parts) == 4:
        mm = parts[1].zfill(2)
        yy = parts[2]
        cvv = parts[3]
        if len(yy) == 4:
            yy = yy[-2:]
        return {
            "card_number": card_num,
            "card_expiry": f"{mm}{yy}",
            "card_cvv": cvv,
        }
    return None


def _normalize_pipe_to_3part(p: str) -> str:
    c = _parse_card_pipe(p)
    return _pipe_str(c) if c else str(p).strip()


def _get_married_card_owners(db_path: Optional[str] = None) -> Dict[str, str]:
    """Carga el mapa de tarjetas casadas en BD: {card_number -> account_email}."""
    owners: Dict[str, str] = {}
    try:
        from app import DB_PATH
        target_db = db_path or DB_PATH
        con = sqlite3.connect(str(target_db))
        cols = [c[1] for c in con.execute("PRAGMA table_info(account_cards)").fetchall()]
        num_col = "card_number" if "card_number" in cols else "number" if "number" in cols else None
        if num_col:
            for r in con.execute(
                f"SELECT {num_col}, account_email FROM account_cards WHERE {num_col} IS NOT NULL AND {num_col} != ''"
            ).fetchall():
                c_num = _extract_card_number(str(r[0]))
                if c_num and r[1]:
                    owners[c_num] = str(r[1]).strip().lower()
        con.close()
    except Exception as ex:
        logger.debug(f"No se pudieron leer account_cards: {ex}")
    return owners


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
      0. Gate KYC Innegociable: kyc_verified == 1 (cuentas sin verificar o con validación revocada jamás depositan)
      0b. Cero dead_reason o dead_at persistidos en BD
      1. status == 'LIVE' (estricto)
      2. published_to_pool == 1 (o excepción RESERVADA_SA)
      3. locked_by IS NULL
      4. cooldown_until no activo
      5. Cooldown de 48h por depósito APROBADO en el dashboard
      6. window_map[email]["available"] >= amount * count
      7. decline_map[email] < MM_ACCOUNT_RECENT_DECLINE_LIMIT (2 declines en 12h)
      8. Cero IsUserInValidationProcess o DEAD reciente en meta_map
      9. Cero racha de declinaciones terminales (a_plus_decline_streak < 2)

    Estratificación Inteligente Backend:
      - Tier TOP: 3DS reciente (<24h), Grade A+ con sesión activa 🟢 o alta afinidad de conversión.
      - Tier MID: Grade A / Grade B con sesión activa 🟢 o historial limpio sin declinaciones.
      - Tier LOW: Depósitos SPEI/externos recientes (<24h), sin sesión activa 🔑 (Login Full) o Grade C.

    JWT vivo NO es exclusión dura: el matchmaker PRIORIZA cuentas con sesión 🟢 por
    rapidez y menor latencia de captcha, pero si no hay suficientes, toma 🔑 sin JWT
    y el flujo hace Login Full.

    Selección: distribución por tiers priorizando calidad y velocidad de conversión.
    """
    now = _now_epoch()
    sa = _sa_tokens()
    out: List[Dict[str, Any]] = []
    meta_map = meta_map or {}

    for r in rows:
        email = r.get("email")

        # 0. Gate KYC Duro e Innegociable: Solo cuentas con KYC 100% verificado
        kyc_val = r.get("kyc_verified")
        if kyc_val not in (1, "1", True):
            continue

        # 0b. Cuenta muerta o con bloqueo terminal (dead_reason / dead_at persistidos en BD)
        if r.get("dead_reason") or r.get("dead_at"):
            continue

        # 0c. Status LIVE estricto
        if (r.get("status") or "").upper() != "LIVE":
            continue

        # 0d. Cuenta degradada (Grade D) -> jamás usar para auto_deposit / match
        if (r.get("grade") or "").upper() == "D":
            continue

        # 0e. Racha de declinaciones activa (a_plus_decline_streak >= 2) -> en reposo
        if (r.get("a_plus_decline_streak") or 0) >= 2:
            continue

        # 1. Cuenta con saldo real / dinero significativo (balance_real >= $10.0) -> EXCLUIDA
        # El auto-depósito /bet es para fondear cuentas vacías; jamás tocar cuentas con fondos en uso.
        bal_real = r.get("balance_real")
        if bal_real is not None:
            try:
                if float(bal_real) >= 10.0:
                    continue
            except (ValueError, TypeError):
                pass
        else:
            bal_fallback = r.get("balance") or r.get("balance_total")
            if bal_fallback is not None:
                try:
                    if float(bal_fallback) >= 10.0:
                        continue
                except (ValueError, TypeError):
                    pass

        # 2. Cuenta en ciclo de retiro o marcada para retiro -> EXCLUIDA
        if r.get("withdrawal_ready") in (1, "1", True):
            continue

        locked_by = r.get("locked_by")
        is_sa_owned = str(locked_by).lower() in sa if locked_by is not None else False
        # RESERVADA_SA (pool=0 + locked_by del SA) → candidata.
        is_sa_reserved = not r.get("published_to_pool") and is_sa_owned
        if not is_sa_reserved:
            if not r.get("published_to_pool"):
                continue
            if locked_by is not None and not is_sa_owned:
                # Comprobar si el lock de otro operador ya expiró
                locked_until = r.get("locked_until")
                locked_at = r.get("locked_at")
                is_stale = False
                if locked_until:
                    is_stale = str(locked_until) < datetime.now(timezone.utc).isoformat()
                elif locked_at:
                    is_stale = True  # lock huérfano sin fecha límite
                if not is_stale:
                    continue

        if _cd_active(r.get("cooldown_until"), now):
            continue

        meta = meta_map.get(email) or {}
        # 3. Enfriamiento 48h por depósito APROBADO en dashboard
        if meta.get("has_dashboard_approved_48h"):
            continue

        # 4. Cuenta en uso activa: depósitos SPEI o retiros recientes (<48h) en account_transactions
        if meta.get("has_spei_48h") or meta.get("has_withdrawal_48h") or meta.get("has_recent_activity_48h"):
            continue

        # 5. Errores de validación o DEAD
        if meta.get("is_validation_blocked") or meta.get("is_dead_blocked"):
            continue

        win = (window_map or {}).get(email) or {}
        avail = win.get("available")
        if avail is not None and float(avail) < amount:
            continue

        if decline_map is not None:
            if (decline_map.get(email) or 0) >= MM_ACCOUNT_RECENT_DECLINE_LIMIT:
                continue

        # JWT vivo (🟢) = sesión reutilizable sin captcha. Flag para priorización.
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
        has_3ds_24h = meta.get("has_3ds_24h", False)
        has_approved_bin = bool(meta.get("approved_bin_pipes"))
        total_fails = meta.get("total_fails", 0)
        mins_since_attempt = meta.get("mins_since_last_attempt", 99999)
        grade = (r.get("grade") or "").upper()

        if has_3ds_24h or (grade == "A+" and r.get("_jwt_alive")):
            tier_top.append(r)
        elif mins_since_attempt <= 1440 and total_fails >= 3:
            tier_low.append(r)
        elif grade in ("A+", "A"):
            tier_mid.append(r)
        elif grade == "B" and has_approved_bin:
            tier_mid.append(r)
        else:
            tier_low.append(r)

    def sort_key(r):
        email = r.get("email")
        meta = meta_map.get(email) or {}
        # 1. Sesión activa 🟢 (0 captcha) SIEMPRE antes que cuentas sin sesión 🔑
        jwt_first = 0 if r.get("_jwt_alive") else 1
        # 2. 3DS reciente eleva prioridad
        has_3ds = 0 if meta.get("has_3ds_24h") else 1
        # 3. Cuentas ya intentadas (<60 min) al final
        mins = meta.get("mins_since_last_attempt", 99999)
        recently_tried = 1 if mins < 60 else 0
        # 4. 2+ tarjetas asociadas pierden prioridad (probabilidad de depósito baja)
        cards_heavy = 1 if (meta.get("cards_count") or 0) >= 2 else 0
        # 5. Afinidad de BIN exitoso previo
        has_bin_success = 0 if meta.get("approved_bin_pipes") else 1
        return (
            jwt_first,
            has_3ds,
            recently_tried,
            cards_heavy,
            has_bin_success,
            _grade_rank(r.get("grade")),
            -(float(r.get("grade_score") or 0)),
            -int(meta.get("last_activity_epoch") or 0),  # más activo reciente primero
        )

    tier_top.sort(key=sort_key)
    tier_mid.sort(key=sort_key)
    tier_low.sort(key=sort_key)

    if count <= 3:
        if tier_top and count >= 1:
            combined = [tier_top[0]] + [r for r in (tier_top[1:] + tier_mid + tier_low) if r != tier_top[0]]
            stratified = combined[:count]
        else:
            stratified = (tier_top + tier_mid + tier_low)[:count]
    else:
        n_top = max(1 if tier_top else 0, int(round(count * 0.4)))
        n_mid = int(round(count * 0.4))
        n_low = count - n_top - n_mid

        stratified = []
        for tier, quota in ((tier_top, n_top), (tier_mid, n_mid), (tier_low, n_low)):
            stratified.extend(tier[:quota])
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
    tol_pipes: Optional[set] = None,
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

    tol_pipes = {_normalize_pipe_to_3part(p) for p in (tol_pipes or [])}

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        try:
            con.execute(
                "UPDATE accounts SET locked_by=NULL, locked_until=NULL "
                "WHERE locked_by IS NOT NULL AND ("
                "  (locked_until IS NOT NULL AND locked_until < datetime('now')) OR "
                "  (locked_at IS NOT NULL AND locked_at < datetime('now', '-4 hours'))"
                ")"
            )
            con.commit()
        except Exception:
            pass
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

            # 2. Depósitos por SPEI / externos recientes (<48h) en account_transactions (gateway=2 o status=6 o txn_type=1)
            spei_48h = con.execute("""
                SELECT COUNT(*) AS n FROM account_transactions 
                WHERE account_email=? AND (gateway=2 OR status=6) AND txn_type=1 
                AND (
                    (julianday('now') - julianday(REPLACE(txn_date, 'T', ' '))) <= 2.0
                    OR txn_date >= datetime('now','-48 hours')
                )
            """, (email,)).fetchone()["n"]

            # 2b. Retiros recientes (<48h) en account_transactions (txn_type=2)
            with_48h = con.execute("""
                SELECT COUNT(*) AS n FROM account_transactions 
                WHERE account_email=? AND txn_type=2 
                AND (
                    (julianday('now') - julianday(REPLACE(txn_date, 'T', ' '))) <= 2.0
                    OR txn_date >= datetime('now','-48 hours')
                )
            """, (email,)).fetchone()["n"]

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

            # RF5: tarjetas asociadas en la cuenta (depriorización si >= 2)
            cards_n = con.execute(
                "SELECT COUNT(*) AS n FROM account_cards WHERE account_email=?",
                (email,),
            ).fetchone()["n"]

            # RF5: recencia de actividad (movimientos/bets) para mover la cuenta en la lista
            last_act = con.execute(
                "SELECT MAX(last) AS last FROM ("
                "  SELECT created_at AS last FROM deposit_attempts WHERE account_email=?"
                "  UNION ALL SELECT txn_date AS last FROM account_transactions WHERE account_email=?"
                ")"
            , (email, email)).fetchone()["last"]
            last_activity_epoch = 0
            if last_act:
                try:
                    dt = datetime.fromisoformat(str(last_act).replace(" ", "T").replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    last_activity_epoch = int(dt.timestamp())
                except Exception:
                    pass

            meta_map[email] = {
                "has_dashboard_approved_48h": bool(app_48h),
                "has_spei_48h": bool(spei_48h),
                "has_withdrawal_48h": bool(with_48h),
                "has_recent_activity_48h": bool(spei_48h or with_48h),
                "has_3ds_24h": bool(threeds_24h),
                "total_fails": int(tot_fails or 0),
                "is_validation_blocked": bool(val_blocked),
                "is_dead_blocked": bool(dead_blocked),
                "approved_bin_pipes": approved_bin_pipes,
                "mins_since_last_attempt": mins_since,
                "cards_count": int(cards_n or 0),
                "last_activity_epoch": last_activity_epoch,
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
        seen_card_nums = set()
        for p in card_pipes or []:
            c = _parse_card_pipe(p)
            if c:
                c_num = c.get("card_number") or ""
                if c_num in seen_card_nums:
                    # Deduplicar número de tarjeta en el pool para no tener 2 pipes con el mismo PAN
                    continue
                seen_card_nums.add(c_num)
                pool.append(c)
        pool.sort(key=lambda c: _rank_key(c, bin_stats_map))

        accounts_out: List[Dict[str, Any]] = []
        assigned_tol: set = set()
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
                    # RF4: tarjeta tolerada solo en 1 cuenta por misión
                    if cand_pipe_str in tol_pipes and cand_pipe_str in assigned_tol:
                        continue
                    # Cooldown 30d del BIN: Si el BIN aprobó con OTRO pipe en los últimos 30d en esta cuenta -> omitir
                    if cand_bin in app_bin_pipes:
                        if cand_pipe_str not in app_bin_pipes[cand_bin]:
                            continue  # Mismo BIN pero otra tarjeta -> bloquear por 30 días

                    pipe = cand_pipe_str
                    assigned_tol.add(cand_pipe_str)
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
            "SELECT * FROM accounts WHERE id=?", (account_id,)
        ).fetchone()
    return dict(row) if row else None


def _is_account_dead(acct: Optional[Dict[str, Any]]) -> bool:
    if not acct:
        return False
    st = str(acct.get("status") or "").strip().upper()
    if st in ("DEAD", "BAN", "RATE_LIMITED", "RATE_LIMITED_PERMANENT"):
        return True
    if acct.get("dead_reason") or acct.get("dead_at"):
        return True
    return False


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
                try:
                    from app import DB_PATH
                    con = sqlite3.connect(str(DB_PATH))
                    try:
                        failed_cards = set(r[0] for r in con.execute("""
                            SELECT DISTINCT card_pipe FROM deposit_attempts
                            WHERE card_pipe IN ({seq})
                              AND status = 'rejected'
                              AND created_at >= datetime('now', '-24 hours')
                        """.format(seq=','.join(['?']*len(card_pipes))), card_pipes).fetchall() if r[0])
                        card_pipes = [p for p in card_pipes if p not in failed_cards]
                    finally:
                        con.close()
                except Exception:
                    pass
        except Exception:
            card_pipes = []

        cap_key = os.environ.get("CAPMONSTER_KEY", "") or os.environ.get(
            "BMX_CAPMONSTER_KEY", ""
        )
        pool = make_pool(cap_key, size=2, workers=1)
        # Pool lazy: no arrancar factory ni prefetch ansioso si hay JWT cache hit

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
            accounts_list = list(plan.get("accounts", []))
            already_checked_emails = set(a["email"] for a in accounts_list)
            retired_cards: set = set()
            retired_card_numbers: set = set()

            def _is_card_retired(p: str) -> bool:
                if not p:
                    return True
                norm = _normalize_pipe_to_3part(p)
                if p in retired_cards or norm in retired_cards:
                    return True
                c_num = _extract_card_number(p)
                if c_num and c_num in retired_card_numbers:
                    return True
                return False

            def _retire_card(p: str, reason: str = "", **kwargs):
                if not p:
                    return
                norm = _normalize_pipe_to_3part(p)
                c_num = _extract_card_number(p)
                retired_cards.add(p)
                retired_cards.add(norm)
                if c_num:
                    retired_card_numbers.add(c_num)
                # Purgar inmediatamente de todas las cuentas activas
                for a in accounts_state:
                    a["candidates"] = [c for c in a["candidates"] if not _is_card_retired(c)]
                    if not a["candidates"] and not a["matched"]:
                        a["done"] = True
                        if a["locked"]:
                            _unlock(a["id"])
                            locked_ids.discard(a["id"])

            # Pre-cargar mapa de tarjetas casadas por cuenta desde BD
            married_card_owners = _get_married_card_owners()
            if married_card_owners:
                logger.info(f"🛡️ Pre-cargadas {len(married_card_owners)} tarjetas casadas en BD")

            # Inicializar estado de cuentas para el despachador Round-Robin
            accounts_state: List[Dict[str, Any]] = []
            for acc in accounts_list:
                aid, email = acc.get("id"), acc.get("email")
                acct = _fetch_account(aid)
                if not acct:
                    continue
                # Filtro estricto: Si la cuenta está muerta o bloqueada, no entra al ciclo
                if _is_account_dead(acct) or _is_account_dead(acc):
                    logger.warning(f"💀 Cuenta {email} descartada en inicio de misión (status={acct.get('status')}, dead_reason={acct.get('dead_reason')})")
                    continue
                cand = [p for p in [acc.get("card_pipe"), *card_pipes] if p]
                cand = [_normalize_pipe_to_3part(p) for p in cand]
                cand = list(dict.fromkeys(cand))
                email_lower = (email or "").strip().lower()
                planned_pipe = _normalize_pipe_to_3part(acc.get("card_pipe")) if acc.get("card_pipe") else None
                cand = [
                    p for p in cand
                    if not _is_card_retired(p) and (p == planned_pipe or married_card_owners.get(_extract_card_number(p), email_lower) == email_lower)
                ]
                if not cand:
                    logger.info(f"⚠️ Sin tarjetas candidatas activas para {email}")
                    continue
                accounts_state.append({
                    "id": aid,
                    "email": email,
                    "acct": acct,
                    "grade": acc.get("grade") or acct.get("grade"),
                    "candidates": cand,
                    "declines": 0,
                    "cooldown_until": 0.0,
                    "locked": False,
                    "matched": False,
                    "done": False,
                })

            last_account_id = None
            backup_checked = False
            _loop = asyncio.get_event_loop()
            _clock_offset = 0.0

            def _get_now() -> float:
                return _loop.time() + _clock_offset

            async def _sleep_step(seconds: float) -> None:
                nonlocal _clock_offset
                t_before = _loop.time()
                await asyncio.sleep(seconds)
                t_after = _loop.time()
                if t_after - t_before < seconds * 0.5:
                    _clock_offset += seconds

            while not _cancelled():
                # Actualizar listas de candidatas filtrando tarjetas jubiladas
                for a in accounts_state:
                    if a["done"]:
                        continue
                    a["candidates"] = [
                        p for p in a["candidates"]
                        if not _is_card_retired(p)
                    ]
                    if not a["candidates"] or a["declines"] >= MM_MAX_ACCOUNT_DECLINES_PER_RUN:
                        a["done"] = True
                        if a["locked"] and not a["matched"]:
                            _unlock(a["id"])
                            locked_ids.discard(a["id"])

                active = [a for a in accounts_state if not a["done"]]

                # Si no quedan cuentas activas y no hay matches, buscar cuentas de respaldo
                if not active:
                    if not matches and not backup_checked and not _cancelled():
                        backup_checked = True
                        try:
                            from app import DB_PATH
                            active_cards = [p for p in card_pipes if not _is_card_retired(p)]
                            if active_cards:
                                remaining = MAX_ACCOUNTS_HARD_CAP - len(accounts_state)
                                if remaining > 0:
                                    backup_plan = plan_auto_mission(DB_PATH, active_cards, amount, target_count, max_accounts=remaining)
                                    if backup_plan and backup_plan.get("feasible"):
                                        for b_acc in backup_plan.get("accounts", []):
                                             b_email = b_acc.get("email")
                                             b_id = b_acc.get("id")
                                             b_acct = _fetch_account(b_id)
                                             if not b_acct:
                                                 continue
                                             # Gate KYC y calidad obligatorio en respaldo dinámico
                                             is_kyc_ok = b_acc.get("kyc_verified") in (1, "1", True) or b_acct.get("kyc_verified") in (1, "1", True)
                                             if not is_kyc_ok or _is_account_dead(b_acc) or _is_account_dead(b_acct) or b_email in already_checked_emails:
                                                 logger.info(f"➖ CUENTA DE RESPALDO SALTADA (kyc≠1 o dead) | {b_email}")
                                                 continue
                                             is_quality = (b_acc.get("grade") or b_acct.get("grade") or "").upper() in ("A+", "A", "B")
                                             if not is_quality:
                                                 continue
                                             b_cands = [p for p in [b_acc.get("card_pipe"), *card_pipes] if p]
                                             b_cands = [_normalize_pipe_to_3part(p) for p in b_cands]
                                             b_cands = list(dict.fromkeys(b_cands))
                                             b_email_lower = (b_email or "").strip().lower()
                                             b_planned_pipe = _normalize_pipe_to_3part(b_acc.get("card_pipe")) if b_acc.get("card_pipe") else None
                                             b_cands = [
                                                 p for p in b_cands
                                                 if not _is_card_retired(p) and (p == b_planned_pipe or married_card_owners.get(_extract_card_number(p), b_email_lower) == b_email_lower)
                                             ]
                                             if not b_cands:
                                                 continue
                                             already_checked_emails.add(b_email)
                                             accounts_state.append({
                                                 "id": b_id,
                                                 "email": b_email,
                                                 "acct": b_acct,
                                                 "grade": b_acc.get("grade") or b_acct.get("grade"),
                                                 "candidates": b_cands,
                                                 "declines": 0,
                                                 "cooldown_until": 0.0,
                                                 "locked": False,
                                                 "matched": False,
                                                 "done": False,
                                             })
                                             logger.info(f"➕ CUENTA DE RESPALDO AÑADIDA DINÁMICAMENTE | {b_email}")
                                             _broadcast_mission(
                                                 mission_id,
                                                 "matching",
                                                 user,
                                                 on_progress=on_progress,
                                                 accounts=len(accounts_state),
                                             )
                                             if len(accounts_state) >= MAX_ACCOUNTS_HARD_CAP:
                                                 break
                        except Exception as ex_backup:
                            logger.warning(f"[Auto {mission_id}] No se pudieron buscar cuentas de respaldo: {ex_backup}")

                    active = [a for a in accounts_state if not a["done"]]
                    if not active:
                        break

                now = _get_now()
                ready = [a for a in active if a["cooldown_until"] <= now]

                if not ready:
                    # Todas las cuentas activas están en cooldown: esperar el tiempo mínimo restante
                    min_wait = min(a["cooldown_until"] - now for a in active)
                    min_wait = max(0.1, min_wait)
                    if abs(min_wait - dep.MM_COOLDOWN) < 0.1:
                        min_wait = dep.MM_COOLDOWN
                    logger.info(f"⏳ Cooldown activo en todas las cuentas ({len(active)} en cola) — esperando {min_wait}s")
                    await _sleep_step(min_wait)
                    continue

                # Seleccionar cuenta lista (rotación equitativa: si hay más de una, preferir distinta a la anterior)
                target = None
                if len(ready) > 1 and last_account_id:
                    target = next((a for a in ready if a["id"] != last_account_id), None)
                if not target:
                    target = ready[0]

                account_id = target["id"]
                email = target["email"]
                acct = target["acct"]

                # Verificación fresca en BD antes de tocar la cuenta (anti-race condition)
                fresh_acct = _fetch_account(account_id)
                if fresh_acct:
                    if _is_account_dead(fresh_acct):
                        logger.warning(f"💀 CUENTA DETECTADA DEAD EN BD | {email} — descartando de inmediato sin intentar")
                        target["done"] = True
                        target["candidates"] = []
                        if target["locked"]:
                            _unlock(account_id)
                            locked_ids.discard(account_id)
                        continue
                    acct = fresh_acct
                    target["acct"] = fresh_acct

                pipe = target["candidates"].pop(0)
                norm_pipe = _normalize_pipe_to_3part(pipe)

                if not target["locked"]:
                    dep._auto_lock_for_deposit(account_id, operator_id, user, hours=4)
                    target["locked"] = True
                    locked_ids.add(account_id)

                _broadcast_mission(
                    mission_id,
                    "logging_in",
                    user,
                    on_progress=on_progress,
                    email=email,
                    current=len(matches) + 1,
                    total=len(accounts_state),
                )

                transient = 0
                while True:
                    sj, sp = dep._mm_session_get(sessions, email)
                    logger.info(
                        f"🏦 BEGIN_DEPOSIT | {email} | Target Pipe: {pipe} | Amt: ${PROBE_AMOUNT}"
                    )
                    r, ok, code = await _attempt(
                        email, acct["password"], pipe, PROBE_AMOUNT, sj, sp
                    )
                    dep._mm_session_update(sessions, email, r)

                    if ok:
                        deposited += PROBE_AMOUNT
                        approved += 1
                        _retire_card(pipe, reason=f"MATCH APROBADO en {email}")
                        logger.info(f"🎯 MATCH FOUND | {email} x {pipe}")
                        logger.info(f"🚫 TARJETA JUBILADA EN MISIÓN (MATCH APROBADO en {email}) | {pipe} (PAN: {_extract_card_number(pipe)})")

                        clabe_stp = None
                        try:
                            import clabe_fetch
                            from app import DB_PATH
                            saved_clabes = clabe_fetch.get_saved_clabes(DB_PATH, account_id)
                            stp_item = next(
                                (c for c in saved_clabes if c.get("integration") in ("STP", 2, "2")),
                                None,
                            )
                            if stp_item:
                                clabe_stp = stp_item.get("clabe")
                            else:
                                jwt_token = r.get("jwt")
                                used_proxy = r.get("used_proxy")
                                if jwt_token:
                                    fetched_data = await clabe_fetch.fetch_clabes_from_betmexico(
                                        jwt_token, used_proxy
                                    )
                                    clabe_fetch._persist_clabes(
                                        DB_PATH, account_id, email, fetched_data
                                    )
                                    accounts_stp = fetched_data.get("accounts") or []
                                    stp_acc = next(
                                        (a for a in accounts_stp if str(a.get("integration")) in ("STP", "2")),
                                        None,
                                    )
                                    if stp_acc:
                                        clabe_stp = str(stp_acc.get("account"))
                        except Exception as ex_clabe:
                            logger.warning(f"[Auto {mission_id}] No se pudo obtener CLABE STP para {email}: {ex_clabe}")

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
                        target["matched"] = True
                        target["done"] = True
                        break

                    if code in dep.MM_THREEDS_RC:
                        try:
                            from app import db as _adb
                            with _adb(write=True) as cdb:
                                cdb.execute(
                                    "UPDATE accounts SET grade='A+' WHERE email=?",
                                    (email,),
                                )
                        except Exception as ex:
                            logger.error(f"[Auto {mission_id}] no pude marcar A+ {email}: {ex}")
                        target["cooldown_until"] = _get_now() + dep.MM_COOLDOWN
                        break

                    # RATE_LIMITED, DEAD, BAN, KYC_PENDING o cualquier código de cuenta muerta
                    if (
                        code in ("RATE_LIMITED", "DEAD", "BAN", "RATE_LIMITED_PERMANENT", "KYC_PENDING")
                        or code in dep.MM_DEAD_RC
                        or r.get("account_dead")
                        or "RATE_LIMITED" in str(r.get("error") or "")
                        or "429" in str(r.get("error") or "")
                    ):
                        if code == "RATE_LIMITED" or "RATE_LIMITED" in str(r.get("error") or "") or "429" in str(r.get("error") or ""):
                            dep._mark_rate_limited_dead(email)
                        elif code == "KYC_PENDING":
                            try:
                                from app import db as _dash_db
                                with _dash_db(write=True) as c:
                                    c.execute(
                                        "UPDATE accounts SET status='DEAD', dead_reason='IsUserInValidationProcess', dead_at=datetime('now'), kyc_verified=0 WHERE email=?",
                                        (email,),
                                    )
                            except Exception as e:
                                logger.warning(f"[Auto {mission_id}] No se pudo marcar dead_reason para {email}: {e}")
                        else:
                            try:
                                from app import db as _appdb
                                with _appdb(write=True) as cdb:
                                    cdb.execute(
                                        "UPDATE accounts SET status='DEAD', dead_reason=?, dead_at=datetime('now') "
                                        "WHERE email=? AND status != 'DEAD'",
                                        (r.get("error") or code, email)
                                    )
                            except Exception:
                                pass
                        failed += 1
                        target["declines"] += 1
                        target["done"] = True
                        target["candidates"] = []  # Eliminar inmediatamente todas las tarjetas restantes para esta cuenta
                        if target["locked"]:
                            _unlock(account_id)
                            locked_ids.discard(account_id)
                        _broadcast_mission(
                            mission_id,
                            "cooldown" if (code == "RATE_LIMITED" or "429" in str(r.get("error") or "")) else "scheduling",
                            user,
                            on_progress=on_progress,
                            email=email,
                            reason="rate_limited" if (code == "RATE_LIMITED" or "429" in str(r.get("error") or "")) else "dead_account",
                            aborted=code,
                        )
                        break

                    if dep._mm_is_real_decline(code) or dep._mm_is_ambiguous_charge(code):
                        failed += 1
                        target["declines"] += 1
                        is_clean_account = target.get("grade") in ("A+", "A")
                        if is_clean_account and code == "BANK_REJECTED":
                            _retire_card(pipe, reason=f"BANK_REJECTED en cuenta limpia {email}")
                            logger.info(f"🚫 TARJETA JUBILADA EN MISIÓN (BANK_REJECTED en cuenta {email} con grado {target.get('grade')}) | {pipe}")
                            logger.info(f"ℹ️ Matriz Diagnóstico: Declinación atribuida a tarjeta, no a pasarela de {email}")

                        target["cooldown_until"] = _get_now() + dep.MM_COOLDOWN
                        if target["declines"] >= MM_MAX_ACCOUNT_DECLINES_PER_RUN or not target["candidates"]:
                            target["done"] = True
                            if target["locked"] and not target["matched"]:
                                _unlock(account_id)
                                locked_ids.discard(account_id)
                        break

                    if code == "CARD_LOCKED_OTHER_ACCOUNT":
                        _retire_card(pipe, reason=f"CARD_LOCKED_OTHER_ACCOUNT en {email}")
                        logger.info(f"🚫 TARJETA JUBILADA (CARD_LOCKED_OTHER_ACCOUNT) | {pipe}")
                        failed += 1
                        target["cooldown_until"] = _get_now() + MM_CROSS_ACCOUNT_GAP
                        break

                    # TRANSITORIO (nuestro lado) → reintentar el par
                    transient += 1
                    if transient > MATCH_TRANSIENT_RETRIES:
                        failed += 1
                        target["cooldown_until"] = _get_now() + dep.MM_COOLDOWN
                        break
                    await _sleep_step(25)

                last_account_id = account_id

                # Respiro entre cuentas si aún quedan otras cuentas activas por atender
                if not _cancelled() and any(a["id"] != account_id and not a["done"] for a in accounts_state):
                    await _sleep_step(MM_CROSS_ACCOUNT_GAP)

            # Liberar cualquier lock de cuenta que no haya conseguido match
            for aid in list(locked_ids):
                if not any(m.get("account_id") == aid for m in matches):
                    _unlock(aid)
                    locked_ids.discard(aid)

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
                        code in ("RATE_LIMITED", "DEAD", "BAN", "RATE_LIMITED_PERMANENT")
                        or code in dep.MM_THREEDS_RC
                        or dep._mm_is_real_decline(code)
                        or code in dep.MM_DEAD_RC
                        or code == "PENDING_NOT_APPLIED"
                        or code == "CARD_LOCKED_OTHER_ACCOUNT"
                        or dep._mm_is_ambiguous_charge(code)
                        or r.get("account_dead")
                        or "RATE_LIMITED" in str(r.get("error") or "")
                        or "429" in str(r.get("error") or "")
                    ):
                        if code == "RATE_LIMITED" or "RATE_LIMITED" in str(r.get("error") or "") or "429" in str(r.get("error") or ""):
                            dep._mark_rate_limited_dead(email)
                        elif code in dep.MM_DEAD_RC or code == "DEAD" or r.get("account_dead"):
                            try:
                                from app import db as _appdb
                                with _appdb(write=True) as cdb:
                                    cdb.execute(
                                        "UPDATE accounts SET status='DEAD', dead_reason=?, dead_at=datetime('now') "
                                        "WHERE email=? AND status != 'DEAD'",
                                        (r.get("error") or code, email)
                                    )
                            except Exception:
                                pass
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
        except Exception as exc:
            # Atrapar cualquier excepción no manejada (ej. 409 lock de cuenta)
            # para que el task no crashee y spamee tracebacks dobles.
            detail = getattr(exc, "detail", str(exc))
            status_code = getattr(exc, "status_code", 0)
            logger.error(
                f"[Auto {mission_id}] misión abortada: [{status_code}] {detail}"
            )
            _m_update(
                mission_id,
                status="failed",
                phase_detail=str(detail)[:200],
                completed_at=_iso(),
            )
            _broadcast_mission(
                mission_id,
                "failed",
                user,
                on_progress=on_progress,
                reason=str(detail)[:200],
            )
        finally:
            await _stop_pool(pool, mission_id)
            for aid in locked_ids:  # regla 7: la misión no deja cuentas reservadas
                try:
                    _unlock(aid)
                except Exception as e:
                    logger.warning(f"[Auto {mission_id}] unlock {aid} falló: {e}")

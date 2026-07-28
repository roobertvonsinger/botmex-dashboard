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
def select_accounts_for_auto(
    rows: List[Dict[str, Any]],
    amount: float,
    count: int,
    window_map: Dict[str, Dict[str, Any]],
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

    Orden: (grade_rank ASC, grade_score DESC, balance_total DESC).
    Corta en `count`.
    """
    now = _now_epoch()
    sa = _sa_tokens()
    out: List[Dict[str, Any]] = []
    for r in rows:
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
        win = (window_map or {}).get(r.get("email")) or {}
        avail = win.get("available")
        if avail is not None and float(avail) < amount * count:
            continue
        out.append(r)

    out.sort(key=lambda r: (
        _grade_rank(r.get("grade")),
        -(r.get("grade_score") or 0),
        -(r.get("balance_total") or 0),
    ))
    return out[:count]


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
def plan_auto_mission(
    db_path,
    card_pipes: List[str],
    amount: float = 150,
    target_count: int = 9,
    max_accounts: int = 5,
) -> Dict[str, Any]:
    """Plan de misión auto: cuentas elegibles + tarjeta asignada a cada una.

    Retorna {accounts: [{id, email, grade, card_pipe}], total_estimated,
    feasible, reason}.

    - Cuentas: select_accounts_for_auto sobre `accounts` de la BD; el
      window_map se computa desde deposit_attempts con la misma semántica de
      deposits._window_status (available = max(0, DEP_MAX_24H - used 24h)).
    - Tarjeta: married ACTIVE de la cuenta si existe; si no, pool de
      card_pipes rankeado por approval_rate computado / 3DS reciente.
    - feasible = hay cuentas Y todas tienen tarjeta viable.
    """
    import sqlite3
    import deposits as dep

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in con.execute("SELECT * FROM accounts").fetchall()]
        window_map: Dict[str, Dict[str, Any]] = {}
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
        try:
            bin_stats_map = {
                str(s["bin"]): dict(s)
                for s in con.execute("SELECT * FROM bin_stats").fetchall()
            }
        except sqlite3.OperationalError:
            bin_stats_map = {}

        selected = select_accounts_for_auto(
            rows, amount, target_count, window_map
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

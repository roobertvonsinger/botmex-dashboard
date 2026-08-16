#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BetMexico Payment Analyzer — Algoritmo V7
Pregunta central: ¿está baneada la pasarela de TARJETA en BetMexico?

Reglas clave V7:
- Solo transacciones de tarjeta (gateway=1, type/txn_type=1) afectan el score
- SPEI, OXXO, retiros IGNORADOS completamente
- Agrupa en sesiones de 60 min: fallo+éxito en misma sesión = problema de tarjeta (NO baneo)
- Time decay ajustado: fallo 30-90 días es más severo (-30/40 pts)
- Penalización por intensidad: si una sesión tiene >4 fallos, se castiga extra (metrallado)
- Escala: A (70-100), B (40-69), C (0-39)
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

MX_TZ = ZoneInfo("America/Mexico_City")
logger = logging.getLogger(__name__)

# ── Status codes (BetMexico API) ──────────────────────────────────
TXN_STATUS_SUCCESS = 6
TXN_STATUS_PENDING = 0
TXN_STATUS_FAILED = -4

# ── Identificadores de transacciones de tarjeta ───────────────────
TXN_TYPE_DEPOSIT = 1   # type=1 (API) / txn_type=1 (BD) → depósito
GATEWAY_CARD = 1       # gateway=1 → tarjeta de crédito/débito

# ── Grades V6 (sin D ni F) ────────────────────────────────────────
GRADE_THRESHOLDS = [
    (70, "A"),   # 70-100 — pasarela sana
    (40, "B"),   # 40-69  — incierta / pocos datos
    (0,  "C"),   # 0-39   — probablemente baneada (ROJO)
]

GRADE_EMOJI = {
    "A": "🟢",
    "B": "🟡",
    "C": "🔴",
}

GRADE_LABEL = {
    "A": "Pasarela sana — ideal para testing",
    "B": "Incierta — proceder con cuidado",
    "C": "Pasarela probablemente baneada",
}


# ── Helpers ───────────────────────────────────────────────────────

def _get_grade(score: int) -> str:
    for threshold, grade in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "C"


def _activity_suffix(days_since: int) -> str:
    """Sufijo basado en días desde última transacción de CUALQUIER tipo."""
    if days_since < 2:
        return "-"
    elif days_since <= 7:
        return ""
    elif days_since <= 30:
        return "+"
    else:
        return "++"


def _parse_txn_date(date_str: str) -> Optional[datetime]:
    """Parsea fecha de transacción en varios formatos."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        pass
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def _parse_deposit_date(date_str: str) -> Optional[datetime]:
    """Parsea fecha de último depósito en varios formatos (compatibilidad)."""
    if not date_str or date_str == "N/A":
        return None
    for fmt in [
        "%d/%m/%Y %H:%M", "%d/%m/%Y",
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
        "%d/%m/%y %H:%M", "%d/%m/%y",
    ]:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def _get_txn_fields(t: Dict) -> Tuple[Optional[datetime], int, int, int]:
    """
    Extrae campos normalizados de una transacción.
    Soporta dos contextos:
    - API crudo (keys: date, type, gateway, status)
    - BD (keys: txn_date, txn_type, gateway, status)
    """
    date_str = t.get("date") or t.get("txn_date") or ""
    txn_type = int(t.get("txn_type") or t.get("type") or 0)
    gateway = int(t.get("gateway") or 0)
    status = int(t.get("status") or 0)
    return _parse_txn_date(date_str), txn_type, gateway, status


def _is_card_deposit(t: Dict) -> bool:
    """True si la transacción es un depósito con tarjeta (éxito o fallo)."""
    _, txn_type, gateway, _ = _get_txn_fields(t)
    return txn_type == TXN_TYPE_DEPOSIT and gateway == GATEWAY_CARD


def _group_into_sessions(card_items: List[Dict], now: datetime) -> List[Dict]:
    """
    Agrupa transacciones de tarjeta en sesiones de 60 minutos.
    Una sesión es un conjunto de transacciones dentro de una ventana de 60 min.

    Retorna lista de sesiones ordenadas de más reciente a más antigua.
    Cada sesión: {days_ago, has_success, has_fail, size}
    """
    # Parsear y ordenar newest-first
    dated: List[Tuple[datetime, int]] = []  # (dt, status)
    for item in card_items:
        dt, _, _, status = _get_txn_fields(item)
        if dt is not None:
            dated.append((dt, status))
    if not dated:
        return []
    dated.sort(key=lambda x: x[0], reverse=True)

    sessions = []
    anchor_dt, _ = dated[0]
    sess_statuses = [dated[0][1]]

    for dt, status in dated[1:]:
        diff_min = (anchor_dt - dt).total_seconds() / 60
        if diff_min <= 60:
            # Mismo bloque temporal → misma sesión
            sess_statuses.append(status)
        else:
            sessions.append({
                "days_ago": max(0, (now - anchor_dt).days),
                "has_success": TXN_STATUS_SUCCESS in sess_statuses,
                "has_fail": TXN_STATUS_FAILED in sess_statuses,
                "size": len(sess_statuses),
            })
            anchor_dt = dt
            sess_statuses = [status]

    sessions.append({
        "days_ago": max(0, (now - anchor_dt).days),
        "has_success": TXN_STATUS_SUCCESS in sess_statuses,
        "has_fail": TXN_STATUS_FAILED in sess_statuses,
        "size": len(sess_statuses),
    })
    return sessions


# ═══════════════════════════════════════════════════════════════════
#  SCORING V6
#  Filosofía: detectar baneo silencioso de pasarela de tarjeta
# ═══════════════════════════════════════════════════════════════════

def score_payment_readiness(details: Dict) -> Optional[Dict]:
    """
    Algoritmo V6: evalúa salud de la pasarela de TARJETA de una cuenta.

    Args:
        details: Dict con key "transactions" → {fetched, items, total_rows}
                 Soporta items del API crudo (key "type") o de BD (key "txn_type")

    Returns:
        Dict con score, grade, activity_suffix, grade_display, flags, breakdown
        None si no hay datos de transacciones disponibles
    """
    if "transactions" not in details:
        return None

    txn_data = details["transactions"]

    # fetched=False = el fetch de API falló. Si no está seteado, asumimos válido.
    if txn_data.get("fetched") is False:
        return None

    items = txn_data.get("items", [])
    total_rows = txn_data.get("total_rows", len(items))
    now = datetime.now()

    # ── Sufijo de actividad (cualquier tipo de txn) ───────────────
    last_activity_dt: Optional[datetime] = None
    for item in items:
        dt = _parse_txn_date(item.get("date") or item.get("txn_date") or "")
        if dt and (last_activity_dt is None or dt > last_activity_dt):
            last_activity_dt = dt
    days_since_activity = (now - last_activity_dt).days if last_activity_dt else 999
    suffix = _activity_suffix(days_since_activity)

    # ── Filtrar solo transacciones de tarjeta ─────────────────────
    card_items = [t for t in items if _is_card_deposit(t)]

    # Cuenta virgen de tarjeta → A (pasarela desconocida pero sin historial negativo)
    if not card_items:
        return {
            "score": 100,
            "grade": "A",
            "activity_suffix": suffix,
            "grade_display": "A" + suffix,
            "grade_emoji": GRADE_EMOJI["A"],
            "flags": ["VIRGIN_CARD"],
            "breakdown": {
                "total_transactions": total_rows,
                "card_sessions": 0,
                "pure_fail_sessions": 0,
                "success_sessions": 0,
                "days_since_last_activity": days_since_activity,
                "days_since_last_success": 999,
            },
        }

    # ── Agrupar en sesiones de 60 min ─────────────────────────────
    sessions = _group_into_sessions(card_items, now)

    success_sessions = [s for s in sessions if s["has_success"]]
    pure_fail_sessions = [s for s in sessions if not s["has_success"] and s["has_fail"]]
    mixed_sessions = [s for s in sessions if s["has_success"] and s["has_fail"]]

    score = 100
    flags: List[str] = []

    # ── 1. Penalizaciones: SOLO sesiones puras de fallo ───────────
    #    Fallo + éxito en misma sesión = problema de tarjeta (no baneo)
    pure_fail_by_recency = sorted(pure_fail_sessions, key=lambda s: s["days_ago"])
    for i, sess in enumerate(pure_fail_by_recency):
        days = sess["days_ago"]
        size = sess.get("size", 1)
        
        # Penalización base por recencia
        if days <= 7:
            base = 50
        elif days <= 30:
            base = 40
        elif days <= 90:
            base = 32 # "Mitad" entre 15 y 50 approx
        elif days <= 365:
            base = 10
        else:
            base = 5

        # Penalización por intensidad (Metrallado)
        # Si tiene > 4 fallos en una sesión, castigar extra
        intensity_extra = 0
        if size > 4:
            intensity_extra = min((size - 4) * 2, 40)
            flags.append(f"MACHINE_GUN_{size}x")

        # La sesión más reciente paga el 100%, las demás el 50%
        penalty = (base + intensity_extra) if i == 0 else (base + intensity_extra) * 0.5
        score -= penalty
        flags.append(f"PURE_FAIL_{days}d")

    # ── 2. Penalización mínima: sesiones mixtas ───────────────────
    mixed_penalty = min(len(mixed_sessions) * 10, 25)
    if mixed_penalty > 0:
        score -= mixed_penalty
        flags.append("MIXED_SESSIONS")

    # ── 3. Bonos: sesiones exitosas ───────────────────────────────
    days_since_last_success = 999
    if success_sessions:
        days_since_last_success = min(s["days_ago"] for s in success_sessions)
        if days_since_last_success <= 7:
            score += 25
            flags.append("SUCCESS_7D")
        elif days_since_last_success <= 30:
            score += 15
            flags.append("SUCCESS_30D")
        elif days_since_last_success <= 90:
            score += 5
            flags.append("SUCCESS_90D")

    # Bono recovery: la sesión más reciente de tarjeta fue exitosa
    # (después de haber tenido sesiones puras de fallo en el pasado)
    if sessions and sessions[0]["has_success"] and pure_fail_sessions:
        score += 15
        flags.append("RECOVERY_CONFIRMED")

    # Bono historial: múltiples sesiones exitosas
    if len(success_sessions) >= 3:
        score += 5
        flags.append("MULTI_SUCCESS")

    # ── 4. Cap: datos insuficientes → máximo B ────────────────────
    if len(sessions) < 2:
        score = min(score, 69)
        flags.append("INSUFFICIENT_DATA")

    # Clamp y grade
    score = max(0, min(100, int(score)))
    grade = _get_grade(score)

    return {
        "score": score,
        "grade": grade,
        "activity_suffix": suffix,
        "grade_display": grade + suffix,
        "grade_emoji": GRADE_EMOJI.get(grade, "⚪"),
        "flags": flags,
        "breakdown": {
            "total_transactions": total_rows,
            "card_sessions": len(sessions),
            "pure_fail_sessions": len(pure_fail_sessions),
            "success_sessions": len(success_sessions),
            "days_since_last_activity": days_since_activity,
            "days_since_last_success": days_since_last_success,
        },
    }


# ═══════════════════════════════════════════════════════════════════
#  ANÁLISIS DE PATRÓN DE BANEO (mantenido para compatibilidad)
# ═══════════════════════════════════════════════════════════════════

def analyze_gateway_ban_pattern(transactions: List[Dict]) -> Dict:
    """
    Analiza transacciones para detectar si la pasarela está baneada.
    Mantenido para compatibilidad — el scoring principal es score_payment_readiness.
    """
    if not transactions:
        return {
            "status": "UNKNOWN",
            "confidence": 0.0,
            "pattern": "Sin transacciones",
            "indicators": [],
        }

    total = len(transactions)
    failed = [t for t in transactions if t.get("status") == TXN_STATUS_FAILED]
    success = [t for t in transactions if t.get("status") == TXN_STATUS_SUCCESS]

    failed_count = len(failed)
    success_count = len(success)
    fail_ratio = failed_count / total if total > 0 else 0

    indicators = []

    if fail_ratio >= 0.7 and total >= 5:
        ban_status = "LIKELY_BANNED"
        indicators.append(f"{failed_count}/{total} fallidas ({fail_ratio:.0%} ratio)")
    elif fail_ratio >= 0.4 and total >= 3:
        ban_status = "SUSPICIOUS"
        indicators.append(f"{failed_count}/{total} fallidas ({fail_ratio:.0%} ratio)")
    elif failed_count > 0:
        ban_status = "CLEAN"
        indicators.append(f"{failed_count}/{total} fallidas ({fail_ratio:.0%} ratio)")
    else:
        ban_status = "CLEAN"

    consecutive_fails = 0
    for t in transactions:
        if t.get("status") == TXN_STATUS_FAILED:
            consecutive_fails += 1
        else:
            break

    if consecutive_fails >= 5:
        ban_status = "LIKELY_BANNED"
        indicators.append(f"{consecutive_fails} fallos consecutivos recientes")
    elif consecutive_fails >= 3:
        if ban_status == "CLEAN":
            ban_status = "SUSPICIOUS"
        indicators.append(f"{consecutive_fails} fallos consecutivos recientes")

    small_failed = [t for t in failed if t.get("amount", 0) <= 20]
    if len(small_failed) >= 3:
        indicators.append(f"{len(small_failed)} intentos de montos bajos (≤$20) rechazados")
        if ban_status == "CLEAN":
            ban_status = "SUSPICIOUS"

    if success_count == 0 and total >= 5:
        ban_status = "LIKELY_BANNED"
        indicators.append("Sin transacciones exitosas en historial consultado")

    confidence_map = {"LIKELY_BANNED": 0.85, "SUSPICIOUS": 0.60, "CLEAN": 0.90, "UNKNOWN": 0.0}
    confidence = confidence_map.get(ban_status, 0.5)
    if total < 5:
        confidence *= 0.6

    return {
        "status": ban_status,
        "confidence": round(confidence, 2),
        "pattern": f"{failed_count}/{total} fallidas, {success_count} exitosas",
        "indicators": indicators,
    }


# ═══════════════════════════════════════════════════════════════════
#  FUNCIONES DE RESUMEN (mantenidas para compatibilidad)
# ═══════════════════════════════════════════════════════════════════

def generate_payment_analysis_summary(all_hits: List[Dict], detailed: bool = True) -> str:
    """Genera resumen de análisis de payment readiness. DEPRECATED."""
    if not all_hits:
        return "📊 Sin hits para analizar."

    scored = [h for h in all_hits if h.get("payment_score")]
    if not scored:
        return "📊 Sin datos de payment scoring disponibles."

    grade_counts: Dict[str, int] = {"A": 0, "B": 0, "C": 0}
    for h in scored:
        ps = h["payment_score"]
        grade = ps.get("grade", "C") if ps else "C"
        grade_counts[grade] = grade_counts.get(grade, 0) + 1

    top = sorted(
        [h for h in scored if h["payment_score"] and h["payment_score"].get("grade") in ("A", "B")],
        key=lambda h: h["payment_score"]["score"],
        reverse=True,
    )[:12]

    lines = []
    lines.append("🧪 *ANÁLISIS DE PASARELA DE PAGOS*")
    lines.append(f"📊 {len(scored)} cuentas analizadas\n")
    lines.append("*Distribución de Grades:*")
    for grade in ["A", "B", "C"]:
        count = grade_counts.get(grade, 0)
        emoji = GRADE_EMOJI.get(grade, "⚪")
        if count > 0:
            lines.append(f"  {emoji} *{grade}* — {count} cuentas")
    lines.append("")

    if top:
        lines.append(f"*🏆 Top {len(top)} Candidatas para Testing:*")
        for i, h in enumerate(top, 1):
            ps = h["payment_score"]
            email = h.get("email", "?")
            balance = h.get("balance", 0)
            display = ps.get("grade_display", ps.get("grade", "?"))
            lines.append(
                f"  {i}. {ps['grade_emoji']}{display} "
                f"*{ps['score']}pts* | ${balance:.2f}"
            )
            if detailed:
                lines.append(f"     `{email}`")
    else:
        lines.append("⚠️ *No se encontraron candidatas Grade A o B*")

    return "\n".join(lines)


def generate_payment_ready_txt(all_hits: List[Dict]) -> str:
    """Genera TXT con cuentas Grade A/B para descarga. DEPRECATED."""
    scored = [h for h in all_hits if h.get("payment_score")]
    top = sorted(
        [h for h in scored if h["payment_score"] and h["payment_score"].get("grade") in ("A", "B")],
        key=lambda h: h["payment_score"]["score"],
        reverse=True,
    )

    if not top:
        return "# Sin cuentas Grade A/B encontradas\n"

    lines = [
        "# BetMexico — Payment Testing Ready Accounts",
        f"# Generado: {datetime.now(MX_TZ).strftime('%d/%m/%Y %H:%M')}",
        f"# Total: {len(top)} cuentas (A, B)",
        "#" + "=" * 60,
        "",
    ]
    for h in top:
        ps = h["payment_score"]
        display = ps.get("grade_display", ps.get("grade", "?"))
        lines.append(
            f"{ps['grade_emoji']}{display} | Score:{ps['score']} | "
            f"${h.get('balance', 0):.2f} | {h.get('email', '?')}:{h.get('password', '?')}"
        )
        lines.append("")

    return "\n".join(lines)

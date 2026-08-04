#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BetMexico Payment Analyzer — Algoritmo V10 (2026-05-22)
Pregunta central: ¿está QUEMADA la pasarela de TARJETA en BetMexico?

V10 (canónico en repos/botmex-dashboard/shared/):
- A: pasarela SANA — sin rechazos recientes y sin patrones de masacre.
     Max 2 fails juntos en ventana de 2h, total ≤3 fails, último fail >60d
     (o VIRGIN_CARD sin historial de tarjeta).
- B: reparándose con el tiempo — tuvo fails pero ya descansó algo.
- C: masacrada históricamente pero ya descansó >90d. Recovery incierto.
- D: actualmente quemada (fail <14d) o crónicamente masacrada (≥3 sesiones
     con 3+ fails en <60min).

Notas:
- Solo txns de tarjeta (gateway=1, type/txn_type=1) afectan grade
- SPEI/OXXO/retiros IGNORADOS
- Sesiones de 60 min: fail+éxito en misma = problema puntual, NO baneo
- Success reciente NO es requisito para A (pasarela limpia puede no tener
  intentos de tarjeta — sigue siendo sana)
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

# ── Grades V8 (escala A/B/C/D) ────────────────────────────────────
GRADE_THRESHOLDS = [
    (80, "A"),   # 80-100 — pasarela sana, ideal
    (60, "B"),   # 60-79  — buena, alta probabilidad de éxito
    (40, "C"),   # 40-59  — cuidado, señales mixtas
    (0,  "D"),   # 0-39   — pasarela probablemente quemada
]

GRADE_EMOJI = {
    "A": "🟢",
    "B": "🔵",
    "C": "🟡",
    "D": "🔴",
}

GRADE_LABEL = {
    "A": "Pasarela sana — ideal para testing",
    "B": "Buena — alta probabilidad de éxito",
    "C": "Cuidado — señales mixtas",
    "D": "Pasarela probablemente quemada",
}


# ── Helpers ───────────────────────────────────────────────────────

def _get_grade(score: int) -> str:
    for threshold, grade in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "C"


def _activity_suffix(hours_since: float) -> str:
    """Sufijo basado en horas desde última transacción de CUALQUIER tipo.
    `!`  = caliente (<1h)  → ojo, no atropellar
    `-`  = fresca (<24h)
    `''` = normal (1-7d)
    `+`  = vieja (8-30d)
    `++` = muy vieja (>30d)
    """
    if hours_since < 1:
        return "!"
    if hours_since < 24:
        return "-"
    days = hours_since / 24
    if days <= 7:
        return ""
    elif days <= 30:
        return "+"
    else:
        return "++"


def _parse_txn_date(date_str: str) -> Optional[datetime]:
    """Parsea fecha de transacción en varios formatos.
    V10: tolerante a microsegundos de cualquier longitud (BD tiene `.94907` con 5 dígitos
    que rompe fromisoformat en Python <3.11)."""
    if not date_str:
        return None
    s = date_str.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s).replace(tzinfo=None)
    except Exception:
        pass
    # Normalizar microsegundos a 6 dígitos exactos
    import re
    m = re.match(r"^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})\.(\d+)(.*)$", s)
    if m:
        head, micro, tail = m.group(1), m.group(2), m.group(3)
        micro = (micro + "000000")[:6]  # pad o truncar a 6 dígitos
        try:
            return datetime.fromisoformat(f"{head}.{micro}{tail}").replace(tzinfo=None)
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
    Resolución horaria (no diaria) — distingue 1h de 23h.

    Cada sesión: {hours_ago, days_ago, has_success, has_fail, size,
                  fail_count, span_minutes}
    span_minutes = duración de la ráfaga (para detectar metrallado fino).
    """
    dated: List[Tuple[datetime, int]] = []
    for item in card_items:
        dt, _, _, status = _get_txn_fields(item)
        if dt is not None:
            dated.append((dt, status))
    if not dated:
        return []
    dated.sort(key=lambda x: x[0], reverse=True)

    def _close_session(anchor_dt, oldest_dt, statuses):
        hours_ago = max(0.0, (now - anchor_dt).total_seconds() / 3600)
        span = max(0.0, (anchor_dt - oldest_dt).total_seconds() / 60)
        return {
            "hours_ago": hours_ago,
            "days_ago": int(hours_ago // 24),
            "has_success": TXN_STATUS_SUCCESS in statuses,
            "has_fail": TXN_STATUS_FAILED in statuses,
            "fail_count": sum(1 for s in statuses if s == TXN_STATUS_FAILED),
            "size": len(statuses),
            "span_minutes": span,
        }

    sessions = []
    anchor_dt, _ = dated[0]   # más reciente de la sesión actual
    oldest_dt = anchor_dt
    sess_statuses = [dated[0][1]]

    for dt, status in dated[1:]:
        if (anchor_dt - dt).total_seconds() / 60 <= 60:
            sess_statuses.append(status)
            oldest_dt = dt
        else:
            sessions.append(_close_session(anchor_dt, oldest_dt, sess_statuses))
            anchor_dt = dt
            oldest_dt = dt
            sess_statuses = [status]

    sessions.append(_close_session(anchor_dt, oldest_dt, sess_statuses))
    return sessions


# ═══════════════════════════════════════════════════════════════════
#  SCORING V6
#  Filosofía: detectar baneo silencioso de pasarela de tarjeta
# ═══════════════════════════════════════════════════════════════════

def _pure_fail_penalty(hours_ago: float, is_most_recent: bool) -> float:
    """Penalty por sesión pure-fail (usado para SCORE numérico, informativo).
    El grade real V10 se decide por reglas explícitas, no por score."""
    if hours_ago < 6:        base = 14
    elif hours_ago < 24:     base = 12
    elif hours_ago < 72:     base = 10
    elif hours_ago < 168:    base = 8
    elif hours_ago < 720:    base = 6
    elif hours_ago < 2160:   base = 4
    else:                    base = 2
    return base if is_most_recent else base * 0.6


def _last_success_bonus(hours_ago: float) -> int:
    """Bonus informativo para score (no decide grade en V10)."""
    if hours_ago < 168:      return 30
    if hours_ago < 720:      return 25
    if hours_ago < 2160:     return 10
    if hours_ago < 8760:     return 5
    return 2


# === V10 thresholds (regla canónica del grade) ============================
A_NO_FAIL_DAYS_MIN = 60      # A: último fail debe estar a ≥60 días
A_MAX_TOTAL_FAILS  = 3       # A: total de fails de tarjeta históricos ≤ 3
A_MAX_BIGFAIL_SESS = 0       # A: 0 sesiones con 3+ fails (max 2 juntos)
D_RECENT_FAIL_DAYS = 14      # D: fail en últimos 14 días → quemada AHORA
D_MASSACRE_COUNT   = 3       # D: ≥3 sesiones machine-gun → crónicamente quemada
C_DEEP_REST_DAYS   = 90      # C: pasaron ≥90 días desde último fail (+ historial malo)
SCORE_FLOOR = {"A": 80, "B": 60, "C": 40, "D": 0}
SCORE_CEIL  = {"A": 100, "B": 79, "C": 59, "D": 39}


def score_payment_readiness(details: Dict) -> Optional[Dict]:
    """
    Algoritmo V8: evalúa salud de la PASARELA de tarjeta.
    Filosofía: que el operador no pierda tiempo en pasarelas quemadas.
    """
    if "transactions" not in details:
        return None

    txn_data = details["transactions"]
    if txn_data.get("fetched") is False:
        return None

    items = txn_data.get("items", [])
    total_rows = txn_data.get("total_rows", len(items))
    now = datetime.now()

    # ── Sufijo de actividad: usa la última txn de cualquier tipo ──
    last_activity_dt: Optional[datetime] = None
    for item in items:
        dt = _parse_txn_date(item.get("date") or item.get("txn_date") or "")
        if dt and (last_activity_dt is None or dt > last_activity_dt):
            last_activity_dt = dt
    hours_since_activity = (now - last_activity_dt).total_seconds() / 3600 if last_activity_dt else 999_999.0
    suffix = _activity_suffix(hours_since_activity)

    # ── Filtrar solo depósitos con tarjeta ────────────────────────
    card_items = [t for t in items if _is_card_deposit(t)]

    # Cuenta virgen de tarjeta → A (pasarela sin historial negativo)
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
                "hours_since_last_activity": round(hours_since_activity, 1),
                "hours_since_last_success": None,
            },
        }

    # ── Agrupar en sesiones (resolución horaria) ──────────────────
    sessions = _group_into_sessions(card_items, now)

    success_sessions = [s for s in sessions if s["has_success"]]
    pure_fail_sessions = [s for s in sessions if not s["has_success"] and s["has_fail"]]
    mixed_sessions = [s for s in sessions if s["has_success"] and s["has_fail"]]

    score = 100.0
    flags: List[str] = []

    # ── 1. Penalty suave por sesiones pure-fail (recientes pesan más) ──
    pure_fail_by_recency = sorted(pure_fail_sessions, key=lambda s: s["hours_ago"])
    for i, sess in enumerate(pure_fail_by_recency):
        h = sess["hours_ago"]
        penalty = _pure_fail_penalty(h, i == 0)

        # Metrallado fino (sentido común):
        # - 2 fails en <5min  → +5 penalty extra
        # - 3+ fails en <60min → +10 penalty extra
        size = sess.get("size", 1)
        span = sess.get("span_minutes", 0)
        fc = sess.get("fail_count", size)
        if fc >= 3 and span <= 60:
            penalty += 10
            flags.append(f"MACHINE_GUN_3x60m")
        elif fc >= 2 and span <= 5:
            penalty += 0
            flags.append(f"MACHINE_GUN_2x5m")

        score -= penalty
        flags.append(f"PURE_FAIL_{int(h)}h")

    # ── 2. Mixed sessions ─────────────────────────────────────────
    # Si la más reciente es mixed con éxito → es señal de recovery, NO penaliza.
    # Mixed antiguas → leve penalty (-3 c/u, max -10)
    if mixed_sessions:
        # ¿la más reciente es mixed?
        most_recent_is_mixed = sessions[0]["has_success"] and sessions[0]["has_fail"]
        old_mixed = len(mixed_sessions) - (1 if most_recent_is_mixed else 0)
        if old_mixed > 0:
            mp = min(old_mixed * 3, 10)
            score -= mp
            flags.append(f"MIXED_OLD_{old_mixed}")

    # ── 3. Bono dominante: última transacción de tarjeta = ÉXITO ──
    # Esta es la señal clave: si lo último fue OK, la pasarela sigue jugando.
    hours_since_last_success: Optional[float] = None
    if success_sessions:
        hours_since_last_success = min(s["hours_ago"] for s in success_sessions)
        # ¿La sesión más reciente fue exitosa (incluye mixed)?
        if sessions[0]["has_success"]:
            bonus = _last_success_bonus(sessions[0]["hours_ago"])
            score += bonus
            flags.append(f"LAST_TXN_OK")
        else:
            # Hay éxitos pero no en la sesión más reciente — bono parcial
            bonus = _last_success_bonus(hours_since_last_success) // 2
            score += bonus
            flags.append(f"PAST_SUCCESS")

    # Bono historial: múltiples sesiones exitosas
    if len(success_sessions) >= 3:
        score += 5
        flags.append("MULTI_SUCCESS")

    # Score numérico (informativo). El GRADE V10 se decide abajo por reglas.
    score_int = max(0, min(100, int(round(score))))

    # ────────────────────────────────────────────────────────────────
    # V10: GRADE por reglas explícitas sobre el estado de la pasarela
    # ────────────────────────────────────────────────────────────────
    days_since_last_fail = None
    if pure_fail_sessions:
        days_since_last_fail = min(s["hours_ago"] for s in pure_fail_sessions) / 24

    total_card_fails = sum(s.get("fail_count", 0) for s in pure_fail_sessions)
    bigfail_session_count = sum(
        1 for s in pure_fail_sessions if s.get("fail_count", 0) >= 3
    )
    massacre_60m_count = sum(
        1 for s in pure_fail_sessions
        if s.get("fail_count", 0) >= 3 and s.get("span_minutes", 0) <= 60
    )

    # ¿Lo MÁS RECIENTE con tarjeta fue una aprobación limpia? (la última sesión de
    # tarjeta es éxito puro, sin fail). Señal DOMINANTE de recuperación: la pasarela
    # está demostrando que FUNCIONA AHORA. Robert 2026-07-09: "cada depósito aprobado
    # con tarjeta (en el dashboard o detectado de BetMexico) sana la percepción; si
    # las 1-2 txns más recientes son aprobadas, empuja a A" — por encima de fails
    # viejos. Una sesión = ventana de 60min, así que cubre "1 o 2 aprobados seguidos".
    recent_pure_success = bool(
        sessions and sessions[0]["has_success"] and not sessions[0]["has_fail"]
    )

    if recent_pure_success:
        grade, _reason = "A", "RECUPERADA_APROBACION_RECIENTE"
    elif days_since_last_fail is None:
        # Sin pure-fail sessions (puede tener fails mezclados con éxito en misma sesión = ok)
        grade, _reason = "A", "NO_PURE_FAILS"
    elif days_since_last_fail < D_RECENT_FAIL_DAYS:
        grade, _reason = "D", f"FAIL_RECIENTE_{int(days_since_last_fail)}D"
    elif massacre_60m_count >= D_MASSACRE_COUNT:
        grade, _reason = "D", f"CRONICAMENTE_MASACRADA_{massacre_60m_count}x"
    elif (days_since_last_fail >= A_NO_FAIL_DAYS_MIN
          and total_card_fails <= A_MAX_TOTAL_FAILS
          and bigfail_session_count <= A_MAX_BIGFAIL_SESS):
        grade, _reason = "A", f"SANA_{int(days_since_last_fail)}D"
    elif bigfail_session_count >= 1 or total_card_fails >= 5:
        # M7: masacre (3+ fails en sesión) o ≥5 fails totales → SIEMPRE C.
        # No sube a B por paso del tiempo: una masacre es señal permanente de daño.
        tag = "DESCANSADA" if days_since_last_fail >= C_DEEP_REST_DAYS else "RECIENTE"
        grade, _reason = "C", f"MASACRADA_{tag}_{int(days_since_last_fail)}D"
    else:
        grade, _reason = "B", "REPARANDOSE"

    flags.append(f"V10_{_reason}")
    # Ajustar score al rango del grade decidido (UI muestra grade + score)
    score_int = max(SCORE_FLOOR[grade], min(SCORE_CEIL[grade], score_int))

    return {
        "score": score_int,
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
            "mixed_sessions": len(mixed_sessions),
            "hours_since_last_activity": round(hours_since_activity, 1),
            "hours_since_last_success": round(hours_since_last_success, 1) if hours_since_last_success is not None else None,
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

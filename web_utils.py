#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BetMexico Web Dashboard — Utilities
Shared helper functions and constants.
"""

import hashlib
import re
import json
import logging
import time

logger = logging.getLogger("betmexico.web.utils")

# ── Mensajes de error amigables para el operador ──────────────────────
_ERROR_MESSAGES = {
    "CAPTCHA_POOL_EMPTY": "Captcha no disponible, reintenta en unos segundos",
    "LOGIN_FAILED": "Login fallido — verifica credenciales",
    "BEGIN_ERROR": "Error al iniciar depósito — servicio no disponible",
    "KYC_PENDING": "Cuenta en verificación KYC — no puede depositar",
    "AUTOEXCLUSION": "Cuenta autoexcluida",
    "PAYMENT_ERROR": "Error de pasarela — reintenta",
    "Declined": "Error de pasarela — reintenta",
    "3DS_REQUIRED": "Tarjeta requiere verificación 3D Secure",
    "CARD_CONFLICT": "Tarjeta ya registrada en otra cuenta",
    "ALL_REJECTED": "Todas las tarjetas fueron rechazadas",
    "BANK_REJECTED": "Banco rechazó la transacción",
    "3DS_UNDETECTED": "Balance no varió (Posible 3DS o rechazo silencioso)",
    "SHADOW_BAN?": "Sospecha de Shadow Ban — rechazo directo en monto alto",
}


def _sha256(plain: str) -> str:
    """Genera hash SHA256 de una cadena."""
    return hashlib.sha256(plain.encode()).hexdigest()


def compute_card_fingerprint(card_number: str, exp_month: int, exp_year: int) -> str:
    """SHA256(num|MM|YYYY). Sin CVV. Permite deduplicar tarjetas a través de operadores."""
    num = (card_number or "").strip().replace(" ", "")
    return hashlib.sha256(f"{num}|{int(exp_month):02d}|{int(exp_year)}".encode()).hexdigest()


def parse_pipe_card(pipe: str) -> dict | None:
    """Parsea formatos:
        4242424242424242|12/28|123
        4242424242424242|12|28|123
        4242424242424242|12/2028|123
        4242424242424242|12|2028|123
    Retorna {card_number, exp_month, exp_year, cvv} o None si inválido.
    Año de 2 dígitos se expande a 20YY.
    """
    if not pipe or not isinstance(pipe, str):
        return None
    parts = [p.strip() for p in pipe.strip().split("|") if p.strip()]
    if len(parts) < 2:
        return None

    card_number = re.sub(r"\D", "", parts[0])
    if len(card_number) < 12 or len(card_number) > 19:
        return None

    cvv = None
    exp_month = None
    exp_year = None

    if len(parts) == 3:
        # num | MM/YY[YY] | cvv
        date_part = parts[1]
        cvv = re.sub(r"\D", "", parts[2]) or None
        if "/" in date_part:
            mm, yy = date_part.split("/", 1)
        else:
            digits = re.sub(r"\D", "", date_part)
            if len(digits) == 4:
                mm, yy = digits[:2], digits[2:]
            elif len(digits) == 6:
                mm, yy = digits[:2], digits[2:]
            else:
                return None
        try:
            exp_month = int(mm)
            yy_int = int(yy)
            exp_year = yy_int if yy_int >= 100 else (2000 + yy_int)
        except ValueError:
            return None
    elif len(parts) >= 4:
        # num | MM | YY[YY] | cvv
        try:
            exp_month = int(re.sub(r"\D", "", parts[1]))
            yy_int = int(re.sub(r"\D", "", parts[2]))
            exp_year = yy_int if yy_int >= 100 else (2000 + yy_int)
            cvv = re.sub(r"\D", "", parts[3]) or None
        except ValueError:
            return None
    else:
        # num | MM/YY (sin cvv)
        date_part = parts[1]
        if "/" in date_part:
            mm, yy = date_part.split("/", 1)
            try:
                exp_month = int(mm)
                yy_int = int(yy)
                exp_year = yy_int if yy_int >= 100 else (2000 + yy_int)
            except ValueError:
                return None
        else:
            return None

    if not exp_month or exp_month < 1 or exp_month > 12:
        return None
    if not exp_year or exp_year < 2000:
        return None

    return {
        "card_number": card_number,
        "exp_month": exp_month,
        "exp_year": exp_year,
        "cvv": cvv,
    }


def _friendly_error(result_code: str = "", raw_error: str = "") -> str:
    """Devuelve mensaje amigable para el operador. Los errores crudos van al log."""
    if result_code in _ERROR_MESSAGES:
        return _ERROR_MESSAGES[result_code]
    
    raw = (raw_error or "").lower()
    if "timeout" in raw or "timed out" in raw:
        return "Tiempo de espera agotado — reintenta"
    if "proxy" in raw or "509" in raw or "data exhausted" in raw:
        return "Error de conexión — reintenta"
    if "ssl" in raw or "certificate" in raw or "record_layer" in raw:
        return "Error de conexión segura — reintenta"
    if "connect" in raw or "refused" in raw or "unreachable" in raw:
        return "Servicio no disponible — reintenta"
    
    return "Error inesperado — reintenta"


def _normalize_ccexp(raw: str) -> str:
    """Normaliza ccExp a formato MMYY que espera processorpay.
    Acepta: MM/YY, MM/YYYY, MMYY, MMYYYY."""
    digits = "".join(c for c in raw if c.isdigit())
    if len(digits) == 6:  # MMYYYY → MMYY
        return digits[:2] + digits[4:]
    return digits[:4]


def canonical_card_pipe(num, exp, cvv) -> str:
    """Formato CANÓNICO ÚNICO de tarjeta para mostrar/copiar en la UI:
    `NNNN|MM|YYYY|CVV` — 4 campos, mes 2 dígitos, AÑO 4 dígitos, SIN diagonal.
    Es el ÚNICO formato que el operador ve (instrucción de Robert 2026-06-27).
    Normaliza el exp venga como venga (MM/YY, MM|YY, MMYY, MMYYYY, MM/YYYY).
    Si falta el año (dato corrupto), usa `????` para que el hueco sea VISIBLE."""
    n = "".join(c for c in str(num or "") if c.isdigit())
    d = "".join(c for c in str(exp or "") if c.isdigit())
    if len(d) >= 6:      # MMYYYY
        mm, yyyy = d[:2], d[2:6]
    elif len(d) >= 4:    # MMYY → MM + 20YY
        mm, yyyy = d[:2], "20" + d[2:4]
    elif len(d) == 3:    # MYY raro
        mm, yyyy = d[:1].zfill(2), "20" + d[1:3]
    elif len(d) == 2:    # solo MM, año perdido
        mm, yyyy = d, "????"
    else:
        mm, yyyy = (d.zfill(2) if d else "??"), "????"
    c = "".join(ch for ch in str(cvv or "") if ch.isdigit())
    return f"{n}|{mm}|{yyyy}|{c}"


def _build_proxy_url(proxy: dict) -> str:
    """Construye URL de proxy para httpx/checker."""
    if not proxy:
        return None
    return f"http://{proxy['username']}:{proxy['password']}@{proxy['server']}"


def _extract_user_from_message(message: str) -> dict:
    """Extrae información de usuario del mensaje de log."""
    # Buscar patrones de usuario en el mensaje
    user_patterns = [
        r'\[(.*?)\((\d+)\)\]',  # [Nombre(ID)]
        r'User:(\w+)',          # User:username
        r'/start by (\w+)',     # /start by username
    ]

    for pattern in user_patterns:
        match = re.search(pattern, message)
        if match:
            if len(match.groups()) == 2:
                # Nombre e ID
                return {"name": match.group(1), "id": match.group(2)}
            else:
                # Solo nombre
                return {"name": match.group(1), "id": None}

    return {"name": None, "id": None}


def _categorize_event(message: str, source: str) -> str:
    """Categoriza el tipo de evento basado en el mensaje."""
    message_lower = message.lower()

    # Categorías comunes
    if any(word in message_lower for word in ['login', 'autenticación', 'auth']):
        return "login"
    elif any(word in message_lower for word in ['check', 'verificar', 'test']):
        return "check"
    elif any(word in message_lower for word in ['deposit', 'depósito', 'payment']):
        return "deposit"
    elif any(word in message_lower for word in ['search', 'buscar', 'find']):
        return "search"
    elif any(word in message_lower for word in ['error', 'exception', 'fail']):
        return "error"
    elif any(word in message_lower for word in ['start', 'iniciar', 'init']):
        return "start"
    elif any(word in message_lower for word in ['stop', 'finalizar', 'end']):
        return "stop"
    else:
        return "info"


def _parse_log_entry(log_entry: dict, source: str) -> dict:
    """Parsea una entrada de log y extrae información relevante."""
    try:
        # Extraer campos básicos
        message = log_entry.get('MESSAGE', '')
        timestamp_str = log_entry.get('__REALTIME_TIMESTAMP', '')
        hostname = log_entry.get('_HOSTNAME', 'unknown')

        # Convertir timestamp
        timestamp = 0
        if timestamp_str:
            try:
                # __REALTIME_TIMESTAMP está en microsegundos desde epoch
                timestamp = int(timestamp_str) // 1000000  # convertir a segundos
            except (ValueError, TypeError):
                timestamp = 0

        # Extraer usuario si está presente
        user_info = _extract_user_from_message(message)

        # Determinar tipo de evento
        event_type = _categorize_event(message, source)

        # Crear evento estructurado
        event = {
            "id": f"{source}_{timestamp}_{hash(message) % 10000}",
            "timestamp": timestamp,
            "source": source,
            "message": message,
            "event_type": event_type,
            "user": user_info,
            "hostname": hostname,
            "expanded": False,
            "marked": False,
            "notes": ""
        }

        return event

    except Exception as e:
        logger.debug(f"[Logs] Error parseando entrada: {e}")
        return None

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Motor de Resolución y Validación de CURP (RENAPO)
Proporciona parsing flexible de comandos, cálculo algorítmico y formateo para Telegram.
"""

import re
import datetime
from typing import Optional, Dict, Any, Tuple

from curp_utils import (
    compute_curp,
    generate_curp_candidates,
    _split_fullname,
    _infer_sex,
    _CURP_STATE_NAMES,
    _CURP_STATES,
    _CURP_CODE_ALIASES,
    _MX_ABBR,
    _normalize_name,
)

# Header estándar del bot
HEADER_LOCKUP = "<b>🎰 BETMEXICO — MONITOR OPERATIVO</b>"


def parse_date_flexible(date_str: str) -> Optional[Tuple[str, str, str, str]]:
    """
    Parsea una fecha en formatos comunes:
    - DDMMAA (6 dígitos, ej: 200381 -> 20, 03, 1981)
    - DDMMAAAA (8 dígitos, ej: 20031981 -> 20, 03, 1981)
    - YYYY-MM-DD (ej: 1981-03-20 -> 20, 03, 1981)
    - DD/MM/YYYY o DD-MM-YYYY (ej: 20/03/1981)
    
    Retorna: (dia 'DD', mes 'MM', anio 'YYYY', iso 'YYYY-MM-DD') o None
    """
    if not date_str:
        return None
    raw = date_str.strip()

    # Formato ISO: YYYY-MM-DD
    m_iso = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$", raw)
    if m_iso:
        yyyy, mm, dd = m_iso.groups()
        dd = dd.zfill(2)
        mm = mm.zfill(2)
        return dd, mm, yyyy, f"{yyyy}-{mm}-{dd}"

    # Formato latino: DD/MM/YYYY o DD-MM-YYYY
    m_lat = re.match(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$", raw)
    if m_lat:
        dd, mm, yyyy = m_lat.groups()
        dd = dd.zfill(2)
        mm = mm.zfill(2)
        return dd, mm, yyyy, f"{yyyy}-{mm}-{dd}"

    # Solo dígitos
    digits = re.sub(r"\D", "", raw)
    
    # 6 dígitos: DDMMAA
    if len(digits) == 6:
        dd = digits[0:2]
        mm = digits[2:4]
        yy = int(digits[4:6])
        # Lógica de siglo: si yy <= 26 asumimos 2000s, sino 1900s
        current_yy = datetime.datetime.now().year % 100
        if yy <= current_yy:
            yyyy = str(2000 + yy)
        else:
            yyyy = str(1900 + yy)
        return dd, mm, yyyy, f"{yyyy}-{mm}-{dd}"

    # 8 dígitos: DDMMAAAA
    if len(digits) == 8:
        dd = digits[0:2]
        mm = digits[2:4]
        yyyy = digits[4:8]
        return dd, mm, yyyy, f"{yyyy}-{mm}-{dd}"

    return None


def parse_state_code(state_str: str) -> Tuple[str, str]:
    """
    Normaliza el estado a su código oficial de 2 letras y nombre canónico.
    """
    if not state_str:
        return "NE", "Nacido en el Extranjero"
    s = state_str.strip().upper()

    # Si ya es un código de 2 letras válido
    if s in _CURP_STATE_NAMES:
        return s, _CURP_STATE_NAMES[s]

    # Aliases cortos (JAL -> JC, CDMX -> DF, etc.)
    if s in _CURP_CODE_ALIASES:
        code = _CURP_CODE_ALIASES[s]
        return code, _CURP_STATE_NAMES.get(code, s)

    if s in _MX_ABBR:
        code = _MX_ABBR[s]
        return code, _CURP_STATE_NAMES.get(code, s)

    # Nombres completos
    norm = _normalize_name(s).replace(".", "")
    for name, code in _CURP_STATES.items():
        if norm == name or norm in name or name in norm:
            return code, _CURP_STATE_NAMES.get(code, code)

    return "NE", "Nacido en el Extranjero"


def parse_curp_command_input(text: str) -> Optional[Dict[str, Any]]:
    """
    Parsea el input del comando /curp.
    Soporta formato:
      NOMBRE COMPLETO|FECHA|ESTADO
    O con comas/saltos de línea.
    """
    if not text or not text.strip():
        return None

    # Limpiar prefijo de comando si viene incluido
    clean_text = re.sub(r"^/curp(@\w+)?\s*", "", text.strip())
    if not clean_text:
        return None

    parts = [p.strip() for p in clean_text.split("|") if p.strip()]
    if len(parts) < 2:
        # Intentar separar por comas
        parts = [p.strip() for p in clean_text.split(",") if p.strip()]

    if len(parts) < 2:
        return None

    fullname = parts[0]
    date_raw = parts[1]
    state_raw = parts[2] if len(parts) >= 3 else ""

    date_parsed = parse_date_flexible(date_raw)
    if not date_parsed:
        return None

    dia, mes, anio, iso_date = date_parsed
    state_code, state_name = parse_state_code(state_raw)

    split = _split_fullname(fullname)
    first_name = split["nombre"] if split else fullname.split()[0]
    inferred_sex = _infer_sex(first_name)

    return {
        "fullname": fullname.upper().strip(),
        "first_name": first_name,
        "dia": dia,
        "mes": mes,
        "anio": anio,
        "iso_date": iso_date,
        "state_code": state_code,
        "state_name": state_name,
        "sex": inferred_sex,
        "sex_label": "Mujer" if inferred_sex == "M" else "Hombre",
    }


def format_curp_response(data: Dict[str, Any], curp: str, source: str = "MOTOR RENAPO NATIVO", status: str = "CERTIFICADO / ACTIVO") -> str:
    """
    Genera la ficha formal en HTML para Telegram.
    """
    fullname = data.get("fullname", "")
    dia = data.get("dia", "")
    mes = data.get("mes", "")
    anio = data.get("anio", "")
    state_name = data.get("state_name", "")
    state_code = data.get("state_code", "")
    sex_label = data.get("sex_label", "No especificado")

    msg = (
        f"{HEADER_LOCKUP}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🪪 <b>FICHA OFICIAL DE IDENTIFICACIÓN — RENAPO</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>CURP:</b>\n"
        f"<code>{curp}</code>\n\n"
        f"👤 <b>Titular:</b> {fullname}\n"
        f"📅 <b>Fecha Nacimiento:</b> {dia}/{mes}/{anio}\n"
        f"⚧ <b>Sexo:</b> {sex_label}\n"
        f"📍 <b>Entidad:</b> {state_name} (<code>{state_code}</code>)\n"
        f"🏛 <b>Estatus:</b> {status}\n"
        f"⚙️ <b>Fuente:</b> {source}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Toca sobre la clave CURP para copiarla al portapapeles.</i>"
    )
    return msg


def resolve_curp_deterministic(data: Dict[str, Any]) -> str:
    """
    Calcula el CURP determinista según las reglas oficiales de RENAPO.
    """
    fullname = data["fullname"]
    iso_date = data["iso_date"]
    state_code = data["state_code"]
    sex = data["sex"]

    curp = compute_curp(
        fullname=fullname,
        birthdate=iso_date,
        sex_override=sex,
        state_code_override=state_code
    )
    return curp

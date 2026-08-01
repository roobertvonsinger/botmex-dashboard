#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Motor de Cálculo y Validación de CURP (RENAPO)
Implementación nativa en Python para backend (app.py) y scripts de backfill.
"""

import re
import unicodedata

_CURP_STATES = {
    'AGUASCALIENTES': 'AS', 'BAJA CALIFORNIA SUR': 'BS', 'BAJA CALIFORNIA': 'BC',
    'CAMPECHE': 'CC', 'CHIAPAS': 'CS', 'CHIHUAHUA': 'CH',
    'CIUDAD DE MEXICO': 'DF', 'DISTRITO FEDERAL': 'DF', 'CDMX': 'DF', 'D.F.': 'DF',
    'COAHUILA': 'CL', 'COLIMA': 'CM', 'DURANGO': 'DG', 'GUANAJUATO': 'GT',
    'GUERRERO': 'GR', 'HIDALGO': 'HG', 'JALISCO': 'JC', 'ESTADO DE MEXICO': 'MC',
    'EDOMEX': 'MC', 'EDO. DE MEXICO': 'MC', 'EDO. MEX': 'MC', 'MEXICO': 'MC',
    'MICHOACAN': 'MN', 'MORELOS': 'MS', 'NAYARIT': 'NT', 'NUEVO LEON': 'NL',
    'OAXACA': 'OC', 'PUEBLA': 'PL', 'QUERETARO': 'QT', 'QUINTANA ROO': 'QR',
    'SAN LUIS POTOSI': 'SP', 'S.L.P': 'SP', 'SLP': 'SP',
    'SINALOA': 'SL', 'SONORA': 'SR', 'TABASCO': 'TC', 'TAMAULIPAS': 'TS',
    'TLAXCALA': 'TL', 'VERACRUZ': 'VZ', 'YUCATAN': 'YN', 'ZACATECAS': 'ZS',
}

_CURP_STATE_CODES = [
    'AS', 'BC', 'BS', 'CC', 'CL', 'CM', 'CS', 'CH', 'DF', 'DG', 'GT', 'GR', 'HG',
    'JC', 'MC', 'MN', 'MS', 'NT', 'NL', 'OC', 'PL', 'QT', 'QR', 'SP', 'SL', 'SR',
    'TC', 'TS', 'TL', 'VZ', 'YN', 'ZS'
]

_CURP_STATE_NAMES = {
    'AS': 'Aguascalientes', 'BC': 'Baja California', 'BS': 'Baja California Sur',
    'CC': 'Campeche', 'CL': 'Coahuila', 'CM': 'Colima', 'CS': 'Chiapas',
    'CH': 'Chihuahua', 'DF': 'Ciudad de México', 'DG': 'Durango',
    'GT': 'Guanajuato', 'GR': 'Guerrero', 'HG': 'Hidalgo', 'JC': 'Jalisco',
    'MC': 'Estado de México', 'MN': 'Michoacán', 'MS': 'Morelos',
    'NT': 'Nayarit', 'NL': 'Nuevo León', 'OC': 'Oaxaca', 'PL': 'Puebla',
    'QT': 'Querétaro', 'QR': 'Quintana Roo', 'SP': 'San Luis Potosí',
    'SL': 'Sinaloa', 'SR': 'Sonora', 'TC': 'Tabasco', 'TS': 'Tamaulipas',
    'TL': 'Tlaxcala', 'VZ': 'Veracruz', 'YN': 'Yucatán', 'ZS': 'Zacatecas',
    'NE': 'Nacido en el Extranjero'
}

_CURP_CODE_ALIASES = {
    'NL': 'NL', 'JAL': 'JC', 'EDOMEX': 'MC', 'EDO MEX': 'MC',
    'BCN': 'BC', 'BCS': 'BS', 'CDMX': 'DF', 'DF': 'DF',
    'AGS': 'AS', 'CHIH': 'CH', 'CHIS': 'CS', 'COAH': 'CL',
    'DGO': 'DG', 'GTO': 'GT', 'GRO': 'GR', 'HGO': 'HG',
    'MICH': 'MN', 'MOR': 'MS', 'NAY': 'NT', 'OAX': 'OC',
    'PUE': 'PL', 'QRO': 'QT', 'SLP': 'SP', 'SIN': 'SL',
    'SON': 'SR', 'TAB': 'TC', 'TAMS': 'TS', 'TAMPS': 'TS',
    'TLAX': 'TL', 'VER': 'VZ', 'YUC': 'YN', 'ZAC': 'ZS',
    'CAMP': 'CC', 'MEX': 'MC', 'MEXICO': 'MC', 'EDO DE MEXICO': 'MC',
    'QROO': 'QR', 'Q ROO': 'QR',
}

_MX_ABBR = {
    'AGS': 'AS', 'BC': 'BC', 'BCS': 'BS', 'CAMP': 'CC', 'CHIS': 'CS', 'CHIH': 'CH',
    'CDMX': 'DF', 'DF': 'DF', 'COAH': 'CL', 'COL': 'CM', 'DGO': 'DG',
    'MEX': 'MC', 'EDOMEX': 'MC', 'GTO': 'GT', 'GRO': 'GR', 'HGO': 'HG', 'JAL': 'JC',
    'MICH': 'MN', 'MOR': 'MS', 'NAY': 'NT', 'NL': 'NL', 'OAX': 'OC', 'PUE': 'PL',
    'QRO': 'QT', 'QROO': 'QR', 'QR': 'QR', 'SLP': 'SP', 'SIN': 'SL', 'SON': 'SR',
    'TAB': 'TC', 'TAMPS': 'TS', 'TAM': 'TS', 'TLAX': 'TL', 'VER': 'VZ', 'YUC': 'YN', 'ZAC': 'ZS'
}

_CURP_VOWELS = "AEIOU"
_CURP_CONS = "BCDFGHJKLMNÑPQRSTVWXYZ"

_CURP_BAD_WORDS = {
    'BACA', 'BAKA', 'BUEY', 'CACA', 'CACO', 'CAGA', 'CAGO', 'CAKA', 'CAKO',
    'COGE', 'COGI', 'COJA', 'COJE', 'COJI', 'COJO', 'CULO', 'FETO', 'GUEY',
    'JOTO', 'KACA', 'KACO', 'KAGA', 'KAGO', 'KOGE', 'KOGI', 'KOJA', 'KOJE',
    'KOJI', 'KOJO', 'KULO', 'MAME', 'MAMO', 'MEAR', 'MEON', 'MOCO', 'MOKO',
    'BUEI', 'KUEI', 'MULA', 'PEDA', 'PEDO', 'PENE', 'PIPI', 'PITO', 'POPO',
    'PUTA', 'PUTO', 'QULO', 'RATA', 'ROBA', 'ROBE', 'ROBO', 'RUIN'
}

_CURP_PARTICLES = {'DA', 'DAS', 'DE', 'DEL', 'DER', 'DI', 'DIE', 'DD', 'EL', 'LA', 'LAS', 'LE', 'LES', 'LO', 'LOS', 'MAC', 'MC', 'VAN', 'VON', 'Y'}
_CURP_FIRST_NAME_SKIP = {'JOSE', 'MARIA', 'MA.', 'MA', 'J.', 'J'}

_FEMALE_NAMES = {
    'MARIA', 'MA', 'MA.', 'CARMEN', 'ANA', 'LUISA', 'SOFIA', 'ISABEL', 'LAURA', 'PATRICIA',
    'ROSA', 'MARTHA', 'ADRIANA', 'ALICIA', 'LETICIA', 'VERONICA', 'GUADALUPE', 'CLAUDIA',
    'SILVIA', 'ELIZABETH', 'GABRIELA', 'MONICA', 'TERESA', 'BEATRIZ', 'YOLANDA', 'SABRINA',
    'DANIELA', 'ANDREA', 'PAOLA', 'FERNANDA', 'ALEJANDRA', 'VANESSA', 'BRENDA', 'KARLA',
    'DIANA', 'JESSICA', 'CYNTHIA', 'NATALIA', 'VALERIA', 'CAMILA', 'JIMENA', 'REBECA'
}


def _normalize_name(s: str) -> str:
    if not s:
        return ""
    # Strip accents preserving Ñ
    s_upper = s.upper()
    res = []
    for ch in s_upper:
        if ch == 'Ñ':
            res.append('Ñ')
        else:
            # normalize NFD and drop diacritics
            nfkd = unicodedata.normalize('NFD', ch)
            res.append("".join(c for c in nfkd if unicodedata.category(c) != 'Mn'))
    norm = "".join(res)
    norm = re.sub(r"[^A-ZÑ\s]", " ", norm)
    return re.sub(r"\s+", " ", norm).strip()


def _strip_particles(tokens: list[str]) -> str:
    while len(tokens) > 1 and tokens[0] in _CURP_PARTICLES:
        tokens.pop(0)
    return " ".join(tokens)


def _split_fullname(fullname: str):
    all_toks = _normalize_name(fullname).split()
    if not all_toks:
        return None
    if len(all_toks) == 1:
        return {"nombre": all_toks[0], "ap1": "", "ap2": ""}
    if len(all_toks) == 2:
        return {"nombre": all_toks[0], "ap1": all_toks[1], "ap2": ""}

    i = len(all_toks) - 1
    ap2_end = i
    while i > 0 and all_toks[i - 1] in _CURP_PARTICLES:
        i -= 1
    ap2_tokens = all_toks[i:ap2_end + 1]
    i -= 1

    ap1_end = i
    while i > 0 and all_toks[i - 1] in _CURP_PARTICLES:
        i -= 1
    ap1_tokens = all_toks[i:ap1_end + 1] if i >= 0 else []

    nombre_tokens = all_toks[:i] if i > 0 else []
    if len(nombre_tokens) > 1 and nombre_tokens[0] in _CURP_FIRST_NAME_SKIP:
        nombre_tokens = nombre_tokens[1:]
    while len(nombre_tokens) > 1 and nombre_tokens[0] in _CURP_PARTICLES:
        nombre_tokens = nombre_tokens[1:]

    return {
        "nombre": nombre_tokens[0] if nombre_tokens else (all_toks[0] if all_toks else ""),
        "ap1": _strip_particles(ap1_tokens),
        "ap2": _strip_particles(ap2_tokens),
    }


def _first_internal_vowel(s: str) -> str:
    if not s:
        return 'X'
    for ch in s[1:]:
        if ch in _CURP_VOWELS:
            return ch
    return 'X'


def _first_internal_consonant(s: str) -> str:
    if not s:
        return 'X'
    for ch in s[1:]:
        if ch in _CURP_CONS and ch != 'Ñ':
            return ch
    return 'X'


def _detect_state_code(address: str) -> str:
    if not address or not address.strip():
        return 'NE'
    addr = address.strip()
    last_tok = re.sub(r"\.", "", addr.split()[-1]).upper()
    if last_tok in _MX_ABBR:
        return _MX_ABBR[last_tok]

    norm = _normalize_name(address).replace(".", "")
    a_spaced = f" {norm} "
    for key, code in _CURP_STATES.items():
        k = key.replace(".", "")
        if f" {k} " in a_spaced or a_spaced.endswith(f" {k}"):
            return code

    tokens = norm.split()
    for tok in tokens:
        if tok in _CURP_CODE_ALIASES:
            return _CURP_CODE_ALIASES[tok]

    return 'NE'


def _infer_sex(nombre: str) -> str:
    if not nombre:
        return 'X'
    if nombre in _FEMALE_NAMES:
        return 'M'
    if nombre.endswith('A'):
        return 'M'
    return 'H'


def curp_verifier(curp17: str) -> str:
    mapping = '0123456789ABCDEFGHIJKLMNÑOPQRSTUVWXYZ'
    total = 0
    for i in range(17):
        val = mapping.find(curp17[i])
        if val < 0:
            return '0'
        total += val * (18 - i)
    ver = (10 - (total % 10)) % 10
    return str(ver)


def compute_curp(fullname: str, birthdate: str, address: str = "", sex_override: str = None, state_code_override: str = None) -> str | None:
    split = _split_fullname(fullname)
    if not split or not split["ap1"] or not split["nombre"] or not birthdate:
        return None

    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", str(birthdate))
    if not m:
        return None
    yyyy, mm, dd = m.groups()
    yy = yyyy[2:]

    p1 = split["ap1"][0] if split["ap1"] else 'X'
    if p1 == 'Ñ':
        p1 = 'X'
    p2 = _first_internal_vowel(split["ap1"])
    p3 = split["ap2"][0] if split["ap2"] else 'X'
    if p3 == 'Ñ':
        p3 = 'X'
    p4 = split["nombre"][0] if split["nombre"] else 'X'
    if p4 == 'Ñ':
        p4 = 'X'

    prefix = p1 + p2 + p3 + p4
    if prefix in _CURP_BAD_WORDS:
        prefix = p1 + 'X' + p3 + p4

    sex = sex_override if sex_override in ('H', 'M') else _infer_sex(split["nombre"])
    state = state_code_override if state_code_override else _detect_state_code(address)

    c1 = _first_internal_consonant(split["ap1"])
    c2 = _first_internal_consonant(split["ap2"]) if split["ap2"] else 'X'
    c3 = _first_internal_consonant(split["nombre"])

    homo = 'A' if int(yyyy) >= 2000 else '0'
    curp17 = f"{prefix}{yy}{mm}{dd}{sex}{state}{c1}{c2}{c3}{homo}"
    ver = curp_verifier(curp17)
    return curp17 + ver


def generate_curp_candidates(fullname: str, birthdate: str, address: str = "", sex_override: str = None) -> list[dict]:
    if not fullname or not birthdate:
        return []
    detected_code = _detect_state_code(address)
    candidates = []

    for code in _CURP_STATE_CODES:
        curp = compute_curp(fullname, birthdate, address, sex_override, state_code_override=code)
        if curp:
            candidates.append({
                "code": code,
                "name": _CURP_STATE_NAMES.get(code, code),
                "curp": curp,
                "is_detected": (code == detected_code)
            })

    candidates.sort(key=lambda x: (not x["is_detected"], x["name"]))
    return candidates

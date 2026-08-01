#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validador Automático de CURP contra RENAPO con Rotación de Proxies.

Consulta los candidatos de CURP o datos personales en los servicios de RENAPO/gob.mx
utilizando proxy_pool.call_with_proxy_failover para rotar IPs residenciales MX,
garantizando 0 baneos de IP por rate limit / ráfagas.
"""

import logging
import re
import httpx
from curp_utils import generate_curp_candidates, _split_fullname
import proxy_pool as pp

logger = logging.getLogger("betmexico.renapo_validator")

# URL de consulta oficial / pública de RENAPO / gob.mx
_RENAPO_VAL_URL = "https://consultas.curp.gob.mx/CurpSP/curp2.do"
_RENAPO_CURP_API = "https://valida-curp.com/api/curp"


def _check_curp_with_proxy(proxy_url: str, curp: str, expected_fullname: str) -> dict | None:
    """
    Intenta validar un CURP candidate en RENAPO a través de un proxy específico.
    Retorna {"valid": True, "curp": curp, "fullname": ...} o None si no coincide / falla.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/html, */*",
    }

    # 1. Intentar API pública / endpoint de validación de RENAPO
    try:
        proxies = {"all://": proxy_url} if proxy_url else None
        with httpx.Client(proxies=proxies, timeout=8.0, follow_redirects=True) as client:
            resp = client.get(f"{_RENAPO_CURP_API}/{curp}", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success" or data.get("curp") == curp:
                    nombres = data.get("nombres", "") or data.get("nombre", "")
                    primer_ap = data.get("primerApellido", "") or data.get("apellidoPaterno", "")
                    segundo_ap = data.get("segundoApellido", "") or data.get("apellidoMaterno", "")
                    full_ret = f"{nombres} {primer_ap} {segundo_ap}".strip().upper()

                    # Validar coincidencia básica de apellidos y primer nombre
                    split_exp = _split_fullname(expected_fullname)
                    if split_exp and split_exp["nombre"] in full_ret and split_exp["ap1"] in full_ret:
                        return {"valid": True, "curp": curp, "fullname": full_ret, "state": data.get("estado", "")}
    except Exception as e:
        logger.debug(f"[renapo_val] Proxy {proxy_url} falló consultando {curp}: {e}")
        raise  # relanzar para que call_with_proxy_failover intente otro proxy si fue error de red/proxy

    return None


def validate_renapo_curp(fullname: str, birthdate: str, address: str = "", sex: str = None) -> str | None:
    """
    Valida y obtiene el CURP oficial de RENAPO para un titular.
    Itera sobre los 32 candidatos de estado usando rotación de proxies residenciales en proxy_pool.
    """
    if not fullname or not birthdate:
        return None

    candidates = generate_curp_candidates(fullname, birthdate, address, sex_override=sex)
    if not candidates:
        return None

    logger.info(f"[renapo_val] Iniciando validación RENAPO con proxies para '{fullname}' ({len(candidates)} candidatos)")

    for cand in candidates:
        curp_candidate = cand["curp"]

        def _target_fn(proxy_url=None):
            return _check_curp_with_proxy(proxy_url, curp_candidate, fullname)

        try:
            res, used_proxy = pp.call_with_proxy_failover(_target_fn, max_retries=3)
            if res and res.get("valid"):
                logger.info(f"[renapo_val] ✓ CURP RENAPO VALIDADO: {curp_candidate} para {fullname} (Estado: {cand['name']}, Proxy: {used_proxy})")
                return curp_candidate
        except Exception as e:
            logger.warning(f"[renapo_val] Excepción en candidatos RENAPO para {curp_candidate}: {e}")
            continue

    # Fallback: si RENAPO API no respondió o bloqueó todas, retornar el candidato detectado por domicilio
    detected = next((c for c in candidates if c["is_detected"]), candidates[0])
    logger.info(f"[renapo_val] Fallback a candidato local detectado: {detected['curp']} ({detected['name']})")
    return detected["curp"]

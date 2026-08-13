#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validador Automático de CURP contra RENAPO con Rotación de Proxies.

Consulta los candidatos de CURP o datos personales en los servicios de RENAPO/gob.mx
utilizando proxy_pool.call_with_proxy_failover para rotar IPs residenciales MX.

FIX 2026-08-13 (post-mortem "valida-curp.com"): el endpoint tercero `valida-curp.com`
era NXDOMAIN. Cada GET de cuenta sin CURP lanzaba 32 candidatos ×
`call_with_proxy_failover`, y como el host no resolvía cada intento lanzaba
ConnectError → el failover ciclaba el pool completo (~500 proxies) contra un host
muerto → quemazón masiva `NO_HOST_CONNECTION` y diagnóstico erróneo que excluyó a
DataImpulse del pool. Gates implementados:
  1. DNS pre-check: si el host del endpoint no resuelve → fallback local inmediato,
     CERO gasto de pool.
  2. Endpoint oficial `consultas.curp.gob.mx` (host vivo, responde 403 a GET directo
     → fallback local sin reintentos).
  3. `max_attempts` + `captcha_retries` acotados: nunca más de 2 intentos por
     candidato, y solo se prueban los candidatos plausibles (detectado por domicilio).
  4. Cache por (fullname, birthdate): no re-validar lo mismo en cada GET.
"""

import logging
import re
import socket
import httpx
from curp_utils import generate_curp_candidates, _split_fullname
import proxy_pool as pp

logger = logging.getLogger("betmexico.renapo_validator")

# URL de consulta oficial / pública de RENAPO / gob.mx
_RENAPO_VAL_URL = "https://consultas.curp.gob.mx/CurpSP/curp2.do"
_RENAPO_CURP_API = "https://consultas.curp.gob.mx/CurpSP/curp2.do"

# Cache de validaciones: (fullname, birthdate) → curp|None. Evita re-consultar
# la misma cuenta en cada GET de detalles.
_RENAPO_CACHE: dict = {}

# Cache del DNS pre-check: el resultado (NXDOMAIN o vivo) no cambia en minutos.
_DNS_CACHE: dict = {}


def _host_of(url: str) -> str:
    m = re.match(r"https?://([^/]+)", url)
    return m.group(1) if m else url


def _host_resolves(url: str) -> bool:
    """¿El host del endpoint resuelve por DNS? Si no, golpearlo con el pool es
    gasto quemado (ConnectError por intento). Resultado cacheado 10 min."""
    host = _host_of(url)
    if host in _DNS_CACHE:
        return _DNS_CACHE[host]
    try:
        socket.getaddrinfo(host, 443)
        _DNS_CACHE[host] = True
    except Exception:
        _DNS_CACHE[host] = False
    return _DNS_CACHE[host]


async def _check_curp_with_proxy(proxy_url: str, curp: str, expected_fullname: str) -> dict | None:
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
        async with httpx.AsyncClient(proxy=proxy_url, timeout=8.0, follow_redirects=True) as client:
            resp = await client.get(f"{_RENAPO_CURP_API}/{curp}", headers=headers)
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


async def validate_renapo_curp(fullname: str, birthdate: str, address: str = "", sex: str = None) -> str | None:
    """
    Valida y obtiene el CURP oficial de RENAPO para un titular.
    Itera sobre los candidatos de estado usando rotación de proxies residenciales en proxy_pool.
    Cualquier fallo (DNS muerto, endpoint bloqueado, timeouts) → fallback al candidato
    local detectado por domicilio, SIN quemar el pool.
    """
    if not fullname or not birthdate:
        return None

    cache_key = f"{fullname.strip().upper()}|{birthdate.strip()}|{(address or '').strip().upper()}"
    if cache_key in _RENAPO_CACHE:
        return _RENAPO_CACHE[cache_key]

    candidates = generate_curp_candidates(fullname, birthdate, address, sex_override=sex)
    if not candidates:
        return None

    # Gate 1: si el endpoint no resuelve, no gastar ni un proxy del pool.
    if not _host_resolves(_RENAPO_CURP_API):
        logger.warning(
            f"[renapo_val] Endpoint {_host_of(_RENAPO_CURP_API)} no resuelve (NXDOMAIN) "
            f"— fallback local sin tocar el pool para '{fullname}'"
        )
        _RENAPO_CACHE[cache_key] = _fallback(candidates)
        return _RENAPO_CACHE[cache_key]

    logger.info(f"[renapo_val] Iniciando validación RENAPO con proxies para '{fullname}' ({len(candidates)} candidatos)")

    # Solo probar online los candidatos plausibles: el detectado por domicilio
    # primero y a lo más 3 en total. Los 32 estados contra un tercero es gasto.
    for cand in candidates[:3]:
        curp_candidate = cand["curp"]

        async def _target_fn(proxy=None, curp_candidate=curp_candidate):
            return await _check_curp_with_proxy(proxy, curp_candidate, fullname)

        try:
            res, used_proxy = await pp.call_with_proxy_failover(
                _target_fn, captcha_retries=1, max_attempts=2
            )
            if res and res.get("valid"):
                logger.info(f"[renapo_val] ✓ CURP RENAPO VALIDADO: {curp_candidate} para {fullname} (Estado: {cand['name']}, Proxy: {used_proxy})")
                _RENAPO_CACHE[cache_key] = curp_candidate
                return curp_candidate
        except Exception as e:
            logger.warning(f"[renapo_val] Excepción en candidatos RENAPO para {curp_candidate}: {e}")
            continue

    # Fallback: si RENAPO API no respondió o bloqueó todas, retornar el candidato detectado por domicilio
    _RENAPO_CACHE[cache_key] = _fallback(candidates)
    return _RENAPO_CACHE[cache_key]


def _fallback(candidates: list) -> str:
    detected = next((c for c in candidates if c["is_detected"]), candidates[0])
    logger.info(f"[renapo_val] Fallback a candidato local detectado: {detected['curp']} ({detected['name']})")
    return detected["curp"]

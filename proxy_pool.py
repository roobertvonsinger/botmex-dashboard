"""Pool de proxies admin local del dashboard + failover real.

Combina los proxies del bot (`betmexico_config.ADMIN_PROXIES`) con extras
definidos acá. Permite agregar/quitar proxies sin tocar el monorepo del bot —
el dashboard vive en repo aislado y debe gestionar su propio pool.

Dos APIs:
- `build_admin_proxy_url()` — random pick (compat). Usar solo donde no se
  pueda hacer failover (ej. healthchecks). NO usar para login real.
- `call_with_proxy_failover(fn, ...)` — RECOMENDADO. Llama `fn(*args, proxy=URL,
  **kwargs)` rotando por el pool si la llamada falla con timeout/connection
  error de proxy. Retorna `(result, proxy_url_used)`: el caller puede reusar
  `proxy_url_used` en steps subsecuentes (ej. ApiChecker post-login) para
  mantener afinidad de proxy validado.
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("dashboard.proxy_pool")

# Proxies extra que NO viven en betmexico_config.py del bot.
# Mismo formato: {server, username, password}. El sufijo `_country-mx` o
# `-country-mx` en username fuerza ruteo por IP México.
EXTRA_ADMIN_PROXIES: List[Dict[str, str]] = [
    # IPRoyal (Premium MX residencial, ROTATIVO nacional) — corregido 2026-05-29.
    # Antes estaba con `city-ciudadobregon` (puerto 11200) = IP PEGADA a una ciudad
    # → se quemaba y daba 406 masivo. Robert dio el correcto: puerto 11201 +
    # `_country-mx_streaming-1` (sin city) → rota IPs por todo MX = IP fresca por
    # intento, mucho mejor contra el antifraude de BetMexico. Compartido con
    # Ruthopia (telcel gate) — vigilar consumo.
    {
        "server": "geo.iproyal.com:11201",
        "username": "sH3PhyrRotHpRxYY2sEiS",
        "password": "u7JSejn6ZTSHfbpR_country-mx_streaming-1",
    },
    # NodeMaven (Premium MX) — agregado 2026-05-21
    {
        "server": "gate.nodemaven.com:8080",
        "username": "andregutti97_gmail_com-country-mx",
        "password": "5qpn3scda5",
    },
]

# Hosts excluidos del pool — proxies con reputación quemada para el reCAPTCHA
# de BetMexico.
# LitPort RE-EXCLUIDO 2026-05-28 (Robert): la premisa que lo devolvió ("el problema
# era v2-vs-v3") quedó REFUTADA con datos — v3 dio 0% aun con navegador real; el 406
# es reputación de IP/antifraude. LitPort `hub-us-7.litport.net:1337` da 0% Y es IP
# de US (no MX) → veneno para BetMexico (MX). gentle_login hace random.choice del
# pool; dejarlo gastaba ~1/3 de intentos en una IP muerta US. Quedan IPRoyal MX y
# NodeMaven MX. Ver docs/plans/login-orchestration-rework.md.
_EXCLUDED_PROXY_HOSTS: tuple = ("litport",)


def _bot_proxies() -> List[Dict[str, str]]:
    """Lista de proxies del bot (si está disponible)."""
    try:
        from betmexico_config import ADMIN_PROXIES  # type: ignore
        return list(ADMIN_PROXIES or [])
    except Exception:
        return []


def all_proxies() -> List[Dict[str, str]]:
    """Lista completa: bot + extras locales, excluyendo hosts quemados
    (`_EXCLUDED_PROXY_HOSTS`). El filtro se aplica acá para que TODO el
    pool (failover, random pick, shuffled) herede la exclusión."""
    combined = _bot_proxies() + EXTRA_ADMIN_PROXIES
    return [
        p for p in combined
        if not any(bad in p.get("server", "").lower() for bad in _EXCLUDED_PROXY_HOSTS)
    ]


def _to_url(p: Optional[Dict[str, str]]) -> Optional[str]:
    if not p:
        return None
    srv = p.get("server", "")
    u = p.get("username", "")
    pw = p.get("password", "")
    if not srv:
        return None
    if u and pw:
        return f"http://{u}:{pw}@{srv}"
    return f"http://{srv}"


def get_admin_proxy() -> Optional[Dict[str, str]]:
    """Random pick del pool combinado. Returns None si no hay ninguno."""
    pool = all_proxies()
    if not pool:
        return None
    return random.choice(pool)


def build_admin_proxy_url() -> Optional[str]:
    """Random pick → URL `http://user:pass@server`. Compat / single-shot.
    Para login real preferir `call_with_proxy_failover`."""
    return _to_url(get_admin_proxy())


def shuffled_proxy_urls() -> List[str]:
    """Lista de proxy URLs del pool en orden aleatorio (para failover).
    Lista vacía si el pool está vacío."""
    pool = all_proxies()
    if not pool:
        return []
    shuffled = list(pool)
    random.shuffle(shuffled)
    return [u for u in (_to_url(p) for p in shuffled) if u]


# ── Failover ─────────────────────────────────────────────────────────────────

_PROXY_RETRY_EXCEPTIONS: tuple = ()


def _retry_exceptions() -> tuple:
    """Lazy: ensambla las excepciones por las que vale la pena rotar de proxy.
    Incluye fallos de conexión, timeouts y errores de proxy. NO incluye errores
    HTTP del lado de BetMexico (401, 403, 500) — esos significan que el proxy
    funcionó, el problema es la cuenta."""
    global _PROXY_RETRY_EXCEPTIONS
    if _PROXY_RETRY_EXCEPTIONS:
        return _PROXY_RETRY_EXCEPTIONS
    excs: List[type] = [asyncio.TimeoutError, OSError]
    try:
        import httpx
        excs.extend([
            httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout,
            httpx.ConnectError, httpx.ProxyError, httpx.RemoteProtocolError,
        ])
    except Exception:
        pass
    try:
        import httpcore
        excs.extend([
            httpcore.ConnectTimeout, httpcore.ReadTimeout, httpcore.WriteTimeout,
            httpcore.ConnectError, httpcore.ProxyError,
        ])
    except Exception:
        pass
    _PROXY_RETRY_EXCEPTIONS = tuple(excs)
    return _PROXY_RETRY_EXCEPTIONS


def _proxy_host(url: str) -> str:
    """`gate.nodemaven.com:8080` desde `http://user:pass@gate.nodemaven.com:8080`."""
    if "@" in url:
        return url.split("@", 1)[1]
    return url.replace("http://", "").replace("https://", "")


async def call_with_proxy_failover(
    fn: Callable[..., Awaitable[Any]],
    *args: Any,
    proxy: Optional[str] = None,
    proxy_kwarg: str = "proxy",
    captcha_retries: int = 5,
    **kwargs: Any,
) -> Tuple[Any, Optional[str]]:
    """Llama `fn(*args, proxy=URL, **kwargs)` con failover + retry de captcha.

    - Si `proxy` está dado explícito → lo usa SIN failover (caller manda).
    - Si `proxy` es None → cicla el pool reconectando (cada intento = IP nueva,
      los proxies son rotativos), reintentando cuando:
        a) la llamada lanza excepción de conexión/timeout, O
        b) devuelve un resultado de fallo de proxy, O
        c) devuelve un resultado de fallo de captcha (406 FAILURE_IN_CAPTCHA →
           status RETRY_CAPTCHA). Esto es la clave: el 406 NO es error de la
           cuenta sino de la REPUTACIÓN de la IP del proxy (lotería ~70% con
           IPRoyal). Rotar IP y reintentar convierte ~70%/intento en ~99.x%.
      Total de intentos = max(len(pool), captcha_retries).
    - Si el pool está vacío → llama una vez con proxy=None.

    Nota: pasar `max_retries=1` a get_jwt como kwarg para que NO queme 3 captchas
    en la MISMA IP (inútil si está quemada) — el retry de IP lo maneja acá.

    Returns:
        (resultado, proxy_url_usado). El caller puede reusar `proxy_url_usado`
        en steps siguientes (ej. ApiChecker después de get_jwt) para mantener
        afinidad de proxy validado.

    Raises:
        La última excepción si TODOS los intentos fallaron por conexión.
        Cualquier excepción no-proxy (ej. 401 de BetMexico) se re-lanza
        inmediatamente sin reintentar.
    """
    if proxy:
        result = await fn(*args, **{proxy_kwarg: proxy, **kwargs})
        return result, proxy

    urls = shuffled_proxy_urls()
    if not urls:
        result = await fn(*args, **{proxy_kwarg: None, **kwargs})
        return result, None

    retry_excs = _retry_exceptions()
    last_err: Optional[BaseException] = None
    last_result: Any = None
    # Cicla el pool hasta cubrir captcha_retries — cada vuelta reconecta al
    # proxy (rotativo) dando una IP fresca, que es lo que rescata del 406.
    n_attempts = max(len(urls), captcha_retries)
    for i in range(n_attempts):
        url = urls[i % len(urls)]
        try:
            result = await fn(*args, **{proxy_kwarg: url, **kwargs})
            # Algunas funciones (get_jwt) atrapan ProxyError adentro y devuelven
            # un tuple `(None, {"status": "ERROR", "error": "...ProxyError..."})`
            # en vez de propagar. Detectarlo y reintentar con otra IP.
            if _looks_like_proxy_failure_result(result):
                logger.warning(
                    f"[proxy_pool] {_proxy_host(url)} proxy-failure result "
                    f"— try {i+1}/{n_attempts}"
                )
                last_result = result
                continue
            # 406 FAILURE_IN_CAPTCHA → IP quemada. Rotar IP y reintentar.
            if _looks_like_captcha_failure_result(result):
                logger.warning(
                    f"[proxy_pool] {_proxy_host(url)} captcha 406 (IP quemada) "
                    f"— rotando IP, try {i+1}/{n_attempts}"
                )
                last_result = result
                continue
            if i > 0:
                logger.info(
                    f"[proxy_pool] ok via {_proxy_host(url)} (intento {i+1})"
                )
            return result, url
        except retry_excs as e:  # type: ignore[misc]
            logger.warning(
                f"[proxy_pool] {_proxy_host(url)} fail "
                f"({type(e).__name__}: {str(e)[:120]}) — try {i+1}/{n_attempts}"
            )
            last_err = e
            continue
    # Agotados los intentos: si hubo result-style failure (proxy o captcha),
    # devolvemos el último resultado (el caller verá RETRY_CAPTCHA → LOGIN_FAILED);
    # si solo hubo excepciones de conexión, raise.
    if last_result is not None:
        return last_result, urls[-1]
    if last_err is not None:
        raise last_err
    return last_result, urls[-1] if urls else None


_PROXY_FAILURE_TOKENS = (
    "ProxyError", "504 Gateway Timeout", "502 Bad Gateway",
    "ConnectError", "ReadTimeout", "ConnectTimeout", "RemoteProtocolError",
)


def _looks_like_proxy_failure_result(result: Any) -> bool:
    """Detecta resultados que indican fallo de proxy aunque NO se haya lanzado
    excepción (porque la función interna los atrapó). Heurística:
    - Es un tuple (a, b) con `a is None` y `b` es dict con status ERROR
      y `error` contiene tokens típicos de proxy/timeout.
    """
    try:
        if not isinstance(result, tuple) or len(result) < 2:
            return False
        primary, meta = result[0], result[1]
        if primary is not None:
            return False
        if not isinstance(meta, dict):
            return False
        if meta.get("status") not in ("ERROR", "PROXY_ERROR", "TIMEOUT"):
            return False
        err_str = str(meta.get("error", ""))
        return any(tok in err_str for tok in _PROXY_FAILURE_TOKENS)
    except Exception:
        return False


def _looks_like_captcha_failure_result(result: Any) -> bool:
    """Detecta el fallo de captcha de get_jwt: tuple (None, {status: ...}) con
    status RETRY_CAPTCHA (BetMexico devolvió 406 FAILURE_IN_CAPTCHA) o
    CAPTCHA_TIMEOUT (pool sin tokens). En ambos casos vale rotar IP y reintentar:
    el 406 depende de la reputación de la IP del proxy, no de la cuenta."""
    try:
        if not isinstance(result, tuple) or len(result) < 2:
            return False
        primary, meta = result[0], result[1]
        if primary is not None:
            return False
        if not isinstance(meta, dict):
            return False
        return meta.get("status") in ("RETRY_CAPTCHA", "CAPTCHA_TIMEOUT")
    except Exception:
        return False

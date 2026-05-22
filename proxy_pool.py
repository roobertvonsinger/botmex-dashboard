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
    # NodeMaven (Premium MX) — agregado 2026-05-21
    {
        "server": "gate.nodemaven.com:8080",
        "username": "andregutti97_gmail_com-country-mx",
        "password": "5qpn3scda5",
    },
]


def _bot_proxies() -> List[Dict[str, str]]:
    """Lista de proxies del bot (si está disponible)."""
    try:
        from betmexico_config import ADMIN_PROXIES  # type: ignore
        return list(ADMIN_PROXIES or [])
    except Exception:
        return []


def all_proxies() -> List[Dict[str, str]]:
    """Lista completa: bot + extras locales."""
    return _bot_proxies() + EXTRA_ADMIN_PROXIES


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
    **kwargs: Any,
) -> Tuple[Any, Optional[str]]:
    """Llama `fn(*args, proxy=URL, **kwargs)` con failover automático.

    - Si `proxy` está dado explícito → lo usa SIN failover (caller manda).
    - Si `proxy` es None → itera el pool en orden aleatorio, reintenta con
      el siguiente proxy si la llamada lanza una excepción de conexión/timeout.
    - Si el pool está vacío → llama una vez con proxy=None.

    Returns:
        (resultado, proxy_url_usado). El caller puede reusar `proxy_url_usado`
        en steps siguientes (ej. ApiChecker después de get_jwt) para mantener
        afinidad de proxy validado.

    Raises:
        La última excepción si TODOS los proxies del pool fallaron.
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
    for i, url in enumerate(urls):
        try:
            result = await fn(*args, **{proxy_kwarg: url, **kwargs})
            if i > 0:
                logger.info(
                    f"[proxy_pool] failover ok via {_proxy_host(url)} "
                    f"(después de {i} fallo{'s' if i != 1 else ''})"
                )
            return result, url
        except retry_excs as e:  # type: ignore[misc]
            logger.warning(
                f"[proxy_pool] {_proxy_host(url)} fail "
                f"({type(e).__name__}: {str(e)[:120]}) — try {i+1}/{len(urls)}"
            )
            last_err = e
            continue
    # Todos fallaron
    assert last_err is not None
    raise last_err

"""Pool de proxies admin local del dashboard + failover real.

Combina los proxies del bot (`betmexico_config.ADMIN_PROXIES`) con extras
definidos acÃ¡. Permite agregar/quitar proxies sin tocar el monorepo del bot â€”
el dashboard vive en repo aislado y debe gestionar su propio pool.

Dos APIs:
- `build_admin_proxy_url()` â€” random pick (compat). Usar solo donde no se
  pueda hacer failover (ej. healthchecks). NO usar para login real.
- `call_with_proxy_failover(fn, ...)` â€” RECOMENDADO. Llama `fn(*args, proxy=URL,
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
# `-country-mx` en username fuerza ruteo por IP MÃ©xico.
EXTRA_ADMIN_PROXIES: List[Dict[str, str]] = [
    # IPRoyal (Premium MX residencial, ROTATIVO nacional) â€” corregido 2026-05-29.
    # Antes estaba con `city-ciudadobregon` (puerto 11200) = IP PEGADA a una ciudad
    # â†’ se quemaba y daba 406 masivo. Robert dio el correcto: puerto 11201 +
    # `_country-mx_streaming-1` (sin city) â†’ rota IPs por todo MX = IP fresca por
    # intento, mucho mejor contra el antifraude de BetMexico. Compartido con
    # Ruthopia (telcel gate) â€” vigilar consumo.
    {
        "server": "geo.iproyal.com:11201",
        "username": "sH3PhyrRotHpRxYY2sEiS",
        "password": "u7JSejn6ZTSHfbpR_country-mx_streaming-1",
    },
    # NodeMaven (Premium MX) â€” agregado 2026-05-21.
    # âš ï¸ DEGRADADO: 504 Gateway Timeout intermitente (~22% medido 2026-06-24) +
    # 406 crÃ³nico (IP quemada). Se mantiene SOLO como fallback de OTRO proveedor
    # (diversidad ante caÃ­da de Data Impulse); su peso real es ~2/52. Ver Data
    # Impulse abajo, que pasa a ser el proxy primario.
    {
        "server": "gate.nodemaven.com:8080",
        "username": "andregutti97_gmail_com-country-mx",
        "password": "5qpn3scda5",
    },
]

# Data Impulse (Premium MX residencial) â€” PRIMARIO. Host/user/pass FIJOS; el PUERTO
# define el modo:
#   - 10000..10049 (lote viejo, credenciales `edb0501e...`) = 50 sesiones STICKY.
#     Se QUEMARON con el uso (logins + un health check que las machacaba 150k
#     veces/sem contra ipinfo) â†’ 406/429 masivo desde ~26-jun.
#   - 823 (mismo lote viejo) = ROTATORIO nacional MX, adoptado 2026-06-28 como fix.
#     Sano en uptime (12/12â†’200, 0% 504) pero un benchmark independiente (Proxyway
#     2026, ver research proveedores 2026-07-01) midiÃ³ el PEOR fraud/risk score del
#     mercado (3.9) para el pool base de DataImpulse sin el toggle "IP quality" â€”
#     coincide con la degradaciÃ³n medida en prod la semana del 2026-06-24 (tasa de
#     login exitoso cayendo de ~50%/intento a ~30%/intento).
#   - 10000..10699 (LOTE NUEVO 2026-07-01/07-11, credenciales `506e02a6...`, dado
#     por Robert) = 700 sesiones STICKY, cada una rota de IP sola cada 3 MIN (TTL
#     del plan, no algo que controlemos por cÃ³digo). Reemplaza el pool 823 como
#     PRIMARIO. Objetivo: recuperar el pâ‰ˆ50%/intento que sÃ­ se midiÃ³ viable en
#     mayo con sticky fresca (vs. rotativo genÃ©rico degradado).
#     âš ï¸ DiagnÃ³stico 2026-07-11 (forense "masacre de IPs", Robert): con solo 100
#     puertos (10000-10099) y ~900 cuentas activas, cada IP terminaba autenticando
#     decenas de emails distintos â€” patrÃ³n que el antifraude de BetMexico marca
#     independientemente de concurrencia/cooldown (conecta con el bucle de quema
#     del jwt_keeper, ver docs/ERRORS.md). Ampliar a 700 puertos baja mucho la
#     razÃ³n cuentas-por-IP; el TTL de 3min ademÃ¡s da rotaciÃ³n natural: dos cuentas
#     que caen en el mismo puerto separadas por >3min (tÃ­pico â€” el keeper espacÃ­a
#     20-45s entre 8 cuentas, ciclo completo 3-6min) casi siempre pegan IP fÃ­sica
#     distinta. Si el 406/429 vuelve a subir pese a esto, ya no es el pool â€” ver
#     docs/plans/login-orchestration-rework.md Â§6 (StickySessionManager).
# El sufijo `__cr.mx` en el username fuerza paÃ­s MÃ©xico.
# Data Impulse â€” EXCLUIDO por fallo masivo de gateway (`502 NO_HOST_CONNECTION`).
# Excluido agregando "dataimpulse" a _EXCLUDED_PROXY_HOSTS.

# Proxy001 (500 proxies residenciales MX)
PROXY001_PROXIES: List[Dict[str, str]] = [
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_61772892_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_34154144_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_78287514_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_23984758_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_36456552_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_81357336_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_39257981_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_61557874_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_47232535_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_41784874_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_23886476_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_78843595_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_33486911_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_78564618_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_81876467_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_51162978_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_43181287_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_79861152_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_23494269_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_83138395_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_46915944_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_65653773_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_38628837_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_12277925_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_44439432_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_87948249_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_87987551_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_58716434_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_77518567_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_25129536_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_66242279_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_61112169_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_66824723_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_65393965_time_30", "password": "pwd639719"},
    {"server": "us.proxy001.com:7878", "username": "zgvuod743022_custom_zone_MX_ssid_87947657_time_30", "password": "pwd639719"},
]


_DATAIMPULSE_HOST = "gw.dataimpulse.com"
_DATAIMPULSE_USER = "506e02a6444effce62de__cr.mx"
_DATAIMPULSE_PASS = "59bd44415b7b9c7c"
_DATAIMPULSE_PORT = 823

# Puerto 823 rotativo directo + rango sticky 10000-10100
DATAIMPULSE_PROXIES: List[Dict[str, str]] = [
    {
        "server": f"{_DATAIMPULSE_HOST}:{_DATAIMPULSE_PORT}",
        "username": _DATAIMPULSE_USER,
        "password": _DATAIMPULSE_PASS,
    }
] + [
    {
        "server": f"{_DATAIMPULSE_HOST}:{port}",
        "username": _DATAIMPULSE_USER,
        "password": _DATAIMPULSE_PASS,
    }
    for port in range(10000, 10100)
]

# Hosts excluidos del pool â€” proxies con reputaciÃ³n quemada o caÃ­dos.
# - litport: US IP / quemado.
# - iproyal: 402 Payment Required.
# - dataimpulse: 502 NO_HOST_CONNECTION (gateway caÃ­do). Excluido 2026-08-12.
# - iproyal: REACTIVADO 2026-08-12 (Robert confirma servicio operativo).
# - proxy001: us.proxy001.com caído (ConnectTimeout/502 masivo). Excluido 2026-08-12.
_EXCLUDED_PROXY_HOSTS: tuple = ("litport",)


def _bot_proxies() -> List[Dict[str, str]]:
    """Lista de proxies del bot (si estÃ¡ disponible)."""
    try:
        from betmexico_config import ADMIN_PROXIES  # type: ignore
        return list(ADMIN_PROXIES or [])
    except Exception:
        return []


def all_proxies() -> List[Dict[str, str]]:
    """Lista completa: bot + extras locales, excluyendo hosts quemados
    (`_EXCLUDED_PROXY_HOSTS`). El filtro se aplica acÃ¡ para que TODO el
    pool (failover, random pick, shuffled) herede la exclusiÃ³n.

    Dedup por (server, username) â€” el bot (monorepo, `betmexico_config.
    ADMIN_PROXIES`) y este archivo pueden listar el MISMO puerto DataImpulse
    dos veces (detectado 2026-07-11: 200 entradas reportadas, 100 servers
    Ãºnicos). Sin dedup, `random.choice`/`shuffled_proxy_urls` pesan doble
    a los puertos duplicados â€” sesga la rotaciÃ³n en vez de repartir parejo
    entre las sesiones sticky reales."""
    combined = _bot_proxies() + EXTRA_ADMIN_PROXIES + PROXY001_PROXIES + DATAIMPULSE_PROXIES
    seen: set = set()
    deduped: List[Dict[str, str]] = []
    for p in combined:
        key = (p.get("server", ""), p.get("username", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(p)
    return [
        p for p in deduped
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
    """Random pick â†’ URL `http://user:pass@server`. Compat / single-shot.
    Para login real preferir `call_with_proxy_failover`."""
    return _to_url(get_admin_proxy())


def shuffled_proxy_urls() -> List[str]:
    """Lista de proxy URLs del pool en orden aleatorio (para failover).
    Lista vacÃ­a si el pool estÃ¡ vacÃ­o."""
    pool = all_proxies()
    if not pool:
        return []
    shuffled = list(pool)
    random.shuffle(shuffled)
    return [u for u in (_to_url(p) for p in shuffled) if u]


# â”€â”€ Failover â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_PROXY_RETRY_EXCEPTIONS: tuple = ()


def _retry_exceptions() -> tuple:
    """Lazy: ensambla las excepciones por las que vale la pena rotar de proxy.
    Incluye fallos de conexiÃ³n, timeouts y errores de proxy. NO incluye errores
    HTTP del lado de BetMexico (401, 403, 500) â€” esos significan que el proxy
    funcionÃ³, el problema es la cuenta."""
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

    - Si `proxy` estÃ¡ dado explÃ­cito â†’ lo usa SIN failover (caller manda).
    - Si `proxy` es None â†’ cicla el pool reconectando (cada intento = IP nueva,
      los proxies son rotativos), reintentando cuando:
        a) la llamada lanza excepciÃ³n de conexiÃ³n/timeout, O
        b) devuelve un resultado de fallo de proxy, O
        c) devuelve un resultado de fallo de captcha (406 FAILURE_IN_CAPTCHA â†’
           status RETRY_CAPTCHA). Esto es la clave: el 406 NO es error de la
           cuenta sino de la REPUTACIÃ“N de la IP del proxy (loterÃ­a ~70% con
           IPRoyal). Rotar IP y reintentar convierte ~70%/intento en ~99.x%.
      Total de intentos = max(len(pool), captcha_retries).
    - Si el pool estÃ¡ vacÃ­o â†’ llama una vez con proxy=None.

    Nota: pasar `max_retries=1` a get_jwt como kwarg para que NO queme 3 captchas
    en la MISMA IP (inÃºtil si estÃ¡ quemada) â€” el retry de IP lo maneja acÃ¡.

    Returns:
        (resultado, proxy_url_usado). El caller puede reusar `proxy_url_usado`
        en steps siguientes (ej. ApiChecker despuÃ©s de get_jwt) para mantener
        afinidad de proxy validado.

    Raises:
        La Ãºltima excepciÃ³n si TODOS los intentos fallaron por conexiÃ³n.
        Cualquier excepciÃ³n no-proxy (ej. 401 de BetMexico) se re-lanza
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
    # Cicla el pool hasta cubrir captcha_retries â€” cada vuelta reconecta al
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
                    f"â€” try {i+1}/{n_attempts}"
                )
                last_result = result
                continue
            # 406 FAILURE_IN_CAPTCHA â†’ IP quemada. Rotar IP y reintentar.
            if _looks_like_captcha_failure_result(result):
                logger.warning(
                    f"[proxy_pool] {_proxy_host(url)} captcha 406 (IP quemada) "
                    f"â€” rotando IP, try {i+1}/{n_attempts}"
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
                f"({type(e).__name__}: {str(e)[:120]}) â€” try {i+1}/{n_attempts}"
            )
            last_err = e
            continue
    # Agotados los intentos: si hubo result-style failure (proxy o captcha),
    # devolvemos el Ãºltimo resultado (el caller verÃ¡ RETRY_CAPTCHA â†’ LOGIN_FAILED);
    # si solo hubo excepciones de conexiÃ³n, raise.
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
    excepciÃ³n (porque la funciÃ³n interna los atrapÃ³). HeurÃ­stica:
    - Es un tuple (a, b) con `a is None` y `b` es dict con status ERROR
      y `error` contiene tokens tÃ­picos de proxy/timeout.
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
    status RETRY_CAPTCHA (BetMexico devolviÃ³ 406 FAILURE_IN_CAPTCHA) o
    CAPTCHA_TIMEOUT (pool sin tokens). En ambos casos vale rotar IP y reintentar:
    el 406 depende de la reputaciÃ³n de la IP del proxy, no de la cuenta."""
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

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
    # NodeMaven (Premium MX) — agregado 2026-05-21.
    # ⚠️ DEGRADADO: 504 Gateway Timeout intermitente (~22% medido 2026-06-24) +
    # 406 crónico (IP quemada). Se mantiene SOLO como fallback de OTRO proveedor
    # (diversidad ante caída de Data Impulse); su peso real es ~2/52. Ver Data
    # Impulse abajo, que pasa a ser el proxy primario.
    {
        "server": "gate.nodemaven.com:8080",
        "username": "andregutti97_gmail_com-country-mx",
        "password": "5qpn3scda5",
    },
]

# Data Impulse (Premium MX residencial) — PRIMARIO. Host/user/pass FIJOS; el PUERTO
# define el modo:
#   - 10000..10049 (lote viejo, credenciales `edb0501e...`) = 50 sesiones STICKY.
#     Se QUEMARON con el uso (logins + un health check que las machacaba 150k
#     veces/sem contra ipinfo) → 406/429 masivo desde ~26-jun.
#   - 823 (mismo lote viejo) = ROTATORIO nacional MX, adoptado 2026-06-28 como fix.
#     Sano en uptime (12/12→200, 0% 504) pero un benchmark independiente (Proxyway
#     2026, ver research proveedores 2026-07-01) midió el PEOR fraud/risk score del
#     mercado (3.9) para el pool base de DataImpulse sin el toggle "IP quality" —
#     coincide con la degradación medida en prod la semana del 2026-06-24 (tasa de
#     login exitoso cayendo de ~50%/intento a ~30%/intento).
#   - 10000..10699 (LOTE NUEVO 2026-07-01/07-11, credenciales `506e02a6...`, dado
#     por Robert) = 700 sesiones STICKY, cada una rota de IP sola cada 3 MIN (TTL
#     del plan, no algo que controlemos por código). Reemplaza el pool 823 como
#     PRIMARIO. Objetivo: recuperar el p≈50%/intento que sí se midió viable en
#     mayo con sticky fresca (vs. rotativo genérico degradado).
#     ⚠️ Diagnóstico 2026-07-11 (forense "masacre de IPs", Robert): con solo 100
#     puertos (10000-10099) y ~900 cuentas activas, cada IP terminaba autenticando
#     decenas de emails distintos — patrón que el antifraude de BetMexico marca
#     independientemente de concurrencia/cooldown (conecta con el bucle de quema
#     del jwt_keeper, ver docs/ERRORS.md). Ampliar a 700 puertos baja mucho la
#     razón cuentas-por-IP; el TTL de 3min además da rotación natural: dos cuentas
#     que caen en el mismo puerto separadas por >3min (típico — el keeper espacía
#     20-45s entre 8 cuentas, ciclo completo 3-6min) casi siempre pegan IP física
#     distinta. Si el 406/429 vuelve a subir pese a esto, ya no es el pool — ver
#     docs/plans/login-orchestration-rework.md §6 (StickySessionManager).
# El sufijo `__cr.mx` en el username fuerza país México.
# Data Impulse — EXCLUIDO por fallo masivo de gateway (`502 NO_HOST_CONNECTION`).
# Excluido agregando "dataimpulse" a _EXCLUDED_PROXY_HOSTS.

# Proxy001 (500 proxies residenciales MX) — reemplazo de DataImpulse
# Se busca en la misma carpeta del script (para producción Docker) o en la carpeta de descargas local.
from pathlib import Path

_BASE_DIR = Path(__file__).parent
_PROXY001_LOCAL = _BASE_DIR / "Proxy001_anamufa96_500.txt"
_PROXY001_DOWNLOADS = Path(r"C:\Users\rober\Downloads\Proxy001_anamufa96_500.txt")

def _load_proxy001() -> List[Dict[str, str]]:
    target_path = None
    if _PROXY001_LOCAL.exists():
        target_path = _PROXY001_LOCAL
    elif _PROXY001_DOWNLOADS.exists():
        target_path = _PROXY001_DOWNLOADS

    if not target_path:
        logger.warning("Proxy001: No se encontró el archivo de proxies en ninguna ruta.")
        return []

    proxies = []
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(":")
                if len(parts) == 4:
                    proxies.append({
                        "server": f"{parts[0]}:{parts[1]}",
                        "username": parts[2],
                        "password": parts[3],
                    })
    except Exception as e:
        logger.warning(f"Error cargando Proxy001 desde {target_path}: {e}")
    return proxies


PROXY001_PROXIES: List[Dict[str, str]] = _load_proxy001()

_DATAIMPULSE_HOST = "gw.dataimpulse.com"
_DATAIMPULSE_USER = "506e02a6444effce62de__cr.mx"
_DATAIMPULSE_PASS = "59bd44415b7b9c7c"
_DATAIMPULSE_STICKY_PORT_START = 10000
_DATAIMPULSE_STICKY_PORT_END = 10999

DATAIMPULSE_PROXIES: List[Dict[str, str]] = [
    {
        "server": f"{_DATAIMPULSE_HOST}:{port}",
        "username": _DATAIMPULSE_USER,
        "password": _DATAIMPULSE_PASS,
    }
    for port in range(_DATAIMPULSE_STICKY_PORT_START, _DATAIMPULSE_STICKY_PORT_END + 1)
]

# Hosts excluidos del pool — proxies con reputación quemada o caídos.
# - litport: US IP / quemado.
# - iproyal: 402 Payment Required.
# - dataimpulse: 502 NO_HOST_CONNECTION (gateway caído). Excluido 2026-08-12.
_EXCLUDED_PROXY_HOSTS: tuple = ("litport", "iproyal", "dataimpulse")


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
    pool (failover, random pick, shuffled) herede la exclusión.

    Dedup por (server, username) — el bot (monorepo, `betmexico_config.
    ADMIN_PROXIES`) y este archivo pueden listar el MISMO puerto DataImpulse
    dos veces (detectado 2026-07-11: 200 entradas reportadas, 100 servers
    únicos). Sin dedup, `random.choice`/`shuffled_proxy_urls` pesan doble
    a los puertos duplicados — sesga la rotación en vez de repartir parejo
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

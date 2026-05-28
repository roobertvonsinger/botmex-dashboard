"""login_orchestrator.py — semilla ÚNICA de login del dashboard.

`gentle_login()` orquesta el login (resolver captcha v2 proxyless vía el
`CaptchaTokenPool` + POST `/api/Session/login`) con estrategia ANTI-RÁFAGA
portada del bot (`betmexico_check.py`): jitter escalado por racha de fallos,
backoff extra en BAN, reintentos espaciados rotando IP. Reemplaza el uso directo
de `call_with_proxy_failover(get_jwt, ...)` — cuyo loop interno es ráfaga sin
throttle (`n_attempts = max(len(urls), captcha_retries)`), que es lo que quema
las IPs y dispara el antifraude de BetMexico.

REGLA DE ROBERT (2026-05-28, NO NEGOCIABLE):
  Una cuenta SOLO muere por 3 razones:
    1. Login denegado DEFINITIVAMENTE (401 credenciales/lock) → code="LOGIN_DENIED"
    2. KYC_PENDING
    3. AUTOEXCLUSION
  TODO lo demás —406/captcha, proxy, BAN(403/429), timeout, 5xx— se convierte en
  REINTENTOS. Si se agotan → code="LOGIN_RETRY_LATER", JAMÁS account_dead.

El bot devuelve la taxonomía correcta en `login_result["status"]`
(`betmexico_login_api.test_login`): LIVE / RETRY_CAPTCHA / CAPTCHA_TIMEOUT /
BAN / ERROR / DEAD. `gentle_login` la lee directo (no la aplana a LOGIN_FAILED).
"""
from __future__ import annotations

import asyncio
import itertools
import logging
import random
import time
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger("betmexico.dashboard.login_orch")

# NodeMaven sticky dura ~2 min; margen para no usarla a punto de expirar.
_STICKY_TTL_SEC = 110


# ── Sticky sessions (NodeMaven) ──────────────────────────────────────────────
@dataclass
class StickySession:
    """Una IP sticky para un intento de login. `proxy_url` se reusa luego para
    el POST del depósito (afinidad de IP login↔depósito)."""
    proxy_url: Optional[str]
    label: str = ""
    expires_at: float = 0.0  # 0 = sin expiración (proxy del pool admin rotativo)

    def alive(self) -> bool:
        return self.expires_at == 0.0 or time.time() < self.expires_at


def parse_nodemaven_line(line: str) -> Optional[StickySession]:
    """Parsea una línea de lote NodeMaven `host:port:user:pass` →
    `http://user:pass@host:port`. El user trae el `sid-<HEX>` sticky.
    Formato típico:
      gate.nodemaven.com:8080:botmexico-country-mx-sid-AB12-ttl-1m57s-...:dashboard
    """
    line = (line or "").strip()
    if not line or line.startswith("#"):
        return None
    parts = line.split(":")
    if len(parts) < 4:
        return None
    host, port, user = parts[0], parts[1], parts[2]
    pw = ":".join(parts[3:])  # password puede traer ':' (raro, pero defensivo)
    proxy_url = f"http://{user}:{pw}@{host}:{port}"
    return StickySession(
        proxy_url=proxy_url, label=user, expires_at=time.time() + _STICKY_TTL_SEC
    )


class StickySessionManager:
    """Gestiona un lote de IPs sticky NodeMaven (TTL ~2 min). Entrega sesiones
    vivas; descarta expiradas. Cuando se agotan, `get_fresh()` devuelve None y el
    caller cae a las IPs del pool admin. Robert entrega los lotes manualmente."""

    def __init__(self) -> None:
        self._sessions: List[StickySession] = []
        self._rr = itertools.cycle([])  # round-robin reiniciable

    def load_lines(self, lines: List[str]) -> int:
        sessions = [s for s in (parse_nodemaven_line(l) for l in lines) if s]
        self._sessions = sessions
        self._rr = itertools.cycle(range(len(sessions))) if sessions else itertools.cycle([])
        logger.info(f"[StickyMgr] lote cargado: {len(sessions)} sesiones")
        return len(sessions)

    def load_file(self, path: str) -> int:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return self.load_lines(f.readlines())
        except FileNotFoundError:
            logger.info(f"[StickyMgr] sin lote ({path} no existe) — se usará el pool admin")
            return 0

    def available(self) -> int:
        return sum(1 for s in self._sessions if s.alive())

    def get_fresh(self) -> Optional[StickySession]:
        """Una sesión sticky viva (round-robin). None si no hay vivas."""
        alive = [i for i, s in enumerate(self._sessions) if s.alive()]
        if not alive:
            return None
        # avanzar el round-robin hasta caer en una viva
        for _ in range(len(self._sessions)):
            try:
                idx = next(self._rr)
            except StopIteration:
                self._rr = itertools.cycle(range(len(self._sessions)))
                idx = next(self._rr)
            if idx < len(self._sessions) and self._sessions[idx].alive():
                return self._sessions[idx]
        return self._sessions[alive[0]]


# ── Resultado ────────────────────────────────────────────────────────────────
@dataclass
class LoginResult:
    ok: bool
    jwt: Optional[str] = None
    # LIVE | LOGIN_RETRY_LATER | LOGIN_DENIED | KYC_PENDING | AUTOEXCLUSION | DEPS_MISSING
    code: str = ""
    account_dead: bool = False
    sticky_session: Optional[StickySession] = None
    error: Optional[str] = None
    attempts: int = 0

    @property
    def used_proxy(self) -> Optional[str]:
        return self.sticky_session.proxy_url if self.sticky_session else None


# ── Helpers internos ─────────────────────────────────────────────────────────
def _import_get_jwt():
    """Runtime import del primitivo de login del bot (igual que deposits.py)."""
    from betmexico_login_service import get_jwt  # type: ignore
    return get_jwt


def _classify_dead(login_result: dict) -> str:
    """Sub-clasifica un status='DEAD' del bot en una de las 3 razones de muerte
    leyendo `api.message`. 401 sin mensaje claro → LOGIN_DENIED (credenciales)."""
    msg = ""
    try:
        msg = str((login_result.get("api") or {}).get("message", "")).upper()
    except Exception:
        pass
    if "AUTOEXCLU" in msg:
        return "AUTOEXCLUSION"
    if "KYC" in msg or "PENDING" in msg or "VALIDATION" in msg:
        return "KYC_PENDING"
    return "LOGIN_DENIED"


def _pool_session() -> Optional[StickySession]:
    """Una IP del pool admin del dashboard (IPRoyal/NodeMaven/bot), envuelta como
    sesión efímera. None si el pool está vacío (→ submit proxyless)."""
    try:
        from proxy_pool import shuffled_proxy_urls
        urls = shuffled_proxy_urls()
    except Exception:
        urls = []
    if not urls:
        return None
    url = random.choice(urls)
    return StickySession(proxy_url=url, label="pool", expires_at=0.0)


def _jitter_base(has_proxy: bool, streak: int) -> float:
    """Base del jitter portada de betmexico_check.py L127-133. Escala con la
    racha de fallos consecutivos para frenar cuando las IPs están quemándose."""
    if streak >= 5:
        return 3.0
    if streak >= 3:
        return 1.5
    return 0.3 if has_proxy else 0.5


# ── Semilla ──────────────────────────────────────────────────────────────────
async def gentle_login(
    email: str,
    password: str,
    *,
    max_login_retries: int = 4,
    throttle: bool = True,
    sticky_session: Optional[StickySession] = None,
    pool=None,
    sticky_mgr: Optional[StickySessionManager] = None,
    use_cache: bool = False,
    attempt_timeout: float = 35.0,
) -> LoginResult:
    """Login gentil con reintentos espaciados rotando IP. Una sesión sticky por
    intento; fresca al reintentar.

    Args:
        max_login_retries: intentos totales con captcha. p≈0.5/intento fresco →
            3≈87%, 4≈94%. Default 4.
        throttle: aplica jitter anti-ráfaga entre intentos (clave anti-quemado).
        sticky_session: si se pasa, se usa en el intento 0 (afinidad con un login
            previo). Reintentos piden sesión fresca.
        pool: CaptchaTokenPool ya iniciado (lo crea el caller con make_pool).
        sticky_mgr: lote NodeMaven opcional; si None o agotado → pool admin.
        use_cache: True permite JWT cache-hit (sin captcha) en el intento 0 —
            útil para updates baratos.
        attempt_timeout: timeout POR INTENTO (no global). Reemplaza el wait_for
            de 25s que envolvía todo el failover y lo mataba a media-rotación.

    Returns:
        LoginResult. ok=True → jwt + sticky_session (reusar proxy para depósito).
        account_dead=True SOLO en LOGIN_DENIED/KYC_PENDING/AUTOEXCLUSION.
    """
    try:
        get_jwt = _import_get_jwt()
    except Exception as e:
        logger.error(f"[gentle_login] no pude importar get_jwt: {e}")
        return LoginResult(ok=False, code="DEPS_MISSING", error=str(e))

    streak = 0
    attempts_done = 0
    last_status: Optional[str] = None
    pool_dry_waits = 0  # cota de esperas por pool seco (no son intentos)

    while attempts_done < max_login_retries:
        # 1. Elegir IP para este intento
        if sticky_session is not None and attempts_done == 0:
            cur = sticky_session
        else:
            cur = sticky_mgr.get_fresh() if sticky_mgr is not None else None
            if cur is None:
                cur = _pool_session()
        proxy_url = cur.proxy_url if cur else None

        # 2. Jitter ANTES del intento (anti-ráfaga)
        base = _jitter_base(bool(proxy_url), streak)
        if throttle:
            await asyncio.sleep(random.uniform(0.1, base))

        # 3. Login: 1 captcha en 1 IP (max_retries=1). Timeout POR INTENTO.
        try:
            jwt, login_result = await asyncio.wait_for(
                get_jwt(email, password, pool, proxy=proxy_url,
                        use_cache=(use_cache and attempts_done == 0), max_retries=1),
                timeout=attempt_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(f"[gentle_login] {email} timeout intento {attempts_done+1}")
            streak += 1
            attempts_done += 1
            last_status = "TIMEOUT"
            continue
        except Exception as e:
            # proxy/conexión → rotar IP, NO mata
            logger.warning(f"[gentle_login] {email} excepción intento {attempts_done+1}: {str(e)[:120]}")
            streak += 1
            attempts_done += 1
            last_status = "ERROR"
            continue

        status = login_result.get("status") if isinstance(login_result, dict) else None

        # 4. Clasificar (REGLA DE ROBERT)
        if jwt and status in (None, "LIVE"):
            logger.info(f"[gentle_login] {email} LIVE en intento {attempts_done+1} "
                        f"({'cache' if isinstance(login_result, dict) and login_result.get('from_cache') else 'fresh'})")
            return LoginResult(ok=True, jwt=jwt, code="LIVE",
                               sticky_session=cur, attempts=attempts_done + 1)

        if status == "DEAD":
            code = _classify_dead(login_result if isinstance(login_result, dict) else {})
            logger.info(f"[gentle_login] {email} MUERTA: {code}")
            return LoginResult(ok=False, code=code, account_dead=True,
                               error=str(login_result)[:200], attempts=attempts_done + 1)

        if status == "CAPTCHA_TIMEOUT":
            # Pool de captcha seco → esperar y NO gastar intento (cota 5).
            if pool_dry_waits < 5:
                pool_dry_waits += 1
                logger.info(f"[gentle_login] {email} pool seco — espera {pool_dry_waits}/5")
                await asyncio.sleep(2.0)
                continue
            # demasiadas esperas → cuenta como intento para no colgar
            attempts_done += 1
            last_status = status
            continue

        if status == "BAN":
            # 403/429 rate-limit → backoff extra (portado: sleep(jitter*2)). NO mata.
            if throttle:
                await asyncio.sleep(random.uniform(0.1, base) * 2)

        # RETRY_CAPTCHA / BAN / ERROR / desconocido → reintentar rotando IP
        streak += 1
        attempts_done += 1
        last_status = status

    # Agotados los reintentos → NUNCA DEAD.
    logger.info(f"[gentle_login] {email} agotó {attempts_done} intentos (last={last_status}) → LOGIN_RETRY_LATER")
    return LoginResult(ok=False, code="LOGIN_RETRY_LATER",
                       error=f"agotado tras {attempts_done} intentos (último={last_status})",
                       attempts=attempts_done)

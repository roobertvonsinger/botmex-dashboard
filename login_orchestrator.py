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
from typing import Any, Dict, List, Optional

logger = logging.getLogger("betmexico.dashboard.login_orch")

# NodeMaven sticky dura ~2 min; margen para no usarla a punto de expirar.
_STICKY_TTL_SEC = 110

# ── Reuso de token v2 (insight Robert 2026-06-01) ────────────────────────────
# Un 406 FAILURE_IN_CAPTCHA NO consume el token: BetMexico rechaza el request
# (por reputación de IP o por esperar otra versión) ANTES de mandarlo a verificar
# con Google, así que el token v2 sigue vivo su TTL (~120s). En vez de quemar un
# token de CapMonster por cada reintento, REUSAMOS el mismo rotando IP/jitter.
_TOKEN_REUSE_MAX_AGE = 100.0  # seg: < 120s de vida real del v2 (margen seguro)
# Tras N reusos forzamos un token fresco. Defensa por si en prod resultara que el
# 406 SÍ consume el token (el test del 2026-06-01 no llegó a observar un 406):
# así el login se auto-cura en vez de martillar con un token muerto.
_TOKEN_MAX_REUSES = 8

# TTL real de CapMonster = 55s (NodeMaven). Margen seguro: 50s para evitar warnings.
_TOKEN_REUSE_MAX_AGE = 50.0

# ── Semáforo GLOBAL de logins reales contra BetMexico ────────────────────────
# CAUSA RAÍZ #1 del rate-limit (forense 2026-07-11 sobre 18k eventos): la TASA
# agregada de logins concurrentes dispara el antifraude — medido ≥100 logins/min
# = 100% denial, 45-74/min ≈65%, <30/min ≈28-48% (piso por reputación de IP).
# El problema NO es la IP (proxies rotan bien) ni por-cuenta (no hay umbral): es
# cuántos POSTs de /api/Session/login llegan JUNTOS, sin importar qué endpoint,
# operador o loop los dispare. Este semáforo es el ÚNICO cuello por el que pasan
# TODOS los logins reales. El cache-hit (reuso de JWT) NO lo toca — no golpea
# BetMexico. N=2 mantiene la tasa en el borde bajo de la zona segura. Env override.
import os as _os
GLOBAL_LOGIN_CONCURRENCY = max(1, int(_os.environ.get("LOGIN_MAX_CONCURRENCY", "2")))
_LOGIN_SEM = asyncio.Semaphore(GLOBAL_LOGIN_CONCURRENCY)


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
    # LIVE | LOGIN_RETRY_LATER | LOGIN_DENIED | KYC_PENDING | AUTOEXCLUSION |
    # DEPS_MISSING | RATE_LIMITED
    code: str = ""
    account_dead: bool = False
    sticky_session: Optional[StickySession] = None
    error: Optional[str] = None
    attempts: int = 0
    # True si el JWT salió del cache de BD (fast-path, sin captcha ni /login).
    # El caller lo usa para decidir re-login si el JWT cacheado da 401 en el
    # depósito (JWT muerto server-side) — ver spec anti-rate-limit Capa 1.
    from_cache: bool = False
    details: Optional[Dict[str, Any]] = None
    raw_result: Optional[Dict[str, Any]] = None

    @property
    def used_proxy(self) -> Optional[str]:
        return self.sticky_session.proxy_url if self.sticky_session else None


# ── Helpers internos ─────────────────────────────────────────────────────────
def _import_get_jwt():
    """Runtime import del primitivo de login del bot (igual que deposits.py)."""
    from betmexico_login_service import get_jwt  # type: ignore
    return get_jwt


def _import_login_primitives():
    """Runtime import de los primitivos para el loop con reuso de token: el checker
    HTTP del bot, el persistidor de JWT cache y el handle de BD. Permite llamar
    `test_login` directo (reusando el mismo token) en vez de pasar por `get_jwt`,
    que pide un token nuevo del pool en cada llamada."""
    from betmexico_login_api import BetmexicoApiChecker  # type: ignore
    from betmexico_login_service import _persist_jwt_cache  # type: ignore
    from betmexico_db import db  # type: ignore
    return BetmexicoApiChecker, _persist_jwt_cache, db


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
    allow_proxyless: bool = False,
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
        BetmexicoApiChecker, _persist_jwt_cache, _db = _import_login_primitives()
    except Exception as e:
        logger.error(f"[gentle_login] no pude importar primitivos de login: {e}")
        return LoginResult(ok=False, code="DEPS_MISSING", error=str(e))

    # ── JWT cache fast-path (intento 0): sin captcha ni POST si hay JWT vigente ──
    if use_cache:
        try:
            cached = _db.get_jwt_cache(email)
            if cached and cached.get("expires_at", 0) > (time.time() + 60):
                logger.info(f"[gentle_login] {email} JWT cache HIT (sin captcha)")
                return LoginResult(ok=True, jwt=cached["token"], code="LIVE",
                                   sticky_session=sticky_session, attempts=0,
                                   from_cache=True)
        except Exception as e:
            logger.debug(f"[gentle_login] {email} cache lookup err: {e}")

    streak = 0
    attempts_done = 0
    last_status: Optional[str] = None
    pool_dry_waits = 0  # cota de esperas por pool seco (no son intentos)
    proxyless_waits = 0  # cota de esperas por falta de proxy (REGLA: nunca proxyless en prod)

    # Estado del token REUSABLE. Se pide uno nuevo solo si no hay / expiró / se
    # reusó demasiado. Un 406 NO consume el token → lo reusamos rotando IP.
    cur_token: Optional[str] = None
    cur_task_id = None
    token_born = 0.0
    token_reuses = 0

    while attempts_done < max_login_retries:
        # 1. Garantizar token: pedir del pool solo si hace falta.
        token_age = (time.time() - token_born) if cur_token else 1e9
        if cur_token is None or token_age >= _TOKEN_REUSE_MAX_AGE or token_reuses >= _TOKEN_MAX_REUSES:
            if pool is None:
                logger.error(f"[gentle_login] {email} sin pool de captcha")
                return LoginResult(ok=False, code="DEPS_MISSING", error="no captcha pool")

            # Inicializar la factory del pool bajo demanda (lazy) si no se ha iniciado aún.
            if hasattr(pool, "start_factory") and getattr(pool, "_factory_task", None) is None and not getattr(pool, "stopped", False):
                logger.info(f"[gentle_login] {email} iniciando pool de captcha bajo demanda")
                await pool.start_factory()

            # Fix: Drenar tokens expirados del pool ANTES de pedir uno nuevo (evitar warnings)
            if hasattr(pool, "drain_stale_tokens"):
                await pool.drain_stale_tokens(max_age=_TOKEN_REUSE_MAX_AGE)
            elif hasattr(pool, "pool"):
                # Implementación manual si el pool no tiene el método
                fresh = []
                drained = 0
                while True:
                    try:
                        item = pool.pool.get_nowait()
                        tok, tid, ts = item
                        if (time.time() - ts) <= _TOKEN_REUSE_MAX_AGE:
                            fresh.append(item)
                        else:
                            drained += 1
                    except Exception:
                        break
                for item in fresh:
                    pool.pool.put_nowait(item)
                if drained > 0:
                    logger.info(f"[gentle_login] {email} drenados {drained} tokens expirados (edad >{_TOKEN_REUSE_MAX_AGE}s)")

            res = await pool.get_token(timeout=90)
            if not res:
                # Pool de captcha seco → esperar y NO gastar intento (cota 5).
                if pool_dry_waits < 5:
                    pool_dry_waits += 1
                    logger.info(f"[gentle_login] {email} pool seco — espera {pool_dry_waits}/5")
                    await asyncio.sleep(2.0)
                    continue
                attempts_done += 1
                last_status = "CAPTCHA_TIMEOUT"
                continue
            cur_token, cur_task_id = res
            token_born = time.time()
            token_reuses = 0
            logger.info(f"[gentle_login] {email} token {'inicial' if attempts_done == 0 else 'refrescado'} "
                        f"(task {cur_task_id})")

        # 2. Elegir IP para este intento
        if sticky_session is not None and attempts_done == 0:
            cur = sticky_session
        else:
            cur = sticky_mgr.get_fresh() if sticky_mgr is not None else None
            if cur is None:
                cur = _pool_session()
        proxy_url = cur.proxy_url if cur else None

        # 2.5 REGLA DURA (Robert): NUNCA loguear proxyless en prod — filtraría la
        # IP real del server. Si el pool no dio proxy → esperar/reintentar; tras la
        # cota → LOGIN_RETRY_LATER. (El captcha SÍ se resuelve proxyless; esto es
        # solo el SUBMIT del login.) Pasar allow_proxyless=True solo en tests.
        if not proxy_url and not allow_proxyless:
            if proxyless_waits < 5:
                proxyless_waits += 1
                logger.error(f"[gentle_login] {email} SIN PROXY disponible — espera "
                             f"{proxyless_waits}/5 (NO se loguea proxyless)")
                await asyncio.sleep(2.0)
                continue
            logger.error(f"[gentle_login] {email} sin proxy tras esperas → LOGIN_RETRY_LATER (bloqueado proxyless)")
            return LoginResult(ok=False, code="LOGIN_RETRY_LATER",
                               error="no proxy disponible (proxyless bloqueado por regla)",
                               attempts=attempts_done)

        # 3. Jitter ANTES del intento (anti-ráfaga)
        base = _jitter_base(bool(proxy_url), streak)
        if throttle:
            await asyncio.sleep(random.uniform(0.1, base))

        # 4. Login REUSANDO el token actual. Timeout POR INTENTO.
        # Semáforo GLOBAL: nunca más de N POSTs de login concurrentes contra
        # BetMexico, sin importar cuántos operadores/loops/endpoints disparen
        # (causa raíz #1 del rate-limit, forense 2026-07-11). Se toma SOLO para
        # el POST real; el jitter/espera de pool quedan fuera para no acaparar.
        try:
            async with _LOGIN_SEM:
                async with BetmexicoApiChecker(proxy=proxy_url) as checker:
                    login_result = await asyncio.wait_for(
                        checker.test_login(email, password,
                                           captcha_token=cur_token, captcha_task_id=cur_task_id,
                                           fetch_mode="minimal"),
                        timeout=attempt_timeout,
                    )
        except asyncio.TimeoutError:
            logger.warning(f"[gentle_login] {email} timeout intento {attempts_done+1}")
            streak += 1; attempts_done += 1; token_reuses += 1; last_status = "TIMEOUT"
            continue
        except Exception as e:
            # proxy/conexión → rotar IP, NO mata
            logger.warning(f"[gentle_login] {email} excepción intento {attempts_done+1}: {str(e)[:120]}")
            streak += 1; attempts_done += 1; token_reuses += 1; last_status = "ERROR"
            continue

        status = login_result.get("status") if isinstance(login_result, dict) else None

        # 5. Clasificar (REGLA DE ROBERT)
        if status == "LIVE":
            jwt = (login_result.get("api") or {}).get("token")
            if jwt:
                try:
                    _persist_jwt_cache(email, jwt)
                except Exception:
                    pass
                acct_details = login_result.get("account_details") if isinstance(login_result, dict) else None
                logger.info(f"[gentle_login] {email} LIVE en intento {attempts_done+1} "
                            f"(token reusado {token_reuses}x, edad {time.time()-token_born:.0f}s)")
                return LoginResult(
                    ok=True,
                    jwt=jwt,
                    code="LIVE",
                    sticky_session=cur,
                    attempts=attempts_done + 1,
                    details=acct_details,
                    raw_result=login_result if isinstance(login_result, dict) else None,
                )
            logger.warning(f"[gentle_login] {email} LIVE sin JWT — reintento")
            streak += 1; attempts_done += 1; token_reuses += 1; last_status = "LIVE_NO_JWT"
            continue

        if status == "DEAD":
            code = _classify_dead(login_result if isinstance(login_result, dict) else {})
            logger.info(f"[gentle_login] {email} MUERTA: {code}")
            return LoginResult(ok=False, code=code, account_dead=True,
                               error=str(login_result)[:200], attempts=attempts_done + 1)

        if status == "BAN":
            # 403/429 = rate-limit POR CUENTA (medido 2026-06-28: 16-20 logins/día
            # → 429). 90% de estas cuentas NO vuelven (Robert 2026-08-12).
            # Decisión: marcar como DEAD PERMANENTE para que desaparezcan de vistas
            # y procesos automáticos.
            # Evitar circular import: usar db directamente
            from app import db
            with db(write=True) as c:
                c.execute(
                    "UPDATE accounts SET status='DEAD', dead_reason=?, dead_at=datetime('now') WHERE email=?",
                    ("RATE_LIMITED_PERMANENT (429 — BetMexico bloqueó la cuenta)", email)
                )
            logger.warning(f"[gentle_login] {email} RATE_LIMITED (BAN) en intento "
                           f"{attempts_done + 1} → DEAD PERMANENTE")
            return LoginResult(ok=False, code="DEAD",
                               error="RATE_LIMITED_PERMANENT (429 — BetMexico bloqueó la cuenta)",
                               account_dead=True,
                               attempts=attempts_done + 1)

        # RETRY_CAPTCHA(406) / ERROR / desconocido → reintentar.
        # 406: el token SOBREVIVE → lo REUSAMOS (solo rotamos IP). token_reuses++
        # fuerza un token fresco tras _TOKEN_MAX_REUSES (auto-cura defensiva).
        streak += 1
        attempts_done += 1
        token_reuses += 1
        last_status = status

    # Agotados los reintentos → NUNCA DEAD.
    logger.info(f"[gentle_login] {email} agotó {attempts_done} intentos (last={last_status}) → LOGIN_RETRY_LATER")
    return LoginResult(ok=False, code="LOGIN_RETRY_LATER",
                       error=f"agotado tras {attempts_done} intentos (último={last_status})",
                       attempts=attempts_done)

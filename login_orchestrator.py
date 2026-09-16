"""login_orchestrator.py — Login directo, determinista y sin paranoias.
Eliminadas colas artificiales, esperas por pool seco y reusos fantasma.
Ejecuta directamente contra BetMexico usando CaptchaHub (:8889) y proxies de pool.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger("betmexico.dashboard.login_orch")

# ── Health-gate de CapMonster ────────────────────────────────────────────────
# Si CapMonster está caído/baneado, cada login real (sin JWT cache) se queda
# ~35s x N reintentos esperando un token que nunca llega — con cientos de
# cuentas eso satura proxies/CPU/logs sin ningún avance (Robert 2026-09-16,
# ver docs/ERRORS.md). Cache corta evita golpear getBalance en cada login.
_CAPMONSTER_HEALTH_TTL_SEC = 60.0
_capmonster_health_cache: Dict[str, Any] = {"ts": 0.0, "ok": True}


async def _capmonster_available() -> bool:
    now = time.time()
    if now - _capmonster_health_cache["ts"] < _CAPMONSTER_HEALTH_TTL_SEC:
        return _capmonster_health_cache["ok"]
    import os
    import httpx
    key = os.environ.get("BMX_CAPMONSTER_KEY") or os.environ.get("CAPMONSTER_KEY", "")
    ok = False
    if key:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.post(
                    "https://api.capmonster.cloud/getBalance",
                    json={"clientKey": key},
                )
                ok = r.json().get("errorId") == 0
        except Exception as e:
            logger.debug(f"[capmonster_health] no disponible: {e}")
    was_ok = _capmonster_health_cache["ok"]
    _capmonster_health_cache["ts"] = now
    _capmonster_health_cache["ok"] = ok
    if not ok and was_ok:
        logger.warning("[CAPTCHA_DOWN] CapMonster no responde — logins nuevos (sin JWT cache) se pausan")
    elif ok and not was_ok:
        logger.info("[CAPTCHA_DOWN] CapMonster respondió de nuevo — logins nuevos reanudados")
    return ok


@dataclass
class StickySession:
    """Proxy asignado para la sesión de login / depósito."""
    proxy_url: Optional[str]
    label: str = ""
    expires_at: float = 0.0

    def alive(self) -> bool:
        return self.expires_at == 0.0 or time.time() < self.expires_at


@dataclass
class LoginResult:
    ok: bool
    jwt: Optional[str] = None
    code: str = ""
    account_dead: bool = False
    sticky_session: Optional[StickySession] = None
    error: Optional[str] = None
    attempts: int = 1
    from_cache: bool = False
    details: Optional[Dict[str, Any]] = None
    raw_result: Optional[Dict[str, Any]] = None

    @property
    def used_proxy(self) -> Optional[str]:
        return self.sticky_session.proxy_url if self.sticky_session else None


class StickySessionManager:
    """Manejador simple de proxies."""
    def __init__(self) -> None:
        self._sessions: List[StickySession] = []

    def get_fresh(self) -> Optional[StickySession]:
        try:
            from proxy_pool import build_admin_proxy_url
            url = build_admin_proxy_url()
            return StickySession(proxy_url=url, label="pool") if url else None
        except Exception:
            return None


def _classify_dead(login_result: dict) -> str:
    """Sub-clasifica un status='DEAD' del bot."""
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


async def gentle_login(
    email: str,
    password: str,
    *,
    max_login_retries: int = 2,
    throttle: bool = False,
    sticky_session: Optional[StickySession] = None,
    pool=None,
    sticky_mgr: Optional[StickySessionManager] = None,
    use_cache: bool = False,
    attempt_timeout: float = 35.0,
    allow_proxyless: bool = False,
) -> LoginResult:
    """Login directo, determinista y rápido.
    1. Si use_cache=True y hay JWT válido en BD, consulta saldo directo.
    2. Si no hay cache o falló, ejecuta login real con CaptchaHub + proxy.
    """
    from betmexico_login_api import BetmexicoApiChecker
    from proxy_pool import build_admin_proxy_url
    from app import db as app_db

    # 1. Fast-path por JWT en accounts si se solicitó
    if use_cache:
        try:
            from betmexico_db import db as bmx_db
            with bmx_db._lock:
                row = bmx_db.conn.cursor().execute(
                    "SELECT jwt_token, jwt_expires_at FROM accounts WHERE email=? COLLATE NOCASE",
                    (email,)
                ).fetchone()
            if row and row["jwt_token"]:
                jexp = row["jwt_expires_at"]
                exp_ts = int(jexp) if jexp and str(jexp).isdigit() else 0
                if exp_ts > (time.time() + 60):
                    jwt = row["jwt_token"]
                    proxy = (sticky_session.proxy_url if sticky_session else None) or build_admin_proxy_url()
                    async with BetmexicoApiChecker(proxy=proxy) as checker:
                        det = await asyncio.wait_for(
                            checker.fetch_account_details_parallel(jwt, fetch_mode="balance_only"),
                            timeout=10.0,
                        )
                        if det and det.get("_auth_ok") and not det.get("jwt_expired"):
                            logger.info(f"[login] {email} JWT cache HIT (vigente)")
                            return LoginResult(
                                ok=True,
                                jwt=jwt,
                                code="LIVE",
                                sticky_session=StickySession(proxy_url=proxy),
                                attempts=0,
                                from_cache=True,
                                details=det,
                            )
        except Exception as e:
            logger.debug(f"[login] {email} cache check: {e}")

    # 2. Login real vía CaptchaHub (hasta 2 intentos en caso de 406)
    # Gate de salud: si CapMonster está caído, fail-fast en vez de quemar
    # ~35s x N reintentos contra un proveedor que no va a responder.
    if not await _capmonster_available():
        return LoginResult(
            ok=False,
            code="CAPTCHA_DOWN",
            account_dead=False,
            error="CapMonster no disponible — login pausado (requiere captcha)",
            attempts=0,
        )

    last_error = None
    last_res = None
    for attempt in range(1, max(2, max_login_retries + 1)):
        proxy = (sticky_session.proxy_url if sticky_session else None) or build_admin_proxy_url()
        captcha_token = None
        captcha_task_id = None
        if pool is not None and hasattr(pool, "get_token"):
            try:
                c_res = await pool.get_token(timeout=min(30.0, attempt_timeout))
                if c_res and isinstance(c_res, tuple) and len(c_res) >= 2:
                    captcha_token, captcha_task_id = c_res[0], c_res[1]
            except Exception as ex_p:
                logger.debug(f"[login] pool.get_token: {ex_p}")

        try:
            async with BetmexicoApiChecker(proxy=proxy) as checker:
                res = await asyncio.wait_for(
                    checker.test_login(
                        email,
                        password,
                        captcha_token=captcha_token,
                        captcha_task_id=captcha_task_id,
                    ),
                    timeout=attempt_timeout,
                )
                last_res = res
                status = res.get("status")
                if status == "LIVE":
                    jwt = res.get("jwt_token") or (res.get("api") or {}).get("token")
                    details = res.get("account_details") or {}
                    jwt_exp = res.get("jwt_expires_at") or details.get("jwt_expires_at")
                    if jwt:
                        try:
                            from betmexico_db import db as bmx_db
                            with bmx_db._lock:
                                bmx_db.conn.cursor().execute(
                                    "UPDATE accounts SET jwt_token=?, jwt_expires_at=? WHERE email=? COLLATE NOCASE",
                                    (jwt, jwt_exp, email)
                                )
                                bmx_db.conn.commit()
                        except Exception:
                            pass
                    logger.info(f"[login] {email} LIVE exitoso (intento {attempt})")
                    return LoginResult(
                        ok=True,
                        jwt=jwt,
                        code="LIVE",
                        account_dead=False,
                        sticky_session=StickySession(proxy_url=proxy),
                        attempts=attempt,
                        from_cache=False,
                        details=details,
                        raw_result=res,
                    )
                elif status == "DEAD":
                    code = _classify_dead(res)
                    logger.info(f"[login] {email} DEAD ({code})")
                    return LoginResult(
                        ok=False,
                        code=code,
                        account_dead=True,
                        error=res.get("error") or code,
                        attempts=attempt,
                        raw_result=res,
                    )
                elif status == "BAN":
                    logger.warning(f"[login] {email} 429 BAN en BetMexico → RATE_LIMITED (sin reintentos para no quemar)")
                    return LoginResult(
                        ok=False,
                        code="RATE_LIMITED",
                        account_dead=False,
                        error="RATE_LIMITED (429)",
                        attempts=attempt,
                        raw_result=res,
                    )
                elif status == "RETRY_PROXY":
                    logger.info(f"[login] {email} fallo de WAF/IP ({res.get('error')}) en intento {attempt} — rotando a proxy fresco")
                    sticky_session = None
                    await asyncio.sleep(1.0)
                    continue
                elif status in ("RETRY_CAPTCHA", "CAPTCHA_TIMEOUT"):
                    last_error = status
                    continue
                else:
                    last_error = res.get("error") or status
                    api_data = res.get("api") or {}
                    api_msg = str(api_data.get("message") or res.get("error") or "").upper()
                    # Fail-fast ante credenciales inválidas o bloqueo definitivo: no quemar más captchas
                    if any(k in api_msg for k in ("CONTRASEÑA", "PASSWORD", "CREDENCIAL", "NO EXISTE", "BLOQUEAD", "AUTOEXCLU", "VALIDACION")):
                        code = _classify_dead(res)
                        logger.warning(f"[login] {email} credenciales o cuenta no viable ({api_msg}) → fail-fast (cero retries de captcha)")
                        return LoginResult(
                            ok=False,
                            code=code,
                            account_dead=True,
                            error=api_msg or "Credenciales inválidas",
                            attempts=attempt,
                            raw_result=res,
                        )
                    continue
        except Exception as e:
            logger.error(f"[login] {email} intento {attempt} error: {e}")
            last_error = str(e)
            continue

    return LoginResult(
        ok=False,
        code="LOGIN_FAILED",
        account_dead=False,
        error=last_error or "Login fallido tras reintentos",
        attempts=max_login_retries,
        raw_result=last_res,
    )

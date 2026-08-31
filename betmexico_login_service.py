#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BetMexico — Servicio centralizado de Login + Captcha + JWT Cache.

Uso:
    from betmexico_login_service import get_jwt, make_pool

    pool = make_pool(solver_or_key, size=12, workers=10)

    # Backward compat: get_jwt(email, password, pool, proxy=...)
    jwt, result = await get_jwt(email, password, pool, proxy=proxy_url)

    # Forzar login fresco saltando cache:
    jwt, result = await get_jwt(email, password, pool, use_cache=False)
"""

import logging
import time

from betmexico_login_api import (
    BetmexicoApiChecker, CaptchaTokenPool, CapMonsterSolverFast,
    BETMEXICO_URLS, RECAPTCHA_V2_SITE_KEY, _decode_jwt_payload,
)
from betmexico_db import db

logger = logging.getLogger("betmexico.login_service")

_MAX_RETRIES = 3
_JWT_CACHE_MARGIN_SEC = 60  # margen de 1 min para evitar usar JWT a punto de expirar


def make_pool(solver_or_key=None, size: int = 12, workers: int = 10) -> CaptchaTokenPool:
    """Crea un CaptchaTokenPool estándar para BetMexico usando CaptchaHub."""
    from betmexico_login_api import CaptchaHubSolverFast, AntiCaptchaSolverFast
    if solver_or_key is None or solver_or_key == "":
        solver = CaptchaHubSolverFast()
    elif isinstance(solver_or_key, str):
        if solver_or_key.startswith("http"):
            solver = CaptchaHubSolverFast(solver_or_key)
        elif solver_or_key.startswith("CAP-"):
            solver = AntiCaptchaSolverFast(solver_or_key)
        else:
            solver = CaptchaHubSolverFast()
    else:
        solver = solver_or_key
    return CaptchaTokenPool(
        solver,
        BETMEXICO_URLS["login"],
        RECAPTCHA_V2_SITE_KEY,
        max_pool=size,
        factory_workers=workers,
    )


def _persist_jwt_cache(email: str, jwt: str) -> None:
    """Decodifica el JWT y guarda en BD para reutilizar (cache)."""
    try:
        payload = _decode_jwt_payload(jwt)
        exp = payload.get("exp")
        user_id = None
        for claim in ("nameid", "sub", "userId", "UserId", "unique_name"):
            val = payload.get(claim)
            if val and str(val).isdigit():
                user_id = str(val)
                break
        if exp and isinstance(exp, (int, float)) and exp > time.time():
            db.save_jwt_cache(email, jwt, int(exp), user_id)
    except Exception as e:
        logger.debug(f"[LoginService] No se pudo persistir JWT cache para {email}: {e}")


async def get_jwt(
    email: str,
    password: str,
    pool: CaptchaTokenPool,
    proxy=None,
    max_retries: int = _MAX_RETRIES,
    use_cache: bool = True,
) -> tuple:
    """
    Obtiene JWT. Si use_cache=True y hay un JWT vigente en BD → lo retorna directo
    saltándose captcha + login. En caso contrario, flujo normal y guarda en cache al terminar.

    Returns:
        (jwt: str | None, login_result: dict)
    """
    # ─── JWT cache check ───────────────────────────────────────
    if use_cache:
        try:
            cached = db.get_jwt_cache(email)
            if cached and cached.get("expires_at", 0) > (time.time() + _JWT_CACHE_MARGIN_SEC):
                logger.info(f"[LoginService] ✅ JWT cache HIT para {email}")
                return cached["token"], {"status": "LIVE", "from_cache": True, "user_id": cached.get("user_id")}
        except Exception as e:
            logger.debug(f"[LoginService] JWT cache lookup error: {e}")

    # ─── Reusar mismo HTTPX client entre retries ──────────────
    try:
        async with BetmexicoApiChecker(proxy=proxy) as checker:
            for attempt in range(max_retries):
                res = await pool.get_token(timeout=90)
                captcha_token, captcha_task_id = (res if res else (None, None))

                if not captcha_token:
                    logger.error(f"[LoginService] Pool vacío para {email} (intento {attempt + 1})")
                    return None, {"status": "CAPTCHA_TIMEOUT"}

                try:
                    login_result = await checker.test_login(
                        email, password,
                        captcha_token=captcha_token,
                        captcha_task_id=captcha_task_id,
                    )
                except Exception as e:
                    logger.error(f"[LoginService] Error en test_login para {email}: {e}")
                    return None, {"status": "ERROR", "error": str(e)}

                status = login_result.get("status")

                if status == "RETRY_CAPTCHA":
                    logger.warning(
                        f"[LoginService] RETRY_CAPTCHA {email} "
                        f"(intento {attempt + 1}/{max_retries})"
                    )
                    continue

                if status == "LIVE":
                    jwt = login_result.get("api", {}).get("token")
                    if jwt:
                        _persist_jwt_cache(email, jwt)
                        return jwt, login_result
                    logger.error(f"[LoginService] Login LIVE pero JWT vacío para {email}")
                    return None, login_result

                # DEAD, BAN, ERROR — no reintentar
                logger.info(f"[LoginService] Login {status} para {email}")
                return None, login_result
    except Exception as e:
        logger.error(f"[LoginService] Excepción en checker context para {email}: {e}")
        return None, {"status": "ERROR", "error": str(e)}

    logger.error(f"[LoginService] {max_retries}x RETRY_CAPTCHA para {email}, abortando")
    return None, {"status": "RETRY_CAPTCHA"}

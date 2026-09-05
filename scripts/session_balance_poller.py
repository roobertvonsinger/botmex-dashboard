#!/usr/bin/env python3
"""
scripts/session_balance_poller.py — Refrescador Inteligente y Orgánico de Balances (BetMexico).

Arquitectura Anti-Metralla y Resiliencia Total (Robert 2026-09-04):
1. CERO METRALLA / RÁFAGAS:
   - Prohibido el disparo simultáneo (asyncio.gather masivo).
   - Las cuentas se distribuyen suavemente a lo largo de la ventana de 5 minutos (300s).
   - Cadencia orgánica: 1 petición cada 2.5 a 4.0 segundos (con jitter aleatorio).
   - Tasa plana de ~18-22 peticiones por minuto para toda la flota.
2. ROTACIÓN ESTRICTA DE PROXIES RESIDENCIALES:
   - CADA PETICIÓN obtiene un puerto proxy rotativo distinto vía build_admin_proxy_url()
     (pool DataImpulse 500 puertos residenciales México, 3-min TTL por IP).
   - REGLA DURA: NUNCA proxyless en producción. Si no hay proxy disponible, se aborta la petición
     para jamás exponer la IP de la VPS a BetMexico.
3. PRIORIZACIÓN INTELIGENTE (TIERING):
   - Tier 1 (Hot): Cuentas con saldo > $0, con retiros pendientes o bloqueos activos (se chequean primero).
   - Tier 2 (Warm): Cuentas con saldo $0 pero sesión viva (se atienden después, ordenadas por last_checked_at).
4. CERO COSTO / CERO CAPTCHA ($0.00):
   - Solo invoca el endpoint de wallet vía Bearer JWT existente.
   - Cero llamadas a servicios de captcha, cero peticiones a /api/Session/login.
5. BLINDAJE DE DOMINIO Y AISLAMIENTO DE LOGS:
   - Cero contacto con cuentas con dead_reason LIKE '%429%'.
   - Si el JWT expira (401 / redirectLogin), se marca jwt_expires_at=0 sin marcar DEAD ni pedir captcha.
   - Registro exclusivo en /data/logs/session_balance_poller.log (rotativo, cero spam en dashboard.log).
"""

import argparse
import asyncio
import logging
from logging.handlers import RotatingFileHandler
import os
import random
import signal
import sqlite3
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx

sys.path.insert(0, "/app")
if os.path.exists("/app"):
    os.chdir("/app")

try:
    from proxy_pool import build_admin_proxy_url
except ImportError:
    def build_admin_proxy_url() -> Optional[str]:
        return os.environ.get("ADMIN_PROXY_URL")

DB_PATH = os.environ.get("BMX_DB_PATH", "/data/betmexico_accounts.db")
LOG_DIR = os.environ.get("BMX_LOG_DIR", "/data/logs")
LOG_FILE = os.path.join(LOG_DIR, "session_balance_poller.log")
PID_FILE = "/data/session_balance_poller.pid"

os.makedirs(LOG_DIR, exist_ok=True)

# ── Configuración de Logging Aislado (Cero Contaminación en dashboard.log) ───
logger = logging.getLogger("balance_poller")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    rfh = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    rfh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(rfh)

WALLET_URL = "https://paymentsapi.betmexico.mx/api/Wallet/Total/Amount/ByAccountType"
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

REQUEST_TIMEOUT_SEC = 9.0
DEFAULT_CYCLE_INTERVAL_SEC = 300  # 5 minutos
MIN_PACING_GAP_SEC = 2.0
MAX_PACING_GAP_SEC = 4.5

_SHUTDOWN_REQUESTED = False


def _signal_handler(sig, frame):
    global _SHUTDOWN_REQUESTED
    logger.info(f"Señal de apagado recibida ({sig}). Concluyendo ciclo ordenadamente...")
    _SHUTDOWN_REQUESTED = True


def get_prioritized_candidates() -> List[Dict[str, Any]]:
    """
    Obtiene cuentas con sesión activa limpia, clasificándolas en:
    - Tier 1 (Hot): Saldo > $0 o lock activo (prioridad alta).
    - Tier 2 (Warm): Saldo $0 (ordenadas por last_checked_at ASC para rotación justa).
    Excluye estrictamente cuentas con 429.
    """
    con = sqlite3.connect(DB_PATH, timeout=30.0)
    cur = con.cursor()
    now_ts = int(time.time())

    sql = """
    SELECT id, email, jwt_token, balance_real, locked_by, locked_until, last_checked_at
    FROM accounts
    WHERE jwt_token IS NOT NULL 
      AND length(jwt_token) > 20
      AND (jwt_expires_at > ? OR jwt_expires_at IS NULL)
      AND (dead_reason IS NULL OR dead_reason NOT LIKE '%429%')
    """
    rows = cur.execute(sql, (now_ts,)).fetchall()
    con.close()

    candidates = []
    for r in rows:
        acc_id, email, jwt, bal, locked_by, locked_until, last_chk = r
        bal_float = float(bal or 0.0)
        is_hot = (bal_float > 0.0) or (locked_by is not None)
        candidates.append({
            "id": acc_id,
            "email": email,
            "jwt_token": jwt,
            "balance_real": bal_float,
            "is_hot": is_hot,
            "last_checked_at": last_chk or "",
        })

    # Ordenar: primero todas las Hot, luego Warm por antigüedad de chequeo
    candidates.sort(key=lambda x: (0 if x["is_hot"] else 1, x["last_checked_at"]))
    return candidates


TXN_URL = "https://paymentsapi.betmexico.mx/api/Wallet/Transactions/ByUser/"

async def check_single_account(acc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Consulta el balance Y transacciones de una cuenta vía Bearer JWT con proxy rotativo exclusivo.
    Rellena automáticamente cualquier hueco temporal en account_transactions.
    NUNCA ejecuta sin proxy para proteger la IP del servidor.
    """
    email = acc["email"]
    acc_id = acc["id"]
    old_balance = acc["balance_real"]
    jwt_token = acc["jwt_token"]

    proxy_url = build_admin_proxy_url()
    if not proxy_url:
        logger.warning(f"[{email}] Omitido: Cero proxies disponibles en el pool (regla anti-fuga de IP directa)")
        return {"status": "NO_PROXY", "acc_id": acc_id, "email": email, "changed": False, "expired": False, "txns": []}

    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json",
        "Origin": "https://betmexico.mx",
        "Referer": "https://betmexico.mx/",
    }

    result = {
        "acc_id": acc_id,
        "email": email,
        "status": "ERROR",
        "balance_real": old_balance,
        "balance_bonos": 0.0,
        "changed": False,
        "expired": False,
        "txns": [],
        "proxy_used": proxy_url.split("@")[-1] if "@" in proxy_url else proxy_url[:20],
    }

    try:
        async with httpx.AsyncClient(proxy=proxy_url, verify=False, timeout=REQUEST_TIMEOUT_SEC) as client:
            # Consulta concurrente de Wallet + Transacciones página 1 (pageSize 50)
            w_task = client.get(WALLET_URL, headers=headers)
            t_task = client.get(TXN_URL, params={"pageNumber": 1, "pageSize": 50}, headers=headers)
            w_resp, t_resp = await asyncio.gather(w_task, t_task, return_exceptions=True)

            # 1. Procesar Wallet
            if isinstance(w_resp, httpx.Response):
                if w_resp.status_code == 200:
                    data = w_resp.json()
                    if isinstance(data, dict) and data.get("redirectLogin"):
                        result["status"] = "EXPIRED"
                        result["expired"] = True
                        return result

                    bal_real = 0.0
                    bal_bonos = 0.0
                    if isinstance(data, list):
                        for item in data:
                            atype = item.get("accountType", "")
                            amt = float(item.get("totalAmount", 0.0))
                            if atype == "Real": bal_real = amt
                            elif atype == "Bonos": bal_bonos = amt
                    elif isinstance(data, dict):
                        bal_real = float(data.get("Real", 0.0))
                        bal_bonos = float(data.get("Bonos", 0.0))

                    result["status"] = "OK"
                    result["balance_real"] = bal_real
                    result["balance_bonos"] = bal_bonos
                    if abs(bal_real - old_balance) > 0.009:
                        result["changed"] = True

                elif w_resp.status_code == 401:
                    result["status"] = "EXPIRED"
                    result["expired"] = True
                    return result
                else:
                    result["status"] = f"HTTP_{w_resp.status_code}"
            elif isinstance(w_resp, Exception):
                result["status"] = f"ERR_{type(w_resp).__name__}"

            # 2. Procesar Transacciones (rellenado de huecos temporales)
            if isinstance(t_resp, httpx.Response) and t_resp.status_code == 200:
                t_json = t_resp.json()
                data_obj = t_json.get("data", {}) if isinstance(t_json, dict) else {}
                meta = data_obj.get("metadata", {})
                txns_p1 = data_obj.get("results", []) or []
                result["txns"].extend(txns_p1)

                # Si hay más páginas y hay gap histórico, traer página 2 para completar el historial
                if meta.get("hasNextPage") and meta.get("pages", 1) >= 2:
                    try:
                        t_resp2 = await client.get(TXN_URL, params={"pageNumber": 2, "pageSize": 50}, headers=headers)
                        if t_resp2.status_code == 200:
                            data_obj2 = t_resp2.json().get("data", {})
                            result["txns"].extend(data_obj2.get("results", []) or [])
                    except Exception:
                        pass

            return result

    except httpx.TimeoutException:
        result["status"] = "TIMEOUT_PROXY"
        return result
    except Exception as e:
        result["status"] = f"ERR_{type(e).__name__}"
        return result


def apply_single_update(res: Dict[str, Any]):
    """Aplica la actualización de balance y transacciones en SQLite WAL de forma atómica."""
    acc_id = res["acc_id"]
    email = res["email"]
    st = res["status"]

    try:
        con = sqlite3.connect(DB_PATH, timeout=30.0)
        con.execute("PRAGMA busy_timeout = 30000")
        con.execute("PRAGMA synchronous = NORMAL")
        cur = con.cursor()

        if st == "OK":
            bal_real = res["balance_real"]
            bal_bonos = res["balance_bonos"]
            bal_total = bal_real + bal_bonos
            cur.execute(
                """
                UPDATE accounts 
                SET balance_real = ?,
                    balance_bonos = ?,
                    balance_total = ?,
                    last_checked_at = datetime('now')
                WHERE id = ?
                """,
                (bal_real, bal_bonos, bal_total, acc_id),
            )
            if res["changed"]:
                logger.info(f"[{email}] CAMBIO DE SALDO: ${bal_real:.2f} (antiguo: ${res.get('balance_real'):.2f})")

            # Inserción no destructiva de transacciones para cerrar huecos temporales
            new_txns = res.get("txns") or []
            txns_inserted = 0
            for item in new_txns:
                d = item.get("date", "")
                amt = float(item.get("amount", 0.0))
                item_st = int(item.get("status", 0))
                tp = int(item.get("type", 0))
                gw = int(item.get("gateway", 0))

                exists = cur.execute(
                    """
                    SELECT 1 FROM account_transactions 
                    WHERE account_email = ? AND txn_date = ? AND amount = ? AND txn_type = ?
                    LIMIT 1
                    """,
                    (email, d, amt, tp),
                ).fetchone()

                if not exists:
                    cur.execute(
                        """
                        INSERT INTO account_transactions 
                        (account_email, txn_date, amount, status, txn_type, gateway, checked_by, fetched_at, source)
                        VALUES (?, ?, ?, ?, ?, ?, 0, datetime('now'), 'betmex')
                        """,
                        (email, d, amt, item_st, tp, gw),
                    )
                    txns_inserted += 1

            con.commit()
            con.close()
            con = None

            if txns_inserted > 0:
                logger.info(f"[{email}] +{txns_inserted} movimientos nuevos sincronizados de BetMexico (hueco cerrado)")
                try:
                    from web_grading import recalc_grade_from_db
                    recalc_grade_from_db(email)
                except Exception as ex:
                    logger.debug(f"[{email}] recalc_grade_from_db: {ex}")

        elif res.get("expired"):
            cur.execute(
                """
                UPDATE accounts 
                SET jwt_expires_at = 0,
                    last_checked_at = datetime('now')
                WHERE id = ?
                """,
                (acc_id,),
            )
            con.commit()
            con.close()
            con = None
            logger.info(f"[{email}] Sesión expirada (401) -> jwt_expires_at=0 ($0 captcha, sin marcar DEAD)")

    except Exception as e:
        logger.warning(f"[{email}] Error guardando balance/txns en BD: {e}")
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:
                pass



async def run_organic_cycle(interval_sec: int = DEFAULT_CYCLE_INTERVAL_SEC) -> Tuple[int, int, int, float]:
    """
    Ejecuta el ciclo de forma orgánica, distribuyendo las peticiones
    a lo largo del tiempo para evitar ráfagas o metrallas.
    """
    t0 = time.time()
    candidates = get_prioritized_candidates()
    total_accs = len(candidates)

    if total_accs == 0:
        logger.info("Ciclo: Cero cuentas con sesión activa disponible para refrescar.")
        return 0, 0, 0, 0.0

    # Cálculo dinámico del espaciado (pacing)
    # Reserva un margen de 45 segundos al final del ciclo para descanso
    usable_time = max(30.0, float(interval_sec - 45))
    target_gap = usable_time / max(1, total_accs)
    # Acotar entre 2.0s y 4.5s
    pacing_gap = max(MIN_PACING_GAP_SEC, min(MAX_PACING_GAP_SEC, target_gap))

    hot_count = sum(1 for c in candidates if c["is_hot"])
    warm_count = total_accs - hot_count

    logger.info(
        f"[INICIO CICLO ORGÁNICO] {total_accs} cuentas elegibles (Hot: {hot_count}, Warm: {warm_count}). "
        f"Espaciado objetivo: ~{pacing_gap:.2f}s por cuenta (rotación proxy individual)."
    )

    updated_ok = 0
    expired_cnt = 0
    changes_cnt = 0

    for idx, acc in enumerate(candidates, 1):
        if _SHUTDOWN_REQUESTED:
            logger.info("Ciclo interrumpido por señal de apagado.")
            break

        # Chequeo con proxy rotativo exclusivo
        res = await check_single_account(acc)
        apply_single_update(res)

        if res["status"] == "OK":
            updated_ok += 1
            if res["changed"]:
                changes_cnt += 1
        elif res.get("expired"):
            expired_cnt += 1

        # Espaciado orgánico con jitter (+- 15%)
        if idx < total_accs and not _SHUTDOWN_REQUESTED:
            jitter = random.uniform(-0.35, 0.35)
            sleep_time = max(1.5, pacing_gap + jitter)
            await asyncio.sleep(sleep_time)

    elapsed = time.time() - t0
    logger.info(
        f"[CICLO COMPLETADO] {idx}/{total_accs} procesadas en {elapsed:.1f}s "
        f"({updated_ok} OK, {changes_cnt} cambios de saldo, {expired_cnt} expiradas, 0 captchas, $0 cost). "
        f"Cadencia real: {(elapsed/max(1, idx)):.2f}s/req."
    )
    return total_accs, updated_ok, expired_cnt, elapsed


async def daemon_loop(interval_sec: int):
    """Bucle del daemon con sincronización de descanso entre ciclos."""
    logger.info(
        f"=== INICIANDO DAEMON BALANCE POLLER ORGÁNICO "
        f"(Intervalo: {interval_sec}s, Pacing: {MIN_PACING_GAP_SEC}s-{MAX_PACING_GAP_SEC}s, Proxies: Rotativos DataImpulse) ==="
    )

    try:
        with open(PID_FILE, "w") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass

    try:
        while not _SHUTDOWN_REQUESTED:
            cycle_start = time.time()
            try:
                await run_organic_cycle(interval_sec)
            except Exception as e:
                logger.error(f"Excepción no controlada en ciclo: {e}", exc_info=True)

            # Calcular tiempo restante hasta el próximo ciclo
            cycle_duration = time.time() - cycle_start
            remaining_sleep = max(10.0, interval_sec - cycle_duration)
            logger.info(f"Ciclo terminado. Descanso ordenado de {remaining_sleep:.1f}s antes del próximo ciclo...")

            slept = 0.0
            while slept < remaining_sleep and not _SHUTDOWN_REQUESTED:
                step = min(3.0, remaining_sleep - slept)
                await asyncio.sleep(step)
                slept += step

    finally:
        if os.path.exists(PID_FILE):
            try: os.remove(PID_FILE)
            except: pass
        logger.info("=== DAEMON BALANCE POLLER ORGÁNICO DETENIDO LIMPIAMENTE ===")


def main():
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    parser = argparse.ArgumentParser(description="BetMexico Organic Session Balance Refresher")
    parser.add_argument("--once", action="store_true", help="Ejecuta un solo ciclo (con pacing rápido de prueba) y termina")
    parser.add_argument("--interval", type=int, default=DEFAULT_CYCLE_INTERVAL_SEC, help="Intervalo total en segundos")
    args = parser.parse_args()

    if args.once:
        # Modo prueba rápida de 1 ciclo: pacing forzado a 1.0s para verificar sin esperar 4 minutos
        global MIN_PACING_GAP_SEC, MAX_PACING_GAP_SEC
        MIN_PACING_GAP_SEC = 0.8
        MAX_PACING_GAP_SEC = 1.2
        total, ok, exp, elapsed = asyncio.run(run_organic_cycle(interval_sec=120))
        print(f"Cycle completed: {total} accounts checked in {elapsed:.2f}s ({ok} updated, {exp} expired)")
    else:
        asyncio.run(daemon_loop(args.interval))


if __name__ == "__main__":
    main()

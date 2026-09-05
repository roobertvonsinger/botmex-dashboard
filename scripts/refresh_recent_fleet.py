"""
scripts/refresh_recent_fleet.py — Refresco manual controlado de la flota reciente de BetMexico.
Procesa las cuentas con actividad reciente en la última semana (excluyendo estrictamente las 429 quemadas).
"""
import asyncio, os, sys, time, logging
import sqlite3

sys.path.insert(0, '/app')
os.chdir('/app')

from betmexico_login_api import BetmexicoApiChecker
from proxy_pool import build_admin_proxy_url
from betmexico_db import db as bldb

LOG_FILE = '/data/logs/manual_refresh_fleet.log'
os.makedirs('/data/logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("fleet_refresh")

DB_PATH = '/data/betmexico_accounts.db'

def get_target_accounts():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    # Cuentas activas recientemente (>= 2026-08-28) excluyendo las 429
    sql = '''
    SELECT id, email, password, jwt_token, jwt_expires_at, balance_total, status, dead_reason
    FROM accounts
    WHERE (last_checked_at >= '2026-08-28' OR last_updated_at >= '2026-08-28'
           OR email IN (SELECT DISTINCT account_email FROM deposit_attempts WHERE created_at >= '2026-08-28'))
      AND (dead_reason IS NULL OR dead_reason NOT LIKE '%429%')
    ORDER BY balance_total DESC, last_checked_at DESC
    '''
    rows = cur.execute(sql).fetchall()
    con.close()
    return rows

async def process_account(row, checker):
    acc_id, email, password, jwt, jwt_exp, bal, status, dead_reason = row
    now_ts = int(time.time())
    
    # 1. Probar con JWT si existe y no está expirado
    if jwt and jwt_exp and int(jwt_exp) > (now_ts + 120):
        try:
            det = await checker.fetch_account_details_parallel(jwt, fetch_mode='balance_only')
            if det and det.get('_auth_ok') and not det.get('jwt_expired'):
                bal_real = det.get("balance_real", 0.0)
                logger.info(f"[{email}] ✓ JWT VIGENTE (Saldo: ${bal_real}) -> LIVE")
                bldb.upsert_account({
                    "email": email,
                    "password": password,
                    "jwt_token": jwt,
                    "jwt_expires_at": jwt_exp,
                    "status": "LIVE",
                    "account_details": det,
                    "balance_real": bal_real,
                    "balance_total": bal_real,
                })
                return "LIVE_JWT", bal_real
        except Exception as e:
            logger.debug(f"[{email}] Falló check JWT: {e}")

    # 2. Login fresh con CaptchaHub
    if not password:
        logger.warning(f"[{email}] Sin password, skip")
        return "NO_PASSWORD", 0.0

    logger.info(f"[{email}] Login fresh con CaptchaHub...")
    try:
        res = await checker.test_login(email, password)
        st = res.get("status")
        if st == "LIVE":
            bal_real = res.get("balance_real", 0.0)
            logger.info(f"[{email}] ✓ LOGIN LIVE EXITOSO (Saldo: ${bal_real}) -> LIVE")
            bldb.upsert_account(res)
            return "LIVE_LOGIN", bal_real
        elif st in ("BAN", "RATE_LIMITED") or "429" in str(res.get("error")):
            logger.warning(f"[{email}] ⚠ 429 Rate limited (se preserva status intacto, sin matar)")
            return "RATE_LIMITED", 0.0
        elif st == "DEAD":
            err = res.get("error", "LOGIN_DENIED")
            logger.warning(f"[{email}] ✗ Login rechazado por credenciales: {err}")
            return "DEAD_CREDENTIALS", 0.0
        else:
            logger.warning(f"[{email}] ✗ Otro resultado: {st} ({res.get('error')})")
            return st or "UNKNOWN", 0.0
    except Exception as e:
        logger.error(f"[{email}] Error en test_login: {e}")
        return "ERROR", 0.0

async def main():
    proxy = build_admin_proxy_url()
    logger.info(f"Iniciando refresco de flota reciente con proxy: {proxy[:35]}...")
    checker = BetmexicoApiChecker(proxy=proxy)
    
    rows = get_target_accounts()
    logger.info(f"Total cuentas encontradas: {len(rows)}")
    
    stats = {"LIVE_JWT": 0, "LIVE_LOGIN": 0, "RATE_LIMITED": 0, "DEAD_CREDENTIALS": 0, "OTHER": 0}
    
    for idx, r in enumerate(rows, 1):
        email = r[1]
        logger.info(f"[{idx}/{len(rows)}] Procesando: {email}...")
        res, bal = await process_account(r, checker)
        if res in stats:
            stats[res] += 1
        else:
            stats["OTHER"] += 1
        await asyncio.sleep(3)  # Pacing de 3 segundos
        
    logger.info(f"--- RESUMEN FINAL ---")
    logger.info(f"Stats: {stats}")
    logger.info(f"Total LIVE recuperadas/refrescadas: {stats['LIVE_JWT'] + stats['LIVE_LOGIN']} de {len(rows)}")

if __name__ == "__main__":
    asyncio.run(main())

"""
scripts/reconcile_macro_fleet.py — Conciliador Inteligente y Recuperador de Flota BetMexico.
Reglas Canónicas Robert (2026-09-04):
1. CERO gasto de captcha si existe sesión (JWT): siempre prueba JWT primero ($0).
2. CERO contaminación: NUNCA toca cuentas con 429 de contraseñas de Cloud.
3. CERO degradación arbitraria: NUNCA marca DEAD si BetMexico responde 429.
4. Prioridad a cuentas con SALDO POSITIVO y cuentas activas recientemente.
"""
import asyncio, os, sys, time, logging
import sqlite3

sys.path.insert(0, '/app')
os.chdir('/app')

from betmexico_login_api import BetmexicoApiChecker
from proxy_pool import build_admin_proxy_url
from betmexico_db import db as bldb

LOG_FILE = '/data/logs/reconcile_macro_fleet.log'
os.makedirs('/data/logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("macro_reconcile")

DB_PATH = '/data/betmexico_accounts.db'

def get_target_accounts(limit=150):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    # Universo sano con prioridad:
    # 1. Cuentas con saldo > 0
    # 2. Cuentas con actividad reciente (Agosto/Septiembre)
    # Excluyendo 429 quemadas y autoexclusiones
    sql = '''
    SELECT id, email, password, jwt_token, jwt_expires_at, balance_total, status, dead_reason
    FROM accounts
    WHERE (
        balance_total > 0
        OR (last_checked_at >= '2026-08-01' OR last_updated_at >= '2026-08-01')
        OR email IN (SELECT DISTINCT account_email FROM deposit_attempts WHERE created_at >= '2026-08-01')
        OR email IN (SELECT DISTINCT account_email FROM account_transactions WHERE txn_date >= '2026-08-01')
    )
    AND (dead_reason IS NULL OR dead_reason NOT LIKE '%429%')
    AND (dead_reason IS NULL OR dead_reason NOT LIKE '%AUTOEXCLUSION%')
    ORDER BY balance_total DESC, last_checked_at DESC
    LIMIT ?
    '''
    rows = cur.execute(sql, (limit,)).fetchall()
    con.close()
    return rows

async def process_account(row, checker):
    acc_id, email, password, jwt, jwt_exp, bal, status, dead_reason = row
    now_ts = int(time.time())
    
    # 1. REGLA DE ORO: SI HAY JWT, PROBAR PRIMERO ($0 CAPTCHA)
    if jwt and len(jwt) > 20:
        try:
            det = await checker.fetch_account_details_parallel(jwt, fetch_mode='balance_only')
            if det and det.get('_auth_ok') and not det.get('jwt_expired'):
                bal_real = det.get("balance_real", 0.0)
                logger.info(f"[{email}] ✓ SESIÓN JWT VIGENTE ($0 captcha) -> LIVE (Saldo: ${bal_real:.2f})")
                bldb.upsert_account({
                    "email": email,
                    "password": password,
                    "jwt_token": jwt,
                    "jwt_expires_at": jwt_exp or (now_ts + 86400 * 7),
                    "status": "LIVE",
                    "account_details": det,
                    "balance_real": bal_real,
                    "balance_total": bal_real,
                })
                return "LIVE_JWT", bal_real
        except Exception as e:
            logger.debug(f"[{email}] Falló check JWT: {e}")

    # 2. LOGIN FRESCO CON CAPTCHAHUB SOLO SI EL JWT NO FUNCIONÓ
    if not password:
        logger.debug(f"[{email}] Sin password, omitiendo login fresh")
        return "NO_PASSWORD", 0.0

    logger.info(f"[{email}] Sesión no válida. Intentando login fresco vía CaptchaHub...")
    try:
        res = await checker.test_login(email, password)
        st = res.get("status")
        if st == "LIVE":
            bal_real = res.get("balance_real", 0.0)
            logger.info(f"[{email}] ✓ LOGIN FRESH EXITOSO -> LIVE (Saldo: ${bal_real:.2f})")
            bldb.upsert_account(res)
            return "LIVE_LOGIN", bal_real
        elif st in ("BAN", "RATE_LIMITED") or "429" in str(res.get("error")):
            logger.warning(f"[{email}] ⚠ Rate limit 429 temporal -> se aísla sin matar (status={status})")
            # Aislar del pool pero NO marcar status='DEAD'
            con = sqlite3.connect(DB_PATH)
            con.execute("UPDATE accounts SET published_to_pool=0, last_checked_at=datetime('now') WHERE email=?", (email,))
            con.commit()
            con.close()
            return "RATE_LIMITED", 0.0
        elif st == "DEAD":
            err = res.get("error", "LOGIN_DENIED")
            logger.warning(f"[{email}] ✗ Login rechazado por credenciales: {err}")
            return "DEAD_CREDENTIALS", 0.0
        else:
            logger.info(f"[{email}] Resultado: {st}")
            return st or "UNKNOWN", 0.0
    except Exception as e:
        logger.error(f"[{email}] Error en test_login: {e}")
        return "ERROR", 0.0

async def main():
    proxy = build_admin_proxy_url()
    logger.info(f"Iniciando reconciliación macro con proxy: {proxy[:35]}...")
    checker = BetmexicoApiChecker(proxy=proxy)
    
    rows = get_target_accounts(limit=200)
    logger.info(f"Total cuentas objetivo en este ciclo: {len(rows)}")
    
    stats = {"LIVE_JWT": 0, "LIVE_LOGIN": 0, "RATE_LIMITED": 0, "DEAD_CREDENTIALS": 0, "OTHER": 0}
    
    for idx, r in enumerate(rows, 1):
        email = r[1]
        logger.info(f"[{idx}/{len(rows)}] Evaluando: {email} (status actual: {r[6]}, saldo registrado: ${r[5]})...")
        res, bal = await process_account(r, checker)
        if res in stats:
            stats[res] += 1
        else:
            stats["OTHER"] += 1
        await asyncio.sleep(4)  # Pacing seguro
        
    logger.info(f"--- RESUMEN FINAL DE CONCILIACIÓN ---")
    logger.info(f"Stats: {stats}")
    logger.info(f"Total LIVE activas/recuperadas: {stats['LIVE_JWT'] + stats['LIVE_LOGIN']} de {len(rows)}")

if __name__ == "__main__":
    asyncio.run(main())

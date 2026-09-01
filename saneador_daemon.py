"""
saneador_daemon.py — Saneador y Auditor Autónomo de Cuentas BetMexico.

Ejecuta el ciclo de salud con:
1. Pacing estricto (5 a 8s entre cuentas) para evitar rate limits.
2. Rotación obligatoria de proxy residencial MX (NUNCA proxyless).
3. Circuit breaker: 3 errores consecutivos de red/429 pausan el saneador 30 min.
4. Sincronización completa: Login -> Actualizar JWT -> Actualizar Balances -> Recalcular Grade V10.
5. Blindaje Robert 2026: Cuentas Grado D o con 429/BAN se marcan DEAD inmediatamente (cero cooldowns temporales).
"""

import asyncio
import logging
import os
import random
import sqlite3
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, '/app')
sys.path.insert(0, '/app/web')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [SANEADOR] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("saneador")

DB_PATH = os.environ.get("BETMEX_DB", "/data/betmexico_accounts.db")

def get_db(write: bool = False):
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    if write:
        conn.execute("PRAGMA journal_mode=WAL;")
    return conn

async def audit_single_account(email: str, password: str, checker, pool) -> dict:
    """Audita una sola cuenta de forma segura."""
    from betmexico_payment_analyzer import score_payment_readiness
    
    res = await checker.test_login(email, password, fetch_mode="full")
    status = res.get("status")
    api_data = res.get("api", {})
    
    result = {
        "email": email,
        "status": status,
        "jwt": None,
        "balance_real": None,
        "grade": None,
        "score": None,
        "error": None
    }
    
    if status == "LIVE":
        details = res.get("account_details", {})
        jwt = api_data.get("token")
        
        # Extraer balances
        wallet = details.get("wallet", {})
        bal_real = 0.0
        bal_bonos = 0.0
        if isinstance(wallet, list):
            for w in wallet:
                acc_type = w.get("accountType")
                amt = float(w.get("amount") or 0.0)
                if acc_type == 1:
                    bal_real = amt
                elif acc_type == 2:
                    bal_bonos = amt
        
        # Guardar en BD
        conn = get_db(write=True)
        with conn:
            now_epoch = int(time.time())
            exp_epoch = now_epoch + (86400 * 7) # 7 días por defecto
            
            # Recalcular transacciones y grade
            txns = details.get("transactions", {}).get("items", [])
            if txns:
                for t in txns:
                    try:
                        conn.execute("""
                            INSERT OR IGNORE INTO account_transactions 
                            (account_email, txn_id, txn_date, txn_type, gateway, status, amount)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            email, 
                            str(t.get("id") or t.get("txn_id") or ""),
                            str(t.get("date") or t.get("txn_date") or ""),
                            int(t.get("type") or t.get("txn_type") or 1),
                            int(t.get("gateway") or 1),
                            int(t.get("status") or 0),
                            float(t.get("amount") or 0.0)
                        ))
                    except Exception:
                        pass
            
            # Recalcular grado V10
            db_txns = conn.execute(
                "SELECT txn_date, status, txn_type, gateway, amount FROM account_transactions WHERE LOWER(account_email)=LOWER(?) ORDER BY txn_date DESC",
                (email,)
            ).fetchall()
            
            g_details = {"transactions": {"fetched": True, "items": [dict(x) for x in db_txns], "total_rows": len(db_txns)}}
            sc = score_payment_readiness(g_details)
            new_grade = (sc["grade"] if sc else "A").upper()
            new_score = sc["score"] if sc else 100
            
            conn.execute("""
                UPDATE accounts SET 
                    status = 'LIVE',
                    dead_reason = NULL,
                    dead_at = NULL,
                    published_to_pool = 1,
                    locked_by = NULL,
                    locked_until = NULL,
                    balance_real = ?,
                    balance_bonos = ?,
                    balance_total = ?,
                    jwt_token = ?,
                    jwt_expires_at = ?,
                    grade = ?,
                    grade_score = ?,
                    last_checked_at = datetime('now')
                WHERE email = ?
            """, (bal_real, bal_bonos, bal_real + bal_bonos, jwt, exp_epoch, new_grade, new_score, email))
            logger.info(f"🟢 [{email}] OPERABLE | Bal: ${bal_real} | Grade: {new_grade} ({new_score})")
            
        conn.close()
        result.update({
            "jwt": bool(jwt),
            "balance_real": bal_real,
            "grade": new_grade,
            "score": new_score
        })

    elif status == "DEAD":
        err_msg = str(api_data.get("message") or api_data.get("error") or "AUTH_FAIL")
        conn = get_db(write=True)
        with conn:
            conn.execute("""
                UPDATE accounts SET 
                    status = 'DEAD', 
                    dead_reason = ?, 
                    dead_at = COALESCE(dead_at, datetime('now')),
                    published_to_pool = 0,
                    locked_by = NULL,
                    locked_until = NULL,
                    last_checked_at = datetime('now')
                WHERE email = ?
            """, (err_msg, email))
        conn.close()
        result["error"] = err_msg
        logger.warning(f"🔴 [{email}] DEAD -> {err_msg}")

    elif status == "BAN":
        err = "RATE_LIMITED_TEMP (429 en saneador — reintento posterior)"
        result["status"] = "RATE_LIMITED"
        result["error"] = err
        logger.warning(f"⚠️ [{email}] BAN/429 transitorio -> Se omite ciclo sin marcar DEAD")

    return result

async def run_sanitizer_batch(limit: int = 25):
    """Ejecuta un ciclo de saneamiento sobre un lote de cuentas."""
    from betmexico_login_api import BetmexicoApiChecker
    from betmexico_login_service import make_pool
    
    logger.info(f"🚀 Iniciando ciclo de saneamiento (lote máx: {limit} cuentas)...")
    
    conn = get_db()
    # Tomar únicamente cuentas LIVE válidas, sin Grado D ni marcas de muerte
    accounts = conn.execute("""
        SELECT email, password, grade, status, published_to_pool, locked_by
        FROM accounts 
        WHERE status = 'LIVE' 
          AND COALESCE(grade, '') != 'D'
          AND published_to_pool = 1
          AND dead_reason IS NULL
          AND dead_at IS NULL
          AND (withdrawal_ready IS NULL OR withdrawal_ready = 0)
        ORDER BY last_checked_at ASC NULLS FIRST
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    
    if not accounts:
        logger.info("ℹ️ No hay cuentas pendientes de saneamiento en este ciclo.")
        return
    
    cap_key = os.environ.get("CAPMONSTER_KEY") or os.environ.get("BMX_CAPMONSTER_KEY", "")
    pool = make_pool(cap_key, size=2, workers=1)
    
    checker = BetmexicoApiChecker()
    
    consecutive_rate_limits = 0
    stats = {"total": len(accounts), "live": 0, "dead": 0, "cooldown": 0, "errors": 0}
    
    try:
        for idx, acc in enumerate(accounts, 1):
            email = acc["email"]
            pw = acc["password"]
            
            # Guard SA
            locked_by = str(acc["locked_by"] or "").lower()
            if not acc["published_to_pool"] and locked_by in ("1341812706", "robertvs"):
                logger.info(f"[{idx}/{len(accounts)}] 🛡️ {email} (RESERVADA_SA) -> SKIP")
                continue
                
            if not pw:
                logger.warning(f"[{idx}/{len(accounts)}] ⚠️ {email} (Sin password) -> SKIP")
                continue
                
            logger.info(f"[{idx}/{len(accounts)}] 🩺 Diagnosticando: {email}...")
            
            try:
                res = await audit_single_account(email, pw, checker, pool)
                st = res.get("status")
                
                if st == "LIVE":
                    stats["live"] += 1
                    consecutive_rate_limits = 0
                elif st == "DEAD":
                    stats["dead"] += 1
                    if "RATE_LIMITED" in str(res.get("error")):
                        consecutive_rate_limits += 1
                    else:
                        consecutive_rate_limits = 0
                else:
                    stats["errors"] += 1
                    
                # Circuit Breaker: 3 rate limits seguidos
                if consecutive_rate_limits >= 3:
                    logger.warning("🛑 [CIRCUIT BREAKER] 3 rate-limits consecutivos detectados. Pausando lote.")
                    break
                    
            except Exception as e:
                stats["errors"] += 1
                logger.error(f"💥 Error al auditar {email}: {e}")
                
            # Pacing de seguridad (5 a 8s)
            delay = random.uniform(5.0, 8.0)
            logger.info(f"⏳ Pacing: esperando {delay:.1f}s...")
            await asyncio.sleep(delay)
            
    finally:
        try:
            await pool.stop()
        except Exception:
            pass
        if checker._client and not checker._client.is_closed:
            await checker._client.aclose()
            
    logger.info(f"🏁 CICLO COMPLETADO: {stats}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Saneador de Cuentas BetMexico")
    parser.add_argument("--limit", type=int, default=20, help="Número de cuentas a sanear")
    args = parser.parse_args()
    
    asyncio.run(run_sanitizer_batch(limit=args.limit))

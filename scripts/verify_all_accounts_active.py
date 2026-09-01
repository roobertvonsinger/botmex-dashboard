"""scripts/verify_all_accounts_active.py — Verificación activa masiva de TODAS las cuentas LIVE en BetMexico.

Ejecuta logins secuenciales con proxy rotativo (gentle_login, use_cache=False)
para refrescar estado y descartar inmediatamente como 'DEAD' cualquier cuenta en
rate limit (429/RATE_LIMITED), BAN, LOGIN_DENIED, KYC_PENDING o AUTOEXCLUSION.

Excluye cuentas RESERVADA_SA (published_to_pool=0 + locked_by del superadmin).
"""

import asyncio
import os
import sys
import time
import logging

# 1. Parche de import circular en legacy bot files (/app):
# Importar betmexico_config ANTES de cualquier modulo del bot para pre-poblar sys.modules
try:
    import betmexico_config
except ImportError:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, "/app/web")
sys.path.insert(0, "/app")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("verify_all_accounts")


def get_db_connection():
    import sqlite3
    db_path = os.environ.get("DB_PATH", "/data/betmexico_accounts.db")
    if not os.path.exists(db_path):
        db_path = "betmexico_accounts.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_target_accounts():
    conn = get_db_connection()
    c = conn.cursor()
    rows = c.execute(
        "SELECT email, password, status, published_to_pool, locked_by FROM accounts WHERE status='LIVE'"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_account_dead(email: str, reason: str):
    from datetime import datetime, timezone
    conn = get_db_connection()
    c = conn.cursor()
    now_cd = int(time.time()) + (86400 * 30)  # 30 dias de cooldown
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        "UPDATE accounts SET status='DEAD', dead_reason=?, dead_at=COALESCE(dead_at, ?), "
        "published_to_pool=0, locked_by=NULL, locked_until=NULL, "
        "cooldown_until=? WHERE email=?",
        (reason, now_str, now_cd, email)
    )
    conn.commit()
    conn.close()
    logger.info(f"❌ [{email}] -> STATUS = 'DEAD' | Razon: {reason}")


async def main():
    from betmexico_login_service import make_pool
    from login_orchestrator import gentle_login

    accounts = get_target_accounts()
    logger.info(f"🚀 Iniciando verificación masiva en prod: {len(accounts)} cuentas LIVE encontradas.")

    cap_key = os.environ.get("CAPMONSTER_KEY", "")
    pool = make_pool(cap_key, size=2, workers=1)

    stats = {"live": 0, "dead": 0, "rate_limited": 0, "errors": 0, "skipped": 0}

    try:
        for idx, acc in enumerate(accounts, 1):
            email = acc["email"]
            pw = acc.get("password") or ""

            # Guard de RESERVADA_SA: no tocar cuentas SA
            locked_by = str(acc.get("locked_by") or "").lower()
            if not acc.get("published_to_pool") and locked_by in ("1341812706", "robertvs"):
                logger.info(f"[{idx}/{len(accounts)}] 🛡️ {email} (RESERVADA_SA) -> SKIP")
                stats["skipped"] += 1
                continue

            if not pw:
                logger.warning(f"[{idx}/{len(accounts)}] ⚠️ {email} (Sin password) -> SKIP")
                stats["skipped"] += 1
                continue

            logger.info(f"[{idx}/{len(accounts)}] 🔑 Probando login secuencial con proxy rotativo para: {email}...")

            try:
                res = await gentle_login(
                    email, pw,
                    max_login_retries=2,
                    throttle=True,
                    pool=pool,
                    use_cache=False,
                    allow_proxyless=False
                )

                if res.ok:
                    stats["live"] += 1
                    logger.info(f"[{idx}/{len(accounts)}] ✅ {email} -> LIVE (JWT valido)")
                elif res.code in ("RATE_LIMITED", "BAN", "429") or "RATE_LIMITED" in str(res.code):
                    stats["dead"] += 1
                    stats["rate_limited"] += 1
                    mark_account_dead(email, f"RATE_LIMITED ({res.code})")
                elif res.account_dead or res.code in ("LOGIN_DENIED", "KYC_PENDING", "AUTOEXCLUSION"):
                    stats["dead"] += 1
                    mark_account_dead(email, f"{res.code}")
                else:
                    stats["errors"] += 1
                    logger.warning(f"[{idx}/{len(accounts)}] ⚠️ {email} -> Estado no decisivo: {res.code}")

            except Exception as e:
                stats["errors"] += 1
                logger.error(f"[{idx}/{len(accounts)}] 💥 Excepcion en login para {email}: {e}")

            # Pausa de 1.5s entre logins para no ráfaguear BetMexico
            await asyncio.sleep(1.5)

    finally:
        try:
            await pool.stop()
        except Exception:
            pass

    logger.info(f"🏁 RESULTADO FINAL VERIFICACIÓN MASIVA: {stats}")


if __name__ == "__main__":
    asyncio.run(main())

"""scripts/verify_all_accounts_active.py — Verificación activa masiva de TODAS las cuentas.

Recorre todas las cuentas LIVE (o todas las cuentas en BD) una por una, usando
proxies rotativos (`gentle_login` con `use_cache=False`) para verificar su estado
real contra BetMexico.

Si la cuenta responde 429 (RATE_LIMITED), BAN, LOGIN_DENIED, KYC_PENDING o AUTOEXCLUSION,
la marca inmediatamente como status='DEAD' en la base de datos y libera sus locks.

Uso en KVM4:
  docker exec betmexico-web python scripts/verify_all_accounts_active.py
"""

import asyncio
import os
import sys
import time
import logging

# Asegurar path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("verify_all_accounts")


def get_all_target_accounts():
    import sqlite3
    db_path = os.environ.get("DB_PATH", "/data/betmexico_accounts.db")
    if not os.path.exists(db_path):
        db_path = "betmexico_accounts.db"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Traer todas las cuentas con status='LIVE' (excluyendo RESERVADA_SA para no tocar superadmin)
    rows = c.execute(
        "SELECT email, password, status, published_to_pool, locked_by FROM accounts WHERE status='LIVE'"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_account_dead(email: str, reason: str):
    import sqlite3
    db_path = os.environ.get("DB_PATH", "/data/betmexico_accounts.db")
    if not os.path.exists(db_path):
        db_path = "betmexico_accounts.db"

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        "UPDATE accounts SET status='DEAD', locked_by=NULL, locked_until=NULL, "
        "cooldown_until=? WHERE email=?",
        (int(time.time()) + 86400 * 30, email)
    )
    conn.commit()
    conn.close()
    logger.info(f"❌ Account {email} marked DEAD: {reason}")


async def verify_all():
    from betmexico_login_service import make_pool
    from login_orchestrator import gentle_login

    accounts = get_all_target_accounts()
    logger.info(f"🚀 Iniciando verificación masiva de {len(accounts)} cuentas...")

    cap_key = os.environ.get("CAPMONSTER_KEY", "")
    pool = make_pool(cap_key, size=2, workers=1)

    stats = {"live": 0, "dead": 0, "rate_limited": 0, "errors": 0}

    try:
        for idx, acc in enumerate(accounts, 1):
            email = acc["email"]
            pw = acc.get("password") or ""

            # Excepción RESERVADA_SA: no tocar cuentas bloqueadas por SA
            locked_by = str(acc.get("locked_by") or "").lower()
            if not acc.get("published_to_pool") and locked_by in ("1341812706", "robertvs"):
                logger.info(f"[{idx}/{len(accounts)}] 🛡️ {email} reservada SA - skip")
                continue

            if not pw:
                logger.warning(f"[{idx}/{len(accounts)}] {email} sin password - skip")
                continue

            logger.info(f"[{idx}/{len(accounts)}] Probando login para {email}...")

            try:
                # Login forzado sin cache (use_cache=False) usando proxy rotativo
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
                    logger.info(f"[{idx}/{len(accounts)}] ✅ {email} LIVE (JWT OK)")
                elif res.code in ("RATE_LIMITED", "BAN", "429"):
                    stats["dead"] += 1
                    stats["rate_limited"] += 1
                    mark_account_dead(email, f"RATE_LIMITED / {res.code}")
                elif res.account_dead or res.code in ("LOGIN_DENIED", "KYC_PENDING", "AUTOEXCLUSION"):
                    stats["dead"] += 1
                    mark_account_dead(email, res.code or "DEAD")
                else:
                    stats["errors"] += 1
                    logger.warning(f"[{idx}/{len(accounts)}] ⚠️ {email} resultado no decisivo: {res.code}")

            except Exception as e:
                stats["errors"] += 1
                logger.error(f"[{idx}/{len(accounts)}] ❌ Excepción en {email}: {e}")

            # Pequeña pausa entre logins para regular tráfico aggregate
            await asyncio.sleep(1.5)

    finally:
        try:
            await pool.stop()
        except Exception:
            pass

    logger.info(f"🏁 Verificación masiva finalizada: {stats}")


if __name__ == "__main__":
    asyncio.run(verify_all())

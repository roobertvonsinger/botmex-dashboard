"""mass_sweep.py — Barrido masivo PARALELO de todas las cuentas de la BD.

OBJETIVO:
  Determinar el estado real de TODAS las 948 cuentas intentando login fresco.
  Dos requisitos para LIVE:
    1. Login exitoso (JWT obtenido + balance_real).
    2. KYC verificado (kyc_verified=1 en los detalles de la cuenta).

SALIDAS:
  - Actualiza status / dead_reason / balance_real / kyc_verified en BD.
  - /tmp/mass_sweep_report.json — reporte completo con tally + detalle.
  - stdout — progreso en tiempo real.

CLASIFICACION DEAD (subcategorias):
  LIVE_FULL      -> Login OK + KYC OK  (los dos requisitos cumplidos)
  LIVE_NO_KYC    -> Login OK, balance obtenido, pero KYC faltante
  RATE_LIMITED   -> BetMexico devolvio 429 confirmado en 2 IPs
  LOGIN_DENIED   -> Credenciales invalidas / cuenta bloqueada
  AUTOEXCLUSION  -> Auto-exclusion activa
  LOGIN_FAILED   -> Agoto reintentos sin resultado claro
  EXCEPTION      -> Error inesperado durante el intento
  NO_PASSWORD    -> Sin contrasena en BD (skip)

USO (dentro del contenedor betmexico-web):
  # barrido completo TODAS las cuentas (default concurrency=8):
  docker exec betmexico-web python3 /app/scripts/mass_sweep.py --go

  # target: all / live / dead
  docker exec betmexico-web python3 /app/scripts/mass_sweep.py --target all --go

  # dry-run (solo lista, sin logins):
  docker exec betmexico-web python3 /app/scripts/mass_sweep.py --target all

  # ajustar paralelismo:
  docker exec betmexico-web python3 /app/scripts/mass_sweep.py --concurrency 12 --go
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import os
import sqlite3
import sys
import time
from typing import Any, Dict, List, Optional

DB_PATH = os.environ.get("BETMEX_DB", "/data/betmexico_accounts.db")
REPORT  = "/tmp/mass_sweep_report.json"

for _p in ("/app", "/app/web"):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ─────────────────────────── clasificacion ──────────────────────────────

def classify(res) -> str:
    if getattr(res, "ok", False) and getattr(res, "jwt", None):
        return "LIVE_OK"
    code = (getattr(res, "code", "") or "").upper()
    err  = (getattr(res, "error", "") or "").upper()
    if code == "RATE_LIMITED" or "429" in err or "RATE_LIMIT" in err:
        return "RATE_LIMITED"
    if code == "AUTOEXCLUSION" or "AUTOEXCLU" in err:
        return "AUTOEXCLUSION"
    if code in ("KYC_PENDING",) or ("KYC" in err and "PENDING" in err):
        return "KYC_PENDING"
    if getattr(res, "account_dead", False) or code in ("LOGIN_DENIED", "DEAD"):
        return "LOGIN_DENIED"
    if code == "LOGIN_FAILED":
        return "LOGIN_FAILED"
    return "OTHER"


def extract_kyc(res) -> bool:
    # Intentar desde raw_result["account_details"]["verified"] (fuente primaria)
    rr = getattr(res, "raw_result", None) or {}
    if isinstance(rr, dict):
        acct = rr.get("account_details") or {}
        if isinstance(acct, dict) and acct.get("verified"):
            return True
    # Fallback: details directos
    details = getattr(res, "details", None) or {}
    if not isinstance(details, dict):
        return False
    if details.get("verified") or details.get("kyc_verified") or details.get("HasFullValidation"):
        return True
    if int(details.get("kyc_docs_approved") or 0) >= 3:
        return True
    return False


def extract_balance(res):
    details = getattr(res, "details", None) or {}
    if not isinstance(details, dict):
        return 0.0, 0.0
    wallet = details.get("wallet")
    if isinstance(wallet, list):
        real = bonos = 0.0
        for w in wallet:
            amt = float(w.get("amount") or 0.0)
            if w.get("accountType") == 1:
                real = amt
            elif w.get("accountType") == 2:
                bonos = amt
        return real, bonos
    real  = float(details.get("balance_real") or details.get("Balance") or 0.0)
    bonos = float(details.get("balance_bonos") or 0.0)
    return real, bonos


# ─────────────────────────── BD ─────────────────────────────────────────

def _connect():
    con = sqlite3.connect(DB_PATH, timeout=30.0)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA busy_timeout=30000;")
    return con


def load_accounts(target: str) -> List[Dict]:
    con = _connect()
    where = {"all": "1=1", "live": "status='LIVE'", "dead": "status='DEAD'"}[target]
    rows = con.execute(
        f"""SELECT email, password, status, grade, kyc_verified, balance_real, dead_reason
              FROM accounts
             WHERE {where}
               AND password IS NOT NULL AND password <> ''
             ORDER BY RANDOM()"""
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def load_no_password(target: str) -> List[str]:
    con = _connect()
    where = {"all": "1=1", "live": "status='LIVE'", "dead": "status='DEAD'"}[target]
    rows = con.execute(
        f"SELECT email FROM accounts WHERE {where} AND (password IS NULL OR password='')"
    ).fetchall()
    con.close()
    return [r[0] for r in rows]


def write_result_db(email: str, verdict: str, res, bal_real: float,
                    bal_bonos: float, kyc: bool) -> None:
    con = _connect()
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    jwt = getattr(res, "jwt", None)
    jwt_exp = int(time.time()) + 86400 * 7

    if verdict == "LIVE_OK" and kyc:
        con.execute(
            """UPDATE accounts SET
                   status='LIVE', dead_reason=NULL, dead_at=NULL,
                   published_to_pool=CASE WHEN published_to_pool=0 AND locked_by IS NULL
                                          THEN 1 ELSE published_to_pool END,
                   kyc_verified=1,
                   balance_real=?, balance_bonos=?, balance_total=?,
                   jwt_token=COALESCE(?, jwt_token), jwt_expires_at=?,
                   last_checked_at=?
               WHERE LOWER(email)=LOWER(?)""",
            (bal_real, bal_bonos, bal_real + bal_bonos, jwt, jwt_exp, now, email))
    elif verdict == "LIVE_OK" and not kyc:
        con.execute(
            """UPDATE accounts SET
                   status='DEAD', dead_reason='NO_KYC', kyc_verified=0,
                   balance_real=?, balance_bonos=?, balance_total=?,
                   jwt_token=COALESCE(?, jwt_token), jwt_expires_at=?,
                   last_checked_at=?
               WHERE LOWER(email)=LOWER(?)""",
            (bal_real, bal_bonos, bal_real + bal_bonos, jwt, jwt_exp, now, email))
    elif verdict == "RATE_LIMITED":
        con.execute(
            """UPDATE accounts SET status='DEAD',
                   dead_reason='RATE_LIMITED_PERMANENT (429)',
                   published_to_pool=0, locked_by=NULL, locked_until=NULL,
                   last_checked_at=? WHERE LOWER(email)=LOWER(?)""",
            (now, email))
    elif verdict == "AUTOEXCLUSION":
        con.execute(
            """UPDATE accounts SET status='DEAD', dead_reason='AUTOEXCLUSION',
                   published_to_pool=0, last_checked_at=?
               WHERE LOWER(email)=LOWER(?)""", (now, email))
    elif verdict == "LOGIN_DENIED":
        con.execute(
            """UPDATE accounts SET status='DEAD', dead_reason='LOGIN_DENIED',
                   published_to_pool=0, last_checked_at=?
               WHERE LOWER(email)=LOWER(?)""", (now, email))
    else:
        con.execute(
            "UPDATE accounts SET last_checked_at=? WHERE LOWER(email)=LOWER(?)",
            (now, email))
    con.commit()
    con.close()


# ─────────────────────────── worker async ───────────────────────────────

async def sweep_one(acc: Dict, sem: asyncio.Semaphore, counters: Dict,
                    results: List, idx: int, total: int) -> None:
    email    = acc["email"]
    password = acc["password"]
    t0       = time.time()

    async with sem:
        try:
            from login_orchestrator import gentle_login
            res     = await gentle_login(
                email, password,
                max_login_retries=2,
                throttle=False,
                use_cache=False,
                allow_proxyless=False,
                attempt_timeout=40.0,
            )
            verdict   = classify(res)
            kyc       = extract_kyc(res)
            bal_real, bal_bonos = extract_balance(res)
            err_msg   = (getattr(res, "error", "") or "")[:120]

            report_verdict = verdict if verdict != "LIVE_OK" else (
                "LIVE_FULL" if kyc else "LIVE_NO_KYC")

        except Exception as exc:
            verdict = report_verdict = "EXCEPTION"
            err_msg = str(exc)[:160]
            kyc = False
            bal_real = bal_bonos = 0.0
            res = None

        elapsed = round(time.time() - t0, 1)

        if verdict not in ("EXCEPTION",) and res is not None:
            try:
                write_result_db(email, verdict, res,
                                float(bal_real or 0), float(bal_bonos or 0), kyc)
            except Exception as db_exc:
                print(f"  DB ERR [{email}]: {db_exc}")

        counters[report_verdict] = counters.get(report_verdict, 0) + 1

        ICONS = {
            "LIVE_FULL":     "✅",
            "LIVE_NO_KYC":   "🟡",
            "RATE_LIMITED":  "⛔",
            "LOGIN_DENIED":  "🔴",
            "AUTOEXCLUSION": "🚫",
            "LOGIN_FAILED":  "⚪",
            "EXCEPTION":     "💥",
        }
        icon    = ICONS.get(report_verdict, "❓")
        kyc_tag = f" KYC={'OK' if kyc else 'NO'}" if verdict == "LIVE_OK" else ""
        bal_tag = f" ${bal_real:.2f}" if verdict == "LIVE_OK" else ""

        total_done = sum(counters.values())
        print(f"  {icon} [{total_done:4d}/{total}] {email[:40]:40s}"
              f" -> {report_verdict}{kyc_tag}{bal_tag}  ({elapsed}s)")

        results.append({
            "email"     : email,
            "status_pre": acc["status"],
            "grade"     : acc.get("grade"),
            "verdict"   : report_verdict,
            "kyc"       : kyc,
            "bal_real"  : float(bal_real or 0),
            "elapsed"   : elapsed,
            "error"     : err_msg,
        })


# ─────────────────────────── main ───────────────────────────────────────

async def run_sweep(accounts, concurrency):
    sem      = asyncio.Semaphore(concurrency)
    counters: Dict[str, int] = {}
    results:  List[Dict]     = []
    total    = len(accounts)
    await asyncio.gather(*(
        sweep_one(acc, sem, counters, results, idx, total)
        for idx, acc in enumerate(accounts, 1)
    ))
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target",      choices=["all","live","dead"], default="all")
    ap.add_argument("--concurrency", type=int, default=20)
    ap.add_argument("--go",          action="store_true")
    args = ap.parse_args()

    accounts   = load_accounts(args.target)
    no_pw_list = load_no_password(args.target)
    total      = len(accounts) + len(no_pw_list)

    print(f"\n{'='*65}")
    print(f"  MASS SWEEP  target={args.target}  total={total}")
    print(f"  Con clave: {len(accounts)}  |  Sin clave: {len(no_pw_list)}")
    print(f"  Concurrencia: {args.concurrency}  |  Modo: {'REAL' if args.go else 'DRY-RUN'}")
    print(f"{'='*65}\n")

    if not args.go:
        for i, acc in enumerate(accounts, 1):
            print(f"  [{i:4d}/{len(accounts)}] {acc['email'][:48]:48s}"
                  f" {acc['status']} grade={acc.get('grade','?')}")
        print(f"\n  SIN CLAVE: {len(no_pw_list)}")
        print("  (dry-run — agrega --go para ejecutar)\n")
        return

    ts = time.time()
    results = asyncio.run(run_sweep(accounts, args.concurrency))

    tally: Dict[str,int] = {}
    for r in results:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1

    elapsed = round(time.time() - ts, 1)
    ORDER = ["LIVE_FULL","LIVE_NO_KYC","RATE_LIMITED","LOGIN_DENIED",
             "AUTOEXCLUSION","LOGIN_FAILED","EXCEPTION","OTHER"]

    print(f"\n{'='*65}")
    print(f"  RESULTADO FINAL — {len(results)} cuentas en {elapsed}s")
    print(f"{'='*65}")
    for k in ORDER:
        if k in tally:
            print(f"  {k:20s} {tally[k]:4d}")
    for k, v in tally.items():
        if k not in ORDER:
            print(f"  {k:20s} {v:4d}")
    if no_pw_list:
        print(f"  {'NO_PASSWORD':20s} {len(no_pw_list):4d}")

    live_full = [r for r in results if r["verdict"] == "LIVE_FULL"]
    live_nokw = [r for r in results if r["verdict"] == "LIVE_NO_KYC"]
    print(f"\n  LIVE REALES (login+balance+KYC): {len(live_full)}")
    for r in sorted(live_full, key=lambda x: -x["bal_real"])[:25]:
        print(f"     {r['email'][:42]:42s} ${r['bal_real']:.2f}  grade={r['grade']}")
    if len(live_full) > 25:
        print(f"     ... (+{len(live_full)-25} mas)")

    print(f"\n  LIVE sin KYC (login OK, KYC pendiente): {len(live_nokw)}")

    report = {
        "ts": datetime.datetime.utcnow().isoformat(),
        "target": args.target,
        "concurrency": args.concurrency,
        "elapsed_s": elapsed,
        "total": total,
        "no_password": no_pw_list,
        "tally": tally,
        "results": results,
    }
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n  Reporte -> {REPORT}")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    main()



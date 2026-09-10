"""rescue_429.py — Reconciliación de cuentas mass-killed por scripts/update_429.py.

CONTEXTO (docs/ERRORS.md):
  scripts/update_429.py (script manual huérfano, ya eliminado) hacía
  `UPDATE accounts SET status='DEAD' WHERE dead_reason LIKE '%429%' AND status='LIVE'`
  sin re-verificar. Corrió 2026-08-28 (→96 "cuarentena") y 2026-09-04 (→65 "sep_429").
  Contradice la regla canónica de `deposits._mark_rate_limited_dead` (Robert 2026-09-04):
  un 429 NO marca status='DEAD', solo published_to_pool=0.

  Sonda 2026-09-10 (scratchpad/probe_rlp.py): la cohorte "cuarentena" recupera
  ~67% al re-loguear; "bloqueo_ago" y "sep_429" siguen en 429 real.

QUÉ HACE:
  Re-loguea (concurrency 1, gap configurable, max_login_retries=1) un lote de
  cuentas DEAD con dead_reason que menciona 429. Las que entran LIMPIO (LIVE + JWT)
  se resucitan a status='LIVE', published_to_pool=1, dead_reason/dead_at NULL y se
  les recalcula grade V10 (mismo path que saneador_daemon.audit_single_account).
  Las que siguen 429 / DEAD real se dejan intactas.

  Circuit breaker: N (default 3) STILL_429 consecutivos abortan el lote — a partir
  de ahí cada intento es gasto de captcha puro.

USO (dentro del contenedor betmexico-web):
  docker exec betmexico-web python3 /app/scripts/rescue_429.py --cohort cuarentena --limit 30 --gap 22          # dry-run
  docker exec betmexico-web python3 /app/scripts/rescue_429.py --cohort cuarentena --limit 30 --gap 22 --go     # ejecuta

Salida: /tmp/rescue_429_report.json + resumen a stdout.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import os
import random
import sqlite3
import time

DB_PATH = os.environ.get("BETMEX_DB", "/data/betmexico_accounts.db")

# dead_reason LIKE por cohorte (ver forense docs/ERRORS.md / memoria 549)
COHORTS = {
    "cuarentena": "RATE_LIMITED_PERMANENT (429 previo — enfriamiento en cuarent%",
    "bloqueo_ago": "RATE_LIMITED_PERMANENT (429 — BetMexico bloqueó la cuenta)",
    "sep_429": "RATE_LIMITED_PERMANENT (429)",
    "any429": "%429%",
}


# ─────────────────────────── lógica pura (testeada) ───────────────────────────

def classify(res) -> str:
    """Clasifica un LoginResult de gentle_login."""
    if getattr(res, "ok", False) and getattr(res, "jwt", None):
        return "LIVE_LIMPIO"
    code = (getattr(res, "code", "") or "").upper()
    err = (getattr(res, "error", "") or "").upper()
    if code == "RATE_LIMITED" or "429" in err or "RATE_LIMIT" in err:
        return "STILL_429"
    if code == "AUTOEXCLUSION" or "AUTOEXCLU" in err:
        return "AUTOEXCLUSION"
    if code in ("KYC_PENDING",) or "KYC" in err:
        return "KYC"
    if getattr(res, "account_dead", False) or code in ("LOGIN_DENIED", "DEAD"):
        return "DEAD_REAL"
    return "OTRO"


def decide_action(verdict: str) -> str:
    """Solo un login LIMPIO (LIVE + JWT) justifica resucitar la cuenta."""
    return "resurrect" if verdict == "LIVE_LIMPIO" else "keep_dead"


class CircuitBreaker:
    """Corta el lote tras `threshold` STILL_429 consecutivos."""

    def __init__(self, threshold: int = 3):
        self.threshold = threshold
        self.streak = 0
        self.tripped = False

    def record(self, verdict: str) -> None:
        if verdict == "STILL_429":
            self.streak += 1
            if self.streak >= self.threshold:
                self.tripped = True
        else:
            self.streak = 0


# ─────────────────────────────── I/O (no testeado) ───────────────────────────

def _connect():
    con = sqlite3.connect(DB_PATH, timeout=30.0)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout = 30000;")
    return con


def _pick(con, like: str, limit: int):
    return con.execute(
        """SELECT email, password, grade, dead_at, balance_total
             FROM accounts
            WHERE status='DEAD' AND dead_reason LIKE ?
              AND password IS NOT NULL AND password <> ''
            ORDER BY RANDOM() LIMIT ?""",
        (like, limit),
    ).fetchall()


def _resurrect(con, email: str, res) -> dict:
    """Devuelve la cuenta al pool. Recalcula grade V10 con las txns frescas si
    el LoginResult trae detalles (mismo criterio que saneador_daemon)."""
    details = getattr(res, "details", None) or {}
    wallet = details.get("wallet") if isinstance(details, dict) else None
    bal_real = bal_bonos = 0.0
    if isinstance(wallet, list):
        for w in wallet:
            amt = float(w.get("amount") or 0.0)
            if w.get("accountType") == 1:
                bal_real = amt
            elif w.get("accountType") == 2:
                bal_bonos = amt

    grade = score = None
    try:
        import sys
        for p in ("/app", "/app/web"):
            if p not in sys.path:
                sys.path.insert(0, p)
        from betmexico_payment_analyzer import score_payment_readiness
        txns = (details.get("transactions") or {}).get("items") if isinstance(details, dict) else None
        if txns is not None:
            for t in txns:
                con.execute(
                    """INSERT OR IGNORE INTO account_transactions
                       (account_email, txn_id, txn_date, txn_type, gateway, status, amount)
                       VALUES (?,?,?,?,?,?,?)""",
                    (email, str(t.get("id") or t.get("txn_id") or ""),
                     str(t.get("date") or t.get("txn_date") or ""),
                     int(t.get("type") or t.get("txn_type") or 1),
                     int(t.get("gateway") or 1), int(t.get("status") or 0),
                     float(t.get("amount") or 0.0)),
                )
            db_txns = con.execute(
                "SELECT txn_date,status,txn_type,gateway,amount FROM account_transactions "
                "WHERE LOWER(account_email)=LOWER(?) ORDER BY txn_date DESC", (email,)
            ).fetchall()
            sc = score_payment_readiness(
                {"transactions": {"fetched": True, "items": [dict(x) for x in db_txns],
                                  "total_rows": len(db_txns)}})
            if sc:
                grade, score = sc["grade"].upper(), sc["score"]
    except Exception as e:  # recálculo best-effort
        print(f"    (grade recalc skip {email}: {e})")

    now_epoch = int(time.time())
    con.execute(
        """UPDATE accounts SET
               status='LIVE', dead_reason=NULL, dead_at=NULL,
               published_to_pool=1, locked_by=NULL, locked_until=NULL,
               jwt_token=COALESCE(?, jwt_token),
               jwt_expires_at=?,
               balance_real=?, balance_bonos=?, balance_total=?,
               grade=COALESCE(?, grade), grade_score=COALESCE(?, grade_score),
               last_checked_at=datetime('now')
           WHERE LOWER(email)=LOWER(?)""",
        (getattr(res, "jwt", None), now_epoch + 86400 * 7,
         bal_real, bal_bonos, bal_real + bal_bonos, grade, score, email),
    )
    con.commit()
    return {"grade": grade, "score": score, "bal_real": bal_real}


async def _run(sample, gap: float, breaker_threshold: int):
    import sys
    for p in ("/app", "/app/web"):
        if p not in sys.path:
            sys.path.insert(0, p)
    from login_orchestrator import gentle_login

    cb = CircuitBreaker(threshold=breaker_threshold)
    con = _connect()
    out = []
    for i, s in enumerate(sample, 1):
        t0 = time.time()
        try:
            r = await gentle_login(s["email"], s["password"], use_cache=False,
                                   max_login_retries=1, throttle=True, allow_proxyless=False)
            verdict = classify(r)
            rec = {"cohort": s["cohort"], "email": s["email"], "grade_old": s["grade"],
                   "verdict": verdict, "action": decide_action(verdict),
                   "code": getattr(r, "code", ""), "error": (getattr(r, "error", "") or "")[:120],
                   "secs": round(time.time() - t0, 1)}
            if rec["action"] == "resurrect":
                rec["resurrect"] = _resurrect(con, s["email"], r)
        except Exception as e:
            verdict = "EXC"
            rec = {"cohort": s["cohort"], "email": s["email"], "verdict": "EXC",
                   "action": "keep_dead", "error": str(e)[:160], "secs": round(time.time() - t0, 1)}
        out.append(rec)
        cb.record(verdict)
        print(f"  [{i:2d}/{len(sample)}] {s['email'][:38]:38s} -> {verdict}"
              f"{'  ✅ RESUCITADA' if rec['action'] == 'resurrect' else ''}")
        if cb.tripped:
            print(f"\n🛑 CIRCUIT BREAKER: {breaker_threshold} STILL_429 consecutivos. Aborto lote "
                  f"({i}/{len(sample)} procesadas).")
            break
        if i < len(sample):
            await asyncio.sleep(gap + random.uniform(0, 3))
    con.close()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cohort", choices=sorted(COHORTS), default="cuarentena")
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--gap", type=float, default=22.0)
    ap.add_argument("--breaker", type=int, default=3, help="STILL_429 consecutivos que abortan el lote")
    ap.add_argument("--go", action="store_true")
    args = ap.parse_args()

    con = _connect()
    rows = _pick(con, COHORTS[args.cohort], args.limit)
    con.close()
    sample = [{"cohort": args.cohort, "email": r["email"], "password": r["password"],
               "grade": r["grade"], "dead_at": r["dead_at"], "bal": r["balance_total"]}
              for r in rows]

    print(f"== rescue_429  cohort={args.cohort}  n={len(sample)}  gap={args.gap}s  breaker={args.breaker} ==")
    for s in sample:
        print(f"  {s['email'][:40]:40s} g={s['grade'] or '?':3s} dead={s['dead_at']} bal={s['bal']}")

    if not args.go:
        print("\n(dry-run — agrega --go para ejecutar logins reales y resucitar)")
        return

    out = asyncio.run(_run(sample, args.gap, args.breaker))

    tally, actions = {}, {"resurrect": 0, "keep_dead": 0}
    for o in out:
        tally[o["verdict"]] = tally.get(o["verdict"], 0) + 1
        actions[o["action"]] = actions.get(o["action"], 0) + 1
    report = {"ts": datetime.datetime.utcnow().isoformat(), "cohort": args.cohort,
              "n": len(out), "gap_s": args.gap, "tally": tally, "actions": actions, "results": out}
    with open("/tmp/rescue_429_report.json", "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n== TALLY ==")
    for k, v in sorted(tally.items(), key=lambda x: -x[1]):
        print(f"  {k:16s} {v}")
    print(f"\n  RESUCITADAS: {actions['resurrect']}   ·   dejadas DEAD: {actions['keep_dead']}")
    print("  reporte -> /tmp/rescue_429_report.json")


if __name__ == "__main__":
    main()

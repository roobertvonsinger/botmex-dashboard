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
  se resucitan a status='LIVE', published_to_pool=1, dead_reason/dead_at NULL con
  JWT + balances frescos (el grade lo recalcula account_refresh / saneador_daemon
  en su propio ciclo — la cuenta conserva el grade previo mientras tanto).
  Las que siguen 429 / DEAD real se dejan intactas.

  Circuit breaker: N (default 3) STILL_429 consecutivos abortan el lote — a partir
  de ahí cada intento es gasto de captcha puro.

COHORTES:
  cuarentena / bloqueo_ago / sep_429 / any429 — DEAD con 429 en dead_reason.
  sin_reason — 85 DEAD sin dead_reason NI dead_at (path desconocido, no son 429).
               $6,281 en balance, 33 grade A KYC=1 — la cohorte con dinero real.

USO (dentro del contenedor betmexico-web):
  docker exec betmexico-web python3 /app/scripts/rescue_429.py --cohort cuarentena --limit 30 --gap 22          # dry-run
  docker exec betmexico-web python3 /app/scripts/rescue_429.py --cohort cuarentena --limit 30 --gap 22 --go     # ejecuta
  docker exec betmexico-web python3 /app/scripts/rescue_429.py --cohort sin_reason --limit 90 --gap 22 --go     # barre las 85

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

# Cohortes de cuentas DEAD a reconciliar (ver forense docs/ERRORS.md / memoria 549).
# Valor = patrón para `dead_reason LIKE`; el sentinel None = `dead_reason IS NULL`.
COHORTS = {
    "cuarentena": "RATE_LIMITED_PERMANENT (429 previo — enfriamiento en cuarent%",
    "bloqueo_ago": "RATE_LIMITED_PERMANENT (429 — BetMexico bloqueó la cuenta)",
    "sep_429": "RATE_LIMITED_PERMANENT (429)",
    "any429": "%429%",
    # 85 cuentas DEAD sin dead_reason NI dead_at (path desconocido, no son 429).
    # $6,281 en balance, 33 grade A KYC=1 — la cohorte con dinero real.
    "sin_reason": None,
}


def cohort_where(cohort: str):
    """(fragmento SQL, params) para el WHERE de la cohorte. `sin_reason` (sentinel
    None) exige dead_reason IS NULL AND dead_at IS NULL — no matchea ningún LIKE."""
    pat = COHORTS[cohort]
    if pat is None:
        return "dead_reason IS NULL AND dead_at IS NULL", ()
    return "dead_reason LIKE ?", (pat,)


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


def _pick(con, cohort: str, limit: int):
    where_frag, where_params = cohort_where(cohort)
    return con.execute(
        f"""SELECT email, password, grade, dead_at, balance_total
             FROM accounts
            WHERE status='DEAD' AND {where_frag}
              AND password IS NOT NULL AND password <> ''
            ORDER BY RANDOM() LIMIT ?""",
        (*where_params, limit),
    ).fetchall()


def _resurrect(con, email: str, res) -> dict:
    """Devuelve la cuenta al pool con JWT + balances frescos. NO recalcula grade:
    eso es responsabilidad de account_refresh / saneador_daemon (loop propio) — la
    cuenta conserva su grade previo hasta el siguiente ciclo. El grade viejo es una
    aproximación válida y `select_accounts_for_auto` maneja cualquier grade."""
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

    now_epoch = int(time.time())
    con.execute(
        """UPDATE accounts SET
               status='LIVE', dead_reason=NULL, dead_at=NULL,
               published_to_pool=1, locked_by=NULL, locked_until=NULL,
               jwt_token=COALESCE(?, jwt_token),
               jwt_expires_at=?,
               balance_real=?, balance_bonos=?, balance_total=?,
               last_checked_at=datetime('now')
           WHERE LOWER(email)=LOWER(?)""",
        (getattr(res, "jwt", None), now_epoch + 86400 * 7,
         bal_real, bal_bonos, bal_real + bal_bonos, email),
    )
    con.commit()
    return {"bal_real": bal_real, "grade_recalc": "deferred_to_account_refresh"}


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
    rows = _pick(con, args.cohort, args.limit)
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

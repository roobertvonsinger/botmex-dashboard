#!/usr/bin/env python3
"""
Recalcula grade/grade_score de TODAS las cuentas usando el analyzer V10.

Lee las transacciones desde `account_transactions` (lo que ya está en BD) — no
hace requests a BetMexico API. Útil después de cambiar el algoritmo del analyzer
o cuando se sospecha que la BD quedó desactualizada.

Uso (dentro del container web en KVM4):
    docker exec betmexico-web python /tmp/recalc_grades.py
"""
from __future__ import annotations
import argparse
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


def _import_analyzer():
    """Importa el analyzer V10 desde shared/ (preferido) o desde el path del bot."""
    here = Path(__file__).resolve().parent
    # IMPORTANTE: /tmp tiene prioridad — es donde se copia la versión nueva
    # para probarla antes de deployar a /app/. Si /app/ tiene una versión vieja
    # del bot, no la queremos para el recalc.
    candidates = [
        Path("/tmp/betmexico_payment_analyzer.py"),                # carga ad-hoc (prioridad)
        here.parent / "shared" / "betmexico_payment_analyzer.py",  # dev local
        Path("/app/web/shared/betmexico_payment_analyzer.py"),     # KVM4 (si se monta)
        Path("/app/betmexico_payment_analyzer.py"),                # KVM4 (fallback bot)
    ]
    for p in candidates:
        if p.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location("analyzer_v10", str(p))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    sys.exit("No encuentro betmexico_payment_analyzer.py")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/data/betmexico_accounts.db")
    ap.add_argument("--dry-run", action="store_true", help="No escribe BD, solo reporta")
    ap.add_argument("--only-status", default=None, help="Filtrar por status (LIVE/DEAD/etc)")
    args = ap.parse_args()

    analyzer = _import_analyzer()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    where = ""
    params: tuple = ()
    if args.only_status:
        where = "WHERE status = ?"
        params = (args.only_status,)
    accts = conn.execute(
        f"SELECT id, email, password, grade, grade_score, status FROM accounts {where}",
        params
    ).fetchall()

    grade_before: Counter = Counter()
    grade_after: Counter = Counter()
    changed = []
    no_txns = 0
    errors = 0
    updates = 0

    now = datetime.now()

    for a in accts:
        grade_before[a["grade"] or "?"] += 1
        try:
            txns = [dict(r) for r in conn.execute(
                "SELECT txn_date, status, txn_type, gateway, amount "
                "FROM account_transactions WHERE LOWER(account_email)=LOWER(?) "
                "ORDER BY txn_date DESC", (a["email"],)
            ).fetchall()]
            if not txns:
                no_txns += 1
                grade_after["?"] += 1
                continue
            details = {"transactions": {"fetched": True, "items": txns, "total_rows": len(txns)}}
            score = analyzer.score_payment_readiness(details)
            if not score:
                grade_after["?"] += 1
                continue
            new_grade = score["grade"]
            new_pts = score["score"]
            grade_after[new_grade] += 1

            if a["grade"] != new_grade or (a["grade_score"] or 0) != new_pts:
                changed.append({
                    "id": a["id"], "email": a["email"],
                    "from": f"{a['grade']}/{a['grade_score']}",
                    "to": f"{new_grade}/{new_pts}",
                    "reason": [f for f in score["flags"] if f.startswith("V10_")],
                })
                if not args.dry_run:
                    conn.execute(
                        "UPDATE accounts SET grade=?, grade_score=? WHERE id=?",
                        (new_grade, new_pts, a["id"])
                    )
                    updates += 1
        except Exception as e:
            errors += 1
            print(f"ERR {a['email']}: {e}", file=sys.stderr)

    if not args.dry_run:
        conn.commit()

    print(f"\n=== Resumen ===")
    print(f"Total cuentas:       {len(accts)}")
    print(f"Sin transacciones:   {no_txns}  (grade no recalculado)")
    print(f"Cambiaron grade:     {len(changed)}")
    print(f"Errores:             {errors}")
    print(f"BD actualizada:      {updates}  ({'DRY RUN' if args.dry_run else 'COMMIT'})")
    print(f"\nDistribución ANTES:  {dict(sorted(grade_before.items()))}")
    print(f"Distribución AHORA:  {dict(sorted(grade_after.items()))}")

    if changed and args.dry_run:
        print("\nPrimeros 20 cambios:")
        for c in changed[:20]:
            print(f"  {c['email']:50}  {c['from']:>8} → {c['to']:<8}  {c['reason']}")


if __name__ == "__main__":
    main()

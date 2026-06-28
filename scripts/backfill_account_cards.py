#!/usr/bin/env python3
"""Backfill de account_cards desde deposit_attempts aprobadas.

Recorre TODAS las `deposit_attempts` con status='approved' y card_pipe, extrae la
tarjeta (mismo `_parse_pipe` que deposits.py) y la registra en `account_cards` para
la cuenta que aprobó — idempotente (UNIQUE card_number, INSERT OR IGNORE).

Por qué: el fix de persistencia de tarjetas (2026-05-25, en `_record_attempt`) solo
aplicó HACIA ADELANTE. Las aprobadas históricas (antes del fix) quedaron sin tarjeta
en `account_cards`, aunque sí en `deposit_attempts.card_pipe`. Esto las recupera.

Ejecución (dentro del container, con la BD montada en /data):
    # DRY-RUN (no escribe, solo reporta):
    docker exec -i betmexico-web python3 - < scripts/backfill_account_cards.py
    # APLICAR (escribe; HACER BACKUP ANTES):
    docker exec -i -e BACKFILL_APPLY=1 betmexico-web python3 - < scripts/backfill_account_cards.py

Backup previo (no-negociable):
    docker exec betmexico-web sh -c 'mkdir -p /data/backups && cp /data/betmexico_accounts.db /data/backups/accounts-pre-backfill-$(date +%Y%m%d-%H%M%S).db'

Trazabilidad: las filas insertadas llevan `registered_by_name = "<operador> (backfill)"`
y `registered_at` = la fecha REAL de la aprobación (no la del backfill). No inventa
ningún dato: cada tarjeta sale 1:1 del card_pipe real de un intento aprobado.

Ejecutado en prod 2026-06-28: 3 tarjetas recuperadas (gap 3→0). Ver docs/ERRORS.md.
"""
import os
import sqlite3

DB = os.environ.get("BETMEX_DB", "/data/betmexico_accounts.db")
APPLY = os.environ.get("BACKFILL_APPLY") == "1"


def _parse_pipe(pipe):
    """VERBATIM de deposits.py `_parse_pipe`. Acepta:
      NUM|MMYY|CVV · NUM|MM/YY|CVV · NUM|MM|YY|CVV (o YYYY). Retorna (num, "MM/YY", cvv)."""
    parts = [p.strip() for p in (pipe or "").replace(" ", "").split("|") if p.strip()]
    if len(parts) == 3:
        ccnum, exp, cvv = parts
        if "/" in exp:
            return ccnum, exp, cvv
        if len(exp) == 4:
            return ccnum, f"{exp[:2]}/{exp[2:]}", cvv
        if len(exp) == 6:
            return ccnum, f"{exp[:2]}/{exp[4:]}", cvv
        raise ValueError("Vencimiento invalido (usa MMYY)")
    if len(parts) == 4:
        return parts[0], f"{parts[1]}/{parts[2][-2:]}", parts[3]
    raise ValueError("Formato pipe invalido. Usa: numero|MMYY|CVV")


def _roster():
    """telegram_id -> nombre de operador (best-effort, no rompe si falla el import)."""
    try:
        import sys
        sys.path.insert(0, "/app/web")
        sys.path.insert(0, "/app")
        from web_auth import WEB_USERS_RAW
        return {int(u["telegram_id"]): name
                for name, u in WEB_USERS_RAW.items() if u.get("telegram_id")}
    except Exception as e:
        print(f"(roster no disponible, uso id crudo): {e}")
        return {}


def main():
    roster = _roster()
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    rows = c.execute(
        """SELECT account_email AS email, card_pipe AS pipe, MAX(created_at) AS last,
                  (SELECT operator_id FROM deposit_attempts d2
                   WHERE d2.account_email=da.account_email AND d2.card_pipe=da.card_pipe
                     AND lower(d2.status)='approved' ORDER BY created_at DESC LIMIT 1) AS op
           FROM deposit_attempts da
           WHERE lower(status)='approved' AND card_pipe LIKE '%|%'
           GROUP BY account_email, card_pipe"""
    ).fetchall()

    ins = skip = err = 0
    print(f"MODE = {'APPLY' if APPLY else 'DRY-RUN'} | parejas approved: {len(rows)}")
    for r in rows:
        email, pipe, op, last = r["email"], r["pipe"], (r["op"] or 0), r["last"]
        try:
            cc_num, cc_exp, cc_cvv = _parse_pipe(pipe)
        except Exception as e:
            err += 1
            print(f"  PARSE-ERR {email} {pipe!r}: {e}")
            continue
        acc = c.execute("SELECT password FROM accounts WHERE email=?", (email,)).fetchone()
        if not acc:
            skip += 1
            print(f"  NO-ACCOUNT (huerfana) {email}")
            continue
        if c.execute("SELECT 1 FROM account_cards WHERE card_number=?", (cc_num,)).fetchone():
            skip += 1
            continue
        op_name = roster.get(int(op)) if op else None
        rbn = f"{op_name} (backfill)" if op_name else "backfill"
        if APPLY:
            cur = c.execute(
                """INSERT OR IGNORE INTO account_cards
                   (card_number, card_expiry, card_cvv, account_email, account_password,
                    registered_by, registered_by_name, registered_at, status)
                   VALUES (?,?,?,?,?,?,?,?, 'ACTIVE')""",
                (cc_num, cc_exp, cc_cvv, email, acc["password"] or "",
                 int(op) if op else 0, rbn, last),
            )
            ok = cur.rowcount > 0
            print(f"  INSERT {email} | {cc_num} {cc_exp} | by={rbn} at={last} -> {'OK' if ok else 'IGNORED'}")
            ins += 1 if ok else 0
            skip += 0 if ok else 1
        else:
            print(f"  WOULD-INSERT {email} | {cc_num} {cc_exp} | by={rbn} at={last}")
            ins += 1
    if APPLY:
        c.commit()
    print(f"\n== {'APPLIED' if APPLY else 'DRY-RUN'}: "
          f"{'inserted' if APPLY else 'would_insert'}={ins} skipped={skip} errors={err} ==")


if __name__ == "__main__":
    main()

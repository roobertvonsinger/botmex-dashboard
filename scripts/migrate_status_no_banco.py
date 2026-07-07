"""Migración retroactiva — reclasificar los `status='rejected'` FALSOS (no-banco).

Bug 2026-07-06 (ver docs/ERRORS.md): rate-limit (429), autoexclusión, login/captcha,
gateway y timeout se persistían con status='rejected' = "Rechazado (banco)" en la UI
y contaban como rechazo del BIN en bin_stats. La causa raíz ya está corregida en
`deposits.classify_deposit_status` (hacia adelante). Este script limpia los registros
VIEJOS, reclasificándolos por el TEXTO del `rejection_reason` — la única señal que
queda en la data histórica.

CONSERVADOR: solo reetiqueta lo que casa con un patrón no-banco de ALTA confianza.
Ante duda, un registro se QUEDA como 'rejected' (nunca borra un rechazo real de banco).
Idempotente: correr N veces = correr 1 vez.

Uso (en el VPS, dentro del contenedor betmexico-web):
    BETMEX_DB=/data/betmexico.db python scripts/migrate_status_no_banco.py
Hace backup del archivo .db antes de tocar nada.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone

# (needles sobre LOWER(rejection_reason), nuevo_status). Orden = prioridad ante
# solape. Espejo de deposits.classify_deposit_status pero por texto, no por code.
_RULES = [
    (["rate-limit", "rate_limited", "rate limit", "429"], "rate_limited"),
    (["autoexclu", "kyc", "login_denied"], "account_dead"),
    (["login_failed", "captcha", "deps_missing"], "login_lost"),
    (["begin_error", "payment_error", "gateway de pagos", "no responde"], "gateway_error"),
    (["timeout"], "timeout"),
    (["submit_error", "unknown_txn_status"], "ambiguous"),
    (["cancellederror", "velocity_skip"], "incomplete"),
]


def reclassify(con: sqlite3.Connection) -> dict:
    """Reetiqueta status='rejected' no-banco → su status real, por el reason.

    Devuelve conteos por categoría migrada + 'total'. NO toca rechazos reales de
    banco ni approved/threeds. Idempotente (solo mira filas aún 'rejected')."""
    counts: dict = {}
    total = 0
    for needles, new_status in _RULES:
        like = " OR ".join(["LOWER(COALESCE(rejection_reason,'')) LIKE ?"] * len(needles))
        params = [f"%{n}%" for n in needles]
        cur = con.execute(
            f"UPDATE deposit_attempts SET status=? "
            f"WHERE LOWER(status)='rejected' AND ({like})",
            [new_status, *params],
        )
        counts[new_status] = counts.get(new_status, 0) + cur.rowcount
        total += cur.rowcount
    con.commit()
    counts["total"] = total
    return counts


def _main() -> int:
    db_path = os.environ.get("BETMEX_DB") or "/data/betmexico.db"
    if not os.path.exists(db_path):
        print(f"[migrate] BD no encontrada: {db_path}", file=sys.stderr)
        return 1
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    bak = f"{db_path}.bak-{stamp}"
    shutil.copy2(db_path, bak)
    print(f"[migrate] Backup: {bak}")
    con = sqlite3.connect(db_path)
    try:
        res = reclassify(con)
    finally:
        con.close()
    print(f"[migrate] Reclasificados (no-banco sacados de 'rejected'): {res}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

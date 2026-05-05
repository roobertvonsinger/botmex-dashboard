#!/usr/bin/env python3
# BetMexico Web v2 — minimal dashboard sobre la BD existente.
# Lee betmexico_accounts.db (la misma que el bot TG). Sin lógica de polling.

from __future__ import annotations
import sqlite3, os
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).parent
STATIC = ROOT / "static"

# La BD vive donde corre el bot. Local: usa ENV BETMEX_DB. VPS: /opt/betmexico/bot/betmexico_accounts.db
DB_PATH = Path(os.environ.get("BETMEX_DB", str(ROOT.parent / "Telegram" / "betmexico_accounts.db")))

app = FastAPI(title="Botmexico v2")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


def db():
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    try:
        with db() as c:
            n = c.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        return {"ok": True, "db": str(DB_PATH), "accounts": n}
    except Exception as e:
        return JSONResponse({"ok": False, "db": str(DB_PATH), "error": str(e)}, status_code=500)


@app.get("/api/accounts")
def list_accounts(
    status: str = Query("LIVE"),
    grade: Optional[str] = None,
    limit: int = Query(200, le=1000),
):
    where, params = [], []
    if status != "all":
        where.append("status = ?"); params.append(status)
    if grade:
        where.append("grade = ?"); params.append(grade)
    sql = (
        "SELECT id, email, password, balance_total, balance_real, "
        "last_deposit_amount, last_deposit_date, status, grade, "
        "locked_by, locked_at, last_checked_at, check_count "
        "FROM accounts"
    )
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY balance_total DESC, last_checked_at DESC LIMIT ?"
    params.append(limit)
    with db() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


@app.get("/api/stats")
def stats():
    with db() as c:
        live = c.execute("SELECT COUNT(*) FROM accounts WHERE status='LIVE'").fetchone()[0]
        total = c.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        balance = c.execute("SELECT COALESCE(SUM(balance_total),0) FROM accounts WHERE status='LIVE'").fetchone()[0]
        with_balance = c.execute("SELECT COUNT(*) FROM accounts WHERE status='LIVE' AND balance_total > 0").fetchone()[0]
        in_use = c.execute("SELECT COUNT(*) FROM accounts WHERE locked_by IS NOT NULL").fetchone()[0]
    return {"live": live, "total": total, "totalBalance": balance, "withBalance": with_balance, "inUse": in_use}


if __name__ == "__main__":
    import uvicorn
    print(f"BD: {DB_PATH} (existe: {DB_PATH.exists()})")
    uvicorn.run(app, host="127.0.0.1", port=5001)

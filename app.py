#!/usr/bin/env python3
# BetMexico Web v2 — minimal dashboard sobre la BD existente.
# Lee betmexico_accounts.db (la misma que el bot TG). Sin lógica de polling.

from __future__ import annotations
import sqlite3, os
import json as _json
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).parent
STATIC = ROOT / "static"

# Load .env (manual mini-parser, no extra deps)
_env_file = ROOT / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _s = _line.strip()
        if not _s or _s.startswith("#") or "=" not in _s:
            continue
        _k, _v = _s.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

# La BD vive donde corre el bot. Local: usa ENV BETMEX_DB. VPS: /opt/betmexico/bot/betmexico_accounts.db
DB_PATH = Path(os.environ.get("BETMEX_DB", str(ROOT.parent / "Telegram" / "betmexico_accounts.db")))


@contextmanager
def db(write: bool = False):
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    if write:
        conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        if write:
            conn.commit()
    except Exception:
        if write:
            conn.rollback()
        raise
    finally:
        conn.close()


def _migrate():
    """Aditivo: agrega columna locked_until si no existe."""
    try:
        with db(write=True) as c:
            c.execute("ALTER TABLE accounts ADD COLUMN locked_until TEXT")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e):
            raise


_migrate()

app = FastAPI(title="Botmexico v2")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


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
        "SELECT id, email, balance_total, balance_real, "
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


@app.get("/api/superadmin/conectados")
def superadmin_conectados():
    """Operadores con cuentas en uso agrupados por operador."""
    with db() as c:
        rows = c.execute(
            "SELECT locked_by, COUNT(*) as count FROM accounts "
            "WHERE locked_by IS NOT NULL GROUP BY locked_by"
        ).fetchall()
    return [{"operator": r["locked_by"], "count": r["count"]} for r in rows]


@app.get("/api/superadmin/actividad")
def superadmin_actividad():
    """Checks recientes y actividad por hora últimas 24h."""
    with db() as c:
        recent = c.execute(
            "SELECT id, email, grade, status, last_checked_at "
            "FROM accounts WHERE last_checked_at IS NOT NULL "
            "ORDER BY last_checked_at DESC LIMIT 20"
        ).fetchall()
        by_hour = c.execute(
            "SELECT strftime('%H', last_checked_at) as hour, COUNT(*) as count "
            "FROM accounts WHERE last_checked_at IS NOT NULL "
            "AND last_checked_at >= datetime('now', '-24 hours') "
            "GROUP BY hour ORDER BY hour"
        ).fetchall()
    return {
        "recentChecks": [dict(r) for r in recent],
        "byHour": [{"hour": r["hour"], "count": r["count"]} for r in by_hour],
    }


@app.get("/api/superadmin/alertas")
def superadmin_alertas():
    """Alertas: DEAD recientes (top 10) + LIVE sin check en 48h."""
    with db() as c:
        recent_dead = c.execute(
            "SELECT id, email, grade, last_checked_at FROM accounts "
            "WHERE status='DEAD' ORDER BY last_checked_at DESC LIMIT 10"
        ).fetchall()
        no_recent = c.execute(
            "SELECT COUNT(*) FROM accounts WHERE status='LIVE' "
            "AND (last_checked_at IS NULL "
            "  OR last_checked_at < datetime('now', '-48 hours'))"
        ).fetchone()[0]
    return {
        "recentDead": [dict(r) for r in recent_dead],
        "noRecentCheck": no_recent,
    }


def _capmonster_balance() -> dict:
    key = os.environ.get("CAPMONSTER_KEY", "")
    if not key:
        return {"balance": None, "error": "CAPMONSTER_KEY not set"}
    try:
        req = urllib.request.Request(
            "https://api.capmonster.cloud/getBalance",
            data=_json.dumps({"clientKey": key}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = _json.loads(resp.read())
        if body.get("errorId") == 0:
            return {"balance": body["balance"], "error": None}
        return {"balance": None, "error": body.get("errorDescription", "API error")}
    except Exception as e:
        return {"balance": None, "error": str(e)}


@app.get("/api/superadmin/pool")
def superadmin_pool():
    """Créditos CapMonster + estado proxy (LitPort pendiente Sprint 5)."""
    return {
        "capmonster": _capmonster_balance(),
        "proxy": {"status": "pending", "note": "LitPort API — Sprint 5"},
    }


class LockRequest(BaseModel):
    operator: str
    hours: int = 2


@app.post("/api/accounts/{account_id}/lock")
def lock_account(account_id: int, req: LockRequest):
    now = datetime.now(timezone.utc)
    locked_at = now.isoformat()
    locked_until = (now + timedelta(hours=req.hours)).isoformat()
    with db(write=True) as c:
        cur = c.execute(
            "UPDATE accounts SET locked_by=?, locked_at=?, locked_until=?"
            " WHERE id=? AND locked_by IS NULL",
            (req.operator, locked_at, locked_until, account_id),
        )
        if cur.rowcount == 0:
            row = c.execute(
                "SELECT id, locked_by FROM accounts WHERE id=?", (account_id,)
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Account not found")
            raise HTTPException(
                status_code=409,
                detail=f"Already locked by {row['locked_by']}",
            )
    return {"id": account_id, "locked_by": req.operator, "locked_until": locked_until}


@app.post("/api/accounts/{account_id}/unlock")
def unlock_account(account_id: int):
    with db(write=True) as c:
        row = c.execute(
            "SELECT id FROM accounts WHERE id=?", (account_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Account not found")
        c.execute(
            "UPDATE accounts SET locked_by=NULL, locked_at=NULL, locked_until=NULL WHERE id=?",
            (account_id,),
        )
    return {"id": account_id, "locked_by": None, "locked_until": None}


if __name__ == "__main__":
    import uvicorn
    print(f"BD: {DB_PATH} (existe: {DB_PATH.exists()})")
    uvicorn.run(app, host="127.0.0.1", port=5001)

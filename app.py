#!/usr/bin/env python3
# BetMexico Web v2 — minimal dashboard sobre la BD existente.
# Lee betmexico_accounts.db (la misma que el bot TG). Sin lógica de polling.

from __future__ import annotations
import sqlite3, os, sys
import asyncio
import json as _json
import logging as _logging
import logging.handlers as _logging_handlers
import queue as _stdlib_queue
import threading
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# ── File logging para que /api/logs pueda servir desde Docker ─────────────────
# Antes el endpoint usaba `journalctl -u betmexico-web.service` pero en KVM4
# corremos en Docker (no hay systemd). Resultado: logs no se cargaban en el
# dashboard desde la migración 2026-05-11. Fix: agregar FileHandler que escriba
# a /data/logs/dashboard.log (volumen montado, persiste entre restarts) y leer
# de ahí en el endpoint.
_LOGS_DIR = Path("/data/logs")
try:
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)
    _LOG_FILE = _LOGS_DIR / "dashboard.log"
    _root_logger = _logging.getLogger()
    # Solo agregar si no existe ya (evita duplicar en hot-reload)
    if not any(isinstance(h, _logging_handlers.RotatingFileHandler)
               and getattr(h, "_dashboard_handler", False)
               for h in _root_logger.handlers):
        _fh = _logging_handlers.RotatingFileHandler(
            str(_LOG_FILE), maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        _fh._dashboard_handler = True  # marker
        _fh.setFormatter(_logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
        ))
        _root_logger.addHandler(_fh)
        if _root_logger.level == _logging.NOTSET or _root_logger.level > _logging.INFO:
            _root_logger.setLevel(_logging.INFO)
except Exception as _e:
    print(f"[boot] file logger init failed: {_e}")

# Permitir importar módulos del bot (betmexico_db, betmexico_login_service, etc.)
# que viven en el directorio padre cuando el VPS los tiene desplegados.
_HERE = Path(__file__).parent
_BOT_DIR = _HERE.parent
if (_BOT_DIR / "betmexico_db.py").exists() and str(_BOT_DIR) not in sys.path:
    sys.path.insert(0, str(_BOT_DIR))

# Carga EAGER de deps del bot — antes que prewarm/deposits los importen lazy.
# Evita circular imports en betmexico_db (carga partial → crash).
BOT_DEPS_OK = False
BOT_RUN_DEPOSIT = None
BOT_MAKE_POOL = None
BOT_SCORE_PAYMENT = None
try:
    if (_BOT_DIR / "betmexico_db.py").exists():
        # Romper ciclo betmexico_db ↔ betmexico_config: cargar config primero
        # para que cuando betmexico_db haga `from betmexico_config import ...`
        # ya esté completo, y betmexico_config no necesite re-import betmexico_db.
        import betmexico_config as _bot_cfg_mod  # noqa
        import betmexico_db as _bot_db_mod  # noqa
        from web_routes_deposits import _run_deposit as BOT_RUN_DEPOSIT  # noqa
        from betmexico_login_service import make_pool as BOT_MAKE_POOL  # noqa
        try:
            from betmexico_payment_analyzer import score_payment_readiness as BOT_SCORE_PAYMENT  # noqa
        except Exception:
            pass
        BOT_DEPS_OK = True
        print("[deps] bot modules loaded OK")
except Exception as _e:
    import traceback as _tb
    print(f"[deps] bot init failed: {_e}")
    _tb.print_exc()

from fastapi import Cookie, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import auth as _auth
from auth import require_session
from prewarm import router as _prewarm_router
from deposits import router as _deposits_router

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
DB_PATH = Path(os.environ.get("BETMEX_DB", str(ROOT.parent / "betmexico_accounts.db")))


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
    """Aditivo: locked_until + published_to_pool (default 1 = pool)."""
    for col, ddl in [
        ("locked_until", "ALTER TABLE accounts ADD COLUMN locked_until TEXT"),
        ("published_to_pool", "ALTER TABLE accounts ADD COLUMN published_to_pool INTEGER DEFAULT 1"),
        ("dead_reason", "ALTER TABLE accounts ADD COLUMN dead_reason TEXT"),
        ("dead_at", "ALTER TABLE accounts ADD COLUMN dead_at TEXT"),
        # Trazabilidad: tarjeta usada en cada intento (apruebado o no). Sin enmascarar.
        ("card_pipe", "ALTER TABLE deposit_attempts ADD COLUMN card_pipe TEXT"),
        # Watchdog auto-release: tracking de notifs enviadas (no spam).
        ("notif_pre24h_sent_at", "ALTER TABLE accounts ADD COLUMN notif_pre24h_sent_at TEXT"),
        ("notif_at24h_sent_at", "ALTER TABLE accounts ADD COLUMN notif_at24h_sent_at TEXT"),
        ("notif_at24h10_sent_at", "ALTER TABLE accounts ADD COLUMN notif_at24h10_sent_at TEXT"),
        # Tracking 3DS por BIN: cada vez que se detecta 3DS (explícito o implícito
        # por JWT cardinal + status Created), se incrementa total_3ds y se actualiza
        # last_3ds_at. Frontend consulta `/api/deposits/bin-check` antes del intento.
        ("total_3ds", "ALTER TABLE bin_stats ADD COLUMN total_3ds INTEGER DEFAULT 0"),
        ("last_3ds_at", "ALTER TABLE bin_stats ADD COLUMN last_3ds_at TEXT"),
    ]:
        try:
            with db(write=True) as c:
                c.execute(ddl)
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e) and "no such table" not in str(e):
                raise


_migrate()


def _resolve_operator(val):
    """Convierte locked_by/operator_id (string nombre o int telegram_id)
    al display name si lo encontramos en USERS. Si no, devuelve crudo."""
    if val is None:
        return None
    if isinstance(val, str):
        u = _auth.USERS.get(val.lower())
        if u:
            return u["display"]
        try:
            iv = int(val)
            for v in _auth.USERS.values():
                if v["telegram_id"] == iv:
                    return v["display"]
        except (TypeError, ValueError):
            pass
        return val
    try:
        iv = int(val)
        for v in _auth.USERS.values():
            if v["telegram_id"] == iv:
                return v["display"]
        return iv
    except (TypeError, ValueError):
        return val


_sse_lock = threading.Lock()
_sse_queues: list = []  # list[queue.SimpleQueue]


def _broadcast(event: dict) -> None:
    """Push event a todos los SSE clients. Thread-safe."""
    msg = f"data: {_json.dumps(event)}\n\n"
    with _sse_lock:
        for q in _sse_queues:
            q.put(msg)


def _dequeue_blocking(q, timeout: float) -> str:
    """Espera un mensaje, devuelve heartbeat si timeout."""
    try:
        return q.get(timeout=timeout)
    except _stdlib_queue.Empty:
        return ": heartbeat\n\n"


app = FastAPI(title="Botmexico v2")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.middleware("http")
async def _no_cache_static_assets(request, call_next):
    """Fuerza no-cache en .js/.css/.html servidos por StaticFiles.

    Sin esto, navegadores cachean agresivamente y los devs/operadores ven
    versiones viejas tras un deploy aunque el index ya use ?v=mtime cache-bust.
    """
    response = await call_next(request)
    path = request.url.path
    if path.endswith((".js", ".css", ".html")) or path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response
app.include_router(_prewarm_router)
app.include_router(_deposits_router)


# ── Páginas ────────────────────────────────────────────────────────────────────

@app.get("/favicon.ico")
def favicon():
    return FileResponse(STATIC / "assets" / "botmexico_logo.png", media_type="image/png")


@app.get("/login")
def login_page(bmx_session: str = Cookie(default=None)):
    if bmx_session and _auth.get_session(bmx_session):
        return RedirectResponse("/", status_code=302)
    return FileResponse(STATIC / "login.html")


@app.get("/")
def index(bmx_session: str = Cookie(default=None)):
    if not bmx_session or not _auth.get_session(bmx_session):
        return RedirectResponse("/login", status_code=302)
    # Cache-bust: añadir mtime de los assets al src para forzar re-fetch tras deploy
    try:
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        v_js = int((STATIC / "app.js").stat().st_mtime)
        v_css = int((STATIC / "style.css").stat().st_mtime)
        html = html.replace('src="/static/app.js"', f'src="/static/app.js?v={v_js}"')
        html = html.replace('href="/static/style.css"', f'href="/static/style.css?v={v_css}"')
        return Response(content=html, media_type="text/html",
                        headers={"Cache-Control": "no-cache, must-revalidate"})
    except Exception:
        return FileResponse(STATIC / "index.html")


# ── Auth endpoints ─────────────────────────────────────────────────────────────

from fastapi.responses import Response as _Response


@app.post("/api/auth/login")
async def auth_login(request: Request, response: _Response):
    body = await request.json()
    username = (body.get("username") or "").strip().lower()
    password = body.get("password") or ""

    if username not in _auth.USERS:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    passwords = _auth.load_passwords()
    stored = passwords.get(username)

    if stored is None:
        return JSONResponse({"first_time": True, "display": _auth.USERS[username]["display"]})

    master = os.environ.get("BMX_MASTER", "")
    if _auth.sha256(password) != stored and password != master:
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")

    token = _auth.create_session(username)
    response.set_cookie(
        "bmx_session", token,
        httponly=True, samesite="lax",
        max_age=_auth.session_max_age(username),
    )
    u = _auth.USERS[username]
    return {"username": u["display"], "role": u["role"]}


@app.post("/api/auth/set-password")
async def auth_set_password(request: Request, response: _Response):
    body = await request.json()
    username = (body.get("username") or "").strip().lower()
    new_pwd = body.get("password") or ""

    if username not in _auth.USERS:
        raise HTTPException(status_code=401, detail="Usuario no válido")
    if len(new_pwd) < 4:
        raise HTTPException(status_code=400, detail="Contraseña muy corta (mínimo 4 caracteres)")

    passwords = _auth.load_passwords()
    if passwords.get(username) is not None:
        raise HTTPException(status_code=400, detail="Ya tienes contraseña")

    passwords[username] = _auth.sha256(new_pwd)
    _auth.save_passwords(passwords)

    token = _auth.create_session(username)
    response.set_cookie(
        "bmx_session", token,
        httponly=True, samesite="lax",
        max_age=_auth.session_max_age(username),
    )
    u = _auth.USERS[username]
    return {"username": u["display"], "role": u["role"]}


@app.post("/api/auth/logout")
def auth_logout(response: _Response, bmx_session: str = Cookie(default=None)):
    if bmx_session:
        _auth.delete_session(bmx_session)
    response.delete_cookie("bmx_session")
    return {"ok": True}


@app.get("/api/auth/me")
def auth_me(user: dict = Depends(require_session)):
    return {
        "username": user["display"],
        "role": user["role"],
        "telegram_id": user.get("telegram_id"),
    }


# ── API — protegida con sesión ─────────────────────────────────────────────────

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
    q: Optional[str] = None,
    cards_only: bool = Query(False),
    limit: int = Query(500, le=2000),
    user: dict = Depends(require_session),
):
    where, params = [], []
    if status != "all":
        where.append("a.status = ?"); params.append(status)
    if grade:
        where.append("a.grade = ?"); params.append(grade)
    # Filtro: solo cuentas con al menos 1 tarjeta (en account_cards o account_notes con card)
    if cards_only:
        where.append(
            "(EXISTS (SELECT 1 FROM account_cards ac WHERE ac.account_email=a.email) "
            " OR EXISTS (SELECT 1 FROM account_notes an WHERE an.account_email=a.email "
            "            AND an.card_number IS NOT NULL AND TRIM(an.card_number) != ''))"
        )

    # Búsqueda multi-campo: email + tarjeta (últimos 4 / fingerprint substr) + nota
    if q:
        like = f"%{q}%"
        where.append(
            "(a.email LIKE ? "
            " OR EXISTS (SELECT 1 FROM account_cards ac WHERE ac.account_email=a.email AND ac.card_number LIKE ?) "
            " OR EXISTS (SELECT 1 FROM account_notes an WHERE an.account_email=a.email AND an.note_text LIKE ?))"
        )
        params.extend([like, like, like])

    role = user.get("role", "user")
    user_tg = int(user.get("telegram_id") or 0)

    # Trastienda: non-SA solo ve cuentas publicadas a la pool
    if role != "superadmin":
        where.append("COALESCE(a.published_to_pool, 1) = 1")
        # Lock-aware: non-SA solo ve cuentas libres O lockeadas por ellos mismos.
        # Si otro operador la tiene, NO la ve. SA ve todo.
        # `locked_by` se guarda como string del telegram_id (ver lock_account).
        where.append("(a.locked_by IS NULL OR a.locked_by = ? OR a.locked_by = ?)")
        params.append(str(user_tg))
        params.append(user.get("username", "__none__"))

    base_cols = (
        "a.id, a.email, a.password, a.balance_total, a.balance_real, "
        "a.last_deposit_amount, a.last_deposit_date, a.status, a.grade, "
        "a.locked_by, a.locked_at, a.locked_until, a.last_checked_at, a.check_count, "
        "COALESCE(a.published_to_pool, 1) AS published_to_pool, "
        "(SELECT COUNT(*) FROM account_cards ac WHERE ac.account_email=a.email) AS cards_count, "
        "(SELECT COUNT(*) FROM account_notes an WHERE an.account_email=a.email "
        " AND COALESCE(an.note_text,'') != '') AS notes_count"
    )
    # Normal user: solo cuentas asignadas a su user_id
    if role == "user" and user_tg:
        sql = (
            f"SELECT {base_cols} FROM accounts a "
            "INNER JOIN account_assignments ass ON ass.email = a.email "
            "WHERE ass.user_id = ?"
        )
        params.insert(0, user_tg)
    else:
        sql = f"SELECT {base_cols} FROM accounts a"
        if where:
            sql += " WHERE " + " AND ".join(where)
            where = []  # ya consumidos

    if where:  # caso user-filter con extras
        sql += " AND " + " AND ".join(where)
    sql += " ORDER BY a.balance_total DESC, a.last_checked_at DESC LIMIT ?"
    params.append(limit)
    try:
        with db() as c:
            rows = [dict(r) for r in c.execute(sql, params).fetchall()]
            for r in rows:
                op = r.get("locked_by")
                # Color del operador (para borde lateral en fila)
                tg_id = None
                if op is not None:
                    try:
                        tg_id = int(op)
                    except (TypeError, ValueError):
                        u = _auth.USERS.get(str(op).lower())
                        tg_id = u["telegram_id"] if u else None
                r["locked_by"] = _resolve_operator(op)
                r["locked_color"] = _auth.USER_COLORS.get(tg_id) if tg_id else None
            return rows
    except sqlite3.OperationalError:
        # Si no hay tabla account_assignments todavía
        return []


# ─── Asignaciones / Liberador ──────────────────────────────────────────────────

@app.get("/api/users")
def list_users(user: dict = Depends(require_session)):
    """Lista los usuarios del sistema (para asignar cuentas).
    Solo visible para superadmin/admin."""
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")
    return [
        {"username": k, "display": v["display"], "telegram_id": v["telegram_id"], "role": v["role"]}
        for k, v in _auth.USERS.items()
    ]


@app.get("/api/assignments")
def list_assignments(
    user_id: Optional[int] = None,
    user: dict = Depends(require_session),
):
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")
    try:
        with db() as c:
            if user_id is not None:
                rows = c.execute(
                    "SELECT email, user_id, assigned_by, assigned_at "
                    "FROM account_assignments WHERE user_id=? ORDER BY assigned_at DESC",
                    (user_id,),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT email, user_id, assigned_by, assigned_at "
                    "FROM account_assignments ORDER BY assigned_at DESC"
                ).fetchall()
            return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []


class AssignRequest(BaseModel):
    emails: list[str]
    user_id: int


@app.post("/api/assignments/assign")
def assign_accounts(req: AssignRequest, user: dict = Depends(require_session)):
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")
    if not req.emails or not req.user_id:
        raise HTTPException(400, "emails y user_id requeridos")
    assigned_by = int(user.get("telegram_id") or 0)
    now = datetime.now(timezone.utc).isoformat()
    ok = 0
    with db(write=True) as c:
        for email in req.emails:
            try:
                c.execute(
                    "INSERT OR IGNORE INTO account_assignments "
                    "(email, user_id, assigned_by, assigned_at) VALUES (?,?,?,?)",
                    (email, req.user_id, assigned_by, now),
                )
                ok += c.rowcount
            except Exception as e:
                print(f"[assign] error {email}: {e}")
    return {"assigned": ok, "requested": len(req.emails)}


@app.post("/api/assignments/unassign")
def unassign_accounts(req: AssignRequest, user: dict = Depends(require_session)):
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")
    removed = 0
    with db(write=True) as c:
        for email in req.emails:
            cur = c.execute(
                "DELETE FROM account_assignments WHERE email=? AND user_id=?",
                (email, req.user_id),
            )
            removed += cur.rowcount
    return {"removed": removed, "requested": len(req.emails)}


@app.get("/api/stats")
def stats(_user: dict = Depends(require_session)):
    with db() as c:
        live = c.execute("SELECT COUNT(*) FROM accounts WHERE status='LIVE'").fetchone()[0]
        total = c.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        balance = c.execute("SELECT COALESCE(SUM(balance_total),0) FROM accounts WHERE status='LIVE'").fetchone()[0]
        with_balance = c.execute("SELECT COUNT(*) FROM accounts WHERE status='LIVE' AND balance_total > 0").fetchone()[0]
        in_use = c.execute("SELECT COUNT(*) FROM accounts WHERE locked_by IS NOT NULL").fetchone()[0]
    return {"live": live, "total": total, "totalBalance": balance, "withBalance": with_balance, "inUse": in_use}


# ── LitPort proxy health (cache 60s) ───────────────────────────────────────────
_proxy_cache: dict = {"ts": 0.0, "data": None}
_PROXY_TTL = 30.0       # cache si OK
_PROXY_TTL_FAIL = 5.0   # cache corto si falló — re-intenta rápido

_wsai_cache: dict = {"ts": 0.0, "data": None}
_WSAI_TTL = 120.0       # 2 min — el balance no cambia tan seguido


def _wsai_status() -> dict:
    """Status de WebScraping.ai (cache 2min)."""
    import time as _t
    now = _t.time()
    if _wsai_cache["data"] and (now - _wsai_cache["ts"]) < _WSAI_TTL:
        return _wsai_cache["data"]
    key = os.environ.get("WSAI_API_KEY", "e338d7e4-3c48-4b65-937c-8508c405ba6f")
    try:
        req = urllib.request.Request(
            f"https://api.webscraping.ai/account?api_key={key}",
            headers={"User-Agent": "curl/8.0"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = _json.loads(resp.read())
        out = {
            "ok": True,
            "remaining": int(body.get("remaining_api_calls", 0)),
            "concurrency": int(body.get("remaining_concurrency", 0)),
            "email": body.get("email", "?"),
            "resets_at": body.get("resets_at"),
            "error": None,
        }
    except Exception as e:
        out = {"ok": False, "error": str(e)[:80]}
    _wsai_cache.update({"ts": now, "data": out})
    return out

# Dedup de alertas push: kind → último timestamp broadcast (anti-spam)
_alert_last_sent: dict = {}
_ALERT_DEDUP_SEC = 5 * 60  # no repetir la misma alerta < 5 min


def _maybe_alert_broadcast(alert: dict) -> None:
    """Broadcast una alerta crítica como notif push, deduplicando por kind."""
    import time as _t
    kind = alert.get("kind", "alert")
    now = _t.time()
    last = _alert_last_sent.get(kind, 0)
    if now - last < _ALERT_DEDUP_SEC:
        return
    _alert_last_sent[kind] = now
    icon = {"capmonster_low": "💸", "proxy_down": "🔌", "prewarm_errors": "🔥"}.get(kind, "⚠️")
    _broadcast({
        "type": "alert",
        "kind": kind,
        "severity": alert.get("severity", "warn"),
        "icon": icon,
        "msg": alert.get("msg", ""),
        "ts": alert.get("ts"),
    })


def _proxy_health() -> dict:
    """Verifica que el proxy LitPort responde haciendo GET a un endpoint de IP.
    Devuelve {ok, ip, latency_ms, country, error}.
    Vars de entorno: LITPORT_HOST, LITPORT_PORT, LITPORT_USER, LITPORT_PASS.
    Cache 60s para no saturar."""
    import time as _time
    now = _time.time()
    if _proxy_cache["data"]:
        ttl = _PROXY_TTL if _proxy_cache["data"].get("ok") else _PROXY_TTL_FAIL
        if (now - _proxy_cache["ts"]) < ttl:
            return _proxy_cache["data"]

    # Defaults desde betmexico_config.py (mismo proxy que usa el bot)
    host = os.environ.get("LITPORT_HOST", "hub-us-7.litport.net")
    port = os.environ.get("LITPORT_PORT", "1337")
    user = os.environ.get("LITPORT_USER", "bmxutop_country-mx")
    pwd  = os.environ.get("LITPORT_PASS", "49O3mC6hl4")

    proxy_url = f"http://{user}:{pwd}@{host}:{port}"
    handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
    opener = urllib.request.build_opener(handler)

    # Intenta ipinfo.io primero, ipify como fallback
    out = None
    for endpoint, parse in [
        ("https://ipinfo.io/json", lambda b: (b.get("ip"), b.get("country"))),
        ("https://api.ipify.org?format=json", lambda b: (b.get("ip"), None)),
    ]:
        t0 = _time.time()
        try:
            req = urllib.request.Request(endpoint, headers={"User-Agent": "curl/8.0"})
            with opener.open(req, timeout=12) as resp:
                body = _json.loads(resp.read())
            ip, country = parse(body)
            latency = int((_time.time() - t0) * 1000)
            out = {
                "ok": True, "ip": ip, "country": country or "MX",
                "latency_ms": latency,
                "host": f"{host}:{port}",
                "error": None, "endpoint": endpoint,
            }
            break
        except Exception as e:
            last_err = str(e)[:100]
            print(f"[proxy_health] {endpoint} fail: {last_err}")
            continue
    if out is None:
        out = {"ok": False, "error": last_err, "host": f"{host}:{port}"}

    _proxy_cache.update({"ts": now, "data": out})
    return out


def _capmonster_balance() -> dict:
    # Misma key que usa el bot (api.py / betmexico_login_api.py)
    key = (os.environ.get("CAPMONSTER_KEY")
           or os.environ.get("BMX_CAPMONSTER_KEY")
           or "a9040840fdb3828ecc6090a6010afcad")
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


# ─── KPIs L invertida (spec chat2) ─────────────────────────────────────────────

def _operator_color(tg_id):
    return _auth.USER_COLORS.get(int(tg_id)) if tg_id else None


@app.get("/api/superadmin/kpis")
def superadmin_kpis(user: dict = Depends(require_session)):
    """L invertida del SuperAdmin (spec chat2):
      1. Online: operadores con actividad < 5 min, lista con dot status
      2. Activity feed (últimos 30 eventos: deposit/lock/prewarm)
      3. Alertas: bulk masivo, prewarm errors, login fallidos, capmonster bajo
      4. Pool stats: pool / en_uso / trastienda / rebotadas

    Roles:
      - superadmin: respuesta completa
      - admin: solo capmonster_balance + proxy (vista premium del sidebar)
      - user: 403
    """
    role = user.get("role")
    if role == "user":
        raise HTTPException(403, "Solo superadmin/admin")
    # Admin: respuesta mínima (solo lo que pinta el sidebar premium)
    if role == "admin":
        cm = _capmonster_balance()
        return {
            "capmonster_balance": cm.get("balance"),
            "capmonster_error": cm.get("error"),
            "proxy": _proxy_health(),
        }
    now = datetime.now(timezone.utc)
    out: dict = {}
    with db() as c:
        # ── 1. ONLINE NOW ──
        # Operador "online" = tiene lock activo o evento < 5 min
        online_ids: set = set()
        try:
            for r in c.execute(
                "SELECT DISTINCT locked_by FROM accounts WHERE locked_by IS NOT NULL"
            ).fetchall():
                online_ids.add(str(r["locked_by"]))
            for r in c.execute(
                "SELECT DISTINCT operator_id FROM deposit_attempts "
                "WHERE created_at >= datetime('now','-5 minutes')"
            ).fetchall():
                if r["operator_id"]:
                    online_ids.add(str(r["operator_id"]))
        except sqlite3.OperationalError:
            pass

        operators = []
        for username, u in _auth.USERS.items():
            tg = u["telegram_id"]
            is_online = str(tg) in online_ids or username in online_ids
            # idle si activo en últimos 30 min pero no ahora
            try:
                idle = c.execute(
                    "SELECT 1 FROM deposit_attempts WHERE operator_id=? "
                    "AND created_at >= datetime('now','-30 minutes') LIMIT 1",
                    (tg,)
                ).fetchone() is not None
            except sqlite3.OperationalError:
                idle = False
            # cuántas cuentas tiene en uso ahora
            try:
                in_use = c.execute(
                    "SELECT COUNT(*) FROM accounts WHERE locked_by IN (?, ?)",
                    (str(tg), username)
                ).fetchone()[0]
            except sqlite3.OperationalError:
                in_use = 0
            operators.append({
                "username": username,
                "display": u["display"],
                "role": u["role"],
                "telegram_id": tg,
                "color": _auth.USER_COLORS.get(tg),
                "status": "online" if is_online else ("idle" if idle else "offline"),
                "in_use": in_use,
            })
        out["online"] = {
            "operators": operators,
            "active": sum(1 for o in operators if o["status"] == "online"),
            "total": len(operators),
        }

        # ── 2. ACTIVITY FEED (últimos 20 eventos mezclados) ──
        feed = []
        kpi_pw_cache: dict[str, str] = {}
        def _kpi_combo(email: str) -> str:
            if not email: return ""
            if email not in kpi_pw_cache:
                row = c.execute("SELECT password FROM accounts WHERE email=? LIMIT 1", (email,)).fetchone()
                kpi_pw_cache[email] = row["password"] if row else ""
            pw = kpi_pw_cache.get(email) or ""
            return f"{email}:{pw}" if pw else email

        try:
            for r in c.execute(
                "SELECT account_email, amount, status, operator_id, created_at "
                "FROM deposit_attempts ORDER BY id DESC LIMIT 15"
            ).fetchall():
                feed.append({
                    "kind": "deposit",
                    "ts": r["created_at"],
                    "who": _resolve_operator(r["operator_id"]),
                    "who_color": _operator_color(r["operator_id"]),
                    "target": _kpi_combo(r["account_email"]),
                    "amount": r["amount"],
                    "status": r["status"],
                })
        except sqlite3.OperationalError:
            pass

        for r in c.execute(
            "SELECT email, locked_by, locked_at FROM accounts "
            "WHERE locked_by IS NOT NULL ORDER BY locked_at DESC LIMIT 15"
        ).fetchall():
            tg = None
            try: tg = int(r["locked_by"])
            except (TypeError, ValueError):
                u = _auth.USERS.get(str(r["locked_by"]).lower())
                tg = u["telegram_id"] if u else None
            feed.append({
                "kind": "lock",
                "ts": r["locked_at"],
                "who": _resolve_operator(r["locked_by"]),
                "who_color": _auth.USER_COLORS.get(tg) if tg else None,
                "target": _kpi_combo(r["email"]),
            })

        feed.sort(key=lambda e: str(e.get("ts", "")), reverse=True)
        out["feed"] = feed[:20]

        # ── 3. ALERTAS REALES ──
        alerts = []
        # bulk: alguien tocó >20 cuentas en <1 min (locks)
        try:
            bulk = c.execute(
                "SELECT locked_by, COUNT(*) as n, MIN(locked_at) as t0, MAX(locked_at) as t1 "
                "FROM accounts WHERE locked_by IS NOT NULL "
                "AND locked_at >= datetime('now','-5 minutes') "
                "GROUP BY locked_by HAVING n >= 20"
            ).fetchall()
            for r in bulk:
                alerts.append({
                    "kind": "bulk", "severity": "warn",
                    "msg": f"{_resolve_operator(r['locked_by'])} lockeó {r['n']} cuentas en <5 min",
                    "ts": r["t1"],
                })
        except sqlite3.OperationalError:
            pass
        # prewarm errors recientes
        try:
            err = c.execute(
                "SELECT COUNT(*) FROM process_log "
                "WHERE process_type='prewarm' AND phase IN ('error','timeout') "
                "AND created_at >= datetime('now','-30 minutes')"
            ).fetchone()[0]
            if err >= 3:
                alerts.append({
                    "kind": "prewarm_errors", "severity": "warn",
                    "msg": f"{err} prewarms fallidos en 30 min",
                    "ts": now.isoformat(),
                })
        except sqlite3.OperationalError:
            pass
        # capmonster bajo
        cm = _capmonster_balance()
        if cm.get("balance") is not None and cm["balance"] < 5:
            alerts.append({
                "kind": "capmonster_low", "severity": "danger",
                "msg": f"CapMonster bajo: ${cm['balance']:.2f}",
                "ts": now.isoformat(),
            })
        # proxy caído
        ph = _proxy_health()
        if ph and not ph.get("ok"):
            alerts.append({
                "kind": "proxy_down", "severity": "danger",
                "msg": f"Proxy LitPort caído: {ph.get('error') or 'sin respuesta'}",
                "ts": now.isoformat(),
            })
        out["alerts"] = alerts

        # Broadcast alertas críticas como notif push (deduplicado por kind+severity en 5min)
        for a in alerts:
            if a.get("severity") == "danger":
                _maybe_alert_broadcast(a)

        # ── 4. POOL STATS (Pool · En uso · Trastienda · Rebotadas) ──
        live = c.execute("SELECT COUNT(*) FROM accounts WHERE status='LIVE'").fetchone()[0]
        in_use = c.execute(
            "SELECT COUNT(*) FROM accounts WHERE locked_by IS NOT NULL"
        ).fetchone()[0]
        # Trastienda = LIVE con published_to_pool=0 (las que tú aún no soltaste a la pool)
        trastienda = c.execute(
            "SELECT COUNT(*) FROM accounts "
            "WHERE status='LIVE' AND COALESCE(published_to_pool, 1) = 0"
        ).fetchone()[0]
        # Pool = LIVE publicadas y libres
        pool = c.execute(
            "SELECT COUNT(*) FROM accounts "
            "WHERE status='LIVE' AND COALESCE(published_to_pool, 1) = 1 "
            "AND locked_by IS NULL"
        ).fetchone()[0]
        try:
            # Rebotadas hoy: lock vencido sin depósito aprobado en últimas 24h
            rebotadas = c.execute(
                "SELECT COUNT(DISTINCT a.email) FROM accounts a "
                "WHERE a.locked_until IS NOT NULL "
                "AND a.locked_until <= datetime('now') "
                "AND NOT EXISTS (SELECT 1 FROM deposit_attempts d "
                "  WHERE d.account_email=a.email AND d.status='approved' "
                "  AND d.created_at >= datetime('now','-24 hours'))"
            ).fetchone()[0]
        except sqlite3.OperationalError:
            rebotadas = 0
        out["pool"] = {
            "pool": pool,
            "in_use": in_use,
            "trastienda": trastienda,
            "rebotadas": rebotadas,
        }

        # ── Sistema (resumen rápido) ──
        try:
            dep24 = c.execute(
                "SELECT COUNT(*) AS total, "
                "SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) AS approved, "
                "COALESCE(SUM(CASE WHEN status='approved' THEN amount ELSE 0 END),0) AS amount "
                "FROM deposit_attempts WHERE created_at >= datetime('now','-24 hours')"
            ).fetchone()
            out["deposits_24h"] = {
                "total": dep24[0] or 0,
                "approved": dep24[1] or 0,
                "amount": dep24[2] or 0.0,
            }
        except sqlite3.OperationalError:
            out["deposits_24h"] = {"total": 0, "approved": 0, "amount": 0.0}

        out["capmonster_balance"] = cm.get("balance")
        out["capmonster_error"] = cm.get("error")

        # ── Proxies (LitPort health check) ──
        out["proxy"] = _proxy_health()

        # ── WebScraping.ai (saldo de API calls) ──
        out["wsai"] = _wsai_status()

    return out


# ─── Refresh visible (re-lectura de DB) ────────────────────────────────────────

class RefreshRequest(BaseModel):
    ids: list[int]


@app.post("/api/accounts/refresh")
def accounts_refresh(req: RefreshRequest, _user: dict = Depends(require_session)):
    """Re-lee del DB las cuentas indicadas. NOTA: el re-check live (login + balance)
    contra BetMexico requiere las deps del bot — se hace via /api/prewarm/select.
    Este endpoint solo refresca lo que el bot ya puso en BD."""
    if not req.ids:
        return {"rows": []}
    placeholders = ",".join("?" * len(req.ids))
    with db() as c:
        rows = c.execute(
            f"SELECT a.id, a.email, a.password, a.balance_total, a.balance_real, "
            f"a.last_deposit_amount, a.last_deposit_date, a.status, a.grade, "
            f"a.locked_by, a.locked_at, a.locked_until, a.last_checked_at, a.check_count, "
            f"(SELECT COUNT(*) FROM account_cards ac WHERE ac.account_email=a.email) AS cards_count "
            f"FROM accounts a WHERE a.id IN ({placeholders})",
            req.ids,
        ).fetchall()
    out = [dict(r) for r in rows]
    for r in out:
        r["locked_by"] = _resolve_operator(r.get("locked_by"))
    return {"rows": out}


# ─── Logs en tiempo real ───────────────────────────────────────────────────────

@app.get("/api/logs")
def get_logs(limit: int = 200, since: Optional[str] = None,
             user: dict = Depends(require_session)):
    """Lee las últimas N líneas del log del dashboard.
    Fix 2026-05-23: antes usaba journalctl, pero en Docker no hay systemd. Ahora
    lee `/data/logs/dashboard.log` que escribe el RotatingFileHandler de app.py."""
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")
    log_file = Path("/data/logs/dashboard.log")
    if not log_file.exists():
        return {"lines": ["(log file no creado todavía — esperar primer flush)"]}
    try:
        n = max(1, min(int(limit or 200), 2000))
        # Lee tail eficiente: lee últimos ~512KB y toma últimas N líneas
        size = log_file.stat().st_size
        with log_file.open("rb") as f:
            if size > 524288:
                f.seek(-524288, 2)
                f.readline()  # descarta línea parcial
            data = f.read().decode("utf-8", errors="replace")
        lines = data.splitlines()[-n:]
        if since:
            # Filtro simple por prefijo timestamp (las líneas empiezan con "YYYY-MM-DD HH:MM:SS,ms")
            lines = [ln for ln in lines if ln[:19] >= since[:19]]
        return {"lines": lines}
    except Exception as e:
        return {"lines": [f"Error leyendo log: {e}"]}


# ─── Health check ──────────────────────────────────────────────────────────────

_health_state: dict = {"last_run": None, "ok": True, "issues": []}


def _run_health_checks() -> dict:
    issues: list[str] = []
    # 1. DB accesible
    try:
        with db() as c:
            c.execute("SELECT 1 FROM accounts LIMIT 1").fetchone()
    except Exception as e:
        issues.append(f"DB: {e}")
    # 2. CapMonster balance
    cm = _capmonster_balance()
    if cm.get("error"):
        issues.append(f"CapMonster: {cm['error']}")
    elif cm.get("balance") is not None and cm["balance"] < 5:
        issues.append(f"CapMonster bajo: ${cm['balance']:.2f}")
    # 3. Cuentas DEAD masivas
    try:
        with db() as c:
            recent_dead = c.execute(
                "SELECT COUNT(*) FROM accounts WHERE status='DEAD' "
                "AND last_checked_at >= datetime('now','-1 hours')"
            ).fetchone()[0]
        if recent_dead >= 10:
            issues.append(f"{recent_dead} cuentas DEAD en última hora")
    except Exception:
        pass
    # 4. Bot deps — solo informativo, NO genera issue (en dev local los deps
    #    no están y eso es esperado; el VPS los tiene siempre).
    # try: import betmexico_db
    # → eliminado del check; la ausencia no rompe el dashboard, solo /api/deposits/execute.

    state = {
        "last_run": datetime.now(timezone.utc).isoformat(),
        "ok": len(issues) == 0,
        "issues": issues,
    }
    _health_state.update(state)
    return state


@app.get("/api/health/full")
def health_full(_user: dict = Depends(require_session)):
    return _run_health_checks()


# ── Panel de controles backend (SA only) ─────────────────────────────────────

import subprocess as _sp


def _require_sa(user: dict):
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")


@app.get("/api/admin/diag")
def admin_diag(user: dict = Depends(require_session)):
    """Diagnóstico completo del sistema."""
    _require_sa(user)
    out = {"ts": datetime.now(timezone.utc).isoformat(), "checks": []}
    # DB
    try:
        with db() as c:
            n = c.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        out["checks"].append({"name": "BD SQLite", "ok": True, "info": f"{n} cuentas"})
    except Exception as e:
        out["checks"].append({"name": "BD SQLite", "ok": False, "error": str(e)[:120]})
    # CapMonster
    cm = _capmonster_balance()
    if cm.get("balance") is not None:
        out["checks"].append({"name": "CapMonster", "ok": cm["balance"] >= 5,
                              "info": f"${cm['balance']:.2f}"})
    else:
        out["checks"].append({"name": "CapMonster", "ok": False, "error": cm.get("error", "?")})
    # Proxy
    p = _proxy_health()
    out["checks"].append({"name": "Proxy LitPort", "ok": p.get("ok", False),
                          "info": f"{p.get('country','?')} · {p.get('latency_ms','?')}ms" if p.get("ok") else None,
                          "error": p.get("error") if not p.get("ok") else None})
    # Bot deps
    try:
        from app import BOT_DEPS_OK
        out["checks"].append({"name": "Bot deps", "ok": bool(BOT_DEPS_OK),
                              "info": "loaded" if BOT_DEPS_OK else None,
                              "error": "no cargan" if not BOT_DEPS_OK else None})
    except Exception:
        pass
    return out


@app.post("/api/admin/ping")
def admin_ping(user: dict = Depends(require_session)):
    """Ping a hosts críticos."""
    _require_sa(user)
    targets = ["betmexico.mx", "api.capmonster.cloud", "hub-us-7.litport.net"]
    results = []
    for host in targets:
        try:
            r = _sp.run(["ping", "-c", "1", "-W", "2", host],
                        capture_output=True, text=True, timeout=5)
            ok = r.returncode == 0
            # Extrae tiempo
            lat = None
            for line in r.stdout.splitlines():
                if "time=" in line:
                    try:
                        lat = float(line.split("time=")[1].split()[0])
                    except Exception:
                        pass
            results.append({"host": host, "ok": ok, "latency_ms": lat})
        except Exception as e:
            results.append({"host": host, "ok": False, "error": str(e)[:100]})
    return {"results": results}


@app.post("/api/admin/refresh-proxy")
def admin_refresh_proxy(user: dict = Depends(require_session)):
    """Invalida cache de proxy_health para forzar re-check inmediato."""
    _require_sa(user)
    _proxy_cache["ts"] = 0.0
    _proxy_cache["data"] = None
    p = _proxy_health()
    return {"ok": p.get("ok"), "country": p.get("country"), "latency_ms": p.get("latency_ms"),
            "error": p.get("error")}


@app.post("/api/admin/services/restart")
def admin_services_restart(target: str, user: dict = Depends(require_session)):
    """Reinicia bot, web, o ambos."""
    _require_sa(user)
    if target not in ("bot", "web", "all"):
        raise HTTPException(400, "target debe ser bot|web|all")
    services = {"bot": ["betmexico-bot"], "web": ["betmexico-web"],
                "all": ["betmexico-bot", "betmexico-web"]}[target]
    out = []
    for s in services:
        try:
            r = _sp.run(["systemctl", "restart", s], capture_output=True, text=True, timeout=15)
            out.append({"service": s, "ok": r.returncode == 0, "stderr": (r.stderr or "")[:200]})
        except Exception as e:
            out.append({"service": s, "ok": False, "error": str(e)[:100]})
    return {"restarted": out}


@app.get("/api/admin/export-logs")
def admin_export_logs(lines: int = Query(500, le=5000),
                      user: dict = Depends(require_session)):
    """Descarga logs recientes (text/plain)."""
    _require_sa(user)
    try:
        cmd = ["journalctl", "-u", "betmexico-web", "-u", "betmexico-bot",
               "-n", str(lines), "--no-pager", "--output=short-iso"]
        r = _sp.run(cmd, capture_output=True, text=True, timeout=15)
        body = r.stdout or r.stderr
    except Exception as e:
        body = f"Error: {e}"
    return Response(content=body, media_type="text/plain",
                    headers={"Content-Disposition": "attachment; filename=betmexico-logs.txt"})


# Estado de pausa global de procesos (SA puede pausar prewarms/deposits para todos)
_GLOBAL_PAUSE = {"paused": False, "since": None, "by": None, "reason": None}


@app.get("/api/admin/pause-state")
def admin_pause_state(user: dict = Depends(require_session)):
    _require_sa(user)
    return _GLOBAL_PAUSE


@app.post("/api/admin/pause")
def admin_pause(user: dict = Depends(require_session), reason: str = ""):
    """Pausa global: bloquea nuevos prewarms y depósitos para TODOS los users."""
    _require_sa(user)
    _GLOBAL_PAUSE.update({
        "paused": True,
        "since": datetime.now(timezone.utc).isoformat(),
        "by": user.get("display"),
        "reason": reason or "manual",
    })
    _broadcast({"type": "alert", "kind": "global_pause", "severity": "warn",
                "icon": "⏸", "msg": f"Sistema pausado por {user.get('display')}",
                "ts": datetime.now(timezone.utc).isoformat()})
    return _GLOBAL_PAUSE


@app.post("/api/admin/resume")
def admin_resume(user: dict = Depends(require_session)):
    _require_sa(user)
    _GLOBAL_PAUSE.update({"paused": False, "since": None, "by": None, "reason": None})
    _broadcast({"type": "alert", "kind": "global_resume", "severity": "info",
                "icon": "▶", "msg": f"Sistema reanudado por {user.get('display')}",
                "ts": datetime.now(timezone.utc).isoformat()})
    return _GLOBAL_PAUSE


@app.post("/api/admin/emergency-stop")
def admin_emergency_stop(user: dict = Depends(require_session)):
    """Paro de emergencia: pausa global + cancela todos los prewarms y schedules activos."""
    _require_sa(user)
    _GLOBAL_PAUSE.update({
        "paused": True,
        "since": datetime.now(timezone.utc).isoformat(),
        "by": user.get("display"),
        "reason": "EMERGENCY_STOP",
    })
    cancelled_pw = 0
    cancelled_sched = 0
    try:
        from prewarm import _PREWARM_TASKS
        for k, t in list(_PREWARM_TASKS.items()):
            if not t.done():
                t.cancel()
                cancelled_pw += 1
    except Exception:
        pass
    try:
        from deposits import _active_schedules, _active_mm_runs
        for sid, info in list(_active_schedules.items()):
            try:
                info["task"].cancel()
                cancelled_sched += 1
            except Exception:
                pass
        for run_id, ev in list(_active_mm_runs.items()):
            ev.set()
    except Exception:
        pass
    _broadcast({"type": "alert", "kind": "emergency_stop", "severity": "danger",
                "icon": "🛑", "msg": f"PARO DE EMERGENCIA por {user.get('display')}",
                "ts": datetime.now(timezone.utc).isoformat()})
    return {"paused": True, "cancelled_prewarms": cancelled_pw,
            "cancelled_schedules": cancelled_sched}


@app.post("/api/admin/vps-reboot")
def admin_vps_reboot(user: dict = Depends(require_session), confirm: str = ""):
    """Reboot del VPS — requiere confirmación."""
    _require_sa(user)
    if confirm != "REBOOT":
        raise HTTPException(400, "Pasa confirm=REBOOT para confirmar")
    try:
        _sp.Popen(["shutdown", "-r", "+1", "Reboot solicitado por SA"])
        _broadcast({"type": "alert", "kind": "vps_reboot", "severity": "danger",
                    "icon": "🔄", "msg": "VPS reboot programado en 1 min",
                    "ts": datetime.now(timezone.utc).isoformat()})
        return {"scheduled": True, "in": "1 minute"}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/health/last")
def health_last(_user: dict = Depends(require_session)):
    return _health_state


@app.post("/api/health/dismiss")
def health_dismiss(_user: dict = Depends(require_session)):
    """Limpia el estado de salud — re-corre el check ahora.
    Si los issues siguen presentes, vuelven a aparecer; si se resolvieron, quedan limpios."""
    return _run_health_checks()


async def _health_loop():
    """Cada 6 horas corre el check. Si falla, broadcast SSE."""
    await asyncio.sleep(60)  # primer check al minuto del start
    while True:
        try:
            res = await asyncio.to_thread(_run_health_checks)
            if not res["ok"]:
                _broadcast({"type": "health_warning", "issues": res["issues"]})
        except Exception as e:
            print(f"[health] error: {e}")
        await asyncio.sleep(6 * 3600)


def _run_lock_janitor() -> int:
    """Auto-unlock (spec chat2):
      - Lock vencido (locked_until < now) Y sin depósito aprobado en últimas 24h → liberar
      - Si hay depósito/tarjeta nueva en últimas 24h → mantener 24h desde ese evento
    Retorna cuántas se liberaron.
    """
    freed = 0
    try:
        with db(write=True) as c:
            # Cuentas con lock vencido
            rows = c.execute(
                "SELECT id, email, locked_by, locked_at, locked_until "
                "FROM accounts WHERE locked_by IS NOT NULL "
                "AND locked_until IS NOT NULL "
                "AND locked_until <= datetime('now')"
            ).fetchall()
            for r in rows:
                # ¿Hubo depósito aprobado o tarjeta nueva en últimas 24h?
                try:
                    sticky = c.execute(
                        "SELECT 1 FROM deposit_attempts "
                        "WHERE account_email=? AND status='approved' "
                        "AND created_at >= datetime('now','-24 hours') LIMIT 1",
                        (r["email"],)
                    ).fetchone()
                    if not sticky:
                        sticky = c.execute(
                            "SELECT 1 FROM account_cards WHERE account_email=? "
                            "AND registered_at >= datetime('now','-24 hours') LIMIT 1",
                            (r["email"],)
                        ).fetchone()
                except sqlite3.OperationalError:
                    sticky = None

                if sticky:
                    # Extender 24h desde ahora (sticky)
                    new_until = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
                    c.execute(
                        "UPDATE accounts SET locked_until=? WHERE id=?",
                        (new_until, r["id"])
                    )
                else:
                    # Vomitada — liberar y broadcast
                    prev = r["locked_by"]
                    c.execute(
                        "UPDATE accounts SET locked_by=NULL, locked_at=NULL, locked_until=NULL "
                        "WHERE id=?",
                        (r["id"],)
                    )
                    freed += 1
                    _broadcast({
                        "type": "activity", "kind": "unlock_auto",
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "who": "janitor", "target": r["email"],
                        "id": r["id"], "prev_locked_by": prev,
                    })
    except Exception as e:
        print(f"[janitor] error: {e}")
    return freed


async def _janitor_loop():
    """Limpia locks vencidos cada 5 minutos."""
    await asyncio.sleep(30)
    while True:
        try:
            n = await asyncio.to_thread(_run_lock_janitor)
            if n:
                print(f"[janitor] auto-unlock {n} cuentas")
        except Exception as e:
            print(f"[janitor] error: {e}")
        await asyncio.sleep(5 * 60)


# ── Watcher de ventanas de depósito 24h ──────────────────────────────────
# Emite notif al operador cuando su window 24h está por cerrar (~30 min antes)
# Emite notif "ya cerró, vuelve" cuando expira
# Auto-libera la cuenta a las 25h post primer-depósito si nadie hizo nada
_window_notified: dict = {}  # email → set de fases ya notificadas

def _run_window_watcher() -> dict:
    """Revisa cuentas con depósitos aprobados últimas 25h y emite alertas."""
    out = {"warned": 0, "expired": 0, "released": 0}
    try:
        with db() as c:
            # Para cada cuenta con dep aprobado en últimas 25h, calcula window
            rows = c.execute(
                "SELECT account_email, MIN(created_at) AS first_at, "
                "  MAX(operator_id) AS operator_id, COUNT(*) AS n, "
                "  COALESCE(SUM(amount),0) AS total "
                "FROM deposit_attempts "
                "WHERE status='approved' "
                "  AND created_at >= datetime('now','-25 hours') "
                "GROUP BY account_email"
            ).fetchall()
        now = datetime.now(timezone.utc)
        for r in rows:
            email = r["account_email"]
            try:
                first_at = datetime.fromisoformat(r["first_at"].replace(" ", "T"))
                if first_at.tzinfo is None:
                    first_at = first_at.replace(tzinfo=timezone.utc)
            except Exception:
                continue
            expires_at = first_at + timedelta(hours=24)
            mins_left = (expires_at - now).total_seconds() / 60
            operator_id = r["operator_id"]
            phases = _window_notified.setdefault(email, set())

            # Fase 1: 30 min antes
            if 0 < mins_left <= 30 and "warning" not in phases:
                phases.add("warning")
                _broadcast({
                    "type": "window_warning",
                    "email": email, "operator_id": operator_id,
                    "mins_left": int(mins_left), "used": float(r["total"]),
                    "expires_at": expires_at.isoformat(),
                })
                out["warned"] += 1

            # Fase 2: window cerró (acaba de pasar)
            if -60 < mins_left <= 0 and "expired" not in phases:
                phases.add("expired")
                _broadcast({
                    "type": "window_expired",
                    "email": email, "operator_id": operator_id,
                    "used_24h": float(r["total"]),
                    "expires_at": expires_at.isoformat(),
                    "deadline": (expires_at + timedelta(hours=1)).isoformat(),
                })
                out["expired"] += 1

            # Fase 3: pasaron 25h sin acción → auto-libera (publish=1, unlock)
            if mins_left <= -60 and "released" not in phases:
                phases.add("released")
                with db(write=True) as c:
                    c.execute(
                        "UPDATE accounts SET locked_by=NULL, locked_at=NULL, locked_until=NULL, "
                        "published_to_pool=1 WHERE email=?",
                        (email,),
                    )
                _broadcast({
                    "type": "window_released",
                    "email": email, "operator_id": operator_id,
                    "msg": f"Cuenta {email} liberada al pool tras 25h sin actividad",
                })
                out["released"] += 1

        # Limpia tracking de cuentas viejas (> 26h sin actividad)
        for email in list(_window_notified.keys()):
            if email not in [r["account_email"] for r in rows]:
                _window_notified.pop(email, None)
    except Exception as e:
        print(f"[window_watcher] error: {e}")
    return out


async def _window_watcher_loop():
    await asyncio.sleep(45)
    while True:
        try:
            r = await asyncio.to_thread(_run_window_watcher)
            if r["warned"] or r["expired"] or r["released"]:
                print(f"[window_watcher] {r}")
        except Exception as e:
            print(f"[window_watcher] error: {e}")
        await asyncio.sleep(2 * 60)  # cada 2 min


def _release_watchdog_tick():
    """Watchdog post-depósito: notif progresivas y auto-release a las 27h.

    Timeline desde `last_deposit_date`:
    - T+23h55m → notif "disponible en 5 min" (info)
    - T+24h    → notif "ya puedes volver a depositar" (warn) + acciones [deposit, release]
    - T+24h10m → notif "segundo aviso" (warn) + acciones [deposit, release]
    - T+27h    → auto-release silencioso

    Las notifs son por-usuario (target_user = locked_by). El frontend filtra para
    mostrar solo al operador dueño del lock. SA siempre las ve.
    """
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    # last_deposit_date está en hora MX (UTC-6) sin tzinfo. Asumir MX.
    mx_tz = timezone(timedelta(hours=-6))

    try:
        with db(write=True) as c:
            rows = c.execute(
                "SELECT id, email, locked_by, last_deposit_date, "
                "notif_pre24h_sent_at, notif_at24h_sent_at, notif_at24h10_sent_at "
                "FROM accounts "
                "WHERE locked_by IS NOT NULL "
                "AND last_deposit_date IS NOT NULL "
                "AND last_deposit_date != 'N/A' "
                "AND TRIM(last_deposit_date) != ''"
            ).fetchall()
    except sqlite3.OperationalError as e:
        print(f"[release_watchdog] db error: {e}")
        return

    for r in rows:
        try:
            dt = datetime.strptime(r["last_deposit_date"], "%d/%m/%Y %H:%M")
            dt_mx = dt.replace(tzinfo=mx_tz)
        except ValueError:
            continue

        delta = now - dt_mx
        hours = delta.total_seconds() / 3600.0
        if hours < 0:
            continue  # depósito en futuro? skip

        acc_id = r["id"]
        email = r["email"]
        owner = r["locked_by"]
        now_iso = now.isoformat()

        # Caso 1: ≥27h → auto-release
        if hours >= 27:
            with db(write=True) as c:
                c.execute(
                    "UPDATE accounts SET locked_by=NULL, locked_at=NULL, locked_until=NULL, "
                    "notif_pre24h_sent_at=NULL, notif_at24h_sent_at=NULL, notif_at24h10_sent_at=NULL "
                    "WHERE id=?",
                    (acc_id,),
                )
            _broadcast({
                "type": "activity", "kind": "unlock_auto",
                "ts": now_iso, "target": email, "id": acc_id,
                "reason": "27h post-deposit, sin acción del operador",
            })
            _broadcast({
                "type": "notification", "kind": "release_auto",
                "severity": "info", "icon": "🕒",
                "msg": f"{email} liberada automáticamente (27h sin actividad)",
                "target_user": owner, "account_id": acc_id,
            })
            continue

        # Caso 2: 24h+10m → segundo aviso con acciones
        if hours >= 24.166 and not r["notif_at24h10_sent_at"]:
            with db(write=True) as c:
                c.execute(
                    "UPDATE accounts SET notif_at24h10_sent_at=? WHERE id=?",
                    (now_iso, acc_id),
                )
            _broadcast({
                "type": "notification", "kind": "release_available_again",
                "severity": "warn", "icon": "⏰",
                "msg": f"{email}: 2do aviso — deposita o libera. Auto-release a las 27h.",
                "target_user": owner, "account_id": acc_id,
                "actions": ["deposit", "release"],
            })
            continue

        # Caso 3: 24h cumplidas → primer aviso con acciones
        if hours >= 24 and not r["notif_at24h_sent_at"]:
            with db(write=True) as c:
                c.execute(
                    "UPDATE accounts SET notif_at24h_sent_at=? WHERE id=?",
                    (now_iso, acc_id),
                )
            _broadcast({
                "type": "notification", "kind": "release_available",
                "severity": "warn", "icon": "🟢",
                "msg": f"{email}: ya puedes depositar de nuevo (24h cumplidas)",
                "target_user": owner, "account_id": acc_id,
                "actions": ["deposit", "release"],
            })
            continue

        # Caso 4: 5 min antes de 24h → pre-aviso (info)
        if 23.917 <= hours < 24 and not r["notif_pre24h_sent_at"]:
            with db(write=True) as c:
                c.execute(
                    "UPDATE accounts SET notif_pre24h_sent_at=? WHERE id=?",
                    (now_iso, acc_id),
                )
            mins_left = max(0, int((24 - hours) * 60))
            _broadcast({
                "type": "notification", "kind": "release_warning_5min",
                "severity": "info", "icon": "⏳",
                "msg": f"{email}: disponible en ~{mins_left} min para volver a depositar",
                "target_user": owner, "account_id": acc_id,
            })


async def _release_watchdog_loop():
    """Loop infinito del watchdog. Tick cada 60s."""
    await asyncio.sleep(15)  # esperar a que app arranque
    while True:
        try:
            _release_watchdog_tick()
        except Exception as e:
            print(f"[release_watchdog] tick error: {e}")
        await asyncio.sleep(60)


@app.on_event("startup")
async def _start_bg_tasks():
    asyncio.create_task(_health_loop())
    asyncio.create_task(_janitor_loop())
    asyncio.create_task(_window_watcher_loop())
    asyncio.create_task(_release_watchdog_loop())


class LockRequest(BaseModel):
    operator: str
    hours: int = 2


@app.post("/api/accounts/{account_id}/lock")
def lock_account(account_id: int, req: LockRequest, _user: dict = Depends(require_session)):
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
        email = c.execute(
            "SELECT email FROM accounts WHERE id=?", (account_id,)
        ).fetchone()["email"]
    _broadcast({
        "type": "activity", "kind": "lock",
        "ts": locked_at, "who": req.operator, "target": email,
        "id": account_id, "locked_until": locked_until,
    })
    return {"id": account_id, "locked_by": req.operator, "locked_until": locked_until}


class PublishRequest(BaseModel):
    ids: list[int]
    publish: bool  # true = a la pool (visible), false = a trastienda (oculta)


@app.post("/api/accounts/publish")
def publish_accounts(req: PublishRequest, user: dict = Depends(require_session)):
    """SA mueve cuentas entre Pool (visible para todos) y Trastienda (oculta).
    El que pediste para 'dosificar' las 900 cuentas."""
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")
    if not req.ids:
        return {"changed": 0}
    placeholders = ",".join("?" * len(req.ids))
    val = 1 if req.publish else 0
    with db(write=True) as c:
        cur = c.execute(
            f"UPDATE accounts SET published_to_pool=? WHERE id IN ({placeholders})",
            [val, *req.ids],
        )
        changed = cur.rowcount
    return {"changed": changed, "publish": req.publish}


@app.post("/api/accounts/hide-all")
def hide_all_accounts(user: dict = Depends(require_session)):
    """SA oculta TODAS las cuentas LIVE de la pool (mueve todo a Trastienda).
    Punto de partida para empezar a publicar selectivamente."""
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")
    with db(write=True) as c:
        cur = c.execute(
            "UPDATE accounts SET published_to_pool=0 "
            "WHERE status='LIVE' AND COALESCE(published_to_pool,1)=1"
        )
        changed = cur.rowcount
    return {"hidden": changed}


@app.get("/api/pool/accounts")
def pool_accounts(user: dict = Depends(require_session)):
    """Cuentas actualmente publicadas a la pool (visibles para los operadores).
    Solo SA — vista de control."""
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")
    with db() as c:
        rows = c.execute(
            "SELECT a.id, a.email, a.password, a.balance_total, a.balance_real, "
            "a.last_deposit_amount, a.last_deposit_date, a.status, a.grade, a.grade_score, "
            "a.locked_by, a.locked_at, a.locked_until, a.last_checked_at, "
            "(SELECT COUNT(*) FROM account_assignments ass WHERE ass.email=a.email) AS assigned_to "
            "FROM accounts a "
            "WHERE a.status='LIVE' AND COALESCE(a.published_to_pool,1)=1 "
            "ORDER BY a.balance_total DESC LIMIT 1000"
        ).fetchall()
        out = [dict(r) for r in rows]
        for r in out:
            r["locked_by"] = _resolve_operator(r.get("locked_by"))
        return out


@app.post("/api/accounts/{account_id}/unlock")
def unlock_account(account_id: int, user: dict = Depends(require_session)):
    with db(write=True) as c:
        row = c.execute(
            "SELECT id, email, locked_by FROM accounts WHERE id=?", (account_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Account not found")
        prev_locked_by = row["locked_by"]
        # Autorización: SA puede unlock cualquier cuenta; otros solo si son quien la bloqueó
        if user.get("role") != "superadmin":
            tg = str(user.get("telegram_id") or "")
            uname = str(user.get("username") or "").lower()
            owner = str(prev_locked_by or "").lower()
            if not prev_locked_by or (owner != tg and owner != uname):
                raise HTTPException(403, "Solo puedes desbloquear cuentas que tú bloqueaste")
        c.execute(
            "UPDATE accounts SET locked_by=NULL, locked_at=NULL, locked_until=NULL, "
            "notif_pre24h_sent_at=NULL, notif_at24h_sent_at=NULL, notif_at24h10_sent_at=NULL "
            "WHERE id=?",
            (account_id,),
        )
    _broadcast({
        "type": "activity", "kind": "unlock",
        "ts": datetime.now(timezone.utc).isoformat(),
        "who": user.get("username"), "target": row["email"],
        "id": account_id, "prev_locked_by": prev_locked_by,
    })
    return {"id": account_id, "locked_by": None, "locked_until": None}


async def _sse_generator():
    q = _stdlib_queue.SimpleQueue()
    with _sse_lock:
        _sse_queues.append(q)
    try:
        yield ": heartbeat\n\n"
        while True:
            msg = await asyncio.get_running_loop().run_in_executor(
                None, _dequeue_blocking, q, 25.0
            )
            yield msg
    finally:
        with _sse_lock:
            if q in _sse_queues:
                _sse_queues.remove(q)


@app.get("/api/events")
async def events(_user: dict = Depends(require_session)):
    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/accounts/{account_id}/cards-pipe")
def account_cards_pipe(account_id: int, _user: dict = Depends(require_session)):
    """Devuelve solo las tarjetas en formato pipe (para tooltip rápido)."""
    with db() as c:
        acc = c.execute("SELECT email FROM accounts WHERE id=?", (account_id,)).fetchone()
        if not acc:
            raise HTTPException(404, "Cuenta no encontrada")
        try:
            rows = c.execute(
                "SELECT card_number, card_expiry, card_cvv, total_approved, total_deposits "
                "FROM account_cards WHERE account_email=? "
                "ORDER BY last_used_at DESC, registered_at DESC LIMIT 20",
                (acc["email"],),
            ).fetchall()
        except sqlite3.OperationalError:
            return {"cards": []}
    out = []
    for r in rows:
        if not (r["card_number"] and r["card_expiry"] and r["card_cvv"]):
            continue
        exp = str(r["card_expiry"]).replace("/", "")
        out.append({
            "pipe": f'{r["card_number"]}|{exp}|{r["card_cvv"]}',
            "approved": r["total_approved"] or 0,
            "deposits": r["total_deposits"] or 0,
        })
    return {"cards": out}


@app.get("/api/accounts/{account_id}/notes-summary")
def account_notes_summary(account_id: int, user: dict = Depends(require_session)):
    """Notas resumidas para tooltip — filtradas por user/SA."""
    role = user.get("role", "user")
    my_tg = int(user.get("telegram_id") or 0)
    with db() as c:
        acc = c.execute("SELECT email FROM accounts WHERE id=?", (account_id,)).fetchone()
        if not acc:
            raise HTTPException(404, "Cuenta no encontrada")
        try:
            if role == "superadmin":
                rows = c.execute(
                    "SELECT note_text, created_by_name, created_at FROM account_notes "
                    "WHERE account_email=? AND COALESCE(note_text,'') != '' "
                    "ORDER BY created_at DESC LIMIT 10",
                    (acc["email"],),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT note_text, created_by_name, created_at FROM account_notes "
                    "WHERE account_email=? AND created_by=? AND COALESCE(note_text,'') != '' "
                    "ORDER BY created_at DESC LIMIT 10",
                    (acc["email"], my_tg),
                ).fetchall()
        except sqlite3.OperationalError:
            return {"notes": []}
    return {"notes": [dict(r) for r in rows]}


@app.get("/api/accounts/{account_id}/details")
def account_details(account_id: int, _user: dict = Depends(require_session)):
    with db() as c:
        acc = c.execute(
            "SELECT id, email, password, balance_total, balance_real, "
            "last_deposit_amount, last_deposit_date, status, grade, grade_score, "
            "locked_by, locked_at, locked_until, last_checked_at, check_count, "
            "first_checked_at, "
            "fullname, birthdate, address, phone, curp, kyc_verified "
            "FROM accounts WHERE id=? LIMIT 1",
            (account_id,),
        ).fetchone()
        if not acc:
            raise HTTPException(404, "Cuenta no encontrada")
        result = dict(acc)

        # Tarjetas guardadas
        try:
            rows = c.execute(
                "SELECT id, card_number, card_expiry, card_cvv, registered_at, "
                "last_used_at, total_deposits, total_approved, total_rejected, status "
                "FROM account_cards WHERE account_email=? "
                "ORDER BY last_used_at DESC, registered_at DESC LIMIT 50",
                (acc["email"],),
            ).fetchall()
            result["cards"] = [dict(r) for r in rows]
        except sqlite3.OperationalError:
            result["cards"] = []

        # Transacciones recientes
        try:
            rows = c.execute(
                "SELECT id, txn_date, amount, status, txn_type, gateway, fetched_at "
                "FROM account_transactions WHERE account_email=? "
                "ORDER BY txn_date DESC LIMIT 30",
                (acc["email"],),
            ).fetchall()
            result["transactions"] = [dict(r) for r in rows]
        except sqlite3.OperationalError:
            result["transactions"] = []

        # Intentos de depósito hechos desde el dashboard (con tarjeta usada)
        try:
            rows = c.execute(
                "SELECT attempt_id, amount, status, rejection_reason, card_pipe, "
                "       duration_ms, operator_id, created_at "
                "FROM deposit_attempts WHERE account_email=? "
                "ORDER BY id DESC LIMIT 30",
                (acc["email"],),
            ).fetchall()
            result["deposit_attempts"] = [dict(r) for r in rows]
        except sqlite3.OperationalError:
            result["deposit_attempts"] = []

        # Notas — non-SA solo ve las propias; SA ve todas
        role = _user.get("role", "user")
        my_tg = int(_user.get("telegram_id") or 0)
        try:
            if role == "superadmin":
                rows = c.execute(
                    "SELECT id, note_text, created_at, created_by, created_by_name "
                    "FROM account_notes WHERE account_email=? AND COALESCE(note_text,'') != '' "
                    "ORDER BY created_at DESC LIMIT 50",
                    (acc["email"],),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT id, note_text, created_at, created_by, created_by_name "
                    "FROM account_notes WHERE account_email=? AND created_by=? "
                    "AND COALESCE(note_text,'') != '' "
                    "ORDER BY created_at DESC LIMIT 50",
                    (acc["email"], my_tg),
                ).fetchall()
            result["notes"] = [dict(r) for r in rows]
            for n in result["notes"]:
                n["mine"] = (n.get("created_by") == my_tg)
        except sqlite3.OperationalError:
            result["notes"] = []

    return result


class NoteCreate(BaseModel):
    text: str


@app.post("/api/accounts/{account_id}/notes")
def create_note(account_id: int, req: NoteCreate, user: dict = Depends(require_session)):
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(400, "Texto vacío")
    if len(text) > 2000:
        raise HTTPException(400, "Nota muy larga (máx 2000)")
    tg = int(user.get("telegram_id") or 0)
    name = user.get("display") or user.get("username") or "?"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with db(write=True) as c:
        acc = c.execute(
            "SELECT email, password FROM accounts WHERE id=?", (account_id,)
        ).fetchone()
        if not acc:
            raise HTTPException(404, "Cuenta no encontrada")
        cur = c.execute(
            "INSERT INTO account_notes "
            "(account_email, account_password, note_type, note_text, "
            " created_by, created_by_name, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (acc["email"], acc["password"] or "", "USER", text, tg, name, now, now),
        )
        note_id = cur.lastrowid
    _broadcast({
        "type": "activity", "kind": "note",
        "ts": now, "who": name, "who_id": tg,
        "target": acc["email"], "id": note_id,
        "text": text[:120],
    })
    return {"id": note_id, "created_at": now}


class CurpUpdate(BaseModel):
    curp: str


@app.post("/api/accounts/{account_id}/curp")
def update_curp(account_id: int, req: CurpUpdate, _user: dict = Depends(require_session)):
    """Guarda CURP validado manualmente por el operador."""
    curp = (req.curp or "").strip().upper()
    # Validación básica: 18 chars, formato general
    import re
    if not re.match(r"^[A-Z]{4}\d{6}[HM][A-Z]{5}[0-9A-Z]\d$", curp):
        raise HTTPException(400, "CURP inválido (formato 18 chars)")
    with db(write=True) as c:
        cur = c.execute("UPDATE accounts SET curp=? WHERE id=?", (curp, account_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "Cuenta no encontrada")
    return {"id": account_id, "curp": curp}


@app.delete("/api/accounts/{account_id}/notes/{note_id}")
def delete_note(account_id: int, note_id: int, user: dict = Depends(require_session)):
    tg = int(user.get("telegram_id") or 0)
    role = user.get("role", "user")
    with db(write=True) as c:
        row = c.execute(
            "SELECT id, created_by, account_email FROM account_notes WHERE id=?", (note_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Nota no encontrada")
        if role != "superadmin" and row["created_by"] != tg:
            raise HTTPException(403, "Solo puedes borrar tus propias notas")
        c.execute("DELETE FROM account_notes WHERE id=?", (note_id,))
    return {"deleted": note_id}


class CombosRequest(BaseModel):
    ids: list[int]


@app.post("/api/accounts/combos")
def accounts_combos(req: CombosRequest, _user: dict = Depends(require_session)):
    if not req.ids:
        return {"combos": []}
    placeholders = ",".join("?" * len(req.ids))
    with db() as c:
        rows = c.execute(
            f"SELECT id, email, password FROM accounts WHERE id IN ({placeholders})",
            req.ids,
        ).fetchall()
    return {"combos": [{"id": r["id"], "email": r["email"], "password": r["password"]} for r in rows]}


@app.get("/api/accounts/pass-map")
def accounts_pass_map(_user: dict = Depends(require_session)):
    """Mapa email→password para todas las cuentas. Uso: resolver combos en activity/live feed."""
    with db() as c:
        rows = c.execute("SELECT email, password FROM accounts WHERE password IS NOT NULL").fetchall()
    return {r["email"]: r["password"] for r in rows}


@app.get("/api/cards/all")
def list_all_cards(user: dict = Depends(require_session)):
    """Lista unificada de tarjetas (account_cards + account_notes con card).

    Devuelve pipe completo sin enmascarar. Dedupe por (card_number, account_email).
    `source` indica origen ('card' = formalmente registrada, 'note' = solo en nota).
    """
    out = []
    seen = set()
    with db() as c:
        # 1) account_cards (registradas formalmente)
        try:
            rows = c.execute(
                "SELECT card_number, card_expiry, card_cvv, account_email, account_password, "
                "registered_by, registered_by_name, registered_at, last_used_at, "
                "total_deposits, total_approved, total_rejected, status "
                "FROM account_cards ORDER BY registered_at DESC"
            ).fetchall()
            for r in rows:
                key = (r["card_number"], r["account_email"])
                seen.add(key)
                out.append({
                    "source": "card",
                    "card_pipe": f"{r['card_number']}|{r['card_expiry'] or ''}|{r['card_cvv'] or ''}",
                    "card_number": r["card_number"],
                    "card_expiry": r["card_expiry"],
                    "card_cvv": r["card_cvv"],
                    "account_email": r["account_email"],
                    "account_password": r["account_password"],
                    "registered_by": r["registered_by_name"] or r["registered_by"],
                    "registered_at": r["registered_at"],
                    "last_used_at": r["last_used_at"],
                    "total_deposits": r["total_deposits"] or 0,
                    "total_approved": r["total_approved"] or 0,
                    "total_rejected": r["total_rejected"] or 0,
                    "status": r["status"] or "ACTIVE",
                })
        except sqlite3.OperationalError:
            pass
        # 2) account_notes con card (no duplicados ya en account_cards)
        try:
            rows = c.execute(
                "SELECT card_number, card_expiry, card_cvv, account_email, account_password, "
                "created_by, created_by_name, created_at, note_type, note_text "
                "FROM account_notes "
                "WHERE card_number IS NOT NULL AND TRIM(card_number) != '' "
                "ORDER BY created_at DESC"
            ).fetchall()
            for r in rows:
                key = (r["card_number"], r["account_email"])
                if key in seen:
                    continue
                seen.add(key)
                out.append({
                    "source": "note",
                    "card_pipe": f"{r['card_number']}|{r['card_expiry'] or ''}|{r['card_cvv'] or ''}",
                    "card_number": r["card_number"],
                    "card_expiry": r["card_expiry"],
                    "card_cvv": r["card_cvv"],
                    "account_email": r["account_email"],
                    "account_password": r["account_password"],
                    "registered_by": r["created_by_name"] or r["created_by"],
                    "registered_at": r["created_at"],
                    "last_used_at": None,
                    "total_deposits": 0,
                    "total_approved": 0,
                    "total_rejected": 0,
                    "status": r["note_type"] or "note",
                })
        except sqlite3.OperationalError:
            pass
    return {"rows": out, "total": len(out)}


@app.get("/api/activity")
def activity_feed(
    limit: int = Query(150, le=500),
    operator_id: Optional[int] = None,
    user: dict = Depends(require_session),
):
    """Feed unificado: depósitos + locks activos + prewarms.
    SA ve todo por defecto; user/admin ve solo lo suyo (su bitácora personal).
    SA puede pasar operator_id para filtrar."""
    events: list[dict] = []
    role = user.get("role", "user")
    if role == "superadmin":
        op_filter = operator_id  # SA puede filtrar manualmente
    else:
        # Non-SA: forzado a sus propios eventos (no acepta operator_id ajeno)
        op_filter = int(user.get("telegram_id") or 0)

    with db() as c:
        # Cache email → password para target=combo
        pw_cache: dict[str, str] = {}
        def _combo(email: str) -> str:
            if not email: return ""
            if email not in pw_cache:
                row = c.execute(
                    "SELECT password FROM accounts WHERE email=? LIMIT 1", (email,)
                ).fetchone()
                pw_cache[email] = row["password"] if row else ""
            pw = pw_cache.get(email) or ""
            return f"{email}:{pw}" if pw else email

        # Depósitos
        try:
            sql = (
                "SELECT account_email, amount, status, rejection_reason, "
                "operator_id, duration_ms, created_at FROM deposit_attempts "
            )
            params: list = []
            if op_filter is not None:
                sql += "WHERE operator_id = ? "
                params.append(op_filter)
            sql += "ORDER BY id DESC LIMIT ?"
            params.append(limit)
            for r in c.execute(sql, params).fetchall():
                events.append({
                    "kind": "deposit", "ts": r["created_at"],
                    "who": _resolve_operator(r["operator_id"]),
                    "target": _combo(r["account_email"]),
                    "amount": r["amount"], "status": r["status"],
                    "reason": r["rejection_reason"], "duration_ms": r["duration_ms"],
                })
        except sqlite3.OperationalError:
            pass

        # Locks activos (ACCOUNTS — solo los actualmente bloqueados)
        sql = "SELECT email, locked_by, locked_at FROM accounts WHERE locked_by IS NOT NULL "
        params = []
        if op_filter is not None:
            sql += "AND locked_by = ? "
            params.append(op_filter)
        sql += "ORDER BY locked_at DESC LIMIT ?"
        params.append(limit)
        for r in c.execute(sql, params).fetchall():
            events.append({
                "kind": "lock", "ts": r["locked_at"],
                "who": _resolve_operator(r["locked_by"]),
                "target": _combo(r["email"]),
            })

        # Notas (de los usuarios — bitácora visible para uno mismo, SA ve todas)
        try:
            sql = (
                "SELECT id, account_email, note_text, created_by, created_by_name, created_at "
                "FROM account_notes WHERE COALESCE(note_text,'') != '' "
            )
            params = []
            if op_filter is not None:
                sql += "AND created_by = ? "
                params.append(op_filter)
            sql += "ORDER BY id DESC LIMIT ?"
            params.append(limit)
            for r in c.execute(sql, params).fetchall():
                events.append({
                    "kind": "note", "ts": r["created_at"],
                    "who": r["created_by_name"] or _resolve_operator(r["created_by"]),
                    "target": _combo(r["account_email"]),
                    "text": (r["note_text"] or "")[:160],
                    "id": r["id"],
                })
        except sqlite3.OperationalError:
            pass

        # Prewarms (process_log)
        try:
            sql = (
                "SELECT phase, payload_json, created_at FROM process_log "
                "WHERE process_type='prewarm' "
            )
            params = []
            if op_filter is not None:
                sql += "AND payload_json LIKE ? "
                params.append(f'%"operator_id": {op_filter}%')
            sql += "ORDER BY timestamp_ms DESC LIMIT ?"
            params.append(limit)
            for r in c.execute(sql, params).fetchall():
                p = {}
                try:
                    p = _json.loads(r["payload_json"])
                except Exception:
                    pass
                events.append({
                    "kind": f"prewarm_{r['phase']}", "ts": r["created_at"],
                    "who": _resolve_operator(p.get("operator_id")),
                    "target": _combo(p.get("email", "")),
                })
        except sqlite3.OperationalError:
            pass

    events.sort(key=lambda e: str(e.get("ts", "")), reverse=True)
    return events[:limit]


@app.get("/api/deposits")
def list_deposits(
    status: Optional[str] = None,
    operator_id: Optional[int] = None,
    limit: int = Query(100, le=500),
    _user: dict = Depends(require_session),
):
    where, params = [], []
    if status:
        where.append("status = ?"); params.append(status)
    if operator_id is not None:
        where.append("operator_id = ?"); params.append(operator_id)
    sql = (
        "SELECT id, attempt_id, account_email, card_id, amount, status, "
        "rejection_reason, balance_before, balance_after, duration_ms, "
        "captcha_cost, operator_id, created_at "
        "FROM deposit_attempts"
    )
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    try:
        with db() as c:
            return [dict(r) for r in c.execute(sql, params).fetchall()]
    except sqlite3.OperationalError:
        return []


@app.get("/api/deposits/stats")
def deposits_stats(_user: dict = Depends(require_session)):
    try:
        with db() as c:
            total = c.execute("SELECT COUNT(*) FROM deposit_attempts").fetchone()[0]
            approved = c.execute(
                "SELECT COUNT(*) FROM deposit_attempts WHERE status='approved'"
            ).fetchone()[0]
            rejected = c.execute(
                "SELECT COUNT(*) FROM deposit_attempts WHERE status='rejected'"
            ).fetchone()[0]
            amount = c.execute(
                "SELECT COALESCE(SUM(amount),0) FROM deposit_attempts WHERE status='approved'"
            ).fetchone()[0]
        return {
            "total": total,
            "approved": approved,
            "rejected": rejected,
            "pending": total - approved - rejected,
            "success_rate": round(approved / total * 100, 1) if total > 0 else 0.0,
            "total_amount_approved": amount,
        }
    except sqlite3.OperationalError:
        return {
            "total": 0, "approved": 0, "rejected": 0, "pending": 0,
            "success_rate": 0.0, "total_amount_approved": 0.0,
        }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("BMX_WEB_PORT", "5001"))
    print(f"BD: {DB_PATH} (existe: {DB_PATH.exists()})")
    uvicorn.run(app, host="0.0.0.0", port=port)

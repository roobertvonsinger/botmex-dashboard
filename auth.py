"""Auth module — session cookie-based, no HTTP Basic dialog."""
from __future__ import annotations
import hashlib, json, os, secrets, time
from pathlib import Path
from typing import Optional
from fastapi import Cookie, HTTPException

# ── Users ─────────────────────────────────────────────────────────────────────
USERS: dict[str, dict] = {
    "robertvs": {"display": "RobertVS", "telegram_id": 1341812706, "role": "superadmin"},
    "lau":      {"display": "Lau",      "telegram_id": 7599631505, "role": "admin"},
    "luisito":  {"display": "Luisito",  "telegram_id": 7847239854, "role": "user"},
    "magdiel":  {"display": "Magdiel",  "telegram_id": 1059367082, "role": "user"},
}

# Color por operador (token name del CSS). Consistente lock-chip y borde fila.
USER_COLORS: dict[int, str] = {
    1341812706: "warn",     # RobertVS — amarillo
    7599631505: "purple",   # Lau — morado
    7847239854: "accent",   # Luisito — verde
    1059367082: "azure",    # Magdiel — azul
}

# ── Password storage ───────────────────────────────────────────────────────────
_DATA_DIR = Path(__file__).parent / "data"
_PWD_FILE = _DATA_DIR / "web_passwords.json"
_PWD_CACHE: dict = {}
_PWD_CACHE_MTIME: float = 0.0


def sha256(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


def load_passwords() -> dict:
    global _PWD_CACHE, _PWD_CACHE_MTIME
    defaults = {k: None for k in USERS}
    if _PWD_FILE.exists():
        try:
            mtime = _PWD_FILE.stat().st_mtime
            if _PWD_CACHE and mtime == _PWD_CACHE_MTIME:
                return _PWD_CACHE
            data = json.loads(_PWD_FILE.read_text(encoding="utf-8"))
            for k in defaults:
                data.setdefault(k, None)
            _PWD_CACHE = data
            _PWD_CACHE_MTIME = mtime
            return data
        except Exception:
            return _PWD_CACHE or defaults
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _PWD_FILE.write_text(json.dumps(defaults, indent=2), encoding="utf-8")
    _PWD_CACHE = defaults
    try:
        _PWD_CACHE_MTIME = _PWD_FILE.stat().st_mtime
    except Exception:
        pass
    return defaults


def save_passwords(data: dict) -> None:
    global _PWD_CACHE, _PWD_CACHE_MTIME
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _PWD_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    _PWD_CACHE = dict(data)
    try:
        _PWD_CACHE_MTIME = _PWD_FILE.stat().st_mtime
    except Exception:
        pass


# ── Session store ──────────────────────────────────────────────────────────────
SESSION_TTL = 86_400  # 24h por defecto
PERSISTENT_USERS = {"robertvs"}  # sus sesiones nunca expiran y se guardan en disco
PERSISTENT_TTL = 60 * 60 * 24 * 365 * 10  # 10 años (efectivamente nunca)
_SESS_FILE = _DATA_DIR / "sessions_persistent.json"


def _is_persistent(s: dict) -> bool:
    return s.get("username") in PERSISTENT_USERS


def _load_persistent_sessions() -> dict:
    if not _SESS_FILE.exists():
        return {}
    try:
        return json.loads(_SESS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_persistent_sessions() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    persisted = {t: s for t, s in _sessions.items() if _is_persistent(s)}
    try:
        _SESS_FILE.write_text(json.dumps(persisted, indent=2), encoding="utf-8")
    except Exception:
        pass


_sessions: dict[str, dict] = _load_persistent_sessions()


def _prune() -> None:
    now = time.time()
    dead = []
    for t, s in _sessions.items():
        if _is_persistent(s):
            continue  # nunca expira para PERSISTENT_USERS
        if now - s["last_seen"] > SESSION_TTL:
            dead.append(t)
    for t in dead:
        del _sessions[t]


def session_max_age(username_lower: str) -> int:
    """TTL de la cookie según usuario."""
    return PERSISTENT_TTL if username_lower in PERSISTENT_USERS else SESSION_TTL


def create_session(username_lower: str) -> str:
    _prune()
    token = secrets.token_hex(32)
    u = USERS[username_lower]
    _sessions[token] = {
        "username": username_lower,
        "display": u["display"],
        "role": u["role"],
        "telegram_id": u["telegram_id"],
        "last_seen": time.time(),
    }
    if username_lower in PERSISTENT_USERS:
        _save_persistent_sessions()
    return token


def get_session(token: str) -> Optional[dict]:
    s = _sessions.get(token)
    if not s:
        return None
    # Sesiones de PERSISTENT_USERS no expiran
    if not _is_persistent(s) and time.time() - s["last_seen"] > SESSION_TTL:
        del _sessions[token]
        return None
    s["last_seen"] = time.time()
    return s


def delete_session(token: str) -> None:
    s = _sessions.pop(token, None)
    if s and _is_persistent(s):
        _save_persistent_sessions()


# ── Dependency ─────────────────────────────────────────────────────────────────
def require_session(bmx_session: str = Cookie(default=None)) -> dict:
    if os.environ.get("BMX_WEB_AUTH_MODE") == "open":
        return {"username": "test", "display": "Test", "role": "superadmin"}
    if not bmx_session:
        raise HTTPException(status_code=401, detail="Sin sesión")
    s = get_session(bmx_session)
    if not s:
        raise HTTPException(status_code=401, detail="Sesión expirada")
    return s

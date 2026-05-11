#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BetMexico Web Dashboard — Authentication
Handles user validation, password management and access control.
"""

import json
import logging
import os
from pathlib import Path
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from web_utils import _sha256

logger = logging.getLogger("betmexico.web.auth")

# --- User Registry ---
WEB_USERS_RAW = {
    "RobertVS": {"telegram_id": 1341812706, "role": "superadmin"},
    "Lau":      {"telegram_id": 7599631505, "role": "admin"},
    "Luisito":  {"telegram_id": 7847239854, "role": "admin"},
    "Magdiel":  {"telegram_id": 1059367082, "role": "user"},
}
WEB_USERS = {k.lower(): v for k, v in WEB_USERS_RAW.items()}

# --- Password Persistence ---
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
if not _DATA_DIR.exists():
    _DATA_DIR = Path(__file__).resolve().parent

_PASSWORD_FILE = _DATA_DIR / "web_passwords.json"

# Cache en memoria con invalidación por mtime — evita disk read en cada request.
_PWD_CACHE: dict = {}
_PWD_CACHE_MTIME: float = 0.0

def _load_passwords() -> dict:
    """Carga passwords con cache invalidado por mtime del archivo."""
    global _PWD_CACHE, _PWD_CACHE_MTIME
    defaults = {k.lower(): None for k in WEB_USERS_RAW}

    if _PASSWORD_FILE.exists():
        try:
            mtime = _PASSWORD_FILE.stat().st_mtime
            if _PWD_CACHE and mtime == _PWD_CACHE_MTIME:
                return _PWD_CACHE
            data = json.loads(_PASSWORD_FILE.read_text(encoding="utf-8"))
            for k, v in defaults.items():
                data.setdefault(k, v)
            _PWD_CACHE = data
            _PWD_CACHE_MTIME = mtime
            return data
        except Exception as e:
            logger.error(f"[Auth] Error cargando contraseñas: {e}")
            return _PWD_CACHE or defaults

    _PASSWORD_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PASSWORD_FILE.write_text(json.dumps(defaults, indent=2), encoding="utf-8")
    _PWD_CACHE = defaults
    try:
        _PWD_CACHE_MTIME = _PASSWORD_FILE.stat().st_mtime
    except Exception:
        _PWD_CACHE_MTIME = 0.0
    return defaults

def _save_passwords(data: dict):
    global _PWD_CACHE, _PWD_CACHE_MTIME
    try:
        _PASSWORD_FILE.parent.mkdir(parents=True, exist_ok=True)
        _PASSWORD_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        _PWD_CACHE = dict(data)
        _PWD_CACHE_MTIME = _PASSWORD_FILE.stat().st_mtime
    except Exception as e:
        logger.error(f"[Auth] Error guardando contraseñas: {e}")

security = HTTPBasic(auto_error=False)
_touch_session_cb = None

def set_session_callback(cb):
    global _touch_session_cb
    _touch_session_cb = cb

def authenticate(request: Request, credentials: HTTPBasicCredentials = Depends(security)) -> dict:
    username = credentials.username if credentials and credentials.username else ""
    password = credentials.password if credentials and credentials.password else ""
    user_data = WEB_USERS.get(username.lower())

    if not user_data:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    passwords = _load_passwords()
    stored_hash = passwords.get(username.lower())

    if stored_hash is None:
        raise HTTPException(status_code=401, detail="FIRST_TIME")

    MASTER_PASSWORD = "Kashau2022"
    auth_open = os.environ.get("BMX_WEB_AUTH_MODE") == "open"

    if not auth_open and _sha256(password) != stored_hash and password != MASTER_PASSWORD:
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")

    orig_name = next((k for k in WEB_USERS_RAW if k.lower() == username.lower()), username)

    if _touch_session_cb:
        _touch_session_cb(orig_name.lower())

    real_user = {"username": orig_name, **user_data}

    # Impersonation: superadmin puede ver el dashboard como cualquier otro usuario
    # mediante header X-Impersonate. La sesión real (heartbeat, audit) usa el real_user.
    if real_user.get("role") == "superadmin":
        target = (request.headers.get("X-Impersonate") or "").strip().lower()
        if target and target != orig_name.lower():
            target_data = WEB_USERS.get(target)
            if target_data:
                target_orig = next((k for k in WEB_USERS_RAW if k.lower() == target), target)
                logger.info(f"[Impersonate] {orig_name} → {target_orig} ({target_data.get('role')})")
                return {
                    "username": target_orig,
                    "telegram_id": target_data["telegram_id"],
                    "role": target_data["role"],
                    "_real_username": orig_name,
                    "_impersonating": True,
                }

    return real_user

def require_admin(current_user: dict = Depends(authenticate)) -> dict:
    if current_user.get("role") not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Acceso restringido a administradores")
    return current_user

def require_superadmin(current_user: dict = Depends(authenticate)) -> dict:
    if current_user.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso restringido a superadministradores")
    return current_user

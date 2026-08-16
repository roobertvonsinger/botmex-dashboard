#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BetMexico Bot — Configuración y constantes globales.
Todos los módulos del bot importan desde aquí.
"""

import json
import logging
import os
import random
from datetime import datetime
from typing import Dict, Optional
from zoneinfo import ZoneInfo

from betmexico_login_api import (
    AntiCaptchaSolverFast, CapMonsterSolverFast,
    CAPMONSTER_API_KEY,
    create_solver,
)
# ─────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("betmexico")

# ─────────────────────────────────────────────────────────────────────
# TIMEZONE
# ─────────────────────────────────────────────────────────────────────

MX_TZ = ZoneInfo("America/Mexico_City")


def now_mx() -> datetime:
    """now_mx() en horario central de México."""
    return datetime.now(MX_TZ)


# ─────────────────────────────────────────────────────────────────────
# TELEGRAM TOKEN
# ─────────────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.getenv("BMX_BOT_TOKEN", "8516175452:AAGz_PCh9Oq3D9l5DZtCzgdU5ObAJH-b1Gs")

# ─────────────────────────────────────────────────────────────────────
# ROLES Y USUARIOS
# ─────────────────────────────────────────────────────────────────────

ADMIN_USERS = [1341812706, 7599631505, 7847239854]       # rober, Lau, Luisito (admins)
SUBADMIN_USERS = [1059367082]                # Magdiel (subadmin)
USER_USERS = [753020051]                    # Vaka (regular)
AUTHORIZED_USERS = ADMIN_USERS + SUBADMIN_USERS + USER_USERS

USER_NAMES = {
    1341812706: "rober",
    7847239854: "Luisito",
    1059367082: "Magdiel",
    7599631505: "Lau",
    753020051: "Vaka",
}


def user_tag(user_id: int) -> str:
    """Retorna tag legible para logs: 'Luisito(784723)'."""
    name = USER_NAMES.get(user_id, "???")
    short_id = str(user_id)[-6:]
    return f"{name}({short_id})"


def is_admin(user_id: int) -> bool:
    """Retorna True solo si es Admin Global (acceso a BD completa)."""
    return user_id in ADMIN_USERS


def is_subadmin(user_id: int) -> bool:
    """Retorna True si es Subadmin (funcionalidades completas, pero solo sus datos)."""
    return user_id in SUBADMIN_USERS


def is_any_admin(user_id: int) -> bool:
    """Admin Global o Subadmin."""
    return is_admin(user_id) or is_subadmin(user_id)


def is_authorized(user_id: int) -> bool:
    return user_id in AUTHORIZED_USERS


# ─────────────────────────────────────────────────────────────────────
# ESTADOS DEL CONVERSATIONHANDLER
# ─────────────────────────────────────────────────────────────────────

(WAIT_PASSWORD, WAIT_INPUT, WAIT_CAPTCHA_KEY, WAIT_USER_PROXIES,
 ASK_PROXY, WAIT_PAYMENT_INPUT, WAIT_SEARCH_INPUT, WAIT_TXN_SELECT,
 WAIT_WITHDRAWAL_INPUT, WAIT_BENEFICIARY_SELECT, WAIT_NEW_BENEFICIARY_DATA,
 WAIT_WITHDRAWAL_AMOUNT, WAIT_WITHDRAWAL_CONFIRM, WAIT_WITHDRAWAL_NOTE,
 WAIT_WITHDRAWAL_LOOP, WAIT_UNIFIED_TXN_SELECT, SMART_FILTER_ASK,
 WAIT_NOTE_INPUT, WAIT_SCRAPE_FILE,
 WAIT_DEPOSIT_CARD, WAIT_DEPOSIT_AMOUNT, WAIT_DEPOSIT_SCHEDULE) = range(22)

# ─────────────────────────────────────────────────────────────────────
# LÍMITES Y CONSTANTES
# ─────────────────────────────────────────────────────────────────────

MAX_TEXT_COMBOS = 100         # Máximo combos pegados en chat
HUMAN_COOLDOWN = 60            # 1 minuto entre checks (antes 2 horas)
MAX_COMBOS = 5000              # Máx combos por check (archivo) - TURBO MODE 🔥
FLUSH_EVERY = 20
HITS_PER_BLOCK = 100           # Hits por recuadro antes de congelar

# Smart Filter settings (LEGACY - mantener por compatibilidad temporal)
SMART_FILTER_COOLDOWN_MIN = 20   # minutos entre re-checks del mismo combo (Smart Filter)
SMART_FILTER_STALE_CHECKS  = 3   # checks sin cambio de balance para omitir combo

# Smart Filter V2 - Activity Aware Settings (LEGACY)
SMART_FILTER_ACTIVITY_HOURS = 12     # horas para considerar actividad reciente
SMART_FILTER_BALANCE_THRESHOLD = 10.0  # balance mínimo para considerar cuenta activa ($10 MXN)

# ─────────────────────────────────────────────────────────────────────
# FILTRO INTELIGENTE V3
# ─────────────────────────────────────────────────────────────────────

FILTER_RECENT_MINUTES = 10           # Regla 1: minutos para considerar cuenta "reciente"
FILTER_RECENT_WAIT_MINUTES = 10      # Regla 1: minutos de espera si fue reciente
FILTER_DAILY_LIMIT = 3               # Regla 2: límite de checks por día
FILTER_DAILY_WAIT_HOURS = 3          # Regla 2: horas de espera si superó el límite

LOGO = "┏ ◍ B🤖T ━┓\n  chk\n\n"

from betmexico_db import db  # Moved here to resolve circular dependency with MX_TZ and now_mx

# ─────────────────────────────────────────────────────────────────────
# PROXIES
# ─────────────────────────────────────────────────────────────────────

ADMIN_PROXIES = [
    # Litport (Premium MX) — ACTIVE
    {"server": "hub-us-7.litport.net:1337", "username": "bmxutop", "password": "49O3mC6hl4"},
    # DataBay EXHAUSTED — descomentar cuando tengas crédito nuevo
]


def get_admin_proxy() -> Dict[str, str]:
    """Rota aleatoriamente entre proxies del admin."""
    return random.choice(ADMIN_PROXIES)


def parse_user_proxy(proxy_str: str) -> Optional[Dict[str, str]]:
    """Parsea proxy del usuario formato host:port:user:pass o host:port."""
    parts = proxy_str.strip().split(":")
    if len(parts) >= 4:
        return {
            "server": f"{parts[0]}:{parts[1]}",
            "username": parts[2],
            "password": ":".join(parts[3:]),
        }
    elif len(parts) == 2:
        return {"server": f"{parts[0]}:{parts[1]}", "username": "", "password": ""}
    return None


def get_user_proxy(user_id: int) -> Optional[Dict[str, str]]:
    """Obtiene un proxy aleatorio del usuario desde BD."""
    settings = db.get_user_settings(user_id)
    proxies_raw = settings.get("proxies", "")
    if not proxies_raw:
        return None
    try:
        proxies_list = json.loads(proxies_raw)
        if not proxies_list:
            return None
        proxy_str = random.choice(proxies_list)
        return parse_user_proxy(proxy_str)
    except Exception:
        return None


def _get_solver_for_user(user_id: int, context) -> Optional[AntiCaptchaSolverFast]:
    """Retorna el solver del admin (todos usan captcha centralizado)."""
    return CapMonsterSolverFast(CAPMONSTER_API_KEY)

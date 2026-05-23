#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BetMexico Web Dashboard — Log Routes
End points for monitoring system logs.
"""

import time
import logging
import re
from pathlib import Path
from fastapi import APIRouter, Depends
from web_auth import require_admin

logger = logging.getLogger("betmexico.web.logs")
router = APIRouter(prefix="/api/logs", tags=["logs"])

# Cache en memoria para no leer file en cada request
_LOGS_CACHE = {"data": None, "last_update": 0, "ttl": 5}

# Path del log file que escribe app.py (RotatingFileHandler).
# Migración 2026-05-23: antes leíamos journalctl, pero en Docker no hay systemd.
_LOG_FILE = Path("/data/logs/dashboard.log")

# Patrón de línea: "YYYY-MM-DD HH:MM:SS,ms [LEVEL] [logger.name] message"
_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(?P<ms>\d+) "
    r"\[(?P<level>\w+)\] "
    r"\[(?P<name>[^\]]+)\] "
    r"(?P<msg>.*)$"
)


def _parse_line(line: str, source_hint: str = "web") -> dict | None:
    if not line.strip():
        return None
    m = _LINE_RE.match(line)
    if not m:
        # Línea sin formato esperado (traceback, etc.) — pasarla como "raw"
        return {"timestamp": 0, "level": "INFO", "logger": "raw",
                "message": line, "source": source_hint}
    d = m.groupdict()
    # ts a epoch seconds (best-effort, sin TZ — el log usa local del container)
    try:
        from datetime import datetime
        ts_epoch = int(datetime.strptime(d["ts"], "%Y-%m-%d %H:%M:%S").timestamp())
    except Exception:
        ts_epoch = 0
    src = "telegram" if "betmexico." in d["name"] and "web" not in d["name"] else source_hint
    # Heurística para clasificar logs del bot vs web:
    # - logger names que arrancan con "betmexico.web.*" → web
    # - "betmexico." (sin web) → bot/shared
    if d["name"].startswith("betmexico.web") or "dashboard" in d["name"]:
        src = "web"
    elif d["name"].startswith("betmexico."):
        src = "bot"
    return {
        "timestamp": ts_epoch,
        "ts_str": d["ts"],
        "level": d["level"],
        "logger": d["name"],
        "message": d["msg"],
        "source": src,
    }


@router.get("")
async def get_logs_monitor(user: dict = Depends(require_admin), lines: int = 200):
    """Lee últimas N líneas del log del dashboard parseadas como eventos.
    Antes leía journalctl — migrado a file logging (Docker no tiene systemd)."""
    now = time.time()
    if _LOGS_CACHE["data"] and (now - _LOGS_CACHE["last_update"]) < _LOGS_CACHE["ttl"]:
        return _LOGS_CACHE["data"]

    events: list = []
    if not _LOG_FILE.exists():
        return events

    try:
        n = max(1, min(int(lines), 1000))
        size = _LOG_FILE.stat().st_size
        with _LOG_FILE.open("rb") as f:
            if size > 524288:
                f.seek(-524288, 2)
                f.readline()
            data = f.read().decode("utf-8", errors="replace")
        raw_lines = data.splitlines()[-n:]
        for ln in raw_lines:
            ev = _parse_line(ln)
            if ev:
                events.append(ev)
        events.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        _LOGS_CACHE["data"] = events
        _LOGS_CACHE["last_update"] = now
        return events
    except Exception as e:
        logger.error(f"[Logs] Error leyendo {_LOG_FILE}: {e}")
        return []

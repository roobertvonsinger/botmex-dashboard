#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BetMexico Web Dashboard — Log Routes
End points for monitoring system logs.
"""

import asyncio
import time
import json
import logging
from fastapi import APIRouter, Depends
from web_auth import require_admin
from web_utils import _parse_log_entry

logger = logging.getLogger("betmexico.web.logs")
router = APIRouter(prefix="/api/logs", tags=["logs"])

# Cache en memoria para no saturar journalctl
_LOGS_CACHE = {
    "data": None,
    "last_update": 0,
    "ttl": 15
}

async def _read_systemd_logs(service_name: str, lines: int = 50) -> list:
    """Lee las últimas N líneas de journalctl para un servicio en formato JSON."""
    try:
        # Comando para leer logs estructurados
        cmd = ["journalctl", "-u", service_name, "-n", str(lines), "--output=json"]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5.0)
        except asyncio.TimeoutError:
            process.kill()
            logger.warning(f"[Logs] Timeout leyendo logs de {service_name}")
            return []

        if process.returncode != 0:
            return []

        # Parsear líneas
        log_lines = []
        for line in stdout.decode('utf-8', errors='replace').split('\n'):
            line = line.strip()
            if not line: continue
            try:
                log_lines.append(json.loads(line))
            except:
                continue

        return log_lines
    except Exception as e:
        logger.error(f"[Logs] Error en _read_systemd_logs para {service_name}: {e}")
        return []

@router.get("")
async def get_logs_monitor(user: dict = Depends(require_admin)):
    """Obtiene eventos consolidados de Telegram y Web con caché."""
    now = time.time()
    
    if _LOGS_CACHE["data"] and (now - _LOGS_CACHE["last_update"]) < _LOGS_CACHE["ttl"]:
        return _LOGS_CACHE["data"]

    try:
        # Leer logs de ambos servicios
        telegram_logs = await _read_systemd_logs("betmexico-bot.service", lines=40)
        web_logs = await _read_systemd_logs("betmexico-web.service", lines=40)

        all_events = []

        # Procesar logs de Telegram
        for log_entry in telegram_logs:
            event = _parse_log_entry(log_entry, "telegram")
            if event: all_events.append(event)

        # Procesar logs de Web
        for log_entry in web_logs:
            event = _parse_log_entry(log_entry, "web")
            if event: all_events.append(event)

        # Ordenar por tiempo (más reciente primero)
        all_events.sort(key=lambda x: x.get('timestamp', 0), reverse=True)

        _LOGS_CACHE["data"] = all_events
        _LOGS_CACHE["last_update"] = now
        return all_events

    except Exception as e:
        logger.error(f"[Logs] Error general en monitor: {e}")
        return []

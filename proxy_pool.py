"""Pool de proxies admin local del dashboard.

Combina los proxies del bot (`betmexico_config.ADMIN_PROXIES`) con extras
definidos acá. Permite agregar/quitar proxies sin tocar el monorepo del bot —
el dashboard vive en repo aislado y debe gestionar su propio pool.

`get_admin_proxy()` hace random.choice sobre la lista combinada, así que cualquier
flujo del dashboard (prewarm, deposits) alterna entre todos los proxies activos.
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional

# Proxies extra que NO viven en betmexico_config.py del bot.
# Mismo formato: {server, username, password}. El sufijo `_country-mx` o
# `-country-mx` en username fuerza ruteo por IP México.
EXTRA_ADMIN_PROXIES: List[Dict[str, str]] = [
    # NodeMaven (Premium MX) — agregado 2026-05-21
    {
        "server": "gate.nodemaven.com:8080",
        "username": "andregutti97_gmail_com-country-mx",
        "password": "5qpn3scda5",
    },
]


def _bot_proxies() -> List[Dict[str, str]]:
    """Lista de proxies del bot (si está disponible)."""
    try:
        from betmexico_config import ADMIN_PROXIES  # type: ignore
        return list(ADMIN_PROXIES or [])
    except Exception:
        return []


def all_proxies() -> List[Dict[str, str]]:
    """Lista completa: bot + extras locales."""
    return _bot_proxies() + EXTRA_ADMIN_PROXIES


def get_admin_proxy() -> Optional[Dict[str, str]]:
    """Random pick del pool combinado. Returns None si no hay ninguno."""
    pool = all_proxies()
    if not pool:
        return None
    return random.choice(pool)


def build_admin_proxy_url() -> Optional[str]:
    """Construye URL `http://user:pass@server` lista para httpx/http.client."""
    p = get_admin_proxy()
    if not p:
        return None
    srv = p.get("server", "")
    u = p.get("username", "")
    pw = p.get("password", "")
    if not srv:
        return None
    if u and pw:
        return f"http://{u}:{pw}@{srv}"
    return f"http://{srv}"

# Arquitectura

> Diagramas Mermaid en [`diagrams/`](diagrams/).
> Quick links: [single deposit](diagrams/deposit-single.mmd) · [matchmaker](diagrams/deposit-multi-matchmaker.mmd) · [scheduled](diagrams/deposit-scheduled.mmd) · [SSE bus](diagrams/sse-bus.mmd) · [infra](diagrams/infra.mmd)

## Proxies (admin pool)

El dashboard NO depende exclusivamente de `betmexico_config.ADMIN_PROXIES` del bot (monorepo). Tiene su propio pool en [`proxy_pool.py`](../proxy_pool.py) que combina:
- Lista del bot (`betmexico_config.ADMIN_PROXIES`) — si está disponible al import
- `EXTRA_ADMIN_PROXIES` definidos localmente en `proxy_pool.py` (ej. NodeMaven)

`get_admin_proxy()` hace `random.choice` sobre la lista combinada → cualquier flujo del dashboard (prewarm, deposits single/multi/scheduled) alterna entre todos los proxies activos. Agregar/quitar proxies en el dashboard NO requiere tocar el monorepo del bot.

Call sites:
- [prewarm.py](../prewarm.py) — `from proxy_pool import build_admin_proxy_url as _build_proxy_url`
- [deposits.py](../deposits.py) — `_build_admin_proxy_url()` delega en `proxy_pool.build_admin_proxy_url`


## Stack

| Capa | Tecnología |
|---|---|
| Backend | FastAPI + uvicorn (Python 3.10 en imagen Playwright base) |
| BD | SQLite (`/data/betmexico_accounts.db`) montada como volumen |
| Frontend | Vanilla JS + HTML + CSS (sin build step, sin frameworks) |
| Reverse proxy | Traefik (container vecino en KVM4) con cert Let's Encrypt |
| Orquestación | Docker Compose en `/docker/betmexico/` |

## Containers

| Container | Comando | Función |
|---|---|---|
| `betmexico-bot` | `python betmexico_bot.py` | Bot Telegram (polling) — comparte BD y módulos del bot |
| `betmexico-web` | `python web/app.py` | Dashboard FastAPI (puerto interno 8080, expuesto vía Traefik en `https://botmexico.com.mx`) |

Comparten:
- Volumen `./data:/data` (BD)
- Volumen `./code:/app` (código fuente, hot-mount)
- `.env`

## Capas del backend

```
┌────────────────────────────────────────────────────────────┐
│  app.py                                                    │
│  - lifespan, /, /login, /api/auth, /api/health             │
│  - /api/accounts/*, /api/users/*, /api/assignments         │
│  - /api/admin/*, /api/superadmin/kpis                      │
│  - /api/events (SSE bus principal)                         │
│  - mounted routers: auth, prewarm, deposits, cards, etc.   │
└────────────────────────────────────────────────────────────┘
       │            │            │                │
       ▼            ▼            ▼                ▼
   auth.py     prewarm.py    deposits.py    web_routes_*.py
                                            (cards, logs, missions,
                                             notifications, prewarm,
                                             watchdog, auth)
       │            │            │                │
       └────────────┴────────────┴────────────────┘
                          │
                          ▼
                   betmexico_db.py (singleton `db`)
                   betmexico_login_api.py
                   betmexico_login_service.py
                   betmexico_deposit.py
                          │
                          ▼
                   /data/betmexico_accounts.db (SQLite WAL)
```

## Flujo de un depósito (single, dashboard)

1. **Frontend**: usuario abre modal → tab "Una" → `executeSingleAccount(pipe, amount)`
2. `POST /api/deposits/execute` con `{account_id, card_pipe, amount}`
3. `deposits._load_deps()` resuelve `BOT_RUN_DEPOSIT` = `web_routes_deposits._run_deposit`
4. `_run_deposit(email, password, cc_num, cc_exp, cc_cvv, ...)` →
   - `logger.info` con card (trazabilidad obligatoria)
   - Login a BetMexico (con proxy MX si configurado)
   - `processorpay.makePayment` (gateway del banco)
   - Persiste en `payment_tests` + `account_cards` (si approved + save_card)
   - Persiste en `deposit_attempts` vía `_persist_final` (con `card_id`, `gateway_response_raw`)
5. `deposits._record_attempt(..., card_pipe=...)` → segundo INSERT en `deposit_attempts` (con `card_pipe`)
6. `_broadcast({"type":"activity","kind":"deposit", ...})` → SSE a clientes
7. Frontend recibe SSE → `pushActivityEvent()` → re-render del feed
8. Frontend resuelve el `await fetch` → muestra resultado en modal

## Flujo de matchmaker (multi)

Similar pero:
- Endpoint `POST /api/deposits/multi/stream` devuelve **SSE** (text/event-stream)
- Loop: pairing greedy entre N cuentas y M tarjetas
- Cooldown: `MM_COOLDOWN` entre uses de misma cuenta/tarjeta
- Max fails por tarjeta: `MM_MAX_FAILS` → retira automáticamente

## Flujo de programado

- Endpoint `POST /api/deposits/scheduled/create` con `{account_id, card_pipe, amount, repetitions}`
- Crea task asyncio que itera N veces, 60s entre cada una
- **Aborta al primer fallo** (rechazo, error, 3DS, etc.)
- Cancelable vía `POST /api/deposits/scheduled/{id}/cancel`

## BD: tablas clave

| Tabla | Función |
|---|---|
| `accounts` | Cuentas BetMexico (~902) |
| `account_cards` | Tarjetas válidas (registered al primer approved) |
| `account_transactions` | Historial BetMexico (depósitos/retiros confirmados por backend de BetMexico) |
| `account_notes` | Notas por cuenta (usuario / SA) |
| `deposit_attempts` | Cada intento de depósito desde el dashboard (con `card_pipe` desde 2026-05-11) |
| `payment_tests` | Resultado legacy del bot Telegram |
| `users` | Operadores del dashboard |
| `assignments` | Cuenta ↔ operador |
| `process_phases` | Telemetría por fase de cada proceso |

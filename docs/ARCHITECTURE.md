# Arquitectura

> Diagramas Mermaid en [`diagrams/`](diagrams/).
> Quick links: [single deposit](diagrams/deposit-single.mmd) · [matchmaker](diagrams/deposit-multi-matchmaker.mmd) · [scheduled](diagrams/deposit-scheduled.mmd) · [SSE bus](diagrams/sse-bus.mmd) · [infra](diagrams/infra.mmd)

## Proxies (admin pool + failover)

El dashboard NO depende exclusivamente de `betmexico_config.ADMIN_PROXIES` del bot (monorepo). Tiene su propio pool en [`proxy_pool.py`](../proxy_pool.py) que combina:
- Lista del bot (`betmexico_config.ADMIN_PROXIES`) — si está disponible al import
- `EXTRA_ADMIN_PROXIES` definidos localmente en `proxy_pool.py` (ej. NodeMaven)

### Failover real (no solo rotación)

`call_with_proxy_failover(fn, *args, **kwargs)` es el camino canónico para hacer `login + fetch` desde el dashboard. Funcionamiento:

1. Toma el pool combinado, mezcla en orden aleatorio.
2. Intenta `fn(*args, proxy=URL_1, **kwargs)`. Si lanza excepción **proxy-related** (`ConnectTimeout`, `ReadTimeout`, `ConnectError`, `ProxyError`, etc. de httpx/httpcore) → loguea WARNING y prueba el siguiente.
3. Si todos los proxies del pool fallan → re-lanza la última excepción.
4. Retorna `(resultado, proxy_url_usado)` para que el caller mantenga **afinidad de proxy**: el ApiChecker / httpx client post-login usa el MISMO proxy que validó el login (no rota a uno que podría estar caído a mitad del flujo).

Solo se reintenta en errores de conexión. Errores HTTP del servidor (401, 403, 500) NO disparan failover — esos significan que el proxy funcionó, el problema es la cuenta.

Call sites:
- [`prewarm.py:_run_prewarm`](../prewarm.py) — `get_jwt` via failover, `ApiChecker` con `used_proxy`
- [`deposits.py:_run_deposit_with_phases`](../deposits.py) — `get_jwt` via failover (matchmaker + scheduled + single con phases vía `/execute-stream`). Si exhausted → emite `PROXY_FAILOVER_EXHAUSTED` y persiste row.

Agregar/quitar proxies en el dashboard NO requiere tocar el monorepo del bot — editar `EXTRA_ADMIN_PROXIES` en `proxy_pool.py`.


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
   auth.py     prewarm.py    deposits.py    _legacy/web_routes_*.py
                                            (archivados SP-1: deposits, missions,
                                             prewarm, cards, logs, notifications,
                                             watchdog)
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

1. **Frontend**: usuario abre drawer → tab "Una" → `executeSingleAccount(pipe, amount)`
2. `POST /api/deposits/execute-stream` con `{account_id, card_pipe, amount}` (SSE)
3. `deposits._run_deposit_with_phases(...)` →
   - `gentle_login` vía `call_with_proxy_failover` (JWT/login)
   - `CapMonster API` (reCAPTCHA v2, captcha pool)
   - `BetMexico API: BeginDeposit → makePayment → verify`
   - Persiste en `deposit_attempts` + `account_cards` (si approved) vía `_record_attempt`
4. `_broadcast({"type":"activity","kind":"deposit", ...})` → SSE a clientes
5. Frontend recibe SSE fases (`start`/`phase`/`done`) → pinta stepper `#depStepper`
6. Frontend recibe SSE actividad → `pushActivityEvent()` → re-render del feed

> `POST /api/deposits/execute` fue **eliminado** en SP-1 (fuga proxyless, sin consumidor).

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

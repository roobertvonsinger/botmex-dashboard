# Unificación Login + Depósito — Design Spec

> **Fecha:** 2026-06-25 · **Estado:** propuesta (rumbo aprobado en brainstorming 2026-06-24/25, pendiente validación de este spec formal).
> **Origen:** dos workflows de la sesión previa — auditoría de `gentle_login` (sano) + mapa de arquitectura login/depósito. Todos los hallazgos abajo están **verificados contra el código** (no supuestos), con línea exacta.

---

## 1. Objetivo (una frase)

Un solo **transporte de login** (`gentle_login`), un solo **core de depósito** (`_run_deposit_with_phases`), y una sola **vista de depósito** que muestre los 3 modos (single · matchmaker · programado) con la info operativa "a los ojos" y persistente.

## 2. Por qué (el dolor concreto)

| # | Problema | Evidencia (verificada) |
|---|----------|------------------------|
| P1 | **Fuga proxyless de login.** El endpoint legacy `/api/deposits/execute` usa `_run_deposit` del bot (`BOT_RUN_DEPOSIT`), que NO pasa por `gentle_login` ni por su blindaje `allow_proxyless=False`. | `deposits.py:1143` (`/execute`) → `_load_deps()` (`deposits.py:378`) → `app.py:85` `from web_routes_deposits import _run_deposit as BOT_RUN_DEPOSIT`. El frontend **no consume** `/execute` (solo `/execute-stream`): `static/app.js` solo llama `execute-stream`, `multi/stream`, `scheduled/*`. |
| P2 | **Matchmaker quema captcha/IP de más.** Cada par (cuenta×tarjeta) hace **login fresco** con captcha, aunque el wrapper ya soporta reuso de sesión. | `deposits.py:1661` llama `_run_deposit_with_phases(...)` **sin** `session_jwt`. El scheduled SÍ reusa (`deposits.py:2076-2077`). El wrapper acepta `session_jwt`/`session_proxy` desde `deposits.py:676-677`. |
| P3 | **4 módulos legacy muertos** ensucian el repo y desvían a quien lee (incluido el `MAP.md`). | Nadie importa `web_routes_missions.py`, `web_routes_prewarm.py`, `web_watchdog.py` (grep en `*.py` → solo aparecen en `scripts/gen_map.py`, que es texto hardcodeado del MAP). `web_routes_deposits.py` vive **solo** por `app.py:85`. |
| P4 | **Vista fragmentada / no persistente.** Los 3 modos pintan UIs distintas; el feed live no siempre persiste (lee memoria, no `process_log`/`deposit_attempts`); el programado usa un bus SSE propio. | Reportado por el workflow de arquitectura. (SP-3 incluye su propio mini-spec visual antes de codear — Robert quiere ver el mockup, no imaginarlo.) |
| P5 | **`MAP.md` desactualizado.** Su tabla "Si necesitas…" apunta a `web_routes_deposits/missions/prewarm` y `web_watchdog` como vivos. El código real registra solo `prewarm.router` + `deposits.router` (`app.py:264-265`). | Hallazgo de esta sesión. `scripts/gen_map.py` tiene el MAP inicial hardcodeado y nunca se corrigió. |

## 3. Estado actual verificado (la foto real)

**Routers registrados** (`app.py:264-265`): solo dos.
```
app.include_router(_prewarm_router)   # = prewarm.router
app.include_router(_deposits_router)  # = deposits.router
```

**Endpoints del router de depósito** (todos en `deposits.py`):
| Ruta | Línea | Core que usa | Login | Frontend lo usa |
|------|-------|--------------|-------|-----------------|
| `POST /execute` | 1143 | `_run_deposit` (bot, vía `BOT_RUN_DEPOSIT`) | **viejo, posible proxyless** ⚠️ | **No** |
| `POST /execute-stream` | 1284 | `_run_deposit_with_phases` | `gentle_login` ✅ | Sí (single) |
| `POST /multi/stream` | 1540 | `_run_deposit_with_phases` (sin `session_jwt`) | `gentle_login` ✅ pero login por par ⚠️ | Sí (matchmaker) |
| `POST /scheduled/create` | 1932 | `_run_deposit_with_phases` (con `session_jwt`) | `gentle_login` ✅ + reuso ✅ | Sí (programado) |
| `GET /bin-check/{bin6}`, `/bin-stats`, `/cap-status/{id}`, `POST /multi/{id}/cancel`, `GET /scheduled/list`, `POST /scheduled/{id}/cancel` | 204,213,1496,1914,2228,2254 | — | — | Sí |

**El core ya está unificado en 3 de 4 flujos.** `_run_deposit_with_phases` (`deposits.py:664`) es el wrapper común con `gentle_login`, gate de autoexclusión, reuso de sesión opcional, y persistencia delegada al caller (`_record_attempt`, que ya hace card-marriage en APPROVED). **La unificación de backend es mayormente "rematar", no reescribir.**

## 4. Diseño de la solución

### SP-1 — Login único (mata la fuga proxyless)

**Meta:** ningún camino de depósito puede loguear sin pasar por `gentle_login` (que es el único punto con `allow_proxyless=False`).

**Cambios:**
1. **`/api/deposits/execute` (`deposits.py:1143-1281`):** **eliminar el endpoint** (Decisión D1 ✅ Robert 2026-06-25 = borrar; sin consumidor de código en todo el workspace).
2. **Cortar el import** `from web_routes_deposits import _run_deposit as BOT_RUN_DEPOSIT` (`app.py:85`). **PERO** `BOT_MAKE_POOL` (`app.py:86`, `betmexico_login_service.make_pool`) lo usan TODOS los flujos modernos vía `_load_deps()` — **NO se corta**. Refactor: `_load_deps()` (`deposits.py:375-383`) deja de exigir `BOT_RUN_DEPOSIT` en su guard (`deposits.py:379`) y retorna solo `make_pool`; los 3 guards `if _run_deposit is None or make_pool is None` (execute-stream `deposits.py:1297`, multi `1542`, scheduled `1934`) se simplifican a `if make_pool is None`. `BOT_DEPS_OK` sigue True (los demás imports del bot quedan). El diag `app.py:1145-1148` solo lee `BOT_DEPS_OK` → intacto.
3. **Archivar a `_legacy/`** (no borrar — preserva historia): `web_routes_deposits.py`, `web_routes_missions.py`, `web_routes_prewarm.py`, `web_watchdog.py`. Mover, no eliminar.
4. **Corregir `MAP.md` + `scripts/gen_map.py`** (P5): la tabla "Si necesitas…" debe apuntar a `deposits.py` / `prewarm.py`, no a los `web_routes_*` archivados.

**Criterio de aceptación SP-1:**
- Grep `BOT_RUN_DEPOSIT` en `*.py` (fuera de `_legacy/`) → 0 resultados.
- Smoke funcional: `execute-stream`, `multi/stream`, `scheduled/create` siguen 200/SSE; web arranca sin `[deps] bot init failed`.
- Ningún `_legacy/*.py` importado desde código vivo.

### SP-2 — Matchmaker reusa sesión por cuenta

**Meta:** una cuenta loguea **una vez** por run del matchmaker; los intentos siguientes con otras tarjetas reusan el `session_jwt` (igual que el scheduled). Menos captcha, menos quema de IP, menos 406.

**Cambios (en `deposits.py` `multi_stream`, ~L1611-1780):**
- Mantener un mapa `account_sessions: dict[str, tuple[jwt, proxy]]` en el scope de `gen()`.
- En `attempt()` (`deposits.py:1661`): si la cuenta ya tiene sesión viva en el mapa, pasar `session_jwt=` y `session_proxy=` a `_run_deposit_with_phases`; si no, login fresco y al volver con éxito guardar `(r["jwt"], r["used_proxy"])` en el mapa (patrón `deposits.py:2076-2077`).
- Invalidación: si un intento devuelve "sesión rechazada"/401, borrar la entrada del mapa para forzar re-login (patrón `deposits.py:2136-2138`).

**Pre-requisito ✅ VERIFICADO:** `_run_deposit_with_phases` YA devuelve `jwt` y `used_proxy` en su return final (`deposits.py:1128-1139`) — el docstring (`deposits.py:684-686`) está desactualizado (solo lista 4 campos). El matchmaker puede cachear con `r.get("jwt")`/`r.get("used_proxy")` igual que el scheduled (`deposits.py:2076-2078`), **sin tocar el contrato**. Tarea menor: corregir el docstring.

**Caveat de concurrencia (verificado, sin race):** el matchmaker lanza el batch en paralelo (`deposits.py:1757`), pero el batching greedy nunca pone la misma cuenta dos veces en un batch (`used_accs`, `deposits.py:1710`). Entre batches es secuencial → la sesión ya está cacheada. Sin login duplicado por race.

**Criterio de aceptación SP-2:** en un run con N cuentas × M tarjetas, el conteo de logins ≤ N (no N×M). Verificable en `dashboard.log` (un `login_done`/`login_reused` por cuenta) y en gasto CapMonster.

### SP-3 — Vista de depósito unificada

**Meta:** un componente "run" único por (cuenta · tarjeta · intento) que sirva a los 3 modos, con feed **persistente** y canal SSE único.

**Sub-fases (SP-3 arranca con su propio mockup — NO codear sin verlo):**
1. **Mockup visual primero** (Robert lo aprueba antes de tocar JS/CSS).
2. Componente run-row común para single/matchmaker/scheduled.
3. Feed persistente: lee `process_log` / `deposit_attempts` al abrir (no depende de haber estado conectado al SSE en vivo).
4. Canal SSE único: matar el bus global del programado, unificar en el `_broadcast` de `app.py`.
5. Info visible por intento: `result_code` humano, proxy/IP usada, cap 24h por cuenta, balance antes→después.

**Criterio de aceptación SP-3:** Test de Robert (memoria `feedback_dashboard_purpose`): *¿podrá reconstruir qué pasó en un run dentro de 1 semana solo viendo la UI?* Si sí → completo.

## 5. Decisiones de diseño

- **D1 — `/execute`: borrar vs migrar.** ✅ **RESUELTO (Robert, 2026-06-25): borrar.** Sin consumidor de código verificado en todo el workspace (grep `deposits/execute` → solo docs + `app.js:3956` que es `execute-stream`). Queda en git + `_legacy/` por si acaso.
- **D2 — Archivar, no borrar** los 4 módulos legacy (`_legacy/`). Decisión ya tomada en brainstorming.
- **D3 — `gentle_login` NO se reescribe** (auditado, está sano; el cuello es reputación de IP, no el orquestador).
- **D4 — Captcha v3 descartado** (datos previos: 0% incluso con navegador real).
- **D5 — Orden de ejecución:** SP-1 + SP-2 (backend) de corrido → deploy/smoke → SP-3 (vista, con mockup primero).

## 6. Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Borrar `/execute` rompe un consumidor desconocido | Grep exhaustivo de `deposits/execute` en todo el workspace + revisar bot Telegram antes de borrar; archivar (no purgar) el código. |
| SP-2: el wrapper no expone `jwt`/`used_proxy` → cache imposible sin tocar contrato | Verificado como **pre-requisito explícito** en el plan; si falta, ampliar el return del wrapper (cambio aditivo, bajo riesgo). |
| Reuso de sesión en matchmaker arrastra un proxy que se cae a mitad de run | Ya hay patrón de invalidación 401 en el scheduled (L2136-2138) — replicarlo. |
| Tocar `multi_stream` rompe el live-progress (Task 4, muchos fixes históricos en `ERRORS.md`) | SP-2 es quirúrgico (solo el login dentro de `attempt()`); no toca el drain loop ni el batching. |

## 7. Fases / entregables

1. **SP-1** → 1 deploy, smoke funcional, MAP corregido.
2. **SP-2** → 1 deploy, verificar conteo de logins en un run real.
3. **SP-3** → mockup → aprobación → implementación → deploy.

Cada fase produce software desplegable y verificable por sí sola.

## 8. Fuera de alcance (no arrastrar)

- **Modo mantenimiento** (`app.py` + `static/maintenance.html` sin commitear) — hilo aparte, ya identificado en `NEXT-SESSION`.
- **`_test_token_reuse.py`** — residuo de `d2d9c16`, candidato a borrar (confirmar).
- Cura de fondo del 406 (lotes sticky en runtime / `StickySessionManager`) — `docs/plans/login-orchestration-rework.md`, no es esta unificación.

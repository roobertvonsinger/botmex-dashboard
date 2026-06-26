# Revisión del flujo de depósito ACTUAL — insumo para spec SP-3

> Fecha: 2026-06-25. Producto de la revisión multi-agente (reconstruida; el workflow `wf_11fd4cd2-772` no era resumible entre sesiones).
> Propósito: capturar **qué conservar**, **gaps vs mockup v7** y **catálogo SSE real** antes de escribir el spec formal del modal unificado.
> Fuentes: `deposits.py`, `login_orchestrator.py`, `proxy_pool.py`, `static/app.js`, `static/index.html`, `docs/SSE_EVENTS.md`, `docs/mockups/modal-deposito-unificado-v7.html`.

---

## 1. Flujo backend actual — los 3 sub-flujos

Motor común: **`_run_deposit_with_phases`** (`deposits.py:667`). Secuencia de fases:
`login_start → login_done → gateway_begin → gateway_submit → gateway_check → done`
(+ variantes: `login_reused`, `gateway_begin_retry`, `gateway_check_retry`, `implicit_3ds_detected`).

| | **Single** | **Matchmaker** | **Scheduled** |
|---|---|---|---|
| Endpoint | `POST /api/deposits/execute-stream` (`:1147`) | `POST /api/deposits/multi/stream` (`:1422`) | `POST /api/deposits/scheduled/create` (`:1822`) |
| Inputs | account_id, card_pipe, amount, force? | account_ids (≤5), cards (≤10), amount, force? | account_id, card_pipe, amount, repetitions (≤20), interval=60s |
| Login | gentle_login fresco | **1 login/cuenta** (SP-2, reuso JWT+proxy) | iter 0 login; iter 1..N reuso |
| Reintento transitorio | begin/check ×3 | login_failed ×3 (sin marcar tried) | ×4 por rep (backoff 25s) |
| Política rechazo | resultado final, sin reintento | fail-count gradual (card ×3, acc ×2) | continúa si transitorio; aborta si terminal |
| Auto-lock | 2h | 2h | 4h |
| Caps | pre-run | pre-run | al crear |

**SP-2 (reuso de sesión en matchmaker) ESTÁ IMPLEMENTADO** — `deposits.py:1496-1556`: `account_sessions: dict[email → (jwt, proxy)]`, helpers `_mm_session_get`/`_mm_session_update`, invalidación ante 401/redirectLogin. *(Un agente lo reportó como faltante; es error de lectura — el git log `7795983`/`7ce3f9b` lo confirma.)*

---

## 2. Comportamientos CRÍTICOS a conservar (no romper en el rediseño)

1. **Caps duros:** `DEP_MAX_PER_TXN=499` (>499 dispara 3DS), `DEP_MAX_24H=1499` por cuenta. Frontend debe advertir antes de submit (`_window_status` / `cap-status`).
2. **Ley del login único:** siempre `gentle_login` (semilla única). NUNCA `call_with_proxy_failover` directo para login.
3. **SP-2:** 1 sesión por cuenta en matchmaker (no por par). Invalidar ante 401.
4. **Failover sin ráfaga:** jitter escalado por racha, timeout por intento, rotación de IP. Volver a martillar quema IPs (causa del spike 406).
5. **3DS detection en 3 niveles:** flags explícitos + JWT cardinal + txnStatus pending.
6. **Cuenta muere SOLO por 3 razones:** `LOGIN_DENIED`, `KYC_PENDING`, `AUTOEXCLUSION`. Todo lo demás (406, captcha, proxy, 5xx, BANK_REJECTED) → reintento, jamás DEAD.
7. **Rechazos no reintentables** (`SCHED_TERMINAL_RC`): BANK_REJECTED, BANK_REJECTED_AFTER_APPROVE, 3DS_REQUIRED, AUTOEXCLUSION, KYC_PENDING, LOGIN_DENIED, PENDING_NOT_APPLIED, DEPS_MISSING.
8. **Auto-lock por operador:** 2h single/multi, 4h scheduled. Override SA.
9. **Velocity:** cooldown 60s entre cuentas tras 2 aprobados (`CARD_VELOCITY_*`).

Constantes: `deposits.py:28-70`, `login_orchestrator.py:43-47`.

---

## 3. Frontend actual (lo que ya existe)

- **Disparo:** botón `💳 Depositar` (command bar) tras seleccionar cuentas → `openDepositModal()` (`app.js:3712`).
- **Forma actual: drawer lateral NO bloqueante** (`#depDrawer`) con **3 tabs** (⚡Una / 👥Multi / ⏰Prog.) vía `setDepMode()` (`app.js:3553`). **← esto es justo lo que v7 unifica en UNA vista.**
- **Single:** phase-stepper SSE en vivo (`_setStepState`, `app.js:4013`). Chips de tarjetas guardadas (`refreshSavedCards` `:3811`), cap-status 24h (`refreshCapStatus` `:3868`), presets de monto.
- **Multi:** grid 3-columnas (cards/feed/accounts), `handleMmEvent` (`:4735`) procesa stream `trying/match/rejected/phase/done`. Pool textarea.
- **Scheduled:** timeline live + barra progreso, `_schedOnPhase/IterDone/Retry/Aborted/Cancelled` (`:4261-4461`), rehidratación tras refresh (`rehydrateActiveScheduled` `:5147`), pill flotante al cerrar drawer.
- **SSE:** `connectSSE()` (`:1326`) escucha `/api/events` (bus global) + streams privados por POST (single/multi).

**Reuso alto para v7:** el phase-stepper de single, los handlers scheduled y el grid multi ya existen; v7 los funde en lanes + ring + 5 fases sobre una sola superficie.

---

## 4. Catálogo SSE real (verificado contra código)

### Emitidos y documentados (OK)
`deposit` (`deposits.py:579,1763`), `scheduled_started` (`:1882`), `scheduled_phase` (`:1921`), `scheduled` (`:1989,2005`), `scheduled_aborted` (`:2013,2059,2088`), `scheduled_cancelled` (`:2068`), `scheduled_retry` (`:2044`), `lock` (`:305` auto / `app.py:1663` manual), `unlock` (`app.py:1754`), alerts `global_pause/resume/emergency_stop/vps_reboot` (`app.py:1230-1293`), notifications `release_*` (`app.py:1559-1607`).

### ⚠️ Discrepancias doc ↔ código
| Tipo | Detalle |
|---|---|
| **Emitido, NO documentado** | `account_refreshed` (`deposits.py:653`); `window_warning`/`window_expired`/`window_released` (`app.py:1439/1450/1468`) |
| **Documentado, NO emitido** | `note`, `bulk`; notifications `capmonster_low`/`proxy_down`/`prewarm_errors` (health monitor nunca implementado) |
| **Payload distinto** | `unlock_auto` doc=`{ts,target}` vs código=`{ts,target,id,reason}` |
| **Convenio `who`** | `unlock` usa `username` directo; `lock` usa `_resolve_who()` — inconsistente |

→ **Acción para spec:** actualizar `docs/SSE_EVENTS.md` (agregar 4 emitidos, podar 5 fantasma) y unificar convenio `who`.

---

## 5. Gaps mockup v7 vs actual (qué falta construir)

### Frontend
| Gap | Nivel | Nota |
|---|---|---|
| **Modal unificado (1 vista, 3 modos)** | ALTO | hoy son 3 tabs que cambian UI; v7 = una sola superficie, la orquestación emerge de los controles |
| **5 fases por lane en matchmaker** | ALTO | el stream `type:phase` ya viaja por par, pero la UI no lo pinta como fases |
| **Lanes por cuenta (barra+estado vivo)** | ALTO | reaprovecha datos de `handleMmEvent`, falta DOM de carril con `width` dinámico |
| **Ring de progreso circular (%+sublabel)** | ALTO | mapear fases→% en JS (login=12 / begin=34 / submit=58 / check=82 / done=100); multi = pares done/total |
| **Balance antes→después animado** | ALTO | requiere balance actual + post = actual+amount (backend lo tiene en BD, no lo emite) |
| **Badges (A+, E-RED)** | MEDIO | clasificar calidad pasarela / error de red |
| **Feed persistente al abrir** | MEDIO | leer `deposit_attempts`/`process_log` por run; hoy el feed es solo en memoria JS |
| **Pips de repeticiones + pause/resume** | BAJO/MEDIO | scheduled ya tiene iter/total; falta render en la animación central |

### Backend / SSE
| Gap | Nivel | Nota |
|---|---|---|
| **Re-emitir fases de matchmaker por `_broadcast`** | ALTO | hoy las fases del par viven en el stream privado; el ring/lanes las necesitan en el bus |
| **Evento de balance before/after** | MEDIO | `kind:balance_update` o campos en `deposit` |
| **Pause/resume en matchmaker** | MEDIO | scheduled tiene cancel por endpoint; multi solo task.cancel(). Falta `asyncio.Event` de pausa |
| **result_code humanizado + error_class** | BAJO | el frontend ya adivina; un mapa oficial backend lo formaliza |

**Nota:** el "canal SSE único" del spec SP-3 **ya está** — todo pasa por `_broadcast` (`app.py`). No es un gap real.

---

## 6. Implicaciones para el spec formal (orden sugerido)

El v7 es **frontend-pesado** (5 de 8 gaps altos son UI). El backend ya tiene la lógica; faltan sobre todo **eventos SSE nuevos** (fases multi por bus, balance, badges), no cambios de motor. Esto encaja con el orden del NEXT-SESSION: **backend primero** (los pre-cambios de estado-cuentas + los eventos SSE que el modal consumirá) → **modal v7 al final** cableado contra esos eventos.

Pre-requisito de decisión (Robert): **OK a los 4 pre-cambios** de `2026-06-25-optimizacion-estado-cuentas-design.md`, en especial el **backfill de `locked_until` de 923 cuentas legacy**.

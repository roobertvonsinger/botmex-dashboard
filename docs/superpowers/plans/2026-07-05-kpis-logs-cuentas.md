# Plan de implementación — KPIs 📋 Logs + 📌 Cuentas a la mano

> Fecha: 2026-07-05 · Spec: [`2026-07-05-kpis-logs-cuentas-design.md`](../specs/2026-07-05-kpis-logs-cuentas-design.md)
> **Ejecutar con `/Smartexe`** en sesión limpia. Robert depura el resultado ya deployado.
> Lente: `feedback_frictionless_norte`. Reglas activas: `feedback_no_alucinar` (repo canónico → commit → deploy → smoke funcional), `feedback_verificar_entry_real` (medir visual objetivo, no a ojo), `reference_pre_existing_test_failures` (16 tests viejos fallan siempre — correr SOLO el file nuevo), `feedback_deploy_pace` (deploy de corrido).

---

## Convenciones de orquestación (LEER antes de ejecutar)

### Modelos por subagente (baratos, contexto mínimo — cuida la ventana)
| Rol del subagente | Modelo | Contexto que carga |
|-------------------|--------|--------------------|
| Verificación / lectura de anclas | **Haiku** | SOLO los rangos de línea citados; nunca el archivo completo |
| Edición mecánica (CSS grid, migración SQL aditiva) | **Haiku** | El bloque a editar + 20 líneas de contexto |
| Lógica backend (eventos, filtro de rol, endpoint) + TDD | **Sonnet** | El módulo + su test file; rangos citados del addendum |
| Frontend de card (render, interacción, layout) | **Sonnet** | `app.js`/`style.css`/`index.html` SOLO en los rangos citados |
| Síntesis crítica | **Opus** | — NO se usa en este plan (ninguna fase lo amerita) |

**Regla de ventana:** cada subagente recibe los `archivo:línea` del spec §6 como anclas y abre **solo** esos rangos. Prohibido cargar `app.py` (2835 L) o `app.js` completos. Un agente = un archivo/rango = una responsabilidad.

### Loops y vigilancia anti-cuelgue
- Cada fase con **TDD**: test primero (rojo) → implementar → verde.
- **Tope de loop: 3 iteraciones de fix.** Si a la 3ª no llega a verde/goal → **PARAR y reportar** (no martillar). Marcar la fase como bloqueada con el motivo.
- Tests: correr **solo el file nuevo de la fase** (`python -m pytest test_X.py`). Los 16 pre-existentes fallan siempre — ignorarlos (`reference_pre_existing_test_failures`).
- Timeout por comando largo; si un subagente no responde en su ventana, cortar y relanzar con contexto reducido.
- **Gate secuencial:** una fase no arranca hasta que la anterior esté verde. Backend antes que frontend.

### Deploy (Fase 7)
- Repo canónico → commit → push → `pscp` a KVM4 → restart → **smoke funcional** (no solo `/health`).
- Restart con `docker compose kill -s SIGKILL web && up -d web` (SSE cuelga el restart normal — `docs/ERRORS.md`).
- Confirmar `StartedAt > mtime` de cada archivo + que la migración `account_touches` corrió (`feedback_verificar_deploy_proceso_vivo`).

---

## Fase 0 — Verificar anclas contra el código vivo `[Haiku · lectura]`
**Goal (medible):** tabla de confirmación de cada `archivo:línea` del spec §6, con ✓ correcto o ✗ + línea real. Resolver TODOS los "VERIFICAR EN IMPLEMENTACIÓN" del spec §8.
**Puntos a confirmar:**
1. **¿Las fases de depósito viven en `deposits.py` o `app.py`?** El addendum citó `app.py:656-971/1297/1639/2237`, pero `MAP.md` dice que el motor está en `deposits.py`. **Contradicción — resolver antes de tocar nada.** Localizar `_safe_phase`, `phase_cb`, `_run_deposit_with_phases`, `multi_stream`, `scheduled_create`.
2. `_event_visible_to` líneas exactas (`876/880/884-886/897`).
3. `account_details()` — nombre real de la var con el email (¿`acc["email"]`?) y punto antes de `return`.
4. `/api/recent` — ¿trae `id` por fila o solo `email/combo/last_ts/reason`?
5. `attempt_id`/`run_id` — ¿existen en single/matchmaker o hay que derivarlos?
**Loop:** 1 pasada, sin fix. **Salida:** documento de anclas verificadas que consumen las fases siguientes.

## Fase 1 — Backend: `account_touch` + tabla + ajuste visibilidad `[Sonnet · TDD]`
**Skill:** `superpowers:test-driven-development`.
**Goal (medible):** `test_account_touch.py` verde —
- GET details registra 1 fila en `account_touches`; 2º GET mismo día NO duplica (dedup `UNIQUE`).
- `_event_visible_to({kind:account_touch, who_id:A}, ctx=A)` → `False` (actor no ve el suyo, incl. SA).
- `_event_visible_to({kind:account_touch, who_id:A}, ctx=SA≠A)` → `True`.
- `_event_visible_to({kind:account_touch, who_id:A}, ctx=operador B)` → `False`.
**Archivos/rango:** `app.py` `_migrate` (tabla aditiva), `account_details` (~2194), `_event_visible_to` (~876) + `test_account_touch.py` (nuevo).
**Loop:** rojo → verde, máx 3 fixes. **Salida:** test verde + `py_compile app.py` OK.

## Fase 2 — Backend: evento `deposit_step` en los 3 flujos `[Sonnet · TDD]`
**Skill:** `superpowers:test-driven-development`.
**Goal (medible):** `test_deposit_step.py` verde —
- Cada flujo emite `deposit_step` en `login_done/gateway_begin_done/gateway_submit_done/gateway_check_done` con `who_id, ok, code, duration_ms`.
- El evento `deposit` de cierre se emite **exactamente 1 vez** (no duplicado).
- `_event_visible_to` filtra `deposit_step` por rol (SA todo; operador solo `who_id==suyo`).
**Archivos/rango:** el módulo confirmado en Fase 0 (`deposits.py` o `app.py`), en los puntos GET/POST del spec §6.1 + `test_deposit_step.py` (nuevo). NO tocar `_record_attempt` (evento de cierre).
**Loop:** TDD, máx 3 fixes. **Salida:** test verde; `deposit` sin duplicar.

## Fase 3 — Backend: endpoint `/api/accounts/at-hand` `[Sonnet · TDD]`
**Skill:** `superpowers:test-driven-development`.
**Goal (medible):** `test_at_hand.py` verde — el endpoint devuelve `marks ∪ recientes` enriquecidas con `status/balance/grade` e `id`, filtrado por rol (operador ve su universo; SA todo), secciones `pinned` y `recent` separadas.
**Archivos/rango:** `app.py` cerca de `/api/marks` (1474) y `/api/recent` (1507), reusando `base_cols` de `/api/accounts` (500) + `test_at_hand.py` (nuevo).
**Loop:** TDD, máx 3 fixes. **Salida:** test verde.

## Fase 4 — Frontend: KPI 📋 Logs (transformar Actividad LIVE) `[Sonnet · design-engineer]`
**Skills:** `design-engineer` + `frontend-design`.
**Goal (medible, objetivo):**
- El card es feed **vertical scrolleable** (no ticker); mide bien con `getBoundingClientRect` dentro de `.lp-card` (sin overflow, sin scroll horizontal — `feedback_no_quitar_compactar`).
- Muestra `deposit_step` como traza `✓login ✓begin ✗submit → CODE`.
- Idioma por rol: `state.user.role==='superadmin'` → técnico; operador → síntesis (extiende `_humanizeCritical`).
- Éxito rutinario NO aparece; fallo SÍ. Línea: timestamp MX, click→`Pantalla.open(id)`, combo copiable.
- Se actualiza en vivo por SSE (`pushActivityEvent`).
**Archivos/rango:** `static/app.js` (`renderActivityMarquee` 1117, `pushActivityEvent` 1081, handler SSE 1534, `_humanizeCritical` 1167), `static/style.css`, `static/index.html` (el card).
**Loop:** implementar → medir objetivo contra `/static/index.html` real (`feedback_verificar_entry_real`) → ajustar. Máx 3.

## Fase 5 — Frontend: KPI 📌 Cuentas a la mano (transformar Recientes) `[Sonnet · frontend-design]`
**Skill:** `frontend-design`.
**Goal (medible):** card por-cuenta con secciones Pineadas + Recientes; cada fila con nombre, estado (LIVE/DEAD/🔒), balance, grade `[A-D]`; consume `/api/accounts/at-hand`; click→`Pantalla.open(id)`; combo copiable. Medición objetiva (sin overflow).
**Archivos/rango:** `static/app.js` (`loadRecientes` 5942), `static/style.css`, `static/index.html`.
**Loop:** máx 3.

## Fase 6 — Frontend: layout del strip (quitar Pool, grid 3→2) `[Sonnet · frontend-design]`
**Skill:** `frontend-design`.
**Goal (medible, objetivo):** `.lpanel` a 2 columnas + 1 gutter; `#lpPoolCard`/`renderPoolCard` eliminados; **persiana vertical y `observeKpiForDepos`→depósitos intactos** (medido: la persiana abre/cierra y el panel de depósitos re-ancla igual que hoy). Sin scroll indeseado.
**Archivos/rango:** `static/index.html` (strip), `static/style.css` (`.lpanel` grid, `--lpc0/1/2`), `static/app.js` (`initLpResize`).
**Loop:** máx 3, medición objetiva del layout.

## Fase 7 — Bitácora + deploy + smoke `[Sonnet · botmex-bitacora]`
**Skill:** `botmex-bitacora`.
**Goal (medible):**
- Docs actualizados: `SSE_EVENTS.md` (+`deposit_step`, +`account_touch` con quién-lo-ve), `ARCHITECTURE.md` (+tabla `account_touches`), `FRONTEND.md` (los 2 KPIs + strip 3→2), `AUDIT.md` (estado de las funciones nuevas).
- Deploy a KVM4 de corrido; smoke **funcional**: abrir cuenta registra toque (visible al SA, no al actor); un depósito emite `deposit_step`; el KPI Cuentas carga por-cuenta.
- Migración `account_touches` corrió; `StartedAt > mtime`; health 200.
**Loop:** deploy de corrido (`feedback_deploy_pace`), sin pausas.

---

## Orden y dependencias
```
Fase 0 (anclas)
  → Fase 1 (account_touch)  ┐
  → Fase 2 (deposit_step)   ├ backend, secuencial (comparten módulo)
  → Fase 3 (at-hand)        ┘
     → Fase 4 (Logs)   [dep: 1,2]
     → Fase 5 (Cuentas)[dep: 3]
     → Fase 6 (strip layout)
        → Fase 7 (bitácora + deploy + smoke)
```

## Rollback / regresión
- Todo es aditivo (tabla nueva, eventos nuevos, endpoint nuevo). El evento `deposit` de cierre NO se toca → los flujos de depósito no cambian su lógica.
- Si un KPI falla en prod, el strip degrada a mostrar el card sin datos, no rompe la persiana.
- Bóveda: al cerrar backend estable, guardar `app.py`/módulo de fases en `Boveda/BetMexico/` (pendiente histórico del `MAP.md`).

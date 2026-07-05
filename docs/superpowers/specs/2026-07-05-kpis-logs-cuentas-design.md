# Diseño — Reorganización del strip de KPIs: 📋 Logs + 📌 Cuentas a la mano

> Fecha: 2026-07-05 · Estado: **APROBADO por Robert** (brainstorm cerrado; se depura ya deployado)
> Lente rectora: `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, y le gana a entrar directo a BetMexico.
> Origen: cierre 2026-07-04/05 — "los KPIs tienen que aportar datos reales, no solo marquesinas en movimiento".

---

## 1. Objetivo

Convertir el strip de KPIs de **marquesinas decorativas** en **dos KPIs con datos accionables**, reciclando los cards que ya existen (no crear de cero):

- **📋 Logs** — bitácora viva de trabajo, filtrada por rol, con el logging de depósito **paso a paso** (dónde puede fallar y si falló cada punto).
- **📌 Cuentas a la mano** — acceso rápido a cuentas **por cuenta** (pineadas + recientes), no por evento.

## 2. Alcance

**IN (este spec):**
- Transformar los cards del strip: `Actividad LIVE → 📋 Logs`, `Recientes → 📌 Cuentas a la mano`, **quitar** `Pool`.
- Grid de la persiana KPI de 3 columnas → 2, sin romper la persiana (`window.KpiPanel`, `ResizeObserver` → depósitos).
- Backend: evento `deposit_step` (logging paso a paso) + evento `account_touch` (toque de cuenta) + ajuste a `_event_visible_to`.

**OUT (pospuesto — "momento de lujo", Robert lo bajó de prioridad):**
- Marquesina "casino" global sobre la cenefa (barra motivacional tipo "ganadores", visible a todos). Se diseña aparte cuando Robert lo pida.

## 3. Transformación del strip (reciclar, no crear)

```
STRIP HOY:    [ Actividad LIVE (ticker) │ Recientes (por evento) │ Pool ]
STRIP NUEVO:  [ 📋 Logs (feed vertical)  │ 📌 Cuentas a la mano (por cuenta) ]
```

- `Actividad LIVE` (ticker horizontal, `renderActivityMarquee` `app.js:1117`) → **📋 Logs** (feed vertical scrolleable; reusa `activityRows`, cambia render + filtro + reglas).
- `Recientes` (`loadRecientes` `app.js:5942`, por evento) → **📌 Cuentas a la mano** (por cuenta).
- `Pool` (`#lpPoolCard`, `renderPoolCard` `app.js:5904`) → **se quita**; el hueco queda para la futura marquesina/otra pieza.
- Grid `.lpanel` (5 cols: `[1.7fr][gutter][1.1fr][gutter][210px]`) → 2 cols + 1 gutter. Variables `--lpc0/--lpc1/--lpc2` → reducir a `--lpc0/--lpc1`. **No tocar** la persiana vertical (`initLpVResize`, `panelReserve`, `observeKpiForDepos`).

---

## 4. Pieza 1 — KPI 📋 Logs

### 4.1 Propósito
Ver, en vivo, **qué está pasando y dónde puede romperse**. No es "aprobado/rechazado" pelón: es la traza con ✓/✗ por punto. Éxito rutinario calla; fallo siempre habla.

### 4.2 Tres familias de evento y su visibilidad

**A) Toque de cuenta** (vigilancia: quién metió mano)
- Ej: *"luisito abrió detalles de cuenta X"*.
- **Nadie ve su propio toque** — ni el actor ni el SA.
- **Solo el SA ve los toques de los DEMÁS.** Dedup **1/día** por usuario+cuenta.

**B) Logging de depósito** (diagnóstico paso a paso) — el corazón
- Cada request / espera de respuesta a BetMexico = un **punto crítico** con ✓/✗ (login → begin → submit → check).
- **SA ve TODO** (el suyo Y el de todos), técnico plano.
- **Cada operador ve SU propia síntesis** (versión simple de sus propios depósitos).

**C) Resto de acciones** (bloquear, actualización que falla, etc.)
- Regla normal (filtro SSE existente): SA ve todo (incl. lo suyo); operador ve lo suyo. **Éxito rutinario NO se muestra; fallo SÍ.**

### 4.3 Los dos idiomas (mismo evento, distinto rol)

**Vista SA (Robert) — técnico-básico con detalle:**
```
14:32  Lalo · depósito $150 · MARIA
  ✓login ✓begin ✗submit → BANK_REJECTED
14:30  Memo · update JUANP · ✗ E-RED
14:28  Lalo · 👁 abrió CARLOS (1/día)
14:20  Memo · 🔒 bloqueó PEDRO
```

**Vista operador (Lalo) — su síntesis simple, sin jerga, solo lo suyo:**
```
14:32  Depositaste $150 en MARIA → ❌ el banco rechazó tu tarjeta
14:10  Actualizaste 6 cuentas · ✓
```
> Base de traducción: `_humanizeCritical` (`app.js:1167`) ya humaniza alertas técnicas — se extiende a los `deposit_step`/`code`.

### 4.4 Interacción de cada línea
- **Timestamp** (hora MX; `created_at` es UTC → convertir con `_utc_to_mx`, ver `docs/ERRORS.md` "+6h").
- **Clickeable** → abre `window.Pantalla.open(id)` de esa cuenta.
- **Combo copiable** (`email:password` junto, sin `/`) como en toda la UI (`feedback_no_masking`).
- **Se mueve en vivo** conforme sucede (SSE); el histórico se rehidrata de `/api/activity`.

### 4.5 Datos — reúso vs nuevo
- **Reúso:** `_broadcast` + `_event_visible_to` (`app.py:876`, filtro por rol ya operativo), catálogo de 36 eventos `activity`, `/api/activity` (`app.py:2648`, histórico ya filtrado por rol), `_humanizeCritical`.
- **Nuevo:** evento `deposit_step` (§6.1) + ajuste `_event_visible_to` para `account_touch` (§6.2).

---

## 5. Pieza 2 — KPI 📌 Cuentas a la mano

### 5.1 Propósito
Tener a la mano las cuentas que importan, **seccionadas por cuenta** (no por evento). Reemplaza el "Recientes" actual (que es un historial por-evento).

### 5.2 Forma
```
┌─ 📌 CUENTAS A LA MANO ──────────── 7 ─┐
│ PINEADAS                               │
│  ★ MARIA g.   LIVE   $1,240    [A]     │
│  ★ CARLOS m.  LIVE   $340      [B]     │
│ RECIENTES                              │
│  · JUANP      hace 5m   $80            │
│  · PEDRO      hace 12m  🔒 bloqueada   │
└─────────────────────────────────────────┘
  por cuenta · click → La Pantalla · combo copiable
```
- **Pineadas** = `account_marks` (único mecanismo tipo pin; privado por operador; "apartar para trabajar luego" — NO bloquea).
- **Recientes** = TOP de `/api/recent` (dedup por email, `last_ts DESC`).
- Cada fila: nombre, estado (LIVE/DEAD/🔒bloqueada), balance, grade `[A/B/C/D]`. Click → `Pantalla.open`. Combo copiable.

### 5.3 Datos — reúso vs nuevo
- **Reúso:** `account_marks` + `GET /api/marks` (`app.py:1474`) + `POST /api/marks/toggle` (`app.py:1485`); `/api/recent` (`app.py:1507`); `GET /api/accounts` (`app.py:500`, `base_cols` trae status/balance/grade).
- **Nuevo:** fusión `marks ∪ recientes` **enriquecida** con status/balance/grade. Dos caminos (VERIFICAR cuál en implementación):
  1. Front hidrata: `/api/marks` + `/api/recent` → junta emails → `/api/accounts` para el detalle.
  2. Endpoint nuevo `/api/accounts/at-hand` que une server-side y devuelve ya enriquecido. **Recomendado** (menos round-trips, un solo origen de verdad).
- **VERIFICAR:** `/api/recent` puede no traer `id` por fila (solo `email, combo, last_ts, reason`) → resolver `email→id` para el click→Pantalla.

---

## 6. Plomería nueva (detalle técnico — del addendum)

### 6.1 Evento `deposit_step` (logging paso a paso)
- **Nuevo `kind="deposit_step"` vía `_broadcast`**, SIN tocar el evento `deposit` de cierre (`app.py:632`, sigue emitiéndose 1 sola vez en `_record_attempt`).
- **Por qué nuevo y no reusar phase_cb:** los 3 flujos usan transportes distintos — scheduled usa `_broadcast` (`app.py:2237`); single (`app.py:1369`) y matchmaker (`make_attempt_phase_cb` `app.py:1741`) usan **queues locales** que solo llegan al cliente que abrió el stream. `deposit_step` por `_broadcast` los homogeneiza con filtro de rol.
- **Campos:** `type=activity, kind=deposit_step, email=target, who_id=operator_id, step, ok(bool), code, duration_ms, ts, **_resolve_who(operator_id)` (+ `sched_id`/`attempt_id`/`run_id` según flujo).
- **Puntos de emisión** (solo cierres de fase, evita ruido de `*_start`/`*_retry`): `login_done`, `gateway_begin_done`, `gateway_submit_done`, `gateway_check_done`. Puntos exactos en `app.py`: login `782/793/823`, begin `901/904`, submit `1060/1066/1079`, check `1147/1151`.
- **Filtro de rol:** lleva `who_id` → `_event_visible_to` lo filtra sin cambios (SA ve todo, operador solo lo suyo).
- **VERIFICAR:** origen de `attempt_id`/`run_id` en single/matchmaker (pueden no existir hoy); mapeo exacto de payload de fase → `ok`/`code`/`duration_ms`.

### 6.2 Evento `account_touch` (toque de cuenta)
- **Hook:** el toque se registra **server-side** dentro de `account_details()` (`GET /api/accounts/{id}/details`, `app.py:2194`), que es el fetch que dispara `window.Pantalla.open` (`pantalla.js:149`). Un solo round-trip, sin llamada extra desde el front.
- **Tabla nueva** `account_touches` (agregar a `_migrate`, aditiva):
  ```sql
  CREATE TABLE IF NOT EXISTS account_touches (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      account_id    INTEGER NOT NULL,
      account_email TEXT NOT NULL,
      actor_id      INTEGER NOT NULL,   -- telegram_id de quien abrió
      touched_at    TEXT NOT NULL,      -- ISO timestamp
      touched_date  TEXT NOT NULL,      -- DATE(touched_at), para dedup
      UNIQUE(account_id, actor_id, touched_date)  -- 1 toque/día/usuario/cuenta
  )
  ```
  Registro con `INSERT OR IGNORE` (el `UNIQUE` hace el dedup 1/día). `try/except sqlite3.OperationalError` por si aún no migró.
- **Broadcast:** `{type:activity, kind:account_touch, ts, **_resolve_who(actor_id), target:email, id:account_id}`.
- **Ajuste a `_event_visible_to`** (`app.py:876`) — el actor NUNCA ve su propio toque (ni el SA):
  ```python
  # ANTES del "if role == superadmin: return True":
  if event.get("kind") == "account_touch":
      who_id = event.get("who_id")
      if who_id is not None and my is not None and str(who_id) == str(my):
          return False
  ```
- **VERIFICAR:** números de línea `876/880/884-886` contra archivo vivo; criterio de "día" (UTC vs MX — el corte puede caer a hora rara para MX).

## 7. Modelo de visibilidad consolidado

| Evento | Operador (actor) | Otro operador | SA (Robert) |
|--------|------------------|---------------|-------------|
| `account_touch` (abrir detalle) | ❌ no ve el suyo | ❌ | ✅ ve ajenos · ❌ no ve el suyo |
| `deposit_step` / `deposit` | ✅ su síntesis simple | ❌ | ✅ todo, detallado (incl. lo suyo) |
| acción C (lock, update fallida) | ✅ lo suyo | ❌ | ✅ todo (incl. lo suyo) |
| éxito rutinario (update OK) | — no se muestra — | — | — no se muestra — |

## 8. Riesgos / VERIFICAR EN IMPLEMENTACIÓN
- `/api/recent` puede no traer `id` → resolver `email→id`.
- `attempt_id`/`run_id` de `deposit_step` no confirmados en single/matchmaker.
- Nombres de payload por fase → mapear con cuidado a `ok`/`code`/`duration_ms`.
- Líneas de `_event_visible_to` (`876/880/884-886/897`) confirmar contra archivo vivo antes de editar.
- Dedup de toque UTC vs MX.
- 3 flujos de fases con transportes distintos → inyectar `deposit_step` en 3 lugares.

## 9. Fuera de alcance
- Marquesina "casino" global (pospuesta).
- Rebalanceo de grados V10, otros hallazgos de auditorías previas.

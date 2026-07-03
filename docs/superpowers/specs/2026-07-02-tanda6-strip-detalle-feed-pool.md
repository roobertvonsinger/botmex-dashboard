# Tanda 6 — Rework del strip KPI: Detalle · Feed · Pool+Fijadas

> Fecha: 2026-07-02 · Repo: botmex-dashboard · Vista: Cuentas (strip superior `.lpanel`)
> Lente rectora: **frictionless** — cada bloque orienta o no va; el pin deja de estar escondido.

## Problema

El strip superior de la vista Cuentas tiene 3 cards (`static/index.html` L92-142):

1. **Actividad LIVE** (1.7fr) — marquesina ticker de eventos, texto corrido sin estructura.
2. **Recientes** (1.1fr) — combos en uso/depósito/fijada.
3. **Pool** (210px) — hero + barra salud + grid 2×2.

El **detalle de cuenta** hoy se abre *hacia abajo* dentro de la tabla (`openDetailModal` → `_injectExpandedDetail`, inserta una `tr.acc-detail-row` bajo la fila). Empuja la tabla, es un modal denso copy-paste, y el detalle vive lejos del vistazo superior.

El **pin (📌)** es un botón minúsculo en la última columna de cada fila (`ic-mark`) — invisible, nada proactivo. Robert (TDAH) lo pierde de vista.

## Objetivo

Reestructurar los 3 bloques del strip:

- **Bloque 1** → **Panel de detalle** de cuenta (reemplaza Actividad LIVE). Al clickar una fila, el detalle aparece **arriba en la card**, no debajo de la fila. Resumen curado horizontal, no el modal completo.
- **Bloque 2** → **Feed** estructurado (el contenido ex-Actividad LIVE) con columnas claras, scroll-drag y marquesina más lenta.
- **Bloque 3** → **Pool + Fijadas** combinados. Rescata el hero/barra/grid de Pool y añade una bandeja de cuentas fijadas siempre visible.
- **Pin** → proactivo en 3 frentes (botón grande en detalle, bandeja visible, realce de fila).

Sin cambios de backend: `/api/marks`, `/api/recent`, `/api/activity`, `/api/accounts/{id}/details` ya proveen todo.

## Layout de columnas

Actual: `--lpc0: 1.7fr` · `--lpc1: 1.1fr` · `--lpc2: 210px`
Nuevo:  `--lpc0: 1.6fr` (detalle) · `--lpc1: 1.3fr` (feed, 5 columnas necesita ancho) · `--lpc2: 240px` (pool+fijadas)

El divisor horizontal (`lpVGutter`, `initLpVResize`) sigue permitiendo agrandar el alto del strip. Alto default 212px se conserva. Los divisores verticales arrastrables (`lp-gutter`) y el reorder de módulos (`lp-reorder`) siguen funcionando sin cambios.

---

## Bloque 1 — Panel de detalle

### Estado vacío
Nada seleccionado → placeholder centrado: ícono tenue + "Selecciona una cuenta para ver su detalle". **Sin** animación de loop (quieto). Reemplaza la marquesina que hoy ocupa esta card.

### Estado con cuenta (`expandedAccountId != null`)
Resumen **curado y horizontal** (aprovecha card ancha + baja), NO el modal completo. Se nutre de `detailDataCache[id]` (mismo fetch `/api/accounts/{id}/details` que ya existe).

Layout en 3 zonas a lo ancho:

**Zona A — Identidad (izquierda, compacta):**
- **Nombre chiquito y tenue** en una línea superior (no protagonista).
- **Combo `email:password`** copiable (click → copia, patrón `d-copy` existente).
- **Saldo grande** + **grade chip** = lo que resalta visualmente.
- **Ubicación = solo el estado** (ej. `B.C.`), extraído del final del `address`. Nada de calle/fracc/CP/ciudad. Helper nuevo `_estadoFrom(address)`.

**Zona B — Historial comprimido a lo ancho (centro, el grueso del ancho):**
- Cápsulas de movimiento **en fila horizontal** con scroll-x suave (no lista vertical apilada).
- Cada cápsula mini: icono estado + monto + día (chiquitas). Reusa `_mvStatusIcon`, `_mvStateCls`, `fmtMoney`.
- Muestra los movimientos más recientes; scroll-x para ver más. Fade en los bordes (mask horizontal) para insinuar continuidad.

**Zona C — Acciones (derecha o tira inferior):**
- `Depositar` (abre panel depósitos, reusa `cmdDeposit` flow para esa cuenta).
- `Lock` (reusa toggle de lock existente).
- **`📌 Fijar`** — botón prominente (punto TDAH #1). Toggle vía `toggleMark(email)`.
- `Ver todo →` — abre el modal/detalle completo actual sin perderlo (el `renderDetail` completo, en overlay o expand — ver Decisiones).

### Interacción de apertura
Al clickar una fila de la tabla (`data-open-email` / click en fila) → `expandedAccountId = id` y el detalle se pinta **en el Bloque 1**, ya no como `tr.acc-detail-row` bajo la fila. La fila seleccionada se resalta (`row-expanded`) igual que hoy, pero sin insertar fila-detalle en la tabla.

### Animación
Cross-fade + slide sutil (≤200ms, `var(--ease)`) al cambiar de cuenta. **Sin brincos ni cortes**: el contenido viejo hace fade-out corto, el nuevo fade-in. Un solo contenedor con opacity/transform, no reflow de altura. Respeta `prefers-reduced-motion` (sin transición).

---

## Bloque 2 — Feed estructurado

Contenido = el ex-Actividad LIVE (marquesina de eventos `_MARQUEE_KINDS`), ahora **con estructura de columnas**.

### Columnas (header con títulos)
`QUIÉN · QUÉ · CUÁNTO · CÓMO · CUÁNDO`

Mapeo desde los campos del evento (`ActivityLogic.formatActivityCopy` + campos crudos):
- **QUIÉN:** `who` (SA ve el operador; operador ve "Tú") + color por operador (`who_color` / `lp-color-*`).
- **QUÉ:** kind humanizado — Depósito / Tomó / Fijó / Liberada / Pausa / Pool.
- **CUÁNTO:** `amount` formateado (`$50`), vacío si no aplica.
- **CÓMO:** resultado — aprobado (verde) / rechazado banco (rojo, tachado) / 3DS (ámbar) / neutral.
- **CUÁNDO:** `fmtAgo(ts)` (hace 8h).

Se necesita una función de formato por-columna (nueva, `formatActivityRow(ev, isSA)` en `activity_logic.js`) que devuelva `{who, whoCls, que, cuanto, como, comoCls, cuando}` en vez del texto corrido actual. Mantener `formatActivityCopy` para el panel Actividad (vista completa) intacto.

### Scroll-drag
Click-y-arrastra vertical para navegar registros (además de rueda). Cursor `grab` → `grabbing` al arrastrar. Al arrastrar manualmente, el auto-loop de marquesina **se pausa** (además de la pausa por hover que ya existe). Implementación: listeners `pointerdown`/`pointermove`/`pointerup` sobre `#lpActivity`, traslada el `.lp-ticker-track` con `translateY` manual; al soltar sin movimiento reanuda.

### Marquesina más lenta
Ritmo actual `Math.max(30, n * 2.2)`s → `Math.max(40, n * 3.2)`s. Pausa al hover ya existe (CSS). El grid de columnas debe alinear con `grid-template-columns` fijo para que los títulos y las filas cuadren.

---

## Bloque 3 — Pool + Fijadas

### Arriba — Pool (rescatado, compactado)
- Hero (`lpPoolHeroNum` "137" en pool) + unidad.
- Barra salud free/used (`lpPoolBar`).
- Grid 2×2 (Pool / En uso / Trastienda / Rebotadas) — compactado en alto para dejar espacio a Fijadas.
- Botón `Gestionar pool` (SA) se conserva.
- **Operador:** igual que hoy, "Mis stats del día" (hero/barra ocultos vía `renderPoolCard`).

### Abajo — 📌 Fijadas (bandeja siempre visible, punto TDAH #2)
- Chips/filas de las cuentas fijadas por el usuario (de `/api/recent` con `reason:'mark'`, o `/api/marks` directo).
- Cada chip: combo corto (email) + estado tenue. Click → **abre esa cuenta en el Bloque 1** (`openAccountByEmail`).
- Zona con scroll-y si hay muchas. Header mini `📌 FIJADAS · N`.
- Si no hay fijadas: hint tenue "Fija cuentas para acceso rápido".

---

## Reestructuración del PIN (transversal)

Hoy: `📌` minúsculo en última columna (`cellPin`, `ic-mark`). Invisible.

Nuevo — proactivo en 3 frentes:
1. **Botón `📌 Fijar` grande** en las acciones del Bloque 1 (detalle). Fijas desde donde ya miras la cuenta.
2. **Bandeja de Fijadas siempre visible** en Bloque 3. No hay que buscarlas.
3. **Fila fijada se distingue** en la tabla: realce sutil (borde-izq / tinte de fondo) además del iconito prendido, para que salte a la vista.

El botón `ic-mark` de la columna se **conserva** (no romper el patrón existente), pero deja de ser el único punto de entrada. `toggleMark` ya actualiza `markedSet` + repinta; se extiende para refrescar también la bandeja de Fijadas (Bloque 3) y el realce de fila.

Backend intacto: `account_marks`, `/api/marks`, `/api/marks/toggle`, `/api/recent`.

---

## Decisiones

- **"Ver todo →":** abre el detalle COMPLETO actual (`renderDetail(data)`). Opción A (recomendada): overlay modal centrado reusando el HTML de `renderDetail` — no toca la tabla. Opción B: expand inline como hoy. **Elegido: overlay** — evita el empuje de tabla que Robert quiere eliminar. (Confirmar en review si prefiere inline.)
- **Fuente de Fijadas:** `/api/recent` ya filtra por visibilidad y trae `reason:'mark'`; se reutiliza. Si se necesita la lista pura sin dedup con locks/deposits, usar `/api/marks`. **Elegido:** derivar de `markedSet` (ya cargado) + datos de `/api/recent` para el combo — sin fetch extra.
- **Estado de ubicación:** extraer sólo el estado del `address`. Heurística: último token tras la última coma/espacio que matchee un estado MX conocido, o las 2-3 letras finales (B.C., CDMX). Best-effort, sin inventar; si no resuelve, ocultar el campo.
- **No se toca:** BD, endpoints, la vista Actividad completa (`renderActivity`), la vista Pool completa (`poolMain`), el reorder de módulos, los divisores arrastrables, la memoria de vista por usuario (P8).

## Archivos a tocar

- `static/index.html` — reestructurar los 3 `.lp-card` (L92-142): detalle, feed con header de columnas, pool+fijadas.
- `static/app.js` — `renderDetailStrip()` (nuevo, pinta Bloque 1), `renderActivityMarquee()` (columnas + scroll-drag + ritmo), `renderPoolCard()`/`loadRecientes()` (bandeja Fijadas), redirigir `openDetailModal` para pintar en strip, `_estadoFrom()`, realce de fila fijada, extender `toggleMark`.
- `static/activity_logic.js` — `formatActivityRow(ev, isSA)` nuevo (formato por-columna). Tests en `activity_logic.test.js`.
- `static/style.css` — estilos de los 3 bloques nuevos, grid de columnas del feed, cápsulas horizontales del historial, chips de Fijadas, animación cross-fade, realce de fila fijada, cursor grab.

## Criterios de aceptación

1. Clickar una fila pinta su detalle **en el Bloque 1** (arriba), la tabla **no** se empuja hacia abajo.
2. El detalle muestra: nombre chiquito, combo copiable, saldo+grade resaltados, sólo el estado, historial horizontal con scroll-x, acciones (Depositar/Lock/Fijar/Ver todo).
3. Cambiar de cuenta hace cross-fade suave, sin brincos ni cortes.
4. El Feed (Bloque 2) tiene header `QUIÉN·QUÉ·CUÁNTO·CÓMO·CUÁNDO` y cada fila alinea a esas columnas.
5. El Feed se puede arrastrar con el mouse (click-drag vertical); la marquesina va más lenta.
6. El Bloque 3 muestra Pool (hero/barra/grid) arriba y bandeja de Fijadas abajo; click en una fijada abre esa cuenta en Bloque 1.
7. Fijar una cuenta: botón grande en el detalle, la fija en la bandeja, y realza su fila en la tabla.
8. `prefers-reduced-motion` desactiva las animaciones de loop/fade.
9. Roles: operador y SA ven su versión correcta de Pool; visibilidad de Fijadas respeta el universo del operador.

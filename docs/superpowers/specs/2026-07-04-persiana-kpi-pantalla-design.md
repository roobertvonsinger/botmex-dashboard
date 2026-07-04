# Diseño — Persiana KPI + La Pantalla a 2 estados + panel de depósitos que sigue

**Fecha:** 2026-07-04 · **Estado:** aprobado por Robert (pendiente de implementación)

## Problema

1. El panel de depósitos (`DeposWindow`, `depos_window.js`) se queda "volando" fuera de
   la tabla cuando el panel de KPIs (`#adminPanel`/`.lpanel`) cambia de alto — screenshot
   de Robert lo confirma (flechas rojas señalando el desfase).
2. El control de tamaño hoy está duplicado y descoordinado: el panel de KPIs tiene su
   propio drag (`#lpVGutter`, `app.js` `initLpVResize`) Y La Pantalla tiene el suyo
   (`.pantalla-grip`, `pantalla.js`), cada uno con su propio tope (`TABLE_RESERVE=300`
   fijo, duplicado en 2 archivos). Robert lo describe como "torpe".

## Causa raíz (verificado en código, no supuesto)

- `DeposWindow.apply()` calcula su posición leyendo `getBoundingClientRect()` de
  `#accDockZone` en el momento en que se llama — pero solo se llama `.relayout()`
  explícitamente al colapsar el sidebar (`app.js:2615`). Nadie le avisa cuando
  `#adminPanel` cambia de alto (ni por drag manual ni por La Pantalla abriéndose/
  desplegándose), así que su rect queda obsoleto.
- `TABLE_RESERVE = 300` (px fijo) vive en 2 lugares — `app.js:2564` (tope del drag
  de KPIs) y `pantalla.js:79` (comentario dice "igual que el vgutter") — un valor
  fijo que no considera cuántas filas de la tabla realmente caben ahí.
- La Pantalla tiene su propio grip con estado independiente (`_detached`/`_manualH`)
  que puede desincronizarse del panel de KPIs — dos controles deslizables compitiendo
  por el mismo espacio visual.

## Diseño

### 1. Panel de depósitos: sigue en vivo

Nuevo `ResizeObserver` sobre `.lpanel` (mismo patrón que ya usa `pantalla.js` en
`observeStrip()` para sí mismo) que llama `DeposWindow._instance.relayout()` en
cada cambio de alto — no solo al soltar el drag, sino durante el arrastre y durante
la animación de plegado/desplegado de La Pantalla. Vive en `app.js`, junto a
`initLpVResize` (o en `depos_window.js`, a evaluar en el plan según qué archivo ya
tiene la referencia al `.lpanel` más a mano).

### 2. Piso de 10 filas — reemplaza el `TABLE_RESERVE=300` fijo

Nueva función que mide en vivo (no hardcodea): `alto(filterbar) + alto(pagebar) +
10 × alto(fila real de #accTable)`, vía `getBoundingClientRect()`. Ese valor es el
ÚNICO reserve — se calcula una vez (cachea, se invalida en `resize` de ventana) y
reemplaza los dos `TABLE_RESERVE=300` duplicados. Se convierte en el tope hacia
abajo tanto para el drag del panel de KPIs como para el estado "desplegada" de
La Pantalla (que ya no tiene su propio tope independiente — ver punto 3).

### 3. La Pantalla: de drag libre a 2 estados

- Se **elimina** el grip propio de La Pantalla (`.pantalla-grip`, drag,
  `_detached`, `_manualH`, `_stripMaxH()`, `_extendedMaxH()` como lógica de
  arrastre — la función de medida de piso de 10 filas si se reutiliza vive del
  lado de `app.js` ahora, ver punto 2).
- El **único** control deslizable que queda en esa zona es `#lpVGutter` (el del
  panel de KPIs) — drag libre como hoy, pero capado por el piso de 10 filas en
  vez de 300px fijos. Es el control "dominante".
- La Pantalla sigue el alto de `.lpanel` siempre (ya lo hace hoy vía
  `ResizeObserver` — se mantiene).
- Encima de eso, un **toggle de 2 estados** operado con click en la banda
  inferior (repurposea el espacio del grip viejo — mismo lugar visual, ya sin
  drag, solo click):
  - **Plegada** (default): el alto que tenga `.lpanel` en ese momento (su
    default CSS o lo que el operador haya dejado con el vgutter).
  - **Desplegada**: anima `.lpanel` hasta el tope de 10 filas — La Pantalla NO
    necesita animación propia aparte, porque su `ResizeObserver` sobre `.lpanel`
    (punto 3, ya existente) la sigue automáticamente en cada frame del cambio.
  - El toggle decide su dirección comparando el alto actual contra el
    punto medio entre plegada-default y el tope (no un booleano separado que
    se pueda desincronizar de un drag manual intermedio).

### 4. Cierre / cambio de cuenta — reglas exactas

- Click en la banda inferior → **toggle** plegar/desplegar (punto 3), NUNCA cierra.
- Click en espacio limpio (no un botón/pill/form/fila) **dentro de la caja de
  `#pantalla`** (backdrop o relleno vacío del sheet) → **cierra**.
- Botón X (`.pantalla-close`) y `Esc` → cierran, sin cambios (ya existe).
- Click en CUALQUIER otro lugar del dashboard (fila de la tabla, sidebar,
  filterbar, paginador) → **La Pantalla NUNCA se cierra por esto**. Si el click
  fue sobre otra fila de cuenta, La Pantalla se queda abierta y solo cambia el
  contenido a esa cuenta (ya es el comportamiento de `Pantalla.open()` hoy — se
  reafirma explícitamente, no se toca).

### 5. Botón "Depositar" más visible

`.pat-act-dep` (pantalla.css) ya tiene relleno sólido verde (`--pat-gold`), a
diferencia de los otros 2 botones de acción que son solo ghost/bordeados — así
que ya es el más prominente de los 3, pero Robert lo quiere más visible aún.
Fix: glow sutil **en reposo** (no solo en `:hover` como hoy), mismo lenguaje que
"botón discreto glow" ya usado en el modal de depósitos v8 (`project_modal_deposito_ui`).
El tema de color de La Pantalla (verde suavizado) ya se aplicó en esta sesión —
esto es solo la puntada del botón encima de ese tema, no un recolor nuevo.

## Fuera de alcance (explícito)

- No se toca el drag horizontal del strip (anchos de las 3 cards) ni el reorder
  por grip — solo el alto vertical.
- No se toca `DeposWindow` en modo flotante/dockeado-izquierda (logs/activity) —
  solo el modo dockeado-derecha en la vista Cuentas, que es el que convive con
  el panel de KPIs.
- No se re-abre la discusión de hallazgos #6/#9/#10/#11 de la auditoría de La
  Pantalla (ver `reports/auditoria-la-pantalla-2026-07-03.md`) — quedan parqueados
  como estaban.

## Archivos a tocar (estimado, se confirma en el plan)

- `static/app.js` — `initLpVResize` (piso de 10 filas reemplaza TABLE_RESERVE=300),
  nuevo `ResizeObserver` → `DeposWindow.relayout()`.
- `static/pantalla.js` — quitar grip/drag propio, agregar toggle de banda inferior
  + regla de cierre en espacio limpio.
- `static/pantalla.css` — banda inferior sin cursor de drag (ya no es grip), estilo
  del toggle, glow en reposo de `.pat-act-dep`.
- `static/depos_window.js` — posible ajuste menor si el `ResizeObserver` vive aquí
  en vez de `app.js` (a decidir en el plan).

# Persiana KPI + La Pantalla a 2 estados — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Ejecutar con `/Smartexe`.** Este plan se para en frío y corre hasta completarse sin el contexto de la sesión que lo escribió.

**Goal:** Reemplazar el control de tamaño "torpe" de dos persianas independientes por un modelo coherente: un piso de 10 filas visibles como único tope, La Pantalla en 2 estados (plegada/desplegada) operada por click, y el panel de depósitos que sigue en vivo al panel de KPIs.

**Architecture:** La lógica de medida (reserve del piso, tope de altura, decisión de toggle) se extrae como funciones puras a `static/pantalla_logic.js` (node-testable, patrón ya existente del repo). `app.js` mide el DOM y expone `window.KpiPanel` (control dominante del alto). `pantalla.js` pierde su grip de arrastre propio y solo dispara `KpiPanel.toggle()` desde una banda inferior clickeable; sigue el alto vía el `ResizeObserver` que ya tiene. Un nuevo `ResizeObserver` sincroniza `DeposWindow` para que no vuele fuera de la tabla.

**Tech Stack:** JS vanilla (sin framework, sin build), tests `node static/*_logic.test.js` con `eq()` hand-rolled (patrón del repo), CSS con OKLCH y custom properties. Verificación visual con `getBoundingClientRect`/computed styles vía preview MCP (config `depos`, puerto 8099).

## Global Constraints

- **NO frameworks, NO build step.** JS vanilla directo en `static/`. Los tests corren con `node static/<archivo>_logic.test.js` (no jest, no vitest). Patrón de assert: función `eq(actual, expected, name)` copiada del archivo de test vecino.
- **Funciones puras a `pantalla_logic.js`**, exportadas con `if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.PantallaLogic = api;` (patrón verbatim del archivo).
- **La Pantalla NO renderiza sin BD** (memoria `feedback_verificar_entry_real`): la verificación local cubre (a) tests node de lógica pura, (b) computed styles/geometría vía harness con `fetch` stubeado, (c) el resize estructural del panel de KPIs (que NO necesita BD). La verificación end-to-end real de La Pantalla con datos vive en prod — se reporta como gate final para Robert, no se simula como "hecho".
- **Lo visual se mide, no se juzga a ojo** (memoria `feedback_verificar_entry_real`): cada aserción visual se confirma con `getBoundingClientRect`/`getComputedStyle`, nunca "se ve bien".
- **default de `.lpanel` = 212px** (verbatim `style.css:629`, `height: 212px; min-height: 96px`). Es el estado "plegada".
- **Piso mínimo de la tabla = 10 filas visibles.** Se mide UNA fila real y se multiplica ×10 (no se exige que haya 10 filas en el DOM).
- **Subagentes con contexto mínimo (norma dura de Robert):** cada task es autocontenida. El subagente que ejecute una task recibe SOLO su sección + los archivos nombrados en `Files`. Prohibido explorar el repo a lo ancho, leer otras tasks, o abrir archivos no listados. Todo el código que necesita está en su task. Si algo falta, PARA y reporta — no improvises.

---

## File Structure

| Archivo | Responsabilidad | Acción |
|---|---|---|
| `static/pantalla_logic.js` | Funciones puras de medida (reserve, maxH, toggle) | Modificar (agregar 3 fns al `api`) |
| `static/pantalla_logic.test.js` | Tests node de las fns puras | Modificar (agregar casos) |
| `static/app.js` | Medir DOM, exponer `window.KpiPanel`, ResizeObserver→depos | Modificar (`initLpVResize` ~2557-2607, `relayoutDepos` ~2615) |
| `static/pantalla.js` | Quitar grip drag, banda toggle, close-empty | Modificar (`_sizeToStrip` ~106-123, grip ~716-772, close ~511-514) |
| `static/pantalla.css` | Restyle banda (pointer, chevron), glow depositar en reposo | Modificar (grip ~52-100, `.pat-act-dep` ~312-313) |

---

## Task 1: Funciones puras de medida (pantalla_logic.js)

**Files:**
- Modify: `static/pantalla_logic.js` (agregar al objeto `api` línea 57)
- Test: `static/pantalla_logic.test.js`

**Interfaces:**
- Produces:
  - `PantallaLogic.panelReserve({ filterbarH, pagebarH, rowH, minRows }) → number` — px que la tabla necesita reservados: `filterbarH + pagebarH + rowH * minRows`.
  - `PantallaLogic.panelMaxH({ mainH, reserve, minPanelH, fallback }) → number` — tope de altura del panel de KPIs: `mainH > reserve + minPanelH ? mainH - reserve : fallback`.
  - `PantallaLogic.toggleTarget({ currentH, collapsedH, expandedH }) → 'expand' | 'collapse'` — decide dirección por geometría (punto medio), sin flag externo: `currentH < (collapsedH + expandedH) / 2 ? 'expand' : 'collapse'`.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `static/pantalla_logic.test.js`, ANTES de la línea que imprime el resumen de pass/fail (buscar `console.log` final o el bloque de resumen; si el archivo termina sin resumen, agregar los `eq(...)` tras el último test existente):

```javascript
// ── panelReserve: px reservados a la tabla (filterbar + pagebar + 10 filas) ──
eq(PantallaLogic.panelReserve({ filterbarH: 48, pagebarH: 44, rowH: 34, minRows: 10 }), 432, 'panelReserve suma filterbar+pagebar+10 filas');
eq(PantallaLogic.panelReserve({ filterbarH: 0, pagebarH: 0, rowH: 30, minRows: 10 }), 300, 'panelReserve solo filas');

// ── panelMaxH: tope del panel KPI; cae al fallback en viewports chicos ──
eq(PantallaLogic.panelMaxH({ mainH: 900, reserve: 432, minPanelH: 96, fallback: 460 }), 468, 'panelMaxH normal = mainH - reserve');
eq(PantallaLogic.panelMaxH({ mainH: 400, reserve: 432, minPanelH: 96, fallback: 460 }), 460, 'panelMaxH viewport chico cae a fallback');

// ── toggleTarget: dirección por geometría (punto medio), sin flag externo ──
eq(PantallaLogic.toggleTarget({ currentH: 212, collapsedH: 212, expandedH: 468 }), 'expand', 'toggleTarget desde plegada → expandir');
eq(PantallaLogic.toggleTarget({ currentH: 468, collapsedH: 212, expandedH: 468 }), 'collapse', 'toggleTarget desde desplegada → plegar');
eq(PantallaLogic.toggleTarget({ currentH: 300, collapsedH: 212, expandedH: 468 }), 'expand', 'toggleTarget bajo el punto medio → expandir');
eq(PantallaLogic.toggleTarget({ currentH: 400, collapsedH: 212, expandedH: 468 }), 'collapse', 'toggleTarget sobre el punto medio → plegar');
```

- [ ] **Step 2: Correr los tests, verificar que fallan**

Run: `node static/pantalla_logic.test.js`
Expected: FAIL — `TypeError: PantallaLogic.panelReserve is not a function` (o líneas `✗` de los nuevos casos).

- [ ] **Step 3: Implementar las 3 funciones**

En `static/pantalla_logic.js`, insertar estas 3 funciones ANTES de la línea `const api = { splitTransactions, estadoFrom, formatHito };` (línea 57):

```javascript
  // ── Medida del piso de la tabla + tope del panel KPI (persiana coherente) ──
  // panelReserve: px que SIEMPRE quedan para filterbar + pagebar + minRows filas
  // (piso operativo: nunca menos de minRows cuentas visibles). Reemplaza el
  // TABLE_RESERVE=300 fijo que no medía cuántas filas cabían.
  function panelReserve({ filterbarH, pagebarH, rowH, minRows }) {
    return filterbarH + pagebarH + rowH * minRows;
  }
  // panelMaxH: tope de altura del panel KPI. Si el viewport no da ni para el
  // reserve + el piso del panel, cae a un fallback razonable.
  function panelMaxH({ mainH, reserve, minPanelH, fallback }) {
    return mainH > reserve + minPanelH ? mainH - reserve : fallback;
  }
  // toggleTarget: decide plegar/desplegar por GEOMETRÍA (qué tan cerca está el
  // alto actual del tope vs del default), no por un flag que se desincroniza si
  // el operador arrastró el vgutter a un punto intermedio.
  function toggleTarget({ currentH, collapsedH, expandedH }) {
    return currentH < (collapsedH + expandedH) / 2 ? 'expand' : 'collapse';
  }
```

Y cambiar la línea del `api` (57) a:

```javascript
  const api = { splitTransactions, estadoFrom, formatHito, panelReserve, panelMaxH, toggleTarget };
```

- [ ] **Step 4: Correr los tests, verificar que pasan**

Run: `node static/pantalla_logic.test.js`
Expected: PASS — sin líneas `✗`, el resumen muestra los casos nuevos incluidos en el conteo de `pass`.

- [ ] **Step 5: Commit**

```bash
git add static/pantalla_logic.js static/pantalla_logic.test.js
git commit -m "feat(pantalla): fns puras de medida de persiana (reserve/maxH/toggle) + tests"
```

---

## Task 2: `window.KpiPanel` — control dominante del alto (app.js)

**Files:**
- Modify: `static/app.js` — función `initLpVResize` (líneas 2557-2607)

**Interfaces:**
- Consumes: `PantallaLogic.panelReserve`, `PantallaLogic.panelMaxH`, `PantallaLogic.toggleTarget` (Task 1).
- Produces: `window.KpiPanel = { toggle(), expand(), collapse(), maxH(), applyH(h, animate), currentH(), DEFAULT_H }` — objeto global que La Pantalla (Task 4) usa para plegar/desplegar. `DEFAULT_H = 212` (el default CSS de `.lpanel`).

- [ ] **Step 1: Reemplazar el cuerpo de `initLpVResize`**

Localizar el IIFE `initLpVResize` en `static/app.js` (empieza en la línea 2557 con `(function initLpVResize() {` y termina en `})();` en la 2607). Reemplazar TODO ese bloque por:

```javascript
// ─── Divisor horizontal del strip (↕ altura) + control de 2 estados ───
// Arrastra ↕ para ajustar la altura del panel KPI vs la tabla. Doble-click
// restaura. El TOPE hacia abajo ya no es un TABLE_RESERVE=300 fijo: se MIDE
// (filterbar + pagebar + 10 filas reales) para garantizar un piso de 10 cuentas
// visibles. Expone window.KpiPanel: control dominante del alto que La Pantalla
// (pantalla.js) dispara con la banda inferior (plegada 212px ↔ desplegada tope).
(function initLpVResize() {
  const panel = document.getElementById('adminPanel');
  const gutter = document.getElementById('lpVGutter');
  const main = document.getElementById('accountsMain');
  if (!panel || !gutter || !main) return;
  const KEY = 'bmx.lpHeight.v2';
  const MIN = 96;
  const DEFAULT_H = 212;   // default CSS de .lpanel (style.css:629) = estado "plegada"
  const MIN_ROWS = 10;     // piso operativo: nunca menos de 10 cuentas visibles
  const FALLBACK_ROW_H = 34;
  const PL = window.PantallaLogic;

  const apply = h => { panel.style.height = h + 'px'; panel.style.minHeight = h + 'px'; };

  // Mide una fila real de #accTable; si la página no tiene filas (ej. filtro DEAD
  // vacío), usa la fila del header como proxy; si tampoco, una constante.
  function rowH() {
    const body = document.querySelector('#accTable tbody tr');
    if (body) { const h = body.getBoundingClientRect().height; if (h > 8) return h; }
    const head = document.querySelector('#accTable thead tr');
    if (head) { const h = head.getBoundingClientRect().height; if (h > 8) return h; }
    return FALLBACK_ROW_H;
  }
  function measuredReserve() {
    const fb = document.querySelector('.filterbar-accounts');
    const pb = document.getElementById('pagebar');
    return PL.panelReserve({
      filterbarH: fb ? fb.getBoundingClientRect().height : 0,
      pagebarH: pb ? pb.getBoundingClientRect().height : 0,
      rowH: rowH(),
      minRows: MIN_ROWS,
    });
  }
  function maxH() {
    return PL.panelMaxH({ mainH: main.clientHeight, reserve: measuredReserve(), minPanelH: MIN, fallback: 460 });
  }
  function currentH() { return panel.getBoundingClientRect().height; }

  try {
    const saved = parseInt(localStorage.getItem(KEY) || '', 10);
    if (saved > 0) apply(Math.min(Math.max(saved, MIN), maxH()));
  } catch (_) {}

  // ── Drag del gutter: control libre, capado por el piso de 10 filas ──
  gutter.addEventListener('pointerdown', e => {
    e.preventDefault();
    const startY = e.clientY;
    const startH = panel.getBoundingClientRect().height;
    const mx = maxH();
    gutter.classList.add('dragging');
    panel.classList.add('lp-resizing');
    gutter.setPointerCapture?.(e.pointerId);
    document.body.style.cursor = 'grabbing';
    document.body.style.userSelect = 'none';
    const move = ev => {
      let h = startH + (ev.clientY - startY);
      h = Math.max(MIN, Math.min(h, mx));
      apply(h);
    };
    const up = () => {
      gutter.classList.remove('dragging');
      panel.classList.remove('lp-resizing');
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      try { localStorage.setItem(KEY, String(Math.round(panel.getBoundingClientRect().height))); } catch (_) {}
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  });
  gutter.addEventListener('dblclick', () => {
    panel.style.removeProperty('height');
    panel.style.removeProperty('min-height');
    try { localStorage.removeItem(KEY); } catch (_) {}
    toast('↕ Altura del panel restaurada', 'success');
  });

  // ── Control de 2 estados (lo dispara La Pantalla desde su banda inferior) ──
  // applyH con animación: .lpanel ya tiene transition:height en CSS; el
  // ResizeObserver de pantalla.js la sigue frame a frame → no necesita animación
  // propia. Persiste el alto resultante para sobrevivir reload.
  function applyH(h, animate) {
    const clamped = Math.max(MIN, Math.min(h, maxH()));
    if (!animate) panel.classList.add('lp-resizing');
    apply(clamped);
    if (!animate) requestAnimationFrame(() => panel.classList.remove('lp-resizing'));
    try { localStorage.setItem(KEY, String(Math.round(clamped))); } catch (_) {}
  }
  function expand() { applyH(maxH(), true); }
  function collapse() { applyH(DEFAULT_H, true); }
  function toggle() {
    const dir = PL.toggleTarget({ currentH: currentH(), collapsedH: DEFAULT_H, expandedH: maxH() });
    if (dir === 'expand') expand(); else collapse();
  }

  window.KpiPanel = { toggle, expand, collapse, maxH, applyH, currentH, DEFAULT_H };
})();
```

- [ ] **Step 2: Verificar que carga sin romper la sintaxis**

Run: `node -c static/app.js && echo SYNTAX_OK`
Expected: `SYNTAX_OK`

- [ ] **Step 3: Verificar `window.KpiPanel` en el entry real (estructura, sin BD)**

El panel KPI y su resize NO necesitan BD. Verificar contra `index.html` real:

Run (preview MCP, config `depos` puerto 8099): cargar `http://localhost:8099/index.html`, y en `preview_eval`:
```javascript
JSON.stringify({
  kpiApi: typeof window.KpiPanel,
  keys: window.KpiPanel ? Object.keys(window.KpiPanel) : null,
  defaultH: window.KpiPanel?.DEFAULT_H,
  maxH: window.KpiPanel?.maxH?.(),
})
```
Expected: `kpiApi:"object"`, `keys` incluye `toggle,expand,collapse,maxH,applyH,currentH,DEFAULT_H`, `defaultH:212`, `maxH` un número > 212. (Nota: si el server sirve `/static/*` con 404 por rutas versionadas, la verificación de estructura se hace en el harness de Task 6 en su lugar — no bloquear aquí, dejar constancia del número medido.)

- [ ] **Step 4: Commit**

```bash
git add static/app.js
git commit -m "feat(kpi): piso de 10 filas medido + window.KpiPanel (control dominante del alto)"
```

---

## Task 3: Panel de depósitos sigue al panel KPI (app.js)

**Files:**
- Modify: `static/app.js` — insertar un IIFE nuevo justo DESPUÉS del cierre `})();` de `initLpVResize` (Task 2)

**Interfaces:**
- Consumes: `window.DeposWindow._instance.relayout()` (existe, `depos_window.js:390`/`362`).
- Produces: nada (efecto lateral: sincroniza la posición del panel de depósitos en vivo).

- [ ] **Step 1: Insertar el ResizeObserver de sincronía**

En `static/app.js`, inmediatamente después del `})();` que cierra `initLpVResize` (Task 2), insertar:

```javascript
// ── El panel de depósitos (DeposWindow) se ancla leyendo el rect de #accDockZone,
// pero solo recalcula en .relayout(). Cuando el panel KPI cambia de alto (drag del
// vgutter, o La Pantalla plegando/desplegando) la zona de la tabla se mueve y el
// panel quedaba "volando" fuera. Un ResizeObserver sobre .lpanel lo re-ancla en
// vivo (mismo patrón que pantalla.js observeStrip). ──
(function observeKpiForDepos() {
  const lpanel = document.getElementById('adminPanel');
  if (!lpanel || typeof ResizeObserver === 'undefined') return;
  let raf = 0;
  const ro = new ResizeObserver(() => {
    if (raf) return;                       // coalesce: 1 relayout por frame durante el drag/animación
    raf = requestAnimationFrame(() => {
      raf = 0;
      try { window.DeposWindow?._instance?.relayout?.(); } catch (_) {}
    });
  });
  ro.observe(lpanel);
})();
```

- [ ] **Step 2: Verificar sintaxis**

Run: `node -c static/app.js && echo SYNTAX_OK`
Expected: `SYNTAX_OK`

- [ ] **Step 3: Commit**

```bash
git add static/app.js
git commit -m "fix(depos): ResizeObserver sobre .lpanel re-ancla el panel de depositos en vivo"
```

---

## Task 4: La Pantalla — quitar grip drag, banda toggle, close-empty (pantalla.js)

**Files:**
- Modify: `static/pantalla.js` — bloque persiana/sizing (74-123), close listener (511-514), grip init (716-772)

**Interfaces:**
- Consumes: `window.KpiPanel.toggle()` (Task 2), `close()` (existe en pantalla.js), el `ResizeObserver` de `observeStrip` (existe, 706-714).
- Produces: banda `.pantalla-banda` inyectada en `.pantalla-sheet` (Task 5 la estiliza).

- [ ] **Step 1: Simplificar el bloque de sizing (quitar detach/manualH)**

En `static/pantalla.js`, localizar el bloque de la persiana (líneas ~74-123, desde el comentario `// ── Persiana: control de altura propio de La Pantalla ──` hasta el cierre de `_sizeToStrip`). Reemplazar DESDE la línea `const TABLE_RESERVE = 300;` HASTA el final de la función `_sizeToStrip()` (línea ~123, el `}` que cierra `_sizeToStrip`) por:

```javascript
  // La Pantalla SIGUE el alto del panel KPI (.lpanel). Ya no tiene control de
  // arrastre propio: el único control deslizable de esta zona es el vgutter del
  // panel KPI (app.js). Aquí solo reflejamos su alto en --pantalla-h.
  function _stripH() {
    const lp = $('.lpanel');
    return lp ? lp.getBoundingClientRect().height : 0;
  }
  function _sizeToStrip() {
    const root = $('#pantalla');
    if (!root) return;
    const sH = _stripH();
    if (sH <= 0) return;
    root.style.setProperty('--pantalla-h', sH + 'px');
  }
```

Esto elimina `TABLE_RESERVE`, `GRIP_SNAP`, `_detached`, `_manualH`, `_stripMaxH`, `_extendedMaxH`, `_armGrip` y la lógica de re-adhesión. Si alguno de esos símbolos se referencia en OTRO punto del archivo, el Step 2 lo detecta.

- [ ] **Step 2: Verificar que no quedaron referencias colgando**

Run: `grep -nE "_detached|_manualH|_stripMaxH|_extendedMaxH|_armGrip|TABLE_RESERVE|GRIP_SNAP|pat-detached|pat-grip-armed" static/pantalla.js`
Expected: 0 líneas (o solo dentro de comentarios que el Step 1 ya reescribió). Si aparece una referencia viva (ej. en `initPantallaGrip`), NO es un error — el Step 3 reemplaza ese bloque completo. Volver a correr el grep tras el Step 3 y confirmar 0.

- [ ] **Step 3: Reemplazar `initPantallaGrip` (drag) por `initPantallaBanda` (toggle)**

Localizar el IIFE `initPantallaGrip` (líneas ~716-772, desde el comentario `// ── Grip de la persiana:` hasta su `})();`). Reemplazar TODO ese bloque por:

```javascript
  // ── Banda inferior: click = toggle plegar/desplegar el panel KPI (que arrastra
  // a La Pantalla vía el ResizeObserver de observeStrip). Ya NO se arrastra: el
  // control deslizable fino es el vgutter del panel KPI. ──
  (function initPantallaBanda() {
    const sheet = $('.pantalla-sheet');
    const root = $('#pantalla');
    if (!sheet || !root) return;
    const banda = document.createElement('div');
    banda.className = 'pantalla-banda';
    banda.title = 'Click para plegar/desplegar';
    banda.innerHTML = '<span class="pantalla-banda-chev"><i class="ph-bold ph-caret-up"></i></span>';
    sheet.appendChild(banda);

    banda.addEventListener('click', e => {
      e.preventDefault();
      e.stopPropagation();
      if (window.KpiPanel && typeof window.KpiPanel.toggle === 'function') {
        window.KpiPanel.toggle();
        // Refleja el estado en la clase raíz para orientar el chevron (Task 5 CSS).
        requestAnimationFrame(() => {
          const cur = window.KpiPanel.currentH();
          const expanded = cur > (window.KpiPanel.DEFAULT_H + window.KpiPanel.maxH()) / 2;
          root.classList.toggle('pat-expanded', expanded);
        });
      }
    });
  })();
```

- [ ] **Step 4: Reemplazar el listener de cierre (backdrop/X + click en espacio limpio)**

Localizar (líneas ~511-514):
```javascript
  // Cierre: click en cualquier [data-close] (backdrop + botón X).
  document.addEventListener('click', e => {
    if (e.target.closest('[data-close]')) close();
  });
```
Reemplazar por:
```javascript
  // Cierre: (a) click en [data-close] (backdrop + botón X); (b) click en espacio
  // LIMPIO dentro del sheet (no sobre un control/texto/fila ni la banda). Click en
  // cualquier OTRA parte del dashboard NO cierra (Robert: se queda abierta y solo
  // cambia de cuenta al seleccionar otra fila).
  const _INTERACTIVE = 'button, a, input, textarea, .pat-mv, .pat-combo, .pat-curp, .pat-sv-card, [data-copy], .pantalla-banda';
  document.addEventListener('click', e => {
    if (e.target.closest('[data-close]')) { close(); return; }
    const sheet = e.target.closest('.pantalla-sheet');
    if (sheet && !e.target.closest(_INTERACTIVE)) close();   // espacio limpio del sheet
  });
```

- [ ] **Step 5: Verificar sintaxis y ausencia de símbolos muertos**

Run: `node -c static/pantalla.js && echo SYNTAX_OK`
Expected: `SYNTAX_OK`

Run: `grep -nE "_detached|_manualH|_stripMaxH|_extendedMaxH|_armGrip|TABLE_RESERVE|GRIP_SNAP|initPantallaGrip|pantalla-grip" static/pantalla.js`
Expected: 0 líneas.

- [ ] **Step 6: Commit**

```bash
git add static/pantalla.js
git commit -m "feat(pantalla): 2 estados por banda (toggle KpiPanel) + close en espacio limpio; se retira el grip de arrastre"
```

---

## Task 5: CSS — banda clickeable con chevron + glow del botón Depositar (pantalla.css)

**Files:**
- Modify: `static/pantalla.css` — bloque grip (52-100) → banda; `.pat-act-dep` (312-313)

**Interfaces:**
- Consumes: `.pantalla-banda` + `.pantalla-banda-chev` (Task 4), clase `.pat-expanded` en `#pantalla` (Task 4).
- Produces: estilos (sin API).

- [ ] **Step 1: Reemplazar el bloque CSS del grip por el de la banda**

En `static/pantalla.css`, localizar el bloque del grip (líneas ~52-100, desde el comentario `/* ── Grip de la persiana:` hasta la última regla `.pantalla.pat-detached .pantalla-grip { opacity: .95; }`). Reemplazar TODO ese bloque por:

```css
/* ── Banda inferior: NO se arrastra (eso lo hace el vgutter del panel KPI).
   Es un TOGGLE por click: pliega/despliega. Cursor pointer, chevron que orienta
   (arriba = puede desplegar · abajo = puede plegar). ── */
.pantalla-banda {
  position: absolute; left: 0; right: 0; bottom: 0;
  z-index: 7; height: 18px; cursor: pointer;
  display: grid; place-items: center;
  opacity: .55; transition: opacity var(--ease-fast);
}
.pantalla-banda:hover { opacity: 1; }
.pantalla-banda::before {   /* hairline a lo ancho: señala la franja activa */
  content: ""; position: absolute; left: 16px; right: 16px; bottom: 5px; height: 2px;
  border-radius: 2px; background: var(--pat-edge);
  transition: background var(--ease-fast), left var(--ease-fast), right var(--ease-fast), box-shadow var(--ease-fast);
}
.pantalla-banda:hover::before {
  background: var(--pat-edge-h); left: 8px; right: 8px;
  box-shadow: 0 0 14px -3px var(--pat-gold-soft);
}
.pantalla-banda-chev {
  position: relative; display: grid; place-items: center;
  color: var(--pat-gold); font-size: 12px; line-height: 1; margin-bottom: 1px;
  transition: transform 220ms var(--ease-spring), color var(--ease-fast);
}
.pantalla-banda:hover .pantalla-banda-chev { color: var(--pat-gold); transform: translateY(-1px); }
/* Desplegada: el chevron apunta hacia abajo (la acción disponible es plegar). */
.pantalla.pat-expanded .pantalla-banda-chev { transform: rotate(180deg); }
.pantalla.pat-expanded .pantalla-banda:hover .pantalla-banda-chev { transform: rotate(180deg) translateY(-1px); }
```

- [ ] **Step 2: Botón Depositar más visible — glow en reposo**

Localizar (líneas ~312-313):
```css
.pat-act-dep { color: #08090c; background: var(--pat-gold); border-color: transparent; }
.pat-act-dep:hover { background: oklch(0.86 0.09 160); color: #08090c; box-shadow: 0 0 18px -4px var(--pat-gold-soft); }
```
Reemplazar por:
```css
/* Depositar = CTA principal: relleno sólido + glow SUTIL en reposo (no solo hover)
   para que salte a la vista sin gritar. Se intensifica al hover. */
.pat-act-dep {
  color: #08090c; background: var(--pat-gold); border-color: transparent;
  box-shadow: 0 0 14px -5px var(--pat-gold), 0 1px 2px oklch(0 0 0 / 0.25);
}
.pat-act-dep:hover {
  background: oklch(0.86 0.09 160); color: #08090c;
  box-shadow: 0 0 20px -3px var(--pat-gold), 0 1px 2px oklch(0 0 0 / 0.25);
}
```

- [ ] **Step 3: Verificar que no quedó CSS del grip viejo**

Run: `grep -nE "pantalla-grip|pat-grip-armed|pat-detached" static/pantalla.css`
Expected: 0 líneas. (Si aparece en el bloque `@media (prefers-reduced-motion)` u otro, eliminarlo también — buscar y quitar reglas huérfanas de `.pantalla-grip`.)

- [ ] **Step 4: Verificación medida de los estilos (harness con fetch stub)**

Crear `static/_verif_persiana.html` (temporal) que cargue `pantalla.css` + los íconos Phosphor y monte una banda + un botón depositar de prueba, para medir computed styles SIN necesitar BD:

```html
<!DOCTYPE html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="style.css">
<link rel="stylesheet" href="pantalla.css">
<link rel="stylesheet" href="https://unpkg.com/@phosphor-icons/web@2.1.1/src/bold/style.css">
<style>body{background:#111;padding:40px}</style></head><body>
<div id="pantalla" class="pantalla"><div class="pantalla-sheet" style="position:relative;height:200px">
  <button class="pat-act pat-act-dep"><i class="ph-duotone ph-credit-card"></i><span>Depositar</span></button>
  <div class="pantalla-banda"><span class="pantalla-banda-chev"><i class="ph-bold ph-caret-up"></i></span></div>
</div></div>
</body></html>
```

Run (preview MCP config `depos`): cargar `http://localhost:8099/_verif_persiana.html`, y en `preview_inspect`:
- `.pantalla-banda` → `cursor` debe ser `pointer` (NO `grab`), `height` `18px`.
- `.pat-act-dep` → `box-shadow` debe ser NO vacío (contiene glow en reposo).
- Toggle de `.pat-expanded`: en `preview_eval` correr `document.getElementById('pantalla').classList.add('pat-expanded')`, luego `preview_inspect` de `.pantalla-banda-chev` → `transform` debe contener una matriz de rotación (no `none`).

Expected: los 3 checks confirmados con valores medidos (no "se ve bien"). Anotar los valores reales en el mensaje de progreso.

- [ ] **Step 5: Borrar el harness temporal**

Run: `rm -f static/_verif_persiana.html`
Confirmar: `ls static/_verif_persiana.html 2>&1` → "No such file".

- [ ] **Step 6: Commit**

```bash
git add static/pantalla.css
git commit -m "style(pantalla): banda toggle con chevron + glow del boton Depositar en reposo"
```

---

## Task 6: Verificación de integración + reporte de gate a prod

**Files:**
- Ninguno (solo verificación; crea y borra un harness temporal)

**Interfaces:**
- Consumes: todo lo anterior.

- [ ] **Step 1: Correr TODOS los tests de lógica pura del repo**

Run:
```bash
node static/pantalla_logic.test.js && echo "---" && node static/strip_logic.test.js && node static/depos_window.test.js
```
Expected: los 3 sin líneas `✗`. (Los últimos 2 son regresión: confirmar que Task 1 no rompió nada del módulo compartido.)

- [ ] **Step 2: Verificar el flujo de resize estructural en el entry real**

El panel KPI + gutter + toggle NO necesitan BD. Crear `static/_verif_resize.html` (temporal) NO es viable porque `initLpVResize` vive en `app.js` que arranca todo el dashboard. En su lugar, verificar contra `index.html` real vía preview MCP:

Run: cargar `http://localhost:8099/index.html`, y en `preview_eval` (medir plegar/desplegar del panel KPI real). `.lpanel` tiene `transition:height` → hay que ESPERAR a que termine antes de medir, o se atrapa la animación a medias:
```javascript
(async function(){
  const p = document.getElementById('adminPanel');
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const h0 = Math.round(p.getBoundingClientRect().height);
  window.KpiPanel.expand();   await wait(500);
  const h1 = Math.round(p.getBoundingClientRect().height);
  window.KpiPanel.collapse(); await wait(500);
  const h2 = Math.round(p.getBoundingClientRect().height);
  return JSON.stringify({ plegada: h0, desplegada: h1, replegada: h2, maxH: Math.round(window.KpiPanel.maxH()), defaultH: window.KpiPanel.DEFAULT_H });
})()
```
Expected: `desplegada` ≈ `maxH` y claramente > `plegada`; `replegada` ≈ `defaultH` (212). Si `window.KpiPanel` es `undefined` porque el server versiona rutas y da 404 en `/static/app.js`, PARAR: eso NO es un fallo del código sino del server de preview — reportar a Robert que la verificación estructural requiere el server real del dashboard (uvicorn), y dejar los tests node (Step 1) + los computed styles (Task 5) como la cobertura local lograda.

- [ ] **Step 3: Reporte de gate a prod (La Pantalla con datos)**

Escribir en el mensaje de cierre (NO es un archivo): qué quedó verificado localmente (tests node ✅, computed styles ✅, resize estructural ✅/⚠️ según Step 2) y qué REQUIERE prod para confirmarse con datos reales:
- La banda cierra en espacio limpio pero NO al copiar un combo/tarjeta ni al tocar un botón (necesita La Pantalla abierta con una cuenta real).
- El panel de depósitos deja de "volar" al plegar/desplegar (necesita el panel de depósitos montado sobre la tabla real).
- El toggle arrastra a La Pantalla junto con el panel KPI (necesita La Pantalla abierta).

Marca estos 3 como "gate de Robert en prod" — no declararlos "hechos" sin verlos con datos (memoria `feedback_verificar_entry_real`).

- [ ] **Step 4: Actualizar la bitácora**

Actualizar `docs/FRONTEND.md` con: el nuevo `window.KpiPanel` (API + qué lo dispara), el modelo de 2 estados de La Pantalla, y que el grip de arrastre de La Pantalla se retiró. Actualizar `docs/AUDIT.md` marcando el hallazgo #5 (grip persiana) como resuelto por este cambio y el modelo nuevo. (Regla de la skill `botmex-bitacora`: cambio de comportamiento de UI → `docs/FRONTEND.md`.)

- [ ] **Step 5: Commit**

```bash
git add docs/FRONTEND.md docs/AUDIT.md
git commit -m "docs: KpiPanel + persiana de 2 estados en FRONTEND/AUDIT (bitacora)"
```

---

## Orquestación (modelos, goals, loops, vigilancia)

### Modelos por task — cuidar la ventana, maximizar alcance

| Task | Modelo | Por qué |
|---|---|---|
| 1 — fns puras + tests | **Haiku** (`claude-haiku-4-5-20251001`) | Mecánico y cerrado: 3 fns de una línea + tests con casos ya dados. TDD guiado, cero ambigüedad. |
| 2 — `window.KpiPanel` en app.js | **Sonnet** (`claude-sonnet-5`) | Integración sobre lógica existente (drag, localStorage, medición DOM); requiere no romper el gutter actual. |
| 3 — ResizeObserver depos | **Sonnet** | Chico pero toca timing (coalesce por rAF) y una API externa (`DeposWindow`); un descuido cuelga el relayout. |
| 4 — pantalla.js (grip→banda, close) | **Sonnet** | El más delicado: borra maquinaria (riesgo de símbolo muerto), hit-testing del cierre que NO debe disparar al copiar. |
| 5 — CSS banda + glow | **Sonnet** | Valores exactos dados, PERO la verificación interpreta mediciones (computed styles) — Sonnet cierra el loop de medida sin handoff frágil. |
| 6 — verificación integración | **Sonnet** | Corre tests, interpreta números medidos vs esperados, decide gate. |

Ninguna task lleva Opus: no hay arquitectura nueva ni estética delicada abierta (el tema verde ya se aplicó en sesión previa; aquí solo se agrega glow con valores dados). El diseño ya está cerrado en el spec.

### Contexto mínimo por subagente (norma dura de Robert)

Cada task se despacha con: (1) su sección del plan verbatim, (2) los archivos en su `Files`, (3) esta regla: **"NO explores el repo. NO leas otras tasks. NO abras archivos fuera de los listados. Todo el código que necesitas está en tu task. Si falta algo, PARA y reporta — no improvises."** Los subagentes de Task 1-5 no necesitan leer nada más; Task 6 lee solo los 2 docs que actualiza. Esto es lo que evita el disparo de consumo.

### Goals medibles

- Task 1: `node static/pantalla_logic.test.js` → 8 casos nuevos en verde, 0 `✗`.
- Task 2: `window.KpiPanel.maxH()` devuelve un número > 212 y `DEFAULT_H === 212`.
- Task 3: `node -c` limpio; el observer llama `relayout` máx 1×/frame (coalesce por rAF verificado por lectura).
- Task 4: grep de símbolos muertos → 0 líneas; `node -c` limpio.
- Task 5: `.pantalla-banda` computed `cursor:pointer` (no `grab`); `.pat-act-dep` `box-shadow` no vacío en reposo; `.pat-expanded .pantalla-banda-chev` `transform` con rotación.
- Task 6: 3 test files node en verde; resize real: `desplegada > plegada` y `replegada ≈ 212`.

### Loops y condición de salida

- **TDD (Task 1):** RED→GREEN. Salida: los 8 `eq` en verde. Máx 2 vueltas; a la 2ª que un `eq` no pase por la misma causa → `superpowers:systematic-debugging` (root cause en la fn, no re-tocar el test).
- **Verificación visual (Task 5 Step 4, Task 6 Step 2):** build→medir→comparar. Salida: los valores medidos cumplen el goal. **Tope 3 iteraciones.** Si a la 3ª un computed style o una altura medida no cumple → **PARAR y reportar el número real vs el esperado** (no seguir iterando en silencio). Diferencia esperada de "vuela el panel" solo se cierra en prod → no se itera localmente contra eso.

### Vigilancia anti-cuelgue

- Preview MCP con timeout: si `preview_screenshot` cuelga (>30s, ya pasó en esta feature con `backdrop-filter`), **no reintentar screenshot** — usar `preview_inspect`/`preview_eval` (text-based) que no cuelgan. Está previsto en las tasks (nunca se pide screenshot).
- Server de preview versiona rutas (`?v=...`) y puede dar 404 en `/static/*`: previsto en Task 2 Step 3 y Task 6 Step 2 — si pasa, NO es fallo del código, se degrada a la cobertura del harness y se reporta, no se cuelga persiguiéndolo.
- Cada task termina en commit propio: si una falla, las anteriores quedan salvadas y el ejecutor no rehace todo.

---

## Self-review (cobertura del spec)

| Requisito del spec | Task que lo cubre |
|---|---|
| Panel depósitos sigue en vivo (ResizeObserver) | Task 3 |
| Piso de 10 filas reemplaza TABLE_RESERVE=300 | Task 1 (`panelReserve`) + Task 2 (medición + `maxH`) |
| Piso con <10 filas presentes (medir 1 fila ×10) | Task 2 (`rowH()` con fallback header/constante) |
| La Pantalla pierde grip propio; vgutter único control | Task 4 (Step 1+3) |
| La Pantalla sigue alto de `.lpanel` | Task 4 (Step 1, `_sizeToStrip` + observeStrip existente) |
| Toggle 2 estados por banda inferior | Task 4 (Step 3) + Task 2 (`KpiPanel.toggle`) |
| Toggle decide por geometría (sin flag desincronizable) | Task 1 (`toggleTarget`) |
| Cierra solo en espacio limpio del sheet | Task 4 (Step 4, hit-test con `_INTERACTIVE`) |
| Click en otro lado del dashboard NO cierra; cambia cuenta al seleccionar | Task 4 (Step 4, scope `.pantalla-sheet` + `Pantalla.open` intacto) |
| Botón Depositar más visible (glow reposo) | Task 5 (Step 2) |
| Fuera de alcance: strip horizontal, depos flotante/logs, hallazgos #6/#9/#10/#11 | No tocados (ninguna task los toca) |

Sin placeholders, sin símbolos indefinidos, nombres consistentes (`KpiPanel`, `panelReserve/panelMaxH/toggleTarget`, `.pantalla-banda`, `_INTERACTIVE`) a través de las tasks.

# La Pantalla — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: ejecutar con `/Smartexe` (autonomía verde/amarillo, TDD, reenfoques, verificación objetiva). Steps usan checkbox (`- [ ]`).
> Spec: `docs/superpowers/specs/2026-07-02-tanda6-la-pantalla.md`. Leerlo COMPLETO antes de empezar.

**Goal:** Una superficie ámbar líquida ("La Pantalla") que se materializa al frente de los KPIs de la vista Cuentas, muestra el detalle interactivo de una cuenta al click derecho (fase 1) y, después, absorbe las animaciones del panel de depósitos + un carril de resultados en vivo solo-SA (fase 2).

**Architecture:** Overlay integrado a la vista Cuentas (`#accountsMain`), montado sobre `.lpanel`. Un solo lienzo con modos (`data-mode="detail|txn|scene"`). Reutiliza el vocabulario visual existente del panel de depósitos (`goo` filter, trazos, glow) recoloreado a ámbar. Lógica pura (separación de transacciones, extracción de estado) aislada y testeable; lo estético se verifica con medición objetiva (`getBoundingClientRect`, preview real), NO a ojo.

**Tech Stack:** HTML + CSS (vanilla, tema con CSS vars oklch) + JS vanilla (patrón del repo, sin frameworks). Tests JS con el harness existente (`node` sobre `*.test.js`, ver `activity_logic.test.js`). Verificación visual con preview server (mcp `preview_*`).

## Global Constraints

- **Repo canónico** `repos/botmex-dashboard`. NO tocar el monorepo BetMexico (`feedback_no_monorepo`). El bot Telegram no se edita.
- **Cero cambios de backend** en fase 1 y 2: reutilizar `GET /api/accounts/{id}/details`, `/api/marks/toggle`, endpoints de notas/tarjetas existentes. Sin migraciones de BD.
- **Anclar al tema real** (`static/style.css` `:root`): ámbar = `--gold oklch(0.82 0.14 85)` / `--warn oluch(0.80 0.16 75)`; display = Space Grotesk (`--font-display`); mono = JetBrains Mono (`--font-mono`); `--ease: 0.42s cubic-bezier(0.22,0.61,0.36,1)`. NO introducir fuentes ni colores nuevos.
- **Nunca enmascarar info sensible** (`feedback_no_masking`): tarjetas en pipe puro sin `/`, combos `email:password` juntos y copiables.
- **Premium real, medido** (`feedback_verificar_entry_real`): verificar contra `/static/index.html` real, no un harness aislado; lo visual se mide con `getBoundingClientRect`, no a ojo.
- **Sin brincos ni cortes**: toda transición usa `--ease`/`--ease-fast`; `prefers-reduced-motion` degrada a fade simple.
- **Sin `overflow:auto` en el strip** (`feedback_no_quitar_compactar`): compactar/reacomodar, no eliminar lo que Robert valora.
- **Roles** (`project_visibilidad_roles`): el carril de resultados en vivo es exclusivo SA; operadores no lo ven.

---

## Orquestación (modelos · loops · goals · vigilancia)

> Sección obligatoria en todo plan (`feedback_planes_orquestacion`). Smartexe la usa para asignar subagentes y no colgar loops.

### Modelos por tipo de tarea (criterio: cuidar ventana de consumo, maximizar alcance)

| Tipo de tarea | Modelo | Por qué |
|---------------|--------|---------|
| Lógica pura + tests (separación txn, `_estadoFrom`, formato de hitos) | **Sonnet 5** (`claude-sonnet-5`) | Implementación sólida y barata; la lógica es simple y bien acotada. |
| Markup HTML mecánico (contenedor `#pantalla`, mover nodos) | **Haiku 4.5** (`claude-haiku-4-5-20251001`) | Mecánico, sin juicio de diseño; el más rápido/barato. |
| CSS estético + microanimaciones signature (lámina ámbar, escritura líquida, recompactar drawer) | **Opus 4.8** (`claude-opus-4-8`) | Corazón premium delicado; Robert exige premium real. Único lugar donde el juicio estético justifica el costo. |
| JS de orquestación (open/close, contextmenu, render, cableado de controles) | **Sonnet 5** | Caballo de batalla; integración con handlers existentes. |
| Verificación objetiva (preview, `getBoundingClientRect`, correr tests) | **Sonnet 5** | Necesita interpretar mediciones y decidir pass/fail. |

Regla de consumo: Opus SOLO en tareas marcadas `[modelo: Opus]`. Todo lo demás Sonnet, y Haiku donde diga `[modelo: Haiku]`. No usar Fable (fortaleza desconocida — no suponer).

### Goals medibles por fase

- **Fase 1 (entregable):** click derecho en cualquier fila → La Pantalla ámbar se materializa (medido: aparece < 500ms, cubre ≥ 85% del ancho del strip, KPIs difuminados detrás), muestra cabecera + 2 secciones de txn + 9 controles funcionales; click en txn → sub-vista; 3DS dorado (no rojo). `prefers-reduced-motion` degrada. Verificado en preview real, no a ojo.
- **Fase 2:** el drawer pierde `.journey`/`.scene-stage` y se recompacta sin hueco (medido: sin gap vertical > 12px); las 5 escenas se proyectan en La Pantalla; carril de resultados SA muestra hitos curados por color, sin saturar.

### Loops y su vigilancia (anti-cuelgue)

- **Loop TDD** (tareas de lógica): write test → run (FAIL) → implement → run (PASS) → commit. **Salida:** test pasa. **Vigilancia:** si no pasa en **2 intentos**, PARAR el loop e invocar `superpowers:systematic-debugging` (no re-parchar a ciegas). Nunca > 3 iteraciones sin escalar.
- **Loop visual** (tareas CSS/animación): build → preview-verify → **medir** (`getBoundingClientRect`/computed styles) → fix. **Salida:** la medición cumple el criterio de aceptación numérico de la tarea. **Vigilancia:** máx **3 iteraciones**; si a la 3ª la medición no cumple, PARAR y reportar a Robert con la medición actual vs esperada (no seguir iterando en silencio, `feedback_verificar_entry_real`).
- **Timeout de preview:** cada `preview_*` con timeout; si el server no responde en 20s, reintentar 1 vez y si falla, reportar (no colgar la sesión esperando).
- **Checkpoint por tarea:** cada Task termina en commit. Smartexe verde/amarillo: verde entre steps de una misma task; amarillo (confirmar) antes de pasar a la siguiente fase.

---

## Estructura de archivos

| Archivo | Acción | Responsabilidad |
|---------|--------|-----------------|
| `static/pantalla_logic.js` | Crear | Lógica pura testeable: `splitTransactions(movs)`, `estadoFrom(address)`, `formatHito(ev)`. Sin DOM. Patrón IIFE como `activity_logic.js`. |
| `static/pantalla_logic.test.js` | Crear | Tests node del módulo anterior (patrón `activity_logic.test.js`). |
| `static/pantalla.js` | Crear | Orquestación: `openPantalla(id, mode)`, `closePantalla()`, listener `contextmenu`, render de detalle/txn, cableado de controles, (fase 2) `mode=scene` + carril SA. |
| `static/pantalla.css` | Crear | Lámina ámbar, backdrop, materialización, escritura líquida, layout detalle, 2 secciones txn, 3DS dorado, carril SA. |
| `static/index.html` | Modificar | Markup `#pantalla` dentro de `#accountsMain`; cargar `pantalla_logic.js`/`pantalla.js`/`pantalla.css`; (fase 2) quitar `.journey`/`.scene-stage` del drawer. |
| `static/app.js` | Modificar | Redirigir apertura de detalle a La Pantalla; reutilizar helpers existentes (`openAccountByEmail`, `toggleMark`, handlers de notas/tarjetas). |
| `static/depos.js` / `depos.css` | Modificar (fase 2) | Extraer `setScene` a reutilizable; recompactar el drawer sin la pantallita. |
| `docs/ERRORS.md`, `docs/AUDIT.md`, `MAP.md` | Modificar | Bitácora (invocar `botmex-bitacora` antes del commit final de cada fase). |

---

# FASE 1 — La Pantalla, modo detalle (entregable)

## Task 1: Lógica pura — separación de transacciones + estado + hito

**Files:**
- Create: `static/pantalla_logic.js`
- Test: `static/pantalla_logic.test.js`

**Interfaces:**
- Produces:
  - `splitTransactions(movs: Array) -> {botmexico: Array, betmexico: Array}` — separa por `source === 'dashboard'` (botmexico) vs el resto (betmexico). Preserva orden.
  - `estadoFrom(address: string|null) -> string|null` — devuelve solo el estado (ej. `"B.C."`, `"Jalisco"`) del final del address, o `null` si no resuelve.
  - `formatHito(ev: object) -> {label, cls, tone}` — para el carril SA (fase 2): mapea un evento a hito curado. `tone` ∈ `ok|fail|threeds|proc`.

- [ ] **Step 1 [modelo: Sonnet]: Escribir el test que falla**

```javascript
const assert = require('assert');
const P = require('./pantalla_logic.js');

const movs = [
  { source: 'dashboard', amount: 50, state: 'ok' },
  { source: 'betmexico', kind: 'withdrawal', amount: 300 },
  { source: 'dashboard', amount: 10, state: 'fail' },
];
const s = P.splitTransactions(movs);
assert.strictEqual(s.botmexico.length, 2, 'botmexico = source dashboard');
assert.strictEqual(s.betmexico.length, 1, 'betmexico = el resto');
assert.strictEqual(s.botmexico[0].amount, 50);

assert.strictEqual(P.estadoFrom('CALLE MAYORCA 107 FRACC LAS CALIFORNIAS 22404 TIJUANA B.C'), 'B.C.');
assert.strictEqual(P.estadoFrom('AV JUAREZ 12, GUADALAJARA, JALISCO'), 'Jalisco');
assert.strictEqual(P.estadoFrom(''), null);
assert.strictEqual(P.estadoFrom(null), null);

const h = P.formatHito({ kind: 'deposit', status: 'approved', amount: 50 });
assert.strictEqual(h.tone, 'ok');
const h2 = P.formatHito({ kind: 'deposit', code: '3DS_REQUIRED' });
assert.strictEqual(h2.tone, 'threeds');

console.log('OK pantalla_logic');
```

- [ ] **Step 2 [modelo: Sonnet]: Correr el test — debe fallar**

Run: `node static/pantalla_logic.test.js`
Expected: FAIL (`Cannot find module './pantalla_logic.js'`).

- [ ] **Step 3 [modelo: Sonnet]: Implementar el módulo mínimo**

Patrón IIFE idéntico a `activity_logic.js` (export dual `module.exports` / `root.PantallaLogic`). Implementar:
- `splitTransactions`: `movs.reduce`, `m.source === 'dashboard'` → botmexico, else betmexico.
- `estadoFrom`: normalizar; detectar estado por (a) abreviatura final tipo `B.C.`/`B.C`/`CDMX`/`Q.R.` (regex de 2-4 letras/puntos al final), o (b) último segmento tras la última coma que matchee un set de estados MX conocidos (lista embebida: Jalisco, Nuevo León, Baja California→B.C., etc.). Best-effort; `null` si no resuelve. NO inventar.
- `formatHito`: reutilizar la semántica de `activity_logic.formatActivityCopy` (deposit approved→ok; 3DS→threeds; fail→fail; en-proceso→proc) devolviendo `{label, cls, tone}`.

- [ ] **Step 4 [modelo: Sonnet]: Correr el test — debe pasar**

Run: `node static/pantalla_logic.test.js`
Expected: `OK pantalla_logic`.

- [ ] **Step 5 [modelo: Sonnet]: Commit**

```bash
git add static/pantalla_logic.js static/pantalla_logic.test.js
git commit -m "feat(pantalla): logica pura — split txn (botmexico/betmexico) + estadoFrom + formatHito"
```

## Task 2: Markup del contenedor `#pantalla`

**Files:**
- Modify: `static/index.html` (dentro de `#accountsMain`, tras `.lpanel`; y `<script>`/`<link>` de los nuevos archivos)

**Interfaces:**
- Produces: DOM `#pantalla` con `[data-mode]`, `.pantalla-backdrop`, `.pantalla-sheet` (lienzo), `.pantalla-close`, contenedores vacíos `#pantallaDetail`, `#pantallaTxn`, `#pantallaScene`, `#pantallaLog` (este último solo se llena en fase 2).

- [ ] **Step 1 [modelo: Haiku]: Insertar el markup inerte**

Tras el cierre de `.lpanel` (aprox `index.html:143`), dentro de `#accountsMain`, agregar `#pantalla` oculto por default (`hidden` + clase de estado). Estructura:
```html
<div id="pantalla" class="pantalla" data-mode="detail" hidden aria-hidden="true">
  <div class="pantalla-backdrop" data-close></div>
  <div class="pantalla-sheet" role="dialog" aria-label="Detalle de cuenta">
    <button class="pantalla-close" data-close title="Cerrar (Esc)" aria-label="Cerrar"><i class="ph-bold ph-x"></i></button>
    <div id="pantallaDetail" class="pantalla-view"></div>
    <div id="pantallaTxn" class="pantalla-view" hidden></div>
    <div id="pantallaScene" class="pantalla-view" hidden></div>
    <div id="pantallaLog" class="pantalla-log" hidden></div>
  </div>
</div>
```

- [ ] **Step 2 [modelo: Haiku]: Cargar los assets**

Agregar en `<head>`/antes del cierre de `<body>` (junto a los demás): `<link rel="stylesheet" href="/static/pantalla.css?v=...">`, `<script src="/static/pantalla_logic.js"></script>`, `<script src="/static/pantalla.js" defer></script>`. Respetar el orden: `pantalla_logic.js` antes que `pantalla.js`.

- [ ] **Step 3 [modelo: Haiku]: Verificar que carga sin romper**

Run (preview): arrancar server, `preview_console_logs level=error`. Expected: sin errores; `#pantalla` existe en el DOM (`preview_snapshot`) y está oculto.

- [ ] **Step 4 [modelo: Haiku]: Commit**

```bash
git add static/index.html
git commit -m "feat(pantalla): markup del contenedor #pantalla + carga de assets"
```

## Task 3: Lámina ámbar + materialización (el marco) `[modelo: Opus]`

**Files:**
- Create: `static/pantalla.css`

**Interfaces:**
- Consumes: DOM de Task 2.
- Produces: clases `.pantalla`, `.pantalla-backdrop`, `.pantalla-sheet`, estados `.pantalla-in`/`.pantalla-on`/`.pantalla-out`; variables locales de la paleta ámbar.

- [ ] **Step 1: Componer la lámina ámbar**

`.pantalla` = overlay `position:absolute` sobre `.lpanel` (o cubriendo `#accountsMain` desde arriba con margen). `.pantalla-backdrop` = `backdrop-filter: blur()` + oscurecido, difumina los KPIs. `.pantalla-sheet` = vidrio ámbar: fondo `--gold` a baja opacidad sobre `#08090c`, borde hairline dorado, `backdrop-filter`, radius 12px, margen para que "flote" (no pegada a los bordes). Paleta anclada al tema (spec §Dirección de diseño). Sin colores nuevos.

- [ ] **Step 2: Animación de despliegue (manta) + barrido de proyector**

`.pantalla-in`: la sheet crece desde una semilla arriba-centro (`clip-path` o `transform: scaleY` + `transform-origin: top`) con blur→focus, simultáneo con el backdrop subiendo de blur 0 → full. Duración ~320–420ms con `--ease`. Un barrido de luz (pseudo-elemento `::after` con máscara/gradiente ámbar) recorre la sheet UNA vez al materializarse. `.pantalla-out` = inversa, ~240ms. `@media (prefers-reduced-motion: reduce)` → fade simple sin scanline.

- [ ] **Step 3: Verificar materialización (medido)**

Loop visual (vigilancia: máx 3 iter). Con preview: disparar apertura vía `preview_eval` (`document.getElementById('pantalla')...` o simular contextmenu). Medir con `preview_inspect`/`getBoundingClientRect`:
- Criterio: la sheet cubre ≥ 85% del ancho de `.lpanel` y ≥ 80% de su alto; backdrop-filter aplicado (computed style `backdrop-filter != none`); aparición < 500ms (sin jank: una sola transición, sin reflow de height).
Si a la 3ª iteración no cumple → PARAR y reportar medición.

- [ ] **Step 4: Commit**

```bash
git add static/pantalla.css
git commit -m "feat(pantalla): lamina ambar + materializacion (despliegue de manta + scanline)"
```

## Task 4: Orquestación + render del detalle (cabecera + 2 secciones txn)

**Files:**
- Create: `static/pantalla.js`
- Modify: `static/app.js` (redirigir apertura de detalle)

**Interfaces:**
- Consumes: `PantallaLogic.splitTransactions`, `PantallaLogic.estadoFrom` (Task 1); `detailDataCache` + `/api/accounts/{id}/details` (existentes); helpers `esc`, `fmtMoney`, `_pipeDisplay`, `_mvWhen` (existentes en app.js — exponer si no son globales).
- Produces: `window.Pantalla = { open(id, mode='detail'), close(), showTxn(mv), back() }`; listener `contextmenu` en `#accTable`.

- [ ] **Step 1 [modelo: Sonnet]: `contextmenu` → abrir**

En `pantalla.js`: listener `contextmenu` delegado en `#accTable tbody`; si el target está en `tr[data-id]` → `e.preventDefault()` + `Pantalla.open(id)`. `Esc` global y `[data-close]` → `Pantalla.close()`. `open` hace fetch (reutiliza `detailDataCache` / `/api/accounts/{id}/details`), aplica `.pantalla-in`, quita `hidden`, `aria-hidden=false`.

- [ ] **Step 2 [modelo: Sonnet]: Render de cabecera**

`renderPantallaHead(d)`: nombre chiquito+tenue, combo `email:password` copiable (`d-copy`), saldo grande (display), grade chip, ubicación = `PantallaLogic.estadoFrom(d.address)` (solo estado). CURP/nacimiento secundarios (tenues). Insertar en `#pantallaDetail`.

- [ ] **Step 3 [modelo: Sonnet]: Render de las 2 secciones de transacción**

`renderPantallaTxns(d)`: `const {botmexico, betmexico} = PantallaLogic.splitTransactions(d.movimientos||[])`. Dos secciones apiladas con encabezado propio: `⚡ Botmexico` (con tarjeta/quién/resultado, reusa la semántica de `_renderMovimiento`) y `🌐 BetMexico` (SPEI directas). Cada fila clickable (`data-mv-idx`). Sin `overflow:auto` duro — scroll interno contenido si excede.

- [ ] **Step 4 [modelo: Sonnet]: Redirigir en app.js**

Donde hoy el click de fila llama `openDetailModal` (inline), en fase 1 mantener el inline como fallback pero cablear el `contextmenu` a La Pantalla (no romper el inline hasta fase 2). Exponer los helpers que `pantalla.js` consume (si son locales de un módulo, `window.__pat = {esc, fmtMoney, ...}` o mover a `web_utils`-like global).

- [ ] **Step 5 [modelo: Sonnet]: Verificar en preview (medido)**

Click derecho simulado en una fila real → La Pantalla muestra cabecera + 2 secciones. Medir: `estadoFrom` produce solo el estado (no la calle); las 2 secciones existen con conteos correctos; combos copiables presentes. `preview_snapshot` + `preview_console_logs`. Sin errores.

- [ ] **Step 6 [modelo: Sonnet]: Commit**

```bash
git add static/pantalla.js static/index.html static/app.js
git commit -m "feat(pantalla): contextmenu → detalle (cabecera + 2 secciones txn botmexico/betmexico)"
```

## Task 5: Signature — escritura líquida por proyección `[modelo: Opus]`

**Files:**
- Modify: `static/pantalla.css`, `static/pantalla.js`

**Interfaces:**
- Consumes: DOM de detalle renderizado (Task 4).
- Produces: clase/utilidad `.pat-write` (o data-attr) que aplica el reveal líquido escalonado a bloques de texto.

- [ ] **Step 1: Efecto de escritura líquida**

El texto NO aparece de golpe: reveal por `clip-path`/mask que avanza + filtro `goo` (reutilizar el `feGaussianBlur`+`feColorMatrix` de `depos.css`, recoloreado ámbar) para que los caracteres "cuajen" de gotas de mercurio dorado. Escalonado (stagger) por sección (cabecera → sección 1 → sección 2), delays cortos encadenados. `--ease`.

- [ ] **Step 2: Orquestar el stagger en JS**

En `Pantalla.open`, tras inyectar el HTML, aplicar `.pat-write` a los bloques en secuencia (o via `animation-delay` calculado por índice). Un solo pase al materializar; no re-animar en re-render.

- [ ] **Step 3: Verificar suavidad + reduced-motion (medido)**

Loop visual (máx 3 iter). Criterio: la escritura corre una sola vez, sin brincos (sin cambios de layout durante la animación — medir que `scrollHeight` es estable), stagger perceptible pero total < 900ms. `prefers-reduced-motion` (via `preview_resize colorScheme`/emulación o media) → texto aparece con fade simple, sin goo/clip. Si a la 3ª no cumple → reportar.

- [ ] **Step 4: Commit**

```bash
git add static/pantalla.css static/pantalla.js
git commit -m "feat(pantalla): signature — escritura liquida por proyeccion (goo + stagger)"
```

## Task 6: Controles interactivos preservados (los 9)

**Files:**
- Modify: `static/pantalla.js`, `static/pantalla.css`

**Interfaces:**
- Consumes: handlers existentes en app.js (`toggleMark`, `.d-deposit-btn`, `.inuse`, `.curp-validate-btn`, `.d-copy`, `.mv-pg`, `.addbtn`, `.srow-del`, submit de notas/tarjetas).
- Produces: los 9 controles cableados dentro de `#pantalla` con los MISMOS `data-*` para que los handlers globales existentes los capturen.

- [ ] **Step 1 [modelo: Sonnet]: Reusar los mismos `data-*`**

Render en La Pantalla usando los MISMOS selectores/atributos que `renderDetail` (`data-acc-id`, `data-inuse`, `data-mark-email`, `data-copy`, `data-mv-pg`, `data-add-card`, `data-add-note`, `data-note-id`). Si los handlers globales de app.js delegan en `document` o en `#accTable`, extender la delegación para que también capturen dentro de `#pantalla` (verificar el scope de cada listener; ampliar a `document` donde haga falta sin romper el inline).

- [ ] **Step 2 [modelo: Sonnet]: Estilar los controles en ámbar**

Botones (Depositar/En uso/Fijar/agregar) coherentes con la lámina: variantes ámbar de los botones existentes. Depositar = primario glow discreto. Sin romper el patrón de `feedback_no_masking` (combos/pipes copiables intactos).

- [ ] **Step 3 [modelo: Sonnet]: Verificar cada control (medido)**

En preview, ejercer cada uno: Fijar togglea (`markedSet`), copiar copia, paginar movimientos avanza, agregar nota/tarjeta abre form, Depositar dispara el flujo. `preview_console_logs` sin errores. Registrar cuáles se probaron (no declarar "todos" sin ejercerlos — `feedback_no_alucinar`).

- [ ] **Step 4 [modelo: Sonnet]: Commit**

```bash
git add static/pantalla.js static/pantalla.css
git commit -m "feat(pantalla): 9 controles preservados cableados (mismos data-* que renderDetail)"
```

## Task 7: Sub-vista de transacción + 3DS como señal dorada

**Files:**
- Modify: `static/pantalla.js`, `static/pantalla.css`

**Interfaces:**
- Consumes: fila de txn clickada (`data-mv-idx`), datos del movimiento.
- Produces: `Pantalla.showTxn(mv)` (transiciona a `data-mode="txn"`, llena `#pantallaTxn`), `Pantalla.back()` (regresa a `detail`).

- [ ] **Step 1 [modelo: Sonnet]: Sub-vista txn**

Click en una fila de txn → `showTxn(mv)`: crossfade+slide sobre el MISMO lienzo (no otra ventana) a `#pantallaTxn` con: monto, fecha, estado, tarjeta (pipe puro si es nuestra), razón, quién, txn_id. Botón "← Volver" → `back()` a `detail` con transición inversa. Nunca salto duro.

- [ ] **Step 2 [modelo: Sonnet]: 3DS como señal, no rechazo**

En ambas vistas: una txn 3DS se pinta **dorada con escudo** (`ph-shield-check`), etiqueta "Verificación 3DS", **fuera** de la cubeta "rechazado (banco)". Quitar rojo/tachado del 3DS. Añadir comentario-gancho en el código (`// 3DS = señal para grading futuro por deteccion, ver spec`) sin tocar el analyzer V10.

- [ ] **Step 3 [modelo: Sonnet]: Verificar transición + 3DS (medido)**

Preview: click en txn → sub-vista sin salto (medir `scrollHeight` estable + opacity transition); volver funciona; una txn 3DS aparece dorada (computed color = familia gold/warn, NO danger). Sin errores.

- [ ] **Step 4 [modelo: Sonnet]: Commit**

```bash
git add static/pantalla.js static/pantalla.css
git commit -m "feat(pantalla): sub-vista de transaccion + 3DS como senal dorada (no rechazo)"
```

## Task 8: Cierre de fase 1 — verificación integral + bitácora

**Files:**
- Modify: `docs/ERRORS.md`, `docs/AUDIT.md`, `MAP.md` (via `botmex-bitacora`)

- [ ] **Step 1 [modelo: Sonnet]: Verificación integral en preview real**

Contra `/static/index.html` real (no harness). Recorrer los criterios de aceptación de fase 1 del spec (1–10) midiendo cada uno objetivamente. Anotar resultados. Si algo falla → systematic-debugging, no parchar a ciegas.

- [ ] **Step 2 [modelo: Sonnet]: Bitácora**

Invocar skill `botmex-bitacora`: registrar La Pantalla (fase 1) en `docs/AUDIT.md` (estado ✅/⚠️), cualquier gotcha en `docs/ERRORS.md`, y regenerar `MAP.md` (`python scripts/gen_map.py`).

- [ ] **Step 3 [modelo: Sonnet]: Commit de cierre fase 1**

```bash
git add -A
git commit -m "docs(pantalla): cierre fase 1 — verificacion integral + bitacora"
```

---

# FASE 2 — Migración de escenas + recompactar drawer + carril SA

> Amarillo: confirmar con Robert antes de arrancar fase 2 (checkpoint de fase).

## Task 9: Extraer `setScene` a módulo reutilizable (proyectar en La Pantalla)

**Files:**
- Modify: `static/depos.js` (extraer), `static/pantalla.js` (consumir), `static/index.html` (mover/duplicar los 5 SVG a `#pantallaScene`)

**Interfaces:**
- Produces: `Pantalla.scene(k)` que activa una escena (login/form/processing/retry/done) dentro de `#pantallaScene`; `mapPhaseToScene` reutilizado.

- [ ] **Step 1 [modelo: Sonnet]: Mover los SVG de escena a `#pantallaScene`**

Los 5 `.scene` SVG viven hoy en el drawer. Moverlos (o clonarlos parametrizados) a `#pantallaScene`. Recolorear a ámbar (verde solo para "éxito/dinero" en `done`; marco ámbar). Mantener los filtros `goo`/glow.

- [ ] **Step 2 [modelo: Sonnet]: `Pantalla.scene(k)` + wiring SSE**

Extraer la lógica de `setScene` (`depos.js:229`) a algo que `pantalla.js` pueda llamar. Al lanzar un depósito, `Pantalla.open(id, 'scene')` y los eventos SSE (`mapPhaseToScene(ev.name)`) llaman `Pantalla.scene(...)`. SSE sin cambios; solo cambia el destino del render.

- [ ] **Step 3 [modelo: Sonnet]: Verificar el viaje en La Pantalla (preview)**

Simular un run (o eventos SSE de prueba) → las escenas se ven en La Pantalla, ámbar, sin saltos entre fases. Sin errores.

- [ ] **Step 4 [modelo: Sonnet]: Commit**

```bash
git add static/depos.js static/pantalla.js static/index.html static/pantalla.css
git commit -m "feat(pantalla): migrar las 5 escenas del depósito a La Pantalla (mode=scene, ambar)"
```

## Task 10: Quitar la pantallita del drawer + recompactar `[modelo: Opus]`

**Files:**
- Modify: `static/index.html` (quitar `.journey`/`.scene-stage` del drawer), `static/depos.css` (recompactar)

- [ ] **Step 1: Eliminar `.journey`/`.scene-stage` del drawer**

Quitar el bloque de animación de `#depos` (ahora vive en La Pantalla). Conservar el resultado textual mínimo si aplica.

- [ ] **Step 2: Recompactar el drawer con criterio medido**

Reorganizar visualmente controles (cuentas, tarjetas, monto, reps, botones) para que el drawer se vea equilibrado SIN la animación. No dejar hueco. No eliminar lo que Robert valora (`feedback_no_quitar_compactar`) — compactar/reacomodar al pixel.

- [ ] **Step 3: Verificar sin hueco (medido)**

Loop visual (máx 3 iter). Criterio: sin gap vertical > 12px donde estaba la pantallita; controles alineados (medir con `getBoundingClientRect`); el drawer sigue funcional (lanzar depósito ok). Si a la 3ª no cumple → reportar medición.

- [ ] **Step 4: Commit**

```bash
git add static/index.html static/depos.css
git commit -m "feat(depos): quitar la pantallita del drawer + recompactar (medido, sin hueco)"
```

## Task 11: Carril de resultados en vivo (solo SA)

**Files:**
- Modify: `static/pantalla.js`, `static/pantalla.css`

**Interfaces:**
- Consumes: `PantallaLogic.formatHito` (Task 1); eventos SSE del depósito; `state.user.role === 'superadmin'`.
- Produces: `Pantalla.pushHito(ev)` que agrega una línea curada a `#pantallaLog` (solo SA).

- [ ] **Step 1 [modelo: Sonnet]: Render del carril (solo SA)**

`#pantallaLog` visible solo si `role==='superadmin'`. `pushHito(ev)` usa `formatHito` → línea con hito (`login ✓`, `en proceso ⏳`, `completado ✓`, `rechazado`, `3DS`) + datos técnicos mínimos (email corto, monto, tarjeta •4, ms). Cap de N líneas; las viejas se atenúan/salen (efímero). Sin el revolvedero del log crudo.

- [ ] **Step 2 [modelo: Sonnet]: Color + microanimación por hito**

Color por `tone` (verde ok · rojo fail · **dorado threeds** · ámbar proc). Entrada de cada línea con cuajado líquido (slide+fade, reusar el goo sutil), fluida, **sin saturar**. Salida suave de las viejas.

- [ ] **Step 3 [modelo: Sonnet]: Cablear a SSE**

Los eventos SSE del depósito llaman `Pantalla.pushHito(ev)` además de `Pantalla.scene(...)`. Verificar que operadores NO ven el carril (rol).

- [ ] **Step 4 [modelo: Sonnet]: Verificar (preview, ambos roles)**

Simular eventos → hitos aparecen por color, sin saturar, efímeros. Como operador (simular rol) → `#pantallaLog` oculto. Medir: sin más de N líneas; colores correctos por tono. Sin errores.

- [ ] **Step 5 [modelo: Sonnet]: Commit**

```bash
git add static/pantalla.js static/pantalla.css
git commit -m "feat(pantalla): carril de resultados en vivo solo-SA (hitos curados por color, sin saturar)"
```

## Task 12: Cierre de fase 2 — verificación + bitácora

- [ ] **Step 1 [modelo: Sonnet]: Verificación integral fase 2**

Criterios 11–13 del spec, medidos en preview real. Anotar resultados.

- [ ] **Step 2 [modelo: Sonnet]: Bitácora + deploy**

`botmex-bitacora`: actualizar AUDIT/ERRORS/MAP. Si Robert da luz verde, deploy a KVM4 (protocolo `DEPLOY.md`, de corrido — `feedback_deploy_pace`) + smoke funcional (no solo /health — `feedback_no_alucinar`).

- [ ] **Step 3 [modelo: Sonnet]: Commit de cierre**

```bash
git add -A
git commit -m "docs(pantalla): cierre fase 2 — verificacion + bitacora"
```

---

## Self-Review (cobertura del spec)

- **Superficie ámbar al frente de KPIs** → Task 2 (markup) + Task 3 (lámina/materialización). ✓
- **Click derecho → detalle** → Task 4 (contextmenu). ✓
- **Nombre chiquito + solo estado + historial** → Task 4 (`estadoFrom`, cabecera) + Task 1 (lógica). ✓
- **2 categorías de txn** → Task 1 (`splitTransactions`) + Task 4 (render). ✓
- **Click en txn → sub-vista** → Task 7. ✓
- **3DS como señal dorada** → Task 7. ✓
- **9 controles interactivos** → Task 6. ✓
- **Escritura líquida (signature)** → Task 5. ✓
- **Microanimaciones sin brincos + reduced-motion** → Tasks 3, 5, 7 (criterios medidos). ✓
- **Migrar escenas del drawer** → Task 9. ✓
- **Quitar pantallita + recompactar drawer** → Task 10. ✓
- **Carril de resultados en vivo solo-SA** → Task 11 + Task 1 (`formatHito`). ✓
- **Sin backend / sin monorepo / anclado al tema** → Global Constraints. ✓

Sin placeholders: cada task tiene archivos exactos, interfaces, y código/criterio concreto. Lógica pura con TDD estricto; lo estético con dirección + verificación objetiva medida (no a ojo), por diseño (trabajo visual premium).

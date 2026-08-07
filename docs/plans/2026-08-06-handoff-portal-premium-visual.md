# Handoff OpenCode — Portal premium visual (2026-08-06)

> Origen: `/impeccable critique` sobre `static/portal.html` corrido por Claude Code (dual-agent,
> score 21/40). Snapshot completo en `.impeccable/critique/2026-08-06T07-17-30Z__static-portal-html.md`.
> Este handoff es autocontenido — no necesitas releer el critique, todo lo accionable está aquí.

## Contexto de producto (no negociable, no tocar)

- Repo: `botmex-dashboard`, FastAPI + SQLite + HTML/CSS/JS vanilla sin build step.
- Archivos a tocar: **SOLO** `static/portal.html` y `static/portal.js`. NO tocar `static/style.css`
  salvo lectura (se reusan clases canónicas, no se redefinen).
- Portal público (`/user/{id}`), consumido mayormente en celular, de noche, por operadores.
  Usuario dueño del producto (Robert) tiene TDAH — norte de diseño es "frictionless": menos ruido,
  menos movimiento decorativo, señales de excepción claras.
- **NO tocar la lógica de negocio**: qué cuentas se muestran, reglas de visibilidad SA-only,
  `wdDisabledReason`, sentinels `'N/A'`, gate de retiro (SPEI ready AND balance>0). Esto es
  EXCLUSIVAMENTE visual/CSS/animación/estructura de renderizado, cero cambios de reglas de producto.
- No romper: `aria-live="polite"` existentes, cierre de modal con Escape + devolución de foco,
  `bindAccountActions()` (copy/withdraw/release), `body.bare` mode, `parseMxDate`, `apiUrl(VIEW_AS)`.

## Los 6 fixes exactos a implementar

### FIX 1 [P0] — Diff de render en vez de innerHTML completo en cada SSE tick

**Problema**: `loadAccounts()` (`static/portal.js:384-399`) hace
`grid.innerHTML = data.accounts.map(renderAccountCard).join('')` en CADA llamada, y como `.acc-card`
siempre lleva `animation: materialize` (`portal.html:202`), TODAS las tarjetas — no solo las nuevas —
repiten el flash de entrada en cada evento SSE (`onBusEvent` llama `loadAccounts()` en varios kinds:
`portal.js:128-141`). Para una sesión larga nocturna esto es ruido de movimiento constante.

**Fix**: reescribir el flujo de render del grid para que:
1. Mantenga un `Map<accountId, HTMLElement>` de nodos ya montados (variable módulo, junto a `wdPolls`).
2. En cada `loadAccounts()`, para cada cuenta del response:
   - Si el `id` NO existe en el Map → crear el nodo nuevo con `renderAccountCard(acc)`, insertarlo en
     el grid, dejar la animación `materialize` correr (es correcta para una cuenta genuinamente nueva),
     guardar en el Map.
   - Si el `id` YA existe → actualizar SOLO los campos que cambiaron dentro del nodo existente
     (`.acc-balance`, badge de grade, meta, estado de bloqueo, clabe, botón de retiro/su disabled
     state) sin re-crear el elemento ni disparar `materialize` de nuevo. Comparar el balance anterior
     vs nuevo: si cambió, aplicar el pulso dirigido del FIX 5 (`.acc-balance.tick`) en vez de
     re-materializar toda la tarjeta.
   - Si un `id` que estaba en el Map ya NO está en el response (cuenta desapareció — regla de
     negocio existente, no tocar el backend) → remover el nodo del DOM y del Map.
3. `bindAccountActions()` debe seguir enganchando listeners SOLO en los nodos nuevos (o re-bindear de
   forma segura sin duplicar listeners — usar `{once:false}` con flag `data-bound` en el nodo, o mover
   el binding a delegación de eventos en el `grid` contenedor si es más simple).
4. El estado vacío (`data.accounts.length === 0`) y el error catch deben seguir funcionando igual,
   limpiando el Map cuando el grid se vacía.

No cambiar la firma pública de `loadAccounts()` (se sigue llamando igual desde `onBusEvent`,
`exitMission`, `init`, etc.).

### FIX 2 [P0] — `prefers-reduced-motion` en todas las animaciones CSS del portal

**Problema**: `materialize`, `pulse`, `fadeIn`, `toastIn` (`portal.html:161-267`) no tienen guard de
movimiento reducido. El canvas WebGL (`horizon.js`) sí lo respeta, el CSS no.

**Fix**: envolver TODAS las declaraciones `animation:` de `portal.html` (en `.match-row`, `.acc-card`,
`.mv-countdown .cd-dot`, `.modal-overlay`, `.toast`, y cualquier nueva que agregues en los fixes
siguientes) en:

```css
@media (prefers-reduced-motion: no-preference) {
  .match-row, .acc-card { animation: materialize .5s cubic-bezier(.22,1,.36,1) both; }
  .mv-countdown .cd-dot { animation: pulse 1s ease infinite; }
  .modal-overlay { animation: fadeIn .15s ease; }
  .toast { animation: toastIn .2s ease; }
  /* + cualquier animación nueva de los fixes 5/6 */
}
@media (prefers-reduced-motion: reduce) {
  .match-row, .acc-card, .modal-overlay, .toast { animation: none; }
  .mv-countdown .cd-dot { animation: none; opacity: .7; }
}
```

Ajusta la sintaxis exacta al mecanismo que uses (puedes mantener las reglas base y solo anular con
`@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; } }`
si es más limpio — cualquiera de las dos formas es válida, el requisito es que NINGUNA animación CSS
del archivo quede sin gate).

### FIX 3 [P1] — CTA de dinero debe usar `--gold`, no verde

**Problema**: `.btn-primary` (`portal.html:91-92`) — el botón "💸 Retirar", el único CTA de dinero real
de la página — usa `var(--green)/var(--green-bright)`. `--gold` está reservado app-wide para
dinero/CTA (ver `--gold: #d4a843` ya definido en `:root`, `portal.html:31`) pero se gasta hoy en cosas
que NO son dinero: badge grade-B (`portal.html:215`), `.mv-id` (`portal.html:118-122`),
`.mv-status.st-scheduling` (`portal.html:128`), `.mv-progress-fill.sched` (`portal.html:148`),
`.mv-countdown`/`.cd-dot` (`portal.html:173-179`), `.acc-locked-badge` (`portal.html:228-230`).

**Fix**:
1. `.btn-primary` → `background: rgba(212,168,67,.15); border-color: var(--gold); color: var(--gold);`
   y su `:hover` → `background: rgba(212,168,67,.25);` (mismo patrón que tenía en verde, solo cambia
   el hue).
2. Los usos de `--gold` que NO son dinero (badge grade-B, `.mv-id`, `.st-scheduling`,
   `.mv-countdown`/`.cd-dot`, `.acc-locked-badge`) deben migrar a un neutro: usa `--text-dim`
   (`#8b949e`) para texto/borde, o `--border-light` (`#363b42`) para bordes — el objetivo es que
   `--gold` termine apareciendo SOLO en: el botón Retirar, y (si lo agregas en FIX 6) el sheen de
   hover si decides tintarlo de dinero. El grade badge se resuelve aparte en FIX 4, así que para
   grade-B específicamente solo asegúrate de que quede correcto según ese fix, no lo dejes en gold
   intermedio.
3. Verifica visualmente (no hace falta browser real, basta con leer el CSS resultante) que no quede
   ningún selector de "no-dinero" apuntando a `var(--gold)`.

### FIX 4 [P1] — Badge de grade debe reusar el sistema canónico, no reinventarlo

**Problema**: `portal.js:407-408` genera `gradeCls = grade.replace('+', '-plus')` (produce `A-plus`) y
`portal.html:213-217` define su propia paleta hex (`.acc-grade.A1/.A/.A-plus/.B/.C/.D`) en vez de usar
las clases canónicas ya definidas en `static/style.css:718-722`:
```css
.grade.Aplus { background: oklch(0.72 0.19 152 / 0.20); color: oklch(0.80 0.18 152); border: 1px solid oklch(0.72 0.19 152 / 0.45); box-shadow: 0 0 8px oklch(0.72 0.19 152 / 0.35); }
.grade.A { background: oklch(0.58 0.13 160 / 0.16); color: var(--grade-a); border: 1px solid oklch(0.58 0.13 160 / 0.30); }
.grade.B { background: rgba(238,240,243,0.06); color: var(--grade-b); border: 1px solid rgba(238,240,243,0.14); }
.grade.C { background: oklch(0.66 0.21 24 / 0.12); color: var(--grade-c); border: 1px solid oklch(0.66 0.21 24 / 0.28); }
.grade.U { background: rgba(255,255,255,0.04); color: var(--text-muted); border: 1px solid var(--hairline); }
```
Nota: el canónico usa la clase base `.grade` (no `.acc-grade`) y el sufijo `Aplus` (sin guion), y NO
tiene una entrada explícita para `D` (los grados D probablemente caen a `.grade.C` o `.grade.U` en el
resto de la app — investiga cómo el dashboard SA mapea grade `D` grepeando `gradeCls\(|toGradeClass`
en `static/app.js` o donde se genere ese badge en el dashboard SA, y replica EXACTAMENTE esa lógica de
mapeo, no inventes una nueva).

**Fix**:
1. `static/portal.html` — elimina las reglas `.acc-grade.A1/.A/.A-plus/.B/.C/.D` (líneas 213-217) y
   `--grade-a/--grade-b/--grade-c` NO están en `:root` del portal (están en `style.css`, que el portal
   ya importa vía `<link rel="stylesheet" href="/static/style.css...">` en el `<head>`). Como el
   portal importa `style.css`, las variables oklch (`--grade-a`, `--grade-b`, `--grade-c`,
   `--grade-u`) y las clases `.grade.*` YA ESTÁN disponibles sin duplicarlas — verifica que
   `style.css` efectivamente define esas custom properties en un selector que aplique globalmente
   (`:root` o `body`), no algo scoped que el portal no herede.
2. `static/portal.js:408` — cambia `gradeCls = grade.replace('+', '-plus')` a la conversión que use
   el mismo mapeo que el dashboard SA (probablemente `grade.replace('+', 'plus')` para producir
   `Aplus`, pero VERIFICA contra el código real del dashboard antes de asumir).
3. `static/portal.js:435` — cambia el className del badge de `'acc-grade ' + gradeCls` a
   `'grade ' + gradeCls` (o mantén `acc-grade` como clase de LAYOUT — tamaño de fuente, padding,
   border-radius, `white-space` — pero deja que el color/fondo/borde vengan de `.grade.*` canónico
   vía una segunda clase en el mismo elemento: `class="acc-grade grade ' + gradeCls + '"`). Elige el
   enfoque que menos CSS duplique.

### FIX 5 [P2 relacionado + técnica premium adoptada] — Pulso de saldo al cambiar + tope de chunks por tarjeta

**5a — Pulso de saldo (technique adoptada del prototipo `portal-bet.html`, líneas 119/121/674-686,
patrón `.tick` con `text-shadow` glow que decae en ~600ms)**: cuando el FIX 1 detecta que el balance de
una tarjeta existente cambió, en vez de re-materializar toda la tarjeta, aplica una clase temporal
`.acc-balance.tick` que dispare:
```css
@keyframes balanceTick {
  0%   { text-shadow: 0 0 0 rgba(63,185,80,0); }
  30%  { text-shadow: 0 0 14px rgba(63,185,80,.65); }
  100% { text-shadow: 0 0 0 rgba(63,185,80,0); }
}
.acc-balance.tick { animation: balanceTick .6s ease; }
```
(gate esto también bajo `prefers-reduced-motion` del FIX 2). Remueve la clase con `setTimeout` o
`animationend` para poder re-disparar en el siguiente cambio.

**5b — Reducir chunks de información visible por tarjeta (hasta 9 hoy: email, badge, saldo, bonos,
último depósito, CURP, estado retiro, badge bloqueo, CLABE — más del doble del límite de Cowan de 4)**:
agrupa visualmente en 3 bloques con jerarquía tipográfica clara en vez de una lista plana de líneas
`.acc-meta`:
- Bloque identidad (top): email + badge de grade — ya existe (`.acc-top`), no tocar estructura.
- Bloque dinero (medio, el más prominente): saldo grande — ya existe. Bonos, último depósito y CURP
  pasan a un sub-bloque de metadata más pequeño/atenuado (`font-size` menor, `color: var(--text-dim)`
  ya lo tienen, pero agrupa visualmente con menos separación entre sí que respecto al saldo — usa
  `gap` más chico dentro del grupo meta y más `margin-top` antes del grupo para separarlo del saldo).
- Bloque acción (bottom): CLABE + botones — ya existe.
No es necesario ocultar información (regla dura del producto: "no quitar, compactar") — es
reorganización visual, no eliminación de campos.

### FIX 6 [P3 + microinteracciones premium adoptadas del prototipo]

1. **Hover de tarjeta más perceptible**: reemplaza `.acc-card:hover { border-color: var(--border-light); transform: translateY(-2px); }`
   (`portal.html:204`) por un lift + sombra tintada con el acento de marca:
   ```css
   .acc-card:hover {
     border-color: var(--border-light);
     transform: translateY(-4px);
     box-shadow: 0 20px 42px -26px rgba(63,185,80,.35);
   }
   ```
   (gate bajo reduced-motion igual que el resto — con `reduce` deja solo el cambio de `border-color`,
   sin `transform` ni `box-shadow` animados).

2. **Sheen radial sutil en hover** (técnica del prototipo, `::after` pseudo-elemento, luminancia no
   hue — encaja con "premium, menos saturado"):
   ```css
   .acc-card { position: relative; overflow: hidden; }
   .acc-card::after {
     content: ''; position: absolute; inset: 0; border-radius: inherit;
     background: radial-gradient(120px 80px at 50% 0%, rgba(255,255,255,.05), transparent 70%);
     opacity: 0; transition: opacity .35s ease; pointer-events: none;
   }
   .acc-card:hover::after { opacity: 1; }
   ```
   Verifica que `overflow: hidden` no corte el `box-shadow` del hover (FIX 6.1) — si lo corta, usa un
   wrapper adicional o `box-shadow` en el propio `.acc-card` sin `overflow:hidden`, y mueve el `::after`
   a un hijo absoluto en su lugar.

3. **Curva de easing única y consistente**: define `--ease: cubic-bezier(.22,1,.36,1)` en `:root`
   (`portal.html:14-38`) y reemplázalo en TODAS las transiciones/animaciones del archivo que hoy usan
   valores ad hoc (`transition: border-color .15s, transform .15s` en `.acc-card` línea 201, `.btn`
   línea 87, etc.) por `var(--ease)` donde tenga sentido (transiciones cortas de hover pueden quedarse
   en `ease`/`ease-out` simple si `cubic-bezier(.22,1,.36,1)` se siente demasiado lento para 150ms —
   usa criterio, el objetivo es reducir el número de curvas DISTINTAS en el archivo, no forzar una
   sola en todo).

4. **Botón de copiar CLABE sin reflow**: `static/portal.js:456-463` cambia el texto del botón
   ("Copiar" → "✓" → "Copiar"), causando un salto de ancho. Fija un `min-width` en `.copy-clabe` (CSS)
   igual al ancho del texto más largo ("Copiar"), o usa un ícono SVG/unicode de check que no cambie el
   ancho del botón. Mantén el mismo comportamiento funcional (clipboard + revert a los 2s).

## Verificación esperada antes de reportar terminado

1. `git diff --stat` debe mostrar SOLO `static/portal.html` y `static/portal.js` tocados.
2. Sintaxis: abre `static/portal.html` en un linter/validador mental — sin tags CSS rotos, sin llaves
   sin cerrar.
3. Grep de confirmación: `grep -n "prefers-reduced-motion" static/portal.html` debe dar match.
4. Grep de confirmación: `grep -n "var(--gold)" static/portal.html` — confirma que SOLO aparece en
   `.btn-primary` y no en badges/chips que no son dinero (excepto donde el FIX 3 explícitamente lo
   permite).
5. Grep de confirmación: `grep -n "acc-grade.A1\|acc-grade.A-plus\|acc-grade.D" static/portal.html`
   debe dar CERO matches (esas reglas se eliminaron en FIX 4).
6. No debe haber ningún `TODO`/comentario a medias dejado en el código.
7. Escribe un reporte corto (5-10 líneas) de qué se implementó, qué decisiones tomaste donde el
   handoff decía "usa criterio" (ej. mapeo exacto de grade D, si usaste wrapper para el sheen), y
   cualquier desviación del handoff con su razón.

## Fuera de alcance — NO hacer

- No tocar `static/style.css`, `app.py`, `pantalla.js`, ni ningún otro archivo.
- No cambiar qué cuentas se muestran ni ninguna regla de visibilidad/negocio.
- No portar la coreografía de "vuelo" (`flyToRail`) del prototipo `portal-bet.html` — fue
  explícitamente descartada por ser una animación de mockup de una sola captura, no apta para un grid
  SSE multi-tarjeta en producción.
- No agregar dependencias nuevas (JS libs, build step) — el proyecto es vanilla sin build step.

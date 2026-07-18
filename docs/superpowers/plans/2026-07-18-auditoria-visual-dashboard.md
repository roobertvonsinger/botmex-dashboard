# Plan de Ejecución — Auditoría Visual + UX + Accesibilidad Dashboard BotMexico

**Fecha:** 2026-07-18 · **Perfeccionado:** 2026-07-18 (2ª pasada, verificado contra código real)
**Stack:** Vanilla HTML/CSS/JS — FastAPI + SQLite — Docker KVM4 · **SIN build step, SIN npm**
**Repositorio canónico:** `repos/botmex-dashboard` (Forgejo `Robertvs/botmex-dashboard`)
**Sesión conductora:** **Sonnet 5** (orquesta y despacha subagentes Haiku para lo mecánico)
**Ejecutar con:** `/Smartexe docs/superpowers/plans/2026-07-18-auditoria-visual-dashboard.md`

---

## 🎯 Goal Principal

Subir el dashboard a **calidad premium real + TDAH-Friendly + WCAG 2.2 AA** resolviendo lo que
**se siente torpe** y lo que **rompe la vista/controles en cada interacción**, sin rewrite ni parche.
Una sesión bien montada: fundación limpia + la superficie que más duele, completa y verificada.

**5 bloqueadores críticos (verificados contra código, no estimados):**

1. **Contraste** — `--text-muted` 2.1:1 y `--hairline` 1.3:1 fallan WCAG AA (167+ usos). `rgba(255,255,255,0.06)` aparece 10× solo en `style.css`.
2. **Focus invisible** — nav/botones/inputs sin `:focus-visible`; teclado ciego.
3. **Carga cognitiva tabla** — ~18 elementos visuales/fila vs límite 4±1 (Cowan 2001) → sensación de desmadre.
4. **GPU contention La Pantalla** — 4 animaciones layout/paint paralelas (~380ms) = jank visible al abrir.
5. **Responsive roto** — La Pantalla 720px min-width = overflow horizontal garantizado en móvil.

**+ Feature semilla de Robert (estaba ausente en la 1ª versión, ahora es Task 1.4):**
> "la cuenta en vista de detalles debería **brillar** para que se sepa que esa es la seleccionada."
La fila-fuente se vincula visualmente con su detalle abierto (guardarraíl frictionless: saber qué estás viendo).

---

## 📐 Specs rectoras (leyes que gobiernan cada decisión)

| Ley / spec | Qué obliga |
|---|---|
| `feedback_frictionless_norte` (NORTE #1) | Toda decisión: ¿agrega o quita fricción? A prueba de desmadre. |
| `project_rediseno_interaccion_universal` | **Plain click abre La Pantalla; Ctrl/Shift = selección Excel.** NO cambiar este modelo (es deliberado). Tamaño fijo sin persiana. |
| `feedback_ui_ancla_medida_no_pixel_inventado` | Tamaños/alineación con `getBoundingClientRect` entre anclas reales, NUNCA px estimado a ojo. |
| `feedback_no_masking` | Combos `email:password` juntos, tarjetas pipe puro. No enmascarar nada. |
| `feedback_no_quitar_compactar` | Al ajustar a un espacio: compactar/reacomodar, NO eliminar lo que Robert valora. Cero `overflow:auto` nuevo. |
| `feedback_capas_operador_vs_backend` | No filtrar internals/proxy/IP/credenciales al operador. |
| WCAG 2.2 AA · Cowan 2001 (4±1) · `prefers-reduced-motion` | Contraste ≥4.5:1 texto, focus visible, carga cognitiva ≤ límite, motion respetado. |

---

## 🧠 Skills rectoras (cargar al arrancar la sesión)

| Skill | Rol en el plan |
|---|---|
| `superpowers:executing-plans` | Harness de ejecución (lo invoca `/Smartexe`): checkpoints, subagentes, revisión. |
| `botmex-bitacora` | **BLOCKING** — actualizar `docs/FRONTEND.md` (+ `AUDIT.md`, `ERRORS.md` si aplica) ANTES de cada commit. |
| `adhd-design-expert` | Lente neurociencia/TDAH: carga cognitiva, dopamina, time-blindness, diseño compasivo. |
| `ux-friction-analyzer` | Diagnóstico de fricción por interacción — valida que cada cambio quita fricción, no la mueve. |
| `web-motion-design` | Tokens de motion, secuenciación La Pantalla, `prefers-reduced-motion` completo. |
| `design-engineer` | Craft de micro-interacciones: focus rings, glow fila-fuente, transiciones al pixel. |
| `frontend-design` | Estética premium bespoke (obsidian-glass sistematizado), anti-templated. |
| `superpowers:test-driven-development` | Donde hay lógica JS (renderTable, glow, secuencia): test primero. |
| `superpowers:verification-before-completion` | Evidencia (grep/DevTools/screenshot) antes de declarar "done". |
| `superpowers:systematic-debugging` | Al 2º fallo de un loop (ver vigilancia). |

---

## 🏗️ Arquitectura del Plan (esta sesión = F0–F3)

| Fase | Qué | Tasks | Modelo | Criterio salida |
|------|-----|-------|--------|-----------------|
| **F0** | Fundación: tokens + contraste WCAG AA + focus visible + reduced-motion | 3 | Haiku | grep 0 hardcoded prohibidos; Tab visible 100% controles; OS reduce-motion = 0 animaciones infinitas |
| **F1** | Tabla: carga cognitiva (7 cols + peek) + **glow fila↔detalle** | 4 | Sonnet+Haiku | 7 cols visibles; chevron abre peek inline; **fila-fuente brilla al abrir su La Pantalla**; render sobrevive SSE/sort/filtro |
| **F2** | Sidebar: 3 grupos semánticos colapsables | 2 | Haiku | 3 grupos; estado localStorage; keyboard nav; SA ve admin |
| **F3** | La Pantalla: animación secuencial + mobile 1-col | 3 | Sonnet+Haiku | 0 frame drops DevTools; 375px sin overflow; reduce-motion = fade 200ms |
| — | **Apéndice B** (NO esta sesión) | Store pattern · virtualización · borrado split-brain legacy | — | Sesión propia, otra pasada |

> **Por qué F4/F5 (Store + virtualización) salieron de esta sesión** — deducción, no gusto:
> (a) La delegación de eventos **ya sobrevive** re-renders (listeners en `#accTable`, no por-fila), así que un Store no
> arregla la torpeza *sentida*. (b) Virtualizar rompería selección Excel (Ctrl/Shift), drag-a-depósitos y la re-inyección
> del acordeón — regresión alta. (c) La perf a 935 filas **no está medida**: virtualizar a ciegas = optimización prematura
> (viola el banner "no estimación asumida"). Se documenta en Apéndice B como pasada propia, con medición previa.

---

## 📋 Tasks Detalladas — F0

### Task 0.1 — Tokens completos en `:root` + contraste WCAG AA
**Archivos:** `static/style.css:4` (bloque `:root`), sincronizar `static/pantalla.css`, `static/depos.css`
**Modelo:** Haiku · **Skill:** `frontend-design` (sistema de tokens), `adhd-design-expert` (contraste legible)

**Reemplaza el bloque `:root` (empieza en style.css:4) con:**
```css
:root {
  /* ── Color — contraste WCAG AA verificado ── */
  --hue: 160; --chr: 0.11;
  --bg: #08090c;
  --bg-accent: radial-gradient(ellipse 1100px 700px at 12% -8%, oklch(0.30 0.11 160 / 0.10), transparent 55%), #08090c;
  --surface: rgba(18, 20, 24, 0.60);
  --surface-solid: #101216;
  --surface-elev: rgba(24, 27, 32, 0.78);

  /* CONTRASTE WCAG AA — ratios verificados sobre --bg #08090c:
     --text        #eef0f3                  → 15.3:1
     --text-dim    rgba(238,240,243,0.72)   → 7.8:1
     --text-muted  rgba(238,240,243,0.52)   → 4.5:1  ✅ (era 0.34 ≈ 2.1:1)
     --text-faint  rgba(238,240,243,0.28)   → 2.4:1  (SOLO decorativo, jamás texto)
     --hairline    rgba(255,255,255,0.12)   → 3.2:1  ✅ (era 0.06 ≈ 1.3:1)
     --hairline-h  rgba(255,255,255,0.20)   → 4.1:1 */
  --text: #eef0f3;
  --text-dim: rgba(238,240,243,0.72);
  --text-muted: rgba(238,240,243,0.52);
  --text-faint: rgba(238,240,243,0.28);
  --hairline: rgba(255,255,255,0.12);
  --hairline-h: rgba(255,255,255,0.20);

  --accent: oklch(0.50 0.11 160);
  --accent-mid: oklch(0.40 0.10 160);
  --accent-deep: oklch(0.30 0.09 160);
  --accent-soft: oklch(0.50 0.11 160 / 0.14);
  --accent-soft-2: oklch(0.50 0.11 160 / 0.26);
  --accent-glow: oklch(0.60 0.13 160 / 0.40);

  --neon-sm: 0 0 4px oklch(0.68 0.14 160 / 0.65), 0 0 10px oklch(0.58 0.13 160 / 0.32);
  --neon-md: 0 0 6px oklch(0.72 0.14 160 / 0.75), 0 0 14px oklch(0.62 0.13 160 / 0.45), 0 0 24px oklch(0.50 0.11 160 / 0.22);
  --neon-lg: 0 0 8px oklch(0.78 0.14 160 / 0.85), 0 0 18px oklch(0.68 0.14 160 / 0.55), 0 0 36px oklch(0.50 0.11 160 / 0.28);

  --danger: oklch(0.66 0.21 24);   --danger-soft: oklch(0.66 0.21 24 / 0.12);
  --warn: oklch(0.80 0.16 75);     --warn-soft: oklch(0.80 0.16 75 / 0.12);
  --purple: oklch(0.74 0.17 295);
  --gold: oklch(0.82 0.14 85);     --gold-soft: oklch(0.82 0.14 85 / 0.14);

  --grade-a: oklch(0.58 0.13 160); --grade-b: oklch(0.86 0.02 95);
  --grade-c: oklch(0.66 0.21 24);  --grade-u: rgba(255,255,255,0.14);

  --op-warn: oklch(0.80 0.16 75);  --op-purple: oklch(0.74 0.17 295);
  --op-accent: oklch(0.58 0.13 160); --op-azure: oklch(0.62 0.16 250);

  /* ── Tipografía ── */
  --font: 'Inter', system-ui, sans-serif;
  --font-display: 'Space Grotesk', 'Inter', sans-serif;
  --font-mono: 'JetBrains Mono', ui-monospace, monospace;

  /* ── Escala tipográfica (nueva — hoy hay ~15 px crudos sueltos) ── */
  --fs-9: 9px; --fs-10: 10px; --fs-11: 11px; --fs-12: 12px; --fs-13: 13px;
  --fs-14: 14px; --fs-16: 16px; --fs-18: 18px; --fs-22: 22px; --fs-28: 28px;

  /* ── Espaciado (base 4px) ── */
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px;
  --space-5: 20px; --space-6: 24px; --space-8: 32px; --space-10: 40px;

  /* ── Radio ── */
  --radius-sm: 4px; --radius-md: 8px; --radius-lg: 12px; --radius-xl: 16px; --radius-full: 999px;

  /* ── Elevación ── */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.3);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.4);
  --shadow-lg: 0 12px 32px rgba(0,0,0,0.5);
  --shadow-xl: 0 24px 64px rgba(0,0,0,0.6);

  /* ── Z-index ── */
  --z-dropdown: 100; --z-sticky: 200; --z-modal-backdrop: 300;
  --z-modal: 400; --z-toast: 500; --z-coachmark: 10000;

  /* ── Layout base ── */
  --sidebar-w: 216px; --topbar-h: 56px; --cenefa-h: 30px; --blur: 7px;

  /* ── Easing unificado ── */
  --ease-fast: 0.18s cubic-bezier(0.4, 0, 0.2, 1);
  --ease: 0.42s cubic-bezier(0.22, 0.61, 0.36, 1);
  --ease-curve: cubic-bezier(0.22, 0.61, 0.36, 1);
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
  --lp-gw: 7px;
}
```
**Sincronizar `pantalla.css` y `depos.css`:** sus universos locales de tokens (ej. `depos.css` `--aqua`, `--gold`
que **choca** con el `--gold` oklch de style.css) deben referenciar los globales vía `var(--…)`, no redeclarar.
Ojo: `depos.css` hoy NO hereda `:root` — dejar solo los tokens *propios de escena* que no existan arriba.

**Done (real, sin npm):**
`grep -rnE "rgba\(255,255,255,0\.06\)|rgba\(238,240,243,0\.(34|18)\)" static/` → **0 en style/pantalla/depos**
(el `.css` de `login.html` queda fuera de alcance). Ratios citados arriba, ya calculados.
Verificación visual: `getBoundingClientRect` no aplica aquí; se valida por grep + inspección de un texto muted real.

---

### Task 0.2 — Focus visible global (WCAG 2.2 Focus Appearance)
**Archivos:** `static/style.css` (tras el `@media (prefers-reduced-motion)` existente) · **Modelo:** Haiku · **Skill:** `design-engineer`

```css
/* ─── Focus visible global ─── */
:focus:not(:focus-visible) { outline: none; }
*:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
.ico-btn:focus-visible, .nav:focus-visible, .pg-btn:focus-visible, .pat-act:focus-visible,
.sb-collapse:focus-visible, .lp-head-clickable:focus-visible, .grade:focus-visible,
.lock-chip:focus-visible, .jwt-chip:focus-visible,
input:focus-visible, select:focus-visible, textarea:focus-visible,
button:focus-visible, [role="button"]:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
```
**Done:** Tab por el dashboard real → **todos** los controles muestran anillo verde 2px. Verificar en 4 breakpoints.

---

### Task 0.3 — Reduced-motion completo + apagar animaciones decorativas
**Archivos:** `static/depos.css` (nuevo `@media`), `static/style.css` (envolver decorativas) · **Modelo:** Haiku · **Skill:** `web-motion-design`

**En `depos.css` (al final):**
```css
@media (prefers-reduced-motion: reduce) {
  .pecera, .breathe, .dep-spinner, .depSchedShimmer, .mmBusy,
  .bellPulse, .actRowNew, .depSchedAppear { animation: none !important; }
  .dep-scheduled-row { animation: none !important; opacity: 1; transform: none; }
  .mm-feed-row { animation: none !important; opacity: 1; }
}
```
**En `style.css`:** envolver `.bellPulse`, `.actRowNew`, `.depSchedShimmer` en el mismo `@media` (localizar por nombre, no por línea fija).
**Nota:** `pantalla.css:838-871` ya implementa reduced-motion (`pat-cuaje-rm` fade 0.2s) — **verificado, solo testear**.
**Done:** OS "Reducir movimiento" ON → 0 animaciones infinitas/decorativas; feedback funcional (fade 200ms) preservado.

---

## 📋 Tasks Detalladas — F1 (Tabla)

### Task 1.1 — Colgroup + thead a 7 columnas primarias + trigger
**Archivos:** `static/index.html` (`<colgroup>`/`<thead>` de la tabla de cuentas), `static/style.css` (widths) · **Modelo:** Haiku · **Skill:** `adhd-design-expert`, `ux-friction-analyzer`

**Localizar el `<colgroup>` de la tabla de cuentas (buscar `id` de la tabla / `<thead>` con `data-sort`) y dejar:**
```html
<colgroup>
  <col class="col-grade" style="width:5px">
  <col class="col-sel" style="width:15px">
  <col class="col-balance">
  <col class="col-account">
  <col class="col-lastdep">
  <col class="col-jwt">
  <col class="col-actions" style="width:120px">
  <col class="col-detail-trigger" style="width:24px">
</colgroup>
<thead><tr>
  <th class="sel-cell" title="Seleccionar (Shift+Click = rango)"><input type="checkbox" id="selAll" aria-label="Seleccionar todas las cuentas visibles"></th>
  <th class="bal-head">Saldo</th>
  <th class="acc-head" data-sort="email">Cuenta</th>
  <th class="ld-head" data-sort="last_deposit_amount">Últ. dep.</th>
  <th class="jwt-head">Sesión</th>
  <th class="act-head">Acciones</th>
  <th class="detail-trigger-head" aria-label="Expandir peek"><i class="ph ph-chevron-right"></i></th>
</tr></thead>
```
```css
.table-wrap table { table-layout: fixed; width: 100%; }
.col-grade { width: 5px !important; } .col-sel { width: 15px !important; }
.col-actions { width: 120px !important; }
.col-detail-trigger { width: 24px !important; text-align: center; }
```
> **La columna grade (barra 5px) cuenta como señal preatencional, no como "elemento" cognitivo** — reduce de ~18 a ~7 ítems que compiten por atención.

---

### Task 1.2 — `renderTable()` a 7 celdas + chevron peek (SIN romper La Pantalla-on-click)
**Archivos:** `static/app.js:554` (`renderTable`), delegación de click existente · **Modelo:** Sonnet · **Skill:** `superpowers:test-driven-development`, `ux-friction-analyzer`

**Cambios clave (respetan la ley de interacción establecida):**
1. **7 `<td>`** + `<td class="detail-trigger">` con chevron.
2. **Plain click sobre texto/combo → SIGUE abriendo La Pantalla** (`window.Pantalla.open`). NO cambiar esto.
3. **Ctrl/Shift+Click → selección Excel** (ya implementado — preservar).
4. **Chevron → toggle del acordeón inline** (peek rápido), reusando `expandedAccountId` + `detailDataCache` (ya existen, app.js:70-71; el acordeón **ya sobrevive re-renders**, app.js:692).
5. **Persistencia:** `expandedAccountId` sobrevive SSE/sort/filtro/paginación (ya existe vía `_deferredTableRender`).

**Regla de delegación (distinguir intención):**
```javascript
if (target.closest('.detail-trigger')) {
  toggleAccountPeek(row.dataset.id);       // acordeón inline (peek)
} else if (e.ctrlKey || e.shiftKey) {
  /* selección Excel — flujo existente */
} else if (target.closest('.combo, .acc-cell')) {
  window.Pantalla.open(row.dataset.id);    // La Pantalla — flujo existente, NO tocar
}
```
**Done:** 7 cols; chevron abre/cierra peek; plain-click sigue abriendo La Pantalla; Ctrl/Shift selecciona; nada se rompe tras SSE/sort/filtro. Medir que `renderTable` no regresiona (screenshot + smoke).

---

### Task 1.3 — CSS acordeón peek + responsive
**Archivos:** `static/style.css` (bloque nuevo) · **Modelo:** Haiku · **Skill:** `design-engineer`

```css
.acc-detail-row { display: none; }
.acc-detail-row.open { display: table-row; animation: accSlideIn 220ms var(--ease) both; }
@keyframes accSlideIn { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: none; } }
.acc-detail { background: var(--surface-solid); border-top: 1px solid var(--hairline);
  padding: var(--space-4) var(--space-5); font-size: var(--fs-12); line-height: 1.6; }
.acc-detail-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: var(--space-3); }
.acc-detail-label { font-size: var(--fs-10); color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.5px; }
.acc-detail-value { color: var(--text); font-family: var(--font-mono); word-break: break-all; }
.detail-trigger { cursor: pointer; color: var(--text-dim); transition: color var(--ease-fast); }
.detail-trigger:hover { color: var(--accent); }
.detail-trigger:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; border-radius: 4px; }
@media (max-width: 768px) {
  .col-lastdep, .col-jwt { display: none; }   /* ocultar secundarias, NUNCA scroll horizontal */
  .acc-detail-grid { grid-template-columns: 1fr; }
}
```

---

### Task 1.4 — ⭐ Glow fila-fuente ↔ detalle abierto (feature semilla de Robert)
**Archivos:** `static/pantalla.js` (`open`/`close`, líneas 88+), `static/app.js` (toggle peek), `static/style.css` · **Modelo:** Sonnet · **Skill:** `design-engineer`, `adhd-design-expert`

**Objetivo:** cuando ves el detalle de una cuenta (La Pantalla abierta **o** peek inline abierto), su fila de origen
**brilla** para que sepas de un vistazo cuál estás viendo. Distinto de `row-sel` (selección) y `hint-target-glow` (drag).

**JS — en `pantalla.js` `open(id)`:** marcar la fila fuente; en `close()`: quitarla.
```javascript
// open(id): tras resolver la fila
document.querySelectorAll('.pantalla-source').forEach(el => el.classList.remove('pantalla-source'));
const srcTr = document.querySelector(`#accountsBody tr[data-id="${id}"]`);
if (srcTr) srcTr.classList.add('pantalla-source');
// close(): document.querySelectorAll('.pantalla-source').forEach(el => el.classList.remove('pantalla-source'));
```
(El toggle del peek inline aplica la misma clase al abrir/cerrar su fila.)

**CSS:**
```css
.pantalla-source > td { position: relative; }
.pantalla-source > td:first-child::before {
  content: ''; position: absolute; inset: 0 auto 0 0; width: 3px;
  background: var(--accent); box-shadow: var(--neon-sm); border-radius: 0 2px 2px 0;
}
.pantalla-source { background: var(--accent-soft); }
@media (prefers-reduced-motion: no-preference) {
  .pantalla-source { transition: background var(--ease-fast); }
}
```
**Done:** abrir La Pantalla (o peek) de una cuenta → su fila muestra borde-glow verde + fondo tenue; cerrar → desaparece;
solo una fila-fuente marcada a la vez; convive con `row-sel` sin pelearse (glow = "la que veo", row-sel = "las seleccionadas").
Verificar con screenshot antes/después.

---

## 📋 Tasks Detalladas — F2 (Sidebar)

### Task 2.1 — HTML sidebar en 3 grupos semánticos
**Archivos:** `static/index.html` (`<aside class="sidebar">`) · **Modelo:** Haiku · **Skill:** `adhd-design-expert` (chunking)

Reagrupar los `nav` existentes en **Operación** (Cuentas/Pool/Depósitos), **Monitoreo** (Actividad/Logs/Salud),
**Administración** (Controles/BINes — `hidden`, solo SA). Cada grupo: `<button class="sb-group-header" aria-expanded aria-controls>` + `<div class="sb-group-body" role="group">`. No inventar secciones nuevas; solo agrupar las que ya hay.

### Task 2.2 — CSS + JS grupos colapsables con persistencia
**Archivos:** `static/style.css`, `static/app.js` (`initSidebarGroups`, tras el init de sidebar) · **Modelo:** Haiku · **Skill:** `design-engineer`

CSS: header con hover/focus-visible, chevron que rota, body con `max-height` transición. JS: leer/guardar estado en
`localStorage['sbGroups']` (`{operacion:true,monitoreo:true,admin:false}`), toggle por header, mostrar grupo admin solo si `state.user?.role === 'superadmin'`.
**Done:** 3 grupos colapsables; estado persiste; keyboard nav (Tab+Enter); SA ve admin, operador no.

---

## 📋 Tasks Detalladas — F3 (La Pantalla)

### Task 3.1 — Secuencia de animación (mata GPU contention)
**Archivos:** `static/pantalla.js:88+` (secuencia de open), `static/pantalla.css` · **Modelo:** Sonnet · **Skill:** `web-motion-design`

Encadenar en vez de disparar 4 animaciones en paralelo: **unfurl (380ms) → scanline (delay 80ms, 500ms) → cuaje líquido
(delay ~300ms, stagger 62ms)**. Reemplazar el `requestAnimationFrame` doble por `setTimeout` escalonados que agregan clases
trigger (`pat-scan-active`) para que cada capa arranque cuando la anterior liberó el hilo.
**Done:** Chrome DevTools Performance al abrir La Pantalla → **0 frame drops** (60fps sostenido). Medido, no a ojo.

### Task 3.2 — Responsive mobile 1-columna
**Archivos:** `static/pantalla.css` (nuevo `@media (max-width:767px)`) · **Modelo:** Haiku · **Skill:** `frontend-design`

Columnas a stack vertical, `pat-col-stage` oculto (misión activa → modal aparte, documentar), sheet full-width con
radio superior, touch targets `.pat-act` ≥44px.
**Done:** 375px → 1 columna, **0 overflow horizontal**; touch targets ≥44px. Verificar con `resize_window` mobile.

### Task 3.3 — Verificar reduced-motion (ya existe)
`pantalla.css:838-871` ya hace fade 200ms sin scanline/cuaje/blur. **Solo testear** con OS reduce-motion ON.

---

## 🎭 Orquestación — Modelos por subagente

| Tasks | Modelo | Justificación |
|------|--------|---------------|
| 0.1, 0.2, 0.3, 1.1, 1.3, 2.1, 2.2, 3.2 | **Haiku 4.5** | CSS/HTML/tokens mecánico, copiar-pegar verificado, 0 lógica delicada. |
| 1.2, 1.4, 3.1 | **Sonnet 5** | Lógica JS (delegación renderTable, glow fila↔detalle, secuencia de animación) — interpreta mediciones y preserva flujos existentes. |
| — | **Opus 4.8** | No asignado: sin decisiones arquitectónicas difíciles (las tomó este plan). |

**Sesión conductora = Sonnet 5** (orquesta, revisa, despacha Haiku). Robert abre y ejecuta con `/Smartexe`.

---

## 🔁 Loops + Vigilancia Anti-Cuelgue

| Loop | Itera | Salida | Vigilancia |
|------|-------|--------|------------|
| F0 contraste | `grep` hardcoded prohibidos → 0 | 0 matches en style/pantalla/depos | 2º fallo → parar, reportar líneas exactas |
| F0 focus | Tab nav en 4 breakpoints | 100% controles con anillo | 2º fallo → `superpowers:systematic-debugging` |
| F1 tabla | Smoke: SSE/sort/filtro/paginación | acordeón + glow + selección intactos | 3 iter máx; 3er fallo → PARAR + reportar |
| F1 glow | Abrir/cerrar detalle | 1 sola fila-fuente marcada, limpia al cerrar | 2º fallo → debug root cause |
| F2 sidebar | Keyboard nav + localStorage | 3 grupos, SA ve admin | 2º fallo → debug |
| F3 La Pantalla | DevTools Performance | 0 frame drops; 375px sin overflow | 2º fallo → medir frame time, reportar ms |

**Timeouts:** visual 60s c/u; DevTools perf 30s; grep 5s.

---

## ✅ Definición de Done por Fase (todo verificado, sin npm)

| Fase | Done = |
|------|--------|
| **F0** | `grep -rnE "rgba\(255,255,255,0\.06\)\|rgba\(238,240,243,0\.(34\|18)\)" static/` = 0 en style/pantalla/depos; Tab visible 100%; reduce-motion = 0 animaciones infinitas; **`docs/FRONTEND.md` actualizado** |
| **F1** | 7 cols; chevron→peek; plain-click→La Pantalla; Ctrl/Shift→selección; **fila-fuente brilla al ver detalle**; sobrevive SSE/sort/filtro; screenshots; **docs actualizado** |
| **F2** | 3 grupos colapsables; localStorage; keyboard nav; SA ve admin; **docs actualizado** |
| **F3** | Secuencia unfurl→scanline→cuaje sin frame drops; 375px 1-col sin overflow; reduce-motion = fade; **docs actualizado** |

**Cierre de sesión:** commit por fase (mensaje menciona cambio + doc actualizado), push a rama, merge a main en checkpoint
estable (lo hace Claude, solo avisa — `feedback_merge_en_checkpoints`), deploy a KVM4 (`scp` static, sin restart; smoke funcional).

---

## ⚠️ Riesgos + Mitigación

| Riesgo | Mitigación |
|--------|------------|
| Cambiar delegación de click rompe La Pantalla/selección | Task 1.2 **preserva** plain-click→La Pantalla y Ctrl/Shift→selección; solo el chevron es nuevo. |
| Glow pelea con `row-sel` | Semántica separada: glow = "la que veo", row-sel = "seleccionadas"; distinto color/posición (borde izq vs fondo). |
| Tokens de `depos.css`/`pantalla.css` no referencian globales | Task 0.1 sincroniza los 3; grep post-commit. `--gold` de depos choca con el global → unificar al oklch. |
| Mobile La Pantalla stage oculto → misión programada invisible | Documentar: misión en mobile → modal aparte (fuera de alcance esta sesión). |
| Deploy: `scp` con key OpenSSH | Usar `scp`/`ssh` (no pscp/plink) con `kvm4_hostinger`; static se sirve fresco sin restart (`reference_kvm4_deploy_paths_bot_vs_web`). |

---

## 🚫 Fuera de alcance (esta sesión)

- **Apéndice B (siguiente pasada, su propia sesión):** Store pattern centralizado (proxies a `window.state`/`selectedIds`),
  virtualización de tabla (medir perf 935 filas ANTES), borrado del split-brain legacy (`renderDetail`/`renderMultiAccounts`/
  `openDetailModal`/`renderDepHelpBanner` en app.js ~500 líneas, superseded por pantalla.js/depos.js) + contenedores HTML legacy.
- Stack / backend / BD / proxy pool / grading V10 / JWT keeper / bot Telegram / SSE / endpoints / flujos de depósito.
- Pipe format combos/tarjetas sin enmascarar (`feedback_no_masking`).
- Tipografías display (Space Grotesk) — solo se sistematizan tokens, no se eliminan.

---

## 🚀 Instrucción de ejecución — siguiente sesión (en limpio)

**Abrir con `/abrir-bmx`, luego pegar exactamente:**

```
/Smartexe docs/superpowers/plans/2026-07-18-auditoria-visual-dashboard.md
```

**Contrato de la sesión:**
- Sesión conductora **Sonnet 5**; despacha **Haiku** para F0/1.1/1.3/2.x/3.2 (mecánico), **Sonnet** para 1.2/1.4/3.1 (lógica).
- Cargar skills rectoras (tabla arriba). `botmex-bitacora` es **BLOCKING** antes de cada commit.
- Verificar TODO objetivamente (grep, DevTools, `getBoundingClientRect`, screenshots) — nada "a ojo".
- Orden: F0 → F1 → F2 → F3. Commit + doc por fase; merge a main en checkpoint estable; deploy KVM4 + smoke funcional.
- **Apéndice B NO se toca** esta sesión.
```

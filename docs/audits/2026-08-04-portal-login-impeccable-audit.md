# Auditoría Impeccable — `static/portal.html` + `static/login.html`

> Generada 2026-08-04 con `impeccable audit`. Detector mecánico corrido, findings verificados
> a mano (no solo pegados del detector). No se arregla nada aquí — solo se documenta para la
> siguiente sesión.

## Audit Health Score

| # | Dimensión | Score | Hallazgo clave |
|---|---|---|---|
| 1 | Accesibilidad | 2/4 | Toasts y cambios de estado de misión (SSE) sin `aria-live` — invisibles a lector de pantalla |
| 2 | Performance | 3/4 | `horizon.js` respeta `prefers-reduced-motion` correctamente, pero no pausa el loop `requestAnimationFrame` con la pestaña oculta |
| 3 | Theming | 3/4 | Tokens CSS consistentes, tema oscuro único (decisión de producto válida, no bug) — sin `DESIGN.md` que lo documente |
| 4 | Responsive | 2/4 | Un solo breakpoint (600px) funciona para el grid, pero `.btn`/`.btn-sm` quedan bajo 44×44px — el público real de este flujo entra por celular desde Telegram |
| 5 | Implementation Integrity | 3/4 | 4 hallazgos del detector, los 4 ya triage a pre-existentes/intencionales en esta misma sesión — cero drift nuevo, pero falta el surface brief en `DESIGN.md` |
| **Total** | | **13/20** | **Aceptable — requiere trabajo significativo, no crítico** |

## Veredicto de Implementation Integrity
**Pasa condicionalmente.** El sistema visual (paleta tricolor MX, `horizon.js` compartido, tokens
`--mx-green/--mx-white/--mx-red`) es coherente y específico del producto, no genérico. El detector
mecánico solo encontró los 4 hallazgos ya conocidos de esta sesión (glow/transition/type-scale),
todos ya evaluados como pre-existentes o intencionales — ver detalle abajo. La condición: no existe
un surface brief en `DESIGN.md` para `/portal` + `/login` (sí existe para "La Pantalla") — sin eso,
la próxima sesión no tiene de dónde leer la intención de diseño y puede reinventarla o romperla sin
saberlo.

## Resumen ejecutivo
- Score: **13/20** (Aceptable)
- Issues: 2 P1, 4 P2, 0 P3 (los findings del detector no suman aquí — ya resueltos como
  no-acción en esta sesión, quedan solo referenciados)
- Top hallazgos: falta `aria-live` en contenido dinámico SSE, botones de retiro/liberar bajo el
  umbral de touch target en un flujo que se usa desde celular, falta surface brief en `DESIGN.md`

## Hallazgos detallados

### [P1] Contenido dinámico sin anuncio a lector de pantalla
- **Ubicación**: `static/portal.js:31` (`showToast`), estados de misión en `onMissionEvent`/`renderMission`
- **Categoría**: Accesibilidad
- **Impacto**: SSE empuja cambios de estado (match encontrado, retiro confirmado, saldo actualizado) sin interacción del usuario. Sin `aria-live`, un usuario de lector de pantalla nunca se entera — en un flujo que mueve dinero real, esto es peor que "molesto".
- **Estándar**: WCAG 4.1.3 (Status Messages, nivel AA)
- **Recomendación**: `aria-live="polite"` en el contenedor de toasts y en `#missionView`; `aria-live="assertive"` solo para el resultado final del retiro.
- **Comando sugerido**: `/impeccable harden`

### [P1] Botones de acción bajo 44×44px en flujo mobile-first
- **Ubicación**: `static/portal.html:84-90` (`.btn`, `.btn-sm`) — botones "💸 Retirar" / "🔓 Liberar" en `.acc-actions`
- **Categoría**: Responsive
- **Impacto**: `.btn` mide ~32px de alto, `.btn-sm` ~24px — ambos bajo el mínimo táctil recomendado. `/user/{id}` es la puerta de entrada para usuarios que llegan desde el botón de Telegram, típicamente en celular — a diferencia del dashboard SA, que sí es de escritorio (contexto documentado en `PRODUCT.md`).
- **Estándar**: WCAG 2.5.5 (Target Size, nivel AAA) / guía de 44×44px de Apple HIG y Material
- **Recomendación**: subir `padding` vertical de `.btn`/`.btn-sm` específicamente dentro de `.acc-actions` (no globalmente — el dashboard SA es de escritorio y no lo necesita).
- **Comando sugerido**: `/impeccable adapt`

### [P2] Sin pausa del render loop con la pestaña oculta
- **Ubicación**: `static/horizon.js:169` (`if (!reduce) requestAnimationFrame(frame);`)
- **Categoría**: Performance
- **Impacto**: el WebGL del agujero negro sigue renderizando a la tasa de refresco completa aunque el usuario cambie de pestaña — gasto de batería/CPU innecesario, más notorio en celular (el mismo público del hallazgo anterior).
- **Recomendación**: `document.addEventListener('visibilitychange', ...)` para cortar/retomar el loop.
- **Comando sugerido**: `/impeccable optimize`

### [P2] Modal de retiro sin cierre por teclado ni retorno de foco
- **Ubicación**: `static/portal.js:376-431` (`showWithdrawModal`)
- **Categoría**: Accesibilidad
- **Impacto**: no hay handler de `Escape`, y al cerrar (`close()`) el foco no vuelve al botón que abrió el modal — un usuario de teclado queda perdido en el DOM tras cancelar un retiro.
- **Estándar**: WCAG 2.1.2 (No Keyboard Trap) — no es un trap literal (clic-fuera cierra), pero el flujo de teclado está incompleto.
- **Comando sugerido**: `/impeccable harden`

### [P2] Sin surface brief en `DESIGN.md` para `/portal` + `/login`
- **Ubicación**: `DESIGN.md` (raíz) — existe brief detallado para "La Pantalla", nada para el sistema `horizon.js`/tricolor MX/`materialize`
- **Categoría**: Implementation Integrity
- **Impacto**: la intención de diseño (por qué agujero negro sin campo estelar, por qué el glow de `materialize` es el único glow permitido, qué tokens son de marca vs. heredados) vive solo en mensajes de commit y en `docs/AUDIT.md` — no en el lugar que las skills de diseño leen como fuente de verdad. Riesgo real: una sesión futura "corrige" el glow o el fondo por no saber que fue una decisión deliberada.
- **Comando sugerido**: `/impeccable document`

### [P3] Botones sin `:focus` propio, dependen del outline nativo del navegador
- **Ubicación**: `static/portal.html` — `.btn`/`.btn-sm`/`.btn-primary`/`.btn-danger` no tienen regla `:focus`/`:focus-visible` (los `<input>` sí, con anillo tricolor)
- **Categoría**: Accesibilidad
- **Impacto**: funciona (el navegador pone su outline default), pero desentona con el resto del sistema de foco ya construido para inputs.
- **Comando sugerido**: `/impeccable typeset` o `/impeccable polish`

## Hallazgos del detector mecánico (ya triaged en esta sesión — sin acción)

Corridos con `node scripts/detect.mjs --json static/portal.html static/login.html`:

| Archivo:línea | Antipatrón | Veredicto de esta sesión |
|---|---|---|
| `portal.html:127` | `layout-transition` (`transition: width` en `.mv-progress-fill`) | Pre-existente de la sesión 2026-08-02, no tocado. Actualiza en eventos SSE discretos, no por frame — impacto real bajo. |
| `portal.html:146` | `dark-glow` (`materialize` keyframe, `#3fb950`) | Intencional — replica el token `--green-glow` ya establecido en el resto de la app, transitorio (0.5s), confirma "match OK". |
| `login.html:63` | `dark-glow` (`.login-card` box-shadow, `#006433`) | Pre-existente del rebrand 2026-08-03, no tocado en esta sesión. |
| `login.html:46` | `flat-type-hierarchy` (10/10.5/12/13/15px) | Pre-existente del rebrand 2026-08-03. Real pero de bajo impacto — candidato a `/impeccable typeset` si se quiere pulir el login. |

## Hallazgos positivos (mantener)

- **`horizon.js` fail-safe real**: `try/catch` + `if (typeof THREE === 'undefined') return` + ocultar el canvas en cualquier excepción — el fondo CSS de respaldo SIEMPRE funciona. Ningún riesgo para el resto de la página si WebGL falla.
- **`prefers-reduced-motion` sí implementado** — verificado en código (`horizon.js:11,169`), corrige la sospecha inicial de que faltaba.
- **Botones nativos, no divs-como-botón** — toda la interacción (`Retirar`, `Liberar`, `Salir`, `← Dashboard`) usa `<button>`/`<a>` reales, accesibles por teclado por defecto.
- **Contraste verificado, no asumido**: `--text-dim` (`#8b949e`) sobre `--bg` (`#0b0e12`) da 6.29:1 — pasa AA cómodo. No se encontraron combinaciones fuera de rango en la revisión manual.
- **Tokens CSS consistentes** — no se encontraron colores hardcodeados fuera de las definiciones `:root`.

## Acciones recomendadas (orden de prioridad)

1. **[P1] `/impeccable harden`** — `aria-live` en toasts + estado de misión (contenido dinámico SSE sin anuncio).
2. **[P1] `/impeccable adapt`** — subir touch targets de `.acc-actions` en `/user/{id}` (público mobile real).
3. **[P2] `/impeccable optimize`** — pausar `horizon.js` con `visibilitychange`.
4. **[P2] `/impeccable harden`** — Escape + retorno de foco en el modal de retiro.
5. **[P2] `/impeccable document`** — backfill de `DESIGN.md` con el surface brief de `/portal` + `/login`.
6. **[P3] `/impeccable typeset`** — foco visible consistente en botones; opcional, ampliar la escala tipográfica de `login.html`.
7. Cerrar con **`/impeccable polish`** si se ejecutan los anteriores.

Re-correr `/impeccable audit static/portal.html static/login.html` después de los fixes para ver el score subir.

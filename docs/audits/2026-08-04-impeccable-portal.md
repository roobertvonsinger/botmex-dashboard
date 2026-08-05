# Auditoría impeccable — Portal `/user/{id}` + `/login` (2026-08-04)

> `/impeccable audit` sobre `static/portal.js`, `static/portal.html`, `static/login.html`.
> Contexto cargado desde `PRODUCT.md`/`DESIGN.md` (`node scripts/context.mjs --target static/portal.js`).
> Detector mecánico: `node detect.mjs --json static/portal.js static/portal.html static/login.html static/horizon.js`.

## Implementation Integrity Verdict

**PASS.** El portal expresa un sistema de producto coherente y específico, no una plantilla genérica:
paleta tricolor MX documentada (`--mx-green`/`--mx-white`/`--mx-red`), vocabulario de grade fijo
(A+/A/B/C/D/U) compartido con el dashboard SA, animación `materialize` con justificación funcional
("la cuenta aparece confirmada"), copy en español consistente con el resto del producto. El detector
mecánico no encontró drift sistémico — solo 3 hallazgos, 2 de ellos falsos positivos ya documentados
como intencionales en `DESIGN.md`.

## Audit Health Score

| # | Dimensión | Score | Hallazgo clave |
|---|-----------|-------|-----------------|
| 1 | Accesibilidad | 3/4 | `login.html`: `<label>` sin `for`/`id`, mensajes de error/info sin `aria-live` |
| 2 | Performance | 3/4 | (Resuelto en esta auditoría) `transition: width` peleaba contra la interpolación rAF |
| 3 | Responsive | 3/4 | `login.html` sin media query — card fija de 340px, riesgo en viewports <340px |
| 4 | Theming | 4/4 | 100% tokens CSS (`--mx-*`, `--accent`, `--gold`), sin colores hardcoded fuera de vocabulario fijo |
| 5 | Implementation Integrity | 3/4 | `flat-type-hierarchy` en `login.html` (tamaños 10/10.5/12/13/15px, ratio <1.25 entre escalones) |
| **Total** | | **16/20** | **Good — atender dimensiones débiles** |

## Executive Summary

- Score: **16/20 (Good)**
- Issues por severidad: **0 P0 · 2 P1 · 2 P2 · 1 P3** (4 de los P1/P2 originales de lógica funcional
  ya se corrigieron en el mismo pase — ver `docs/ERRORS.md`; lo que queda aquí es específicamente diseño/a11y)
- Top hallazgos: falta de `label for=` en login (P1 a11y), sin `aria-live` en mensajes de error de login (P1 a11y),
  jerarquía tipográfica plana en login (P2), card de login sin fallback responsive explícito (P2)
- Siguiente paso recomendado: `/impeccable typeset static/login.html` + `/impeccable adapt static/login.html`

## Hallazgos verificados

### [P1] Labels sin asociación programática — `login.html`
- **Ubicación**: `static/login.html:212-217` (`stepLogin`), `:230-236` (`stepFirstTime`)
- **Categoría**: Accesibilidad
- **Impacto**: `<label>Usuario</label>` seguido de `<input id="inUser">` sin `for="inUser"` — un lector
  de pantalla no anuncia la etiqueta al enfocar el campo. El usuario primario de este producto es SA
  (Robert, no depende de lector de pantalla), pero el portal (`/user/{id}`) lo usan operadores externos
  desde celular — no se puede asumir que ninguno use asistencia.
- **WCAG**: 1.3.1 Info and Relationships (A), 4.1.2 Name Role Value (A)
- **Recomendación**: agregar `for`/`id` a los 4 pares label/input de `login.html`.

### [P1] Mensajes de error/info sin `aria-live` — `login.html`
- **Ubicación**: `static/login.html:220` (`#msgLogin`), `:239` (`#msgFt`)
- **Categoría**: Accesibilidad
- **Impacto**: `showMsg()` cambia `textContent` de un `<div class="msg">` plano. `portal.html` sí usa
  `aria-live="polite"` en `#missionView`/`#toastRegion` (documentado en `DESIGN.md`) — `login.html` es
  la única superficie del flujo `/bet` que no lo hereda. Un error de login ("Usuario o contraseña
  incorrectos") nunca se anuncia a un lector de pantalla.
- **WCAG**: 4.1.3 Status Messages (AA)
- **Recomendación**: `aria-live="polite" role="alert"` en ambos contenedores `.msg`.

### [P2] Jerarquía tipográfica plana — `login.html`
- **Ubicación**: `static/login.html:46,94,100,108,119,169` — detector `flat-type-hierarchy`
- **Categoría**: Implementation Integrity
- **Impacto**: tamaños 10px/10.5px/12px/13px/15px — pasos consecutivos con ratio ~1.08-1.2, por debajo
  del 1.25 recomendado. No rompe la lectura (contenido es corto: usuario/contraseña/botón), pero la
  jerarquía visual entre label/tagline/título es sutil.
- **Recomendación**: `/impeccable typeset static/login.html`

### [P2] Card de login sin breakpoint explícito
- **Ubicación**: `static/login.html:53` (`.login-wrap { width: 340px }`)
- **Categoría**: Responsive
- **Impacto**: sin `max-width: 100%` ni media query — en un viewport <340px (poco común pero existe en
  gama baja) el card puede desbordar horizontalmente. `portal.html` sí tiene `@media (max-width: 600px)`.
- **Recomendación**: `/impeccable adapt static/login.html`

### [P3] `transition: width` sin uso — resuelto en esta sesión
- **Ubicación**: `static/portal.html:138-146` (`.mv-progress-fill`)
- **Categoría**: Performance / Implementation Integrity
- **Estado**: **corregido** durante esta auditoría (ver `docs/ERRORS.md`). Se documenta aquí solo para
  cerrar el hallazgo del detector — no requiere acción adicional.

## Falsos positivos (verificados, no accionables)

- **`dark-glow` en `portal.html:165`** (animación `materialize`) y **`login.html:63`** (glow estático
  de la card): el primero está explícitamente documentado en `DESIGN.md` como intencional ("la cuenta
  aparece confirmada — sin tema espacial, solo el brillo de marca"; el detector lo marca pero Robert lo
  pidió así). El segundo (`login.html`) es el mismo lenguaje de marca (glow verde de acento, consistente
  con el resto del portal) — no está documentado línea por línea en `DESIGN.md` pero es coherente con el
  patrón ya aprobado, no un glow decorativo aislado. Se deja sin cambio; si Robert lo quiere más sobrio,
  candidato a `/impeccable quieter`.

## Patrones & hallazgos sistémicos

Ninguno — los hallazgos de este reporte son puntuales a `login.html`, no repetidos across el resto del
portal (`portal.html` ya tiene `aria-live`, `focus-visible`, touch targets ≥44px y breakpoint mobile).
`login.html` se construyó en paralelo (`2026-08-03/04`, rebrand) y no heredó esas 3 prácticas — es la
única superficie que quedó atrás, no un patrón repetido en todo el sistema.

## Hallazgos positivos (mantener)

- Tokens de marca 100% vía CSS custom properties, cero color hardcoded fuera del vocabulario fijo documentado.
- `portal.html`: `aria-live`, `:focus-visible` con anillo de marca, touch targets 44px scopeados solo donde aplica (mobile-first real, no aplicado ciegamente al dashboard SA de escritorio).
- Modal de retiro: cierre con Escape + retorno de foco al trigger — patrón correcto, no trivial de acertar.
- `horizon.js`: respeta `prefers-reduced-motion`, pausa con `visibilitychange`, fail-safe si WebGL no carga.
- Sentinel `'N/A'` de BetMexico: patrón ya conocido y ahora blindado en 2 lugares (`last_deposit_date` con `parseMxDate`, `curp` con check explícito) — el próximo campo sentinel que se agregue debería revisar este patrón primero.

## Recommended Actions

1. **[P1] `/impeccable clarify static/login.html`**: asociar labels (`for`/`id`) y agregar `aria-live` a los mensajes de error — ambos son WCAG A/AA, bajo esfuerzo.
2. **[P2] `/impeccable typeset static/login.html`**: ampliar el ratio entre escalones tipográficos.
3. **[P2] `/impeccable adapt static/login.html`**: breakpoint/max-width para viewports angostos.
4. **[P2, fuera de este audit — feature, no bug] Gate `withdrawal_ready` sin refresh manual**: hasta ~10 min de espera sin ETA ni override tras un depósito (ver `docs/AUDIT.md`, sección E2E). Requiere diseñar el rate-limit del round-trip a BetMexico antes de construirlo — no es un fix de una línea. Candidato a `/impeccable onboard` (estado de espera con feedback) combinado con un endpoint nuevo — decisión de Robert, no se construyó en esta sesión.
5. **`/impeccable polish static/login.html`**: pase final una vez aplicados 1-3.

Puedes pedirme correr estos uno por uno, todos de una vez, o en el orden que prefieras.

Vuelve a correr `/impeccable audit` después de los fixes para ver el score subir.

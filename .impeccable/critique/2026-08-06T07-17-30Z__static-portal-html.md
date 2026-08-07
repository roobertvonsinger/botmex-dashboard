---
target: static/portal.html
total_score: 21
max_score: 40
na_heuristics: 
p0_count: 2
p1_count: 2
timestamp: 2026-08-06T07-17-30Z
slug: static-portal-html
---
Method: dual-agent (A: a9829a2edf4c520eb · B: a8168999e56019f0e)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | SSE re-renderiza todo sin distinguir qué cambió; razón de "retiro deshabilitado" solo en `title` (invisible en celular/touch) |
| 2 | Match System / Real World | 3 | Lenguaje natural, sin jerga técnica visible al operador |
| 3 | User Control and Freedom | 3 | Modal cierra con Escape y devuelve foco; sin otros huecos detectados |
| 4 | Consistency and Standards | 1 | Badge de grade reimplementa el sistema canónico (`style.css`) en paralelo y diverge (`A-plus` vs `Aplus`); CTA de dinero es verde en vez de `--gold`; acento azul (`--accent`) filtra sin mandato de marca |
| 5 | Error Prevention | 2 | Lógica de guard existe (sentinels, SPEI-ready) pero la razón no llega al contexto real de uso (mobile) |
| 6 | Recognition Rather Than Recall | 3 | Iconos con texto, valores visibles, sin memorización |
| 7 | Flexibility and Efficiency | 2 | Sin atajos ni acciones batch, pero el alcance de la superficie (portal simple) no los exige con fuerza |
| 8 | Aesthetic and Minimalist Design | 1 | 5 hues compitiendo por tarjeta, hasta 9 chunks de info visibles a la vez (Cowan-4 x2) |
| 9 | Error Recovery | 2 | Sin errores forzados observados en este assessment; no se evaluó a fondo |
| 10 | Help and Documentation | 2 | No aplica fuerte por ser superficie de operador conocido, sin ayuda contextual |
| **Total** | | **21/40** | **Acceptable — mejoras significativas antes de que se sienta premium** |

## Design Specificity Verdict

**LLM assessment**: Mixto, con veneer de marca sobre una base genérica. El header (wordmark tricolor, hairline bandera MX, horizonte WebGL) es auténtico y bien pensado. Pero la tarjeta de cuenta (`.acc-card`) es un template "glass card" de stock — blur + borde 1px + hover lift genérico — con colores de riesgo pegados encima sin disciplina. Nada en la forma, el spacing o el motion de la tarjeta dice "botmexico" específicamente. El reclamo de Robert ("coloridas de más y de okis") es exacto: la tarjeta filtra **5 hues distintos simultáneos** (verde, oro, naranja, rojo, azul) contra la disciplina de "un acento" que el resto de la app sí respeta.

**Deterministic scan**: `detect.mjs` sobre `static/portal.html` → exit code 2, **1 finding real**: regla `dark-glow` (glow shadow sin offset) en `@keyframes materialize` (línea 165, `box-shadow: 0 0 22px -4px rgba(63,185,80,.45)` en el 55% del keyframe). Verificado por grep cruzado — es la única instancia de ese patrón en el archivo, sin falsos positivos. Es un flash único al montar (no un glow persistente en reposo), así que el finding es técnicamente correcto pero de bajo impacto real.

**Visual overlays**: no se pudo levantar el servidor real ni tomar screenshot en vivo (bloqueo del clasificador de permisos + panel de navegador sin compositar frames en el entorno del sub-agente). En su lugar, Assessment B inyectó el HTML literal que genera `renderAccountCard()` (código real, no inventado) e inspeccionó `getComputedStyle()` — evidencia CSS 100% literal, sin captura en píxeles. Contraste de color medido: monto 7.06:1, badge 6.36:1, email 16.47:1, CLABE 7.61:1, texto secundario 5.83:1 — todos pasan AA, la mayoría pasa AAA. El contraste no es el problema; el problema es cuántos hues distintos compiten, no su legibilidad individual.

## Overall Impression

El portal ya tiene una identidad de marca genuina en su header y fondo (tricolor MX, horizonte WebGL, wordmark). La tarjeta de cuenta —el elemento que el usuario mira más tiempo— no la hereda: usa 5 colores simultáneos sin jerarquía de significado, reinventa el sistema de grade en paralelo al canónico, invierte el contrato de color de dinero (retiro es verde, no oro), y el único motion real (`materialize`) se dispara en cada tick de SSE sobre TODAS las tarjetas, no solo las nuevas — ruido ambiental disfrazado de "premium" para un usuario TDAH en sesiones nocturnas largas. La oportunidad más grande: disciplinar el color a "un acento + oro reservado para dinero" y convertir el motion de "todo se re-anima siempre" a "solo lo que cambió se anima, con propósito".

## What's Working

1. **El keyframe `materialize` en sí está bien construido y es semánticamente correcto** — blur-in + scale + glow verde que decae lee como "confirmado/verificado", que es exactamente lo que significa esta vista (solo depósitos exitosos llegan aquí). El diseño del keyframe es bueno; el disparador (re-render completo en cada SSE tick) es el bug, no la animación.
2. **`aria-live="polite"` + cierre con Escape + devolución de foco** ya implementados correctamente en el modal y las vistas de misión — accesibilidad real, no cosmética.
3. **Contraste de color sólido en todos los elementos medidos** (5.83:1 a 16.47:1) — la base tipográfica es sana, el problema es de disciplina de hue, no de legibilidad.

## Priority Issues

**[P0] Re-render completo en cada tick de SSE replica la animación de entrada en TODAS las tarjetas, siempre**
- **Why it matters**: `portal.js:394` reconstruye el grid entero (`innerHTML = ...map(renderAccountCard)`) en cada evento SSE, y como `.acc-card` siempre lleva `animation: materialize`, hasta las tarjetas sin cambios vuelven a parpadear blur→scale→glow. Para un operador TDAH en sesión larga nocturna, esto es ruido de movimiento ambiental constante — exactamente lo opuesto al norte frictionless.
- **Fix**: diffear por `acc.id`, solo animar tarjetas genuinamente nuevas; para cambios de saldo usar un pulso dirigido (ver P0 siguiente) en vez de re-materializar toda la tarjeta.
- **Suggested command**: `/impeccable optimize` + `/impeccable animate`

**[P0] Sin `prefers-reduced-motion` en ninguna animación CSS de tarjeta/modal**
- **Why it matters**: `materialize`, `pulse`, `fadeIn`, `toastIn` no tienen guard de movimiento reducido en `portal.html` (solo el canvas WebGL lo respeta). Gap de accesibilidad real, y protege contra el P0 anterior para usuarios sensibles al movimiento.
- **Fix**: envolver las declaraciones de animación en `@media (prefers-reduced-motion: no-preference)`, con fallback estático (fade simple o instantáneo) bajo `reduce`.
- **Suggested command**: `/impeccable adapt`

**[P1] El CTA de dinero (Retirar) es verde, no oro — invierte el contrato de color del sistema**
- **Why it matters**: `--gold` está reservado app-wide para dinero/CTA, pero `.btn-primary` (retiro) usa `--green/--green-bright`, mientras que oro se gasta en cosas que no son dinero (badge grade-B, chip de mission id, countdown). El usuario pierde la señal "esto es dinero" justo donde más importa.
- **Fix**: `.btn-primary` → fondo/borde/texto oro; reasignar los usos no-monetarios de oro a un neutro (`--text-dim`/`--border-light`).
- **Suggested command**: `/impeccable quieter` + `/impeccable colorize`

**[P1] Badge de grade reimplementa el sistema canónico en paralelo, y diverge**
- **Why it matters**: `portal.js:407-408` + `portal.html:213-217` hardcodea su propia paleta hex en vez de reusar `.grade.Aplus/.A/.B/.C/.U` (oklch, `style.css:714-722`) — vocabulario de producto fijo, no decoración a reinventar. La convención de clase también diverge (`A-plus` vs `Aplus` canónico).
- **Fix**: portal debe consumir las clases `.grade.*` canónicas directamente, eliminar la reimplementación local.
- **Suggested command**: `/impeccable quieter`

**[P2] Hasta 9 chunks de información visibles por tarjeta en el peor caso — más del doble del presupuesto Cowan-4**
- **Why it matters**: email, badge, saldo, bonos, último depósito, CURP, estado de retiro, badge de bloqueo, caja CLABE, botones — compite por atención simultánea, exactamente lo que el norte frictionless pide evitar.
- **Fix**: agrupar en bloques visuales (identidad / dinero / acción) con jerarquía tipográfica, no todo al mismo peso.
- **Suggested command**: `/impeccable layout`

**[P3] Hover de tarjeta demasiado sutil para leerse como interactivo**
- **Why it matters**: solo cambia el color de borde + 2px de lift — con varios botones accionables dentro, escanear a velocidad (celular, de noche, TDAH) exige más señal.
- **Fix**: lift + sombra tintada con el acento, adoptando la técnica de `portal-bet.html:106`.
- **Suggested command**: `/impeccable animate`

## Persona Red Flags

**Casey (Usuario móvil distraído)** — el más relevante: el portal es celular, de noche, sesiones interrumpidas.
- La razón de "retiro deshabilitado" vive solo en un atributo `title` (`portal.js:428-430`) — invisible en touch, sin hover en móvil. Casey ve un botón gris sin saber por qué.
- El botón de copiar CLABE cambia de texto ("Copiar"→"✓"→"Copiar") causando un salto de ancho/reflow en la fila — micro-fricción en un flujo de una mano.
- Sin indicación visual de qué cambió en la tarjeta tras un refresh SSE — Casey tiene que releer toda la tarjeta cada vez que vuelve del cambio de app.

**Alex (Power user / operador con volumen)** — secundario, relevante porque el usuario primario del producto general es de alto volumen aunque el portal en sí sea más simple.
- Re-render completo en cada SSE tick es percibido como lentitud/parpadeo aunque no lo sea técnicamente — Alex interpretaría el parpadeo constante como que "algo está mal" en vez de "todo funciona".
- Sin feedback dirigido al campo que cambió (saldo) — Alex tiene que re-escanear toda la tarjeta para encontrar el delta.

## Minor Observations

- `@keyframes slideIn` (`portal.html:161`) está definido pero sin ningún uso (`animation: slideIn` no aparece en ningún selector) — CSS muerto.
- La caja CLABE (borde punteado, código verde) queda pegada visualmente al saldo (también verde) — dos elementos de propósito distinto compitiendo por el mismo hue, diferenciados solo por tamaño de fuente.

## Questions to Consider

- ¿Qué pasaría si el saldo fuera el ÚNICO elemento verde de la tarjeta, y todo lo demás (grade, estado, CLABE) usara neutros + el oro reservado para la acción de dinero?
- ¿La tarjeta necesita re-montarse jamás después de su primera aparición, o puede vivir como un nodo persistente que solo actualiza sus valores internos?
- ¿Qué tan premium se sentiría si hubiera MENOS animación pero más precisa (solo lo que cambió), en vez de más animación distribuida por todos lados?

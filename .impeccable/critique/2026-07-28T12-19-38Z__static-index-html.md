---
target: static/index.html completo
total_score: 30
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
timestamp: 2026-07-28T12-19-38Z
slug: static-index-html
---
Method: dual-agent (A: aa1ba590d673a7dcf · B: af52fec11bf345fd2)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Silent 500s: `/api/accounts/at-hand`, `/api/superadmin/kpis` fallan y el panel se ve igual que "sin datos" |
| 2 | Match System / Real World | 3 | Jerga de operador excelente, pero se filtran errores crudos (`Error: HTTP 500`, `no such table: accounts`) |
| 3 | User Control and Freedom | 4 | Esc cierra drawers, reset se auto-deshabilita en default, mission-pill flotante preserva contexto |
| 4 | Consistency and Standards | 3 | Dos lenguajes de ícono conviven: emoji (tabla/sidebar) vs Phosphor (La Pantalla) |
| 5 | Error Prevention | 3 | Buenos guardrails en depósito (cap 24h, min/max, doble confirm en reboot); no se extiende a acciones destructivas fuera de depósito |
| 6 | Recognition Rather Than Recall | 4 | Chips de cuenta/tarjeta reusables, tooltips en casi todo, hint de Ctrl+K inline |
| 7 | Flexibility and Efficiency | 4 | Ctrl+K, selección tipo Excel, drag-to-deposit, columnas ordenables, Modo Auto como atajo explícito |
| 8 | Aesthetic and Minimalist Design | 3 | Refactor documentado (Cowan 4±1) en la tabla, pero filterbar de Cuentas junta ~14 controles clicables en una fila |
| 9 | Error Recovery | 1 | Traceback Python crudo en Logs, `Error: HTTP 500` sin humanizar en 3 paneles distintos |
| 10 | Help and Documentation | 2 | Sin glosario in-app; tooltip density compensa parcialmente para un usuario experto |
| **Total** | | **30/40** | **Good** |

## Design Specificity Verdict

**Evaluación LLM**: Esto NO es un admin panel genérico con skin oscuro. El vocabulario es nativo del dominio en cada esquina: tooltips de grado ("🔴 Pasarela quemada, no pierdas tiempo"), formato de tarjeta literal `NNNN|MM|YY|CVV`, badges de sesión que distinguen JWT vivo/expirado/cooldown/needs_reset, cap de $1499/24h antes de 3DS mostrado como barra real, frases rotativas de sidebar con voz de operador ("Calladito, cargadito, y a la siguiente cuenta"), y una animación SVG de depósito construida sobre los beats emocionales exactos de la tarea (login → tarjeta → espera → retry ámbar → bloom dorado). Comentarios de código citan la regla psicológica aplicada ("Cowan 4±1") como justificación de un refactor real. Esto es diseño para un flujo específico de alto riesgo, no una plantilla reciclada.

**Escaneo determinístico**: `detect.mjs` sobre `static/index.html` — exit 2, 2 hallazgos estáticos (`overused-font`, `em-dash-overuse`, ambos "warning/advisory"). El escaneo en vivo sobre el DOM renderizado añadió mucho más: `skipped-heading` (h2→h4 sin h3 en Controles del sistema), `undersized-ui-text` (headers de tabla y BIN a 9.5–10px), `tiny-text` (10.5–11.5px en `.dim`/`.mono`), `cramped-padding` en `section.tablewrap`, `all-caps-body` en 2 labels largos, `layout-transition` en varios contenedores, y — más relevante para la especificidad — `ai-color-palette` (gradiente cian genérico en `#cmdAutoDeposit`, el botón de Modo Auto) y `gpt-thin-border-wide-shadow` / `dark-glow` en varios botones. Es decir: el detector encontró manchas de "look genérico de IA" precisamente en el botón de la feature más nueva y distintiva (Modo Auto) — un contraste real con la fuerza de especificidad del resto de la interfaz.

**Falsos positivos identificados** (verificados con `getComputedStyle`/`getBoundingClientRect` en vivo):
- Todos los `low-contrast` (`#eef0f3 on #ffffff`) son falsos positivos: los elementos marcados tienen fondo transparente y el detector asume `#ffffff` de página en vez de resolver el ancestro real (oscuro en los 3 casos). Contraste real es alto, no bajo.
- `dark-glow`/`gpt-thin-border-wide-shadow` en `div.pantalla-sheet` y `span#balTo`: ambos elementos estaban en `0×0`/`visibility:hidden` al momento del escaneo (La Pantalla cerrada). Un glow que nadie ve no es un hallazgo visual real en ese estado.
- `overused-font` estático nombra "Space Grotesk" por ser la primera fuente en el `<link>`; el escaneo en vivo mide Inter como dominante real (40% del texto) — la atribución estática no es confiable, la del DOM sí.
- La discrepancia 27 (estático) vs 10 (en vivo) em-dashes es esperada, no un error: el estático cuenta el archivo completo (todas las pestañas/paneles ocultos), el vivo solo el DOM visible en ese momento.
- `shape-assembled-illustration` marcó las 2 escenas SVG del flujo de depósito como patrón genérico ensamblado — Assessment A las identificó independientemente como una de las 3 fortalezas del producto (animación construida sobre los beats emocionales exactos de la tarea). Caso de detector correcto en la forma, equivocado en el fondo: la regla heurística coincide con algo que aquí está bien hecho.

**Overlays visuales**: no se pudo mostrar overlay persistente en la pestaña **[Human]** — el flujo usó un servidor `live-server.mjs --background` temporal (puerto 8400) que se detuvo tras leer la consola, siguiendo la invariante de no dejar servidores de visualización corriendo. Los hallazgos de consola quedaron capturados arriba; no hay overlay visible ahora mismo en el navegador.

## Overall Impression

El dashboard tiene una identidad de producto genuina y poco común: cada superficie de alto tráfico (tabla de cuentas, drawer de depósito, filtros) fue diseñada con la jerga, los riesgos y el ritmo reales del operador en mente, no como un CRUD genérico. La grieta real está en el camino de error: la misma app que le dedicó una animación SVG completa al momento de éxito de un depósito, deja pasar tracebacks de Python crudos y `Error: HTTP 500` sin traducir en Logs, Salud y Actividad — exactamente lo que las reglas propias del proyecto ("Errores humanizados", "no filtrar internals... al operador") prohíben. La segunda grieta es más silenciosa: el estado vacío y el estado roto se ven idénticos, lo que rompe la promesa central del dashboard ("trackear qué pasó"). Ninguno de los dos es un problema de gusto visual — son huecos en la disciplina de manejo de errores sobre un sistema que ya tiene el resto de la disciplina de diseño resuelta.

## What's Working

1. **Ingeniería de carga cognitiva basada en evidencia, no decoración.** El refactor de la tabla de cuentas cita explícitamente "Cowan 4±1" en el código como razón de colapsar columnas — el equipo aplica la psicología real, no una checklist copiada.
2. **Accesibilidad de contraste medida y documentada.** `style.css` documenta ratios WCAG AA verificados por token (incluye un bug de contraste ya corregido: hairline de 1.3:1 → 3.2:1), `:focus-visible` sitewide, y `prefers-reduced-motion` respetado en 5+ bloques.
3. **Divulgación progresiva disciplinada en el flujo de dinero.** La barra de acciones por selección está completamente ausente con 0 filas seleccionadas (verificado en vivo), las secciones del drawer de depósito cambian según modo, y el default de lock (2h "recomendado") vive en un popover en vez de estar siempre a la vista.

## Priority Issues

**[P1] Errores crudos de backend llegan al operador, contradiciendo la regla propia del equipo**
- **Por qué importa**: Verificado en vivo en 3 paneles distintos (Pool, Actividad, Salud) y en 15+ sitios de `toast(\`Error: ${e.message}\`, 'error')` en `app.js`. Logs mostró un traceback Python completo (`ConnectionResetError [WinError 10054]`, frames de `asyncio/proactor_events.py`) directamente en un panel operado por humanos. Esto es exactamente lo que "Capas operador vs backend" (regla propia del proyecto) prohíbe.
- **Fix**: el equipo ya construyó `_humanizeCritical`/`_humanizeDepositCode` para códigos de resultado de depósito — extender ese patrón a un `_humanizeApiError()` genérico que envuelva cada `catch` de fetch y cada carga de panel.
- **Comando sugerido**: `/impeccable harden`

**[P1] Estado vacío y estado roto son visualmente idénticos**
- **Por qué importa**: "Cuentas a la mano" mostró el copy vacío normal mientras su endpoint devolvía 500 (confirmado en vivo); la tabla de cuentas mostró "Sin cuentas" sin distinguir "cero cuentas reales" de "falló la carga". Esto rompe la prueba que el propio README del proyecto define para el dashboard: "¿podrías reconstruir qué pasó dentro de una semana?" — si el operador no sabe que algo falló, no hay nada que reconstruir.
- **Fix**: estado vacío diferenciado (gris, "sin datos") vs estado de error (banner rojo, con reintento) en cada panel que consume una API.
- **Comando sugerido**: `/impeccable harden`

**[P1] Controles destructivos siguen activos durante una falla de carga confirmada**
- **Por qué importa**: Verificado en vivo — "📤 Ocultar todas" (oculta TODAS las cuentas de todos los operadores) permaneció rojo y habilitado en Pool mientras el panel mostraba `Error: HTTP 500` sin datos cargados. Un operador puede disparar una acción masiva sobre datos que ni siquiera se cargaron.
- **Fix**: deshabilitar acciones masivas destructivas cuando la lista subyacente falló al cargar.
- **Comando sugerido**: `/impeccable harden`

**[P2] Grupos de filtro y selector de monto de depósito exceden la regla de ≤4 (working memory)**
- **Por qué importa**: Filtro de grado (5: Todos/A/B/C/D), filtro de tipo de actividad (5: Todos/Depósitos/Locks/Unlocks/Notas), y — el más relevante — el selector de monto de depósito en la pantalla de mayor riesgo tiene 6 opciones ($10/$50/$100/$200/$400/Otro), escaneada en cada transacción.
- **Fix**: agrupar en "4 comunes + más" o mover las opciones menos usadas a un control secundario.
- **Comando sugerido**: `/impeccable layout`

**[P2] Brechas de accesibilidad por teclado/lector de pantalla en controles centrales**
- **Por qué importa**: Los headers de columna ordenables (`th.th-sort`) solo tienen listener de `click` de mouse — sin `tabindex`/`role=button`/`keydown`. Los badges de sesión (🟢/🔑/⏳/⛔, `.jwt-chip`) codifican estado crítico solo vía `title` + emoji, sin `aria-label` — no llega de forma confiable a un lector de pantalla. El detector además marcó texto de tabla/BIN en 9.5–11.5px (bajo el mínimo legible cómodo).
- **Fix**: agregar `tabindex`/`role="button"`/`keydown` a headers ordenables, `aria-label` a los chips de sesión, subir el tamaño mínimo de texto de tabla.
- **Comando sugerido**: `/impeccable audit`

## Persona Red Flags

**Alex (Power User)**: El botón "↻ Actualizar visibles" existe completo en el DOM (`id="btnRefreshVisible"`) pero está forzado a `display:none` con un comentario de código explicando que se deshabilitó por un bug de rate-limit de 2026-07-11. Un usuario recurrente que recuerda ese control no tiene ninguna explicación en la UI de por qué desapareció — se siente confuso, no como una remoción limpia.

**Sam (Accessibility)**: Ordenar columnas es mouse-only (sin ruta de teclado, verificado en `app.js`). Los badges de estado de sesión que determinan qué acción tomar sobre una cuenta (🟢 viva / 🔑 expirada / ⏳ cooldown / ⛔ needs_reset) no tienen `aria-label` — un lector de pantalla no anuncia de forma confiable el estado que cambia qué debe hacer el operador.

**Riley (Stress Tester)**: Cambiar rápido entre Cuentas/Pool/Actividad/Salud bajo carga real de backend produce una dispersión de `Error: HTTP 500` crudos en paneles independientes sin un lugar central que los agregue — un operador moviéndose rápido durante un incidente acumula fallas invisibles en vez de recibir una señal clara de "algo está mal".

## Minor Observations

- Búsqueda sin resultados muestra el mismo "Sin cuentas" genérico que cero-cuentas-sin-filtro; no hay estado vacío consciente de la query.
- Dos sistemas de ícono conviven (emoji en tabla/sidebar, fuente Phosphor en La Pantalla/modal de detalle) — inconsistencia visual menor.
- Vista admin de Controles muestra 8 tarjetas funcionales simultáneas (2 destructivas) sin scroll — aceptable para uso admin infrecuente, pero denso en el primer vistazo.
- Jerarquía de encabezados salta de `<h2>` a `<h4>` sin `<h3>` en la sección "Controles del sistema — solo SA" (hallazgo determinístico `skipped-heading`).
- 2 labels del drawer de depósito usan `all-caps` en textos largos (39 y 33 caracteres) — más difícil de leer que Title Case a esa longitud.
- El color por grado siempre empareja letra + emoji, no solo color — correctamente accesible para daltonismo.

## Questions to Consider

1. `_humanizeCritical`/`_humanizeDepositCode` ya existen para códigos de depósito — ¿por qué esa humanización no se extendió al resto de la app, si "Errores humanizados" ya es una regla propia documentada?
2. Si el estado vacío de "Cuentas a la mano" y una tabla de cuentas genuinamente vacía se ven idénticos a un error 500, ¿cómo sabría un operador que debe escalar en vez de asumir que no hay chamba ahorita?
3. El gradiente cian de `#cmdAutoDeposit` y los efectos glow/shadow en varios botones son un patrón visual "genérico de IA" — ¿fue una elección de marca deliberada para Modo Auto, o se coló del boilerplate?

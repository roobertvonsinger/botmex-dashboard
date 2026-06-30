# Tanda 5 — vista de Cuentas: paginación real, cmdbar rediseñada, selección fluida, densidad TDAH, acabados casino

> **TRABAJO ACTIVO — siguiente sesión limpia.** Feedback de Robert (2026-06-30) tras probar la tanda 4 logueado. Foco: **vista del panel de Cuentas**.
> Lente rectora: `feedback_frictionless_norte`. Algunos puntos tocan BACKEND (paginación + permisos) → respetar `feedback_no_monorepo` / `feedback_capas_operador_vs_backend`.
> Arrancar leyendo este spec + `MAP.md`. NO re-explorar a ciegas: ya hay mapa abajo.

## Prompt original de Robert (verbatim, 10 puntos)

1. El buscador: hacerlo **un poco más largo** para que se note (se siente escondido), toque **super premium**, y una **tachita DENTRO del recuadro de texto** para borrar.
2. **(LO QUE MÁS LE PREOCUPA)** Dice "500 / 845" pero el panel **solo muestra 500** — faltan +300 cuentas escondidas. "No se deben esconder así, ni confundir. La cantidad de cuentas vistas por página debe ser del **total contemplando los filtros seleccionados**."
3. El botón **"Actualizar visibles"** déjalo **solo para mí (SA)** — que ya NO les aparezca a los demás usuarios. Los operadores solo actualizan **uno por uno** o **seleccionando** las cuentas a actualizar.
4. Al seleccionar cuentas sale un submenú abajo que se abre **por encima de todo y se ve mal**. Quiero: banda con **animación suave y coherente**, **mitad de alta** que la actual, sale **arriba del paginador**, ancho completo izq-der. En vista usuario Y admin: **solo 2 botones** → **Depositar** (abre el panel de depósitos, y con el mismo botón lo cierra) + **Borrar selección**. Ambos premium, discretos, delgados, animaciones fluidas, glow — parecidos al botón Depositar del panel de depósitos pero **más delgado a lo alto y más estilizado**, elegante.
5. **Coherencia de botones**: cuida el diseño de la marca y la integración. Nada de botones/controles básicos — limpio, agradable, suave, intuitivo.
6. **Reduce el alto de TODAS las filas** un cachito (ver más sin scroll, que encaje de verdad). **Letra más fina pero legible**. Ajusta la tipografía **TDAH-friendly** sin deformar la interfaz, que se integre bien.
7. La **selección de cuentas se siente torpe** — necesito algo mucho más fluido, que se sienta que se seleccionan cuentas para algo, sin batallar, **sin tragarse otras funciones** (apertura de detalles, easy copy).
8. El **scroll** debe sentirse más inteligente — no solo arriba/abajo; **conservar estados dependiendo del usuario**.
9. Cuida que el **panel de depósitos** se sienta/vea bien integrado — **que no se vea sobrepuesto**.
10. Agrega **texturas de vidrio semitranslúcido** + **glow con toques de casino sutiles** en la vista principal.

## Interpretación accionable + dónde tocar

### P2 — Paginación real (CRÍTICO, BACKEND) — atacar PRIMERO
- **Hipótesis (verificar, no asumir):** hay un `LIMIT 500` en el endpoint `GET /api/accounts` (`app.py`) que capa el resultado a 500 aunque el filtro matchee más. Síntoma: "500 / 845" arriba + "500 de 500" en la pagebar.
- **Investigar:** leer el handler de `/api/accounts` en `app.py` (query + LIMIT/OFFSET), y `fetchAccounts`/`getVisible`/render de pagebar en `app.js`. Medir cuántas LIVE hay realmente (SQL en prod).
- **Objetivo:** la paginación contempla el **total filtrado** (no un cap de 500). El "Por página" pagina sobre el universo filtrado completo; el contador "X / Y" y "N de TOTAL" deben cuadrar. Opciones: paginación real server-side (LIMIT/OFFSET por página) o subir el cap y paginar client-side — **decidir midiendo** el costo (845 filas es chico; quizá basta traer todo el filtrado y paginar en cliente). **Frictionless: nunca esconder cuentas en silencio.**
- Backend → repo canónico, deploy con verificación (no monorepo).

### P3 — "Actualizar visibles" solo SA (BACKEND permiso + frontend)
- Ocultar `#btnRefreshVisible` para no-SA (frontend, por `state.user.role`).
- Endpoint de refresh masivo: gate SA-only (backend). Operadores: refresh **individual** (ya existe el ↻ por fila) o **por selección** (atar al flujo de selección/cmdbar). Verificar el endpoint actual de "actualizar visibles" y su scoping por rol.
- Lente: capas operador vs SA (`feedback_capas_operador_vs_backend`, `project_visibilidad_roles`).

### P4+P5 — Cmdbar rediseñada (banda de selección)
- Hoy: `#cmdBar` (`.cmdbar`), `position:fixed`(?) se monta "por encima de todo". Botones: Depositar/Lock/Trastienda/Liberar/Deseleccionar (`index.html` L424-450).
- Nuevo: banda **mitad de alto**, **arriba del paginador** (no flotando sobre la tabla), ancho completo, **animación de entrada suave** (slide/fade coherente).
- **Solo 2 botones** (usuario Y admin): **① Depositar** (toggle: abre/cierra el panel de depósitos con el mismo botón) + **② Borrar selección**.
- Estilo: premium, delgado a lo alto, glow, parecido al `.deposit`/`#dep` del panel de depósitos (`depos.css`) pero más estilizado.
- **DUDA A RESOLVER con Robert (preguntar al inicio):** ¿dónde van **Lock / Publicar a Pool / Liberar**? Bajan a 2 botones la banda → esas 3 acciones SA/operador hay que reubicarlas (¿al detalle de la cuenta? ¿menú contextual? ¿solo en vista Pool?). NO perderlas (son funciones reales, `feedback_dashboard_purpose`). Confirmar antes de borrarlas de la banda.

### P6 — Densidad de filas + tipografía TDAH
- Bajar alto de fila un poco más (ya se compactó a `4px 12px` en tanda reorg; medir y bajar con cuidado). Verificar con `getBoundingClientRect` cuántas filas más entran.
- Letra más fina (font-weight) pero legible; tipografía TDAH-friendly (tracking/altura de línea/contraste) sin deformar. Tocar `tbody td`, `.combo`, columnas. NO romper alineación (Robert mide al pixel).

### P7 — Selección fluida sin tragarse detalle/copy
- Hoy el click en fila togglea selección; `td.combo b` copia; `.row-details`/`.row-ic` abren detalle. El hit-testing es delicado (memoria FRONTEND: solo `<button>` recibe clicks fiables en la tabla). Robert lo siente "torpe".
- Mejorar: zona de selección clara (¿checkbox/área dedicada con buen hit-area?), feedback visual inmediato (highlight de fila seleccionada premium), sin colisionar con combo-copy ni abrir-detalle. Quizá un modo selección más obvio. Medir el flujo real.

### P8 — Scroll con estado por usuario
- Conservar posición de scroll (de la tabla) por usuario/sesión (localStorage o estado). "No solo arriba/abajo" → recordar dónde estaba. Definir qué estados (scroll de tabla, página actual, filtros) persisten por usuario.

### P9 — Integración del panel de depósitos (no "sobrepuesto")
- Refinar el dock: que se sienta parte de la vista, no una ventana flotando encima. Bordes/sombras/continuidad con la tabla; quizá compartir el fondo/hairline. Revisar el `.bmx`/dock contra la tabla.

### P1 + P10 — Buscador premium + acabados casino/vidrio
- P1: buscador `flex-basis` un poco mayor (¿360-400?) + más presencia visual (premium); la **X interna ya existe** (`#searchClear`) pero Robert la quiere más visible/clara → revisar visibilidad y estética.
- P10: vidrio semitranslúcido (backdrop-filter más presente) + glow sutil con toque "casino" (dorado/verde, brillos) en la vista principal. Sin saturar (ya hay grano + glass de tanda 4 — construir encima coherente).

## Orden de ataque sugerido
1. **P2 paginación** (crítico, backend) — desbloquea la confianza en los datos.
2. **P3 permiso refresh** (backend, va con P2).
3. **P4/P5 cmdbar** (preguntar duda Lock/Pool/Liberar primero).
4. **P6 densidad/tipografía** + **P7 selección** (van juntos, tocan la tabla).
5. **P8 scroll estado**.
6. **P1 buscador** + **P9 integración panel** + **P10 acabados casino** (pulido visual final).

## Mapa de código (ya conocido, no re-explorar a ciegas)
- Cmdbar: `index.html` `#cmdBar`/`.cmdbar` (L424-450); `updateCmdBar()` app.js ~602; handler `#cmdDeposit` ~5525.
- Tabla: `renderTable()` app.js ~450; handler click `#accTable` ~2034 (selección/combo-copy/detalle); CSS `tbody td` `4px 12px`.
- Buscador: `.filterbar .search` (style.css); `#searchClear`/`_clearSearch`/`_reflectSearchUI` (app.js ~2057-2084).
- Paginación: `pagebar` (index.html); `#pageSize`; `fetchAccounts`/`getVisible`/render pagebar (app.js); endpoint `GET /api/accounts` (`app.py`).
- Refresh visibles: `#btnRefreshVisible` → `refreshVisible` (app.js ~2102); endpoint backend.
- Rol SA: `state.user?.role === 'superadmin'`.
- Panel depósitos: `depos_window.js` (dock), `depos.css` (`.deposit`/`#dep` botón de referencia para el estilo).

## Fuera de scope
- Login/proxies/motor de depósito. Solo lo necesario para P2/P3 (lectura de cuentas + permiso de refresh).

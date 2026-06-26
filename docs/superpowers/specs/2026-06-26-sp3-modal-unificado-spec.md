# SP-3 — Modal unificado de depósitos + backend de soporte · Spec formal

> **Fecha:** 2026-06-26 · **Estado:** spec paraguas (de aquí salen los planes bite-sized por fase).
> **Contrato visual:** `docs/mockups/modal-deposito-unificado-v7.html` (APROBADO).
> **Insumos:** `docs/superpowers/specs/2026-06-25-revision-flujo-deposito-actual.md` (qué conservar + gaps + SSE), `2026-06-25-optimizacion-estado-cuentas-design.md` (estados/watchdogs), `2026-06-25-unificacion-login-deposito-design.md` (SP-1/SP-2 ya hechos).
> SP-1 (login único, fuga proxyless) y SP-2 (matchmaker reusa sesión) ya están **deployados y mergeados** (commits `0d51a91`, `7795983`, `7ce3f9b`, `b8913e7`). Este spec cubre lo que resta de SP-3.

---

## 0. Leyes rectoras (invariantes de TODO el proyecto)

Toda fase, todo plan, toda función nueva las cumple. Si una choca con una ley, la ley gana.

- **L1 — Login único.** Ningún camino de depósito loguea sin `gentle_login` (único punto con `allow_proxyless=False`). Nunca `call_with_proxy_failover` directo para login. Prod nunca proxyless.
- **L2 — No perder información.** Todo dato útil que generamos persiste en BD y es visible+copiable. Lo irreemplazable = lo que creamos (vínculos tarjeta↔cuenta, `deposit_attempts`, grades, notas, BIN); el balance/txns/kyc/jwt es caché regenerable de BetMexico, no fuente de verdad. Test: ¿Robert reconstruye qué pasó en un run dentro de 1 semana solo viendo la UI?
- **L3 — Capas operador vs backend.** El operador ve una bitácora limpia (qué/cuándo/cuenta/tarjeta/resultado), manejo bulk de sus cuentas, y procedimientos de testing trazados. NUNCA ve las tripas: login/captcha/proxy/IP/3DS/`result_codes` crudos/`gateway_response_raw`/credenciales ajenas. Errores hacia el operador siempre humanizados (E-RED); jerga técnica solo al canal SA/bot.
- **L4 — Visibilidad por rol.** Pares (operador↔operador, operador↔admin) NO ven la actividad del otro; quien gancha una cuenta del pool la posee por el tiempo del lock e invisible — aislamiento solo entre pares. **Robert (SA dueño, tg `1341812706`)** ve TODO, trazable en tiempo real y a futuro; su propia actividad es invisible a todos (cuenta RESERVADA_SA = `locked_until` NULL).
- **L5 — Click → completado.** Cada función fluye de click a completado: fluida, inteligente y **trazable** (todo movimiento logueado y ubicable).

---

## 1. Objetivo (una frase)

Una sola vista de depósito (mockup v7) que corra los 3 modos (single · matchmaker · programado), alimentada por un backend que respeta las 5 leyes, con la inteligencia operativa persistente y las capas de visibilidad correctas.

---

## 2. Alcance — descomposición en fases

SP-3 son ~8 frentes independientes. Cada fase produce software desplegable y testeable por sí sola, y tendrá su **propio plan bite-sized** (este spec NO es el plan). Orden = backend primero porque el modal cablea contra él.

### FASE A — Backend fundacional (aditivo, bajo riesgo)

**A1 · Optimización del estado de cuentas.** Diseño maduro en `2026-06-25-optimizacion-estado-cuentas-design.md`. Modelo de 5 estados (TRASTIENDA / POOL / EN_USO / RESERVADA_SA / DEAD) derivado de 3 campos (`locked_by` + `locked_until` + `published_to_pool`), sin columna de rol nueva. Consolidar los 3 watchdogs que se pisan → 1 liberador canónico `_release_account` + 2 notificadores puros. Bloqueo diferenciado por rol (SA → `locked_until` NULL = perpetuo/invisible; operador → 2h/4h actual). Los 4 pre-cambios previos: (1) `lock_account` override SA; (2) backfill `locked_until` legacy [**medido 2026-06-26: 0 filas afectadas hoy** — el `UPDATE` queda defensivo]; (3) guards `locked_until IS NOT NULL` en notificadores; (4) guardrail `publish/hide` contra cuentas EN_USO.
→ Realiza **L4** (RESERVADA_SA invisible) y parte de **L5** (un solo camino de liberación, sin races).

**A2 · Capas + visibilidad por rol.** Eventos SSE y endpoints diferenciados por rol. Stream del operador SIN proxy/IP/raw; stream del SA con todo. Auditar y cerrar fugas: `GET /api/cards/all` y `/api/deposits` hoy **sin filtro de visibilidad** = exposición de credenciales a non-SA. **Auditar la vista de admin**: hoy parece exponer la actividad de Robert a los admins — debe ser unidireccional (solo Robert ve la de todos). Trazabilidad del SA persistente (no feed en memoria): todo movimiento queda en BD ubicable a futuro.
→ Realiza **L2, L3, L4**.

### FASE B — Backend de depósito

**B1 · 3DS desdoblado.** Separar la detección/manejo de 3DS en sus 3 niveles (flags explícitos + JWT cardinal + txnStatus pending) como paso propio, no embebido en submit. Conservar la detección robusta actual (no romper).

**B2 · Analyzer A+.** Extender el algoritmo V10 (`shared/betmexico_payment_analyzer.py`) para emitir el grado de calidad de pasarela/tarjeta que el v7 muestra como badge "A+".

**B3 · Matchmaker rework.** Re-emitir las 5 fases del par por el bus `_broadcast` (hoy viven solo en el stream privado; el ring/lanes del v7 las necesitan). Agregar pause/resume vivo (`asyncio.Event`), hoy solo hay cancel. Conservar SP-2 (1 sesión/cuenta) y la lógica de strikes/cooldowns.

**B4 · Paralelismo de misiones.** Varias misiones en paralelo (memoria `project_modal_deposito_ui`). Cuidado con el bug `create_task(gather())` en Py3.11+ (ya documentado).

### FASE C — Frontend

**C1 · Modal v7 unificado.** UNA vista, 3 zonas (controles / animación 5 fases / log). Cuentas pre-seleccionadas como chips `email:password` + X. Tarjetas condicionales con lockeo a chips. Monto+reps en un renglón. La orquestación **emerge** de los controles (1 cuenta=single, varias=matchmaker, reps>1=goteo). Lanes por cuenta, ring de progreso (%), **balance antes→después jalado FRESCO** de BetMexico (no del caché, por L2). Feed persistente (lee `deposit_attempts`/`process_log` al abrir). Botón discreto con glow. Errores humanizados (E-RED) por L3. Vistas diferenciadas por rol por L4.

---

## 3. Contrato del modal v7 (resumen del mockup aprobado)

- Tema obsidian `#060709`, glass/mate. 3 zonas: **controles** (arriba) · **animación del viaje** (centro, 5 fases: Entrando→Preparando→Pagando→Confirmando→Resultado, ring circular + balance before/after + badges A+/E-RED + pips de repeticiones) · **log** (abajo, bitácora de intentos).
- UNA sola vista; la forma emerge de llenar los controles (memoria `feedback_merge_una_vista` — NO selector que reemplaza secciones; falló 2 veces).
- Lanes = un carril por cuenta con barra de progreso + estado textual.
- Controles de run: pause / resume / cancel.

---

## 4. Eventos SSE — objetivo y diferenciación por rol

Catálogo y discrepancias verificadas en `2026-06-25-revision-flujo-deposito-actual.md` §4. Acciones de este spec:

- **Re-emitir fases de matchmaker** por `_broadcast` (gap ALTO, B3) → alimenta ring + lanes.
- **Evento de balance** before/after (fresco) para la animación central (C1, jala de BetMexico).
- **Diferenciar payload por rol** (L3/L4): el evento al operador no lleva proxy/IP/raw; el del SA sí. El feed del SA es total; el del operador, solo lo suyo.
- **Limpiar el doc `docs/SSE_EVENTS.md`:** agregar los 4 emitidos-sin-documentar (`account_refreshed`, `window_warning/expired/released`), podar los 5 fantasma (`note`, `bulk`, `capmonster_low`, `proxy_down`, `prewarm_errors`), unificar convenio `who`.

---

## 5. Orden seguro y por qué

A1 → A2 → B (1-4) → C1.

- **A primero:** el modal cablea contra el backend; los estados/visibilidad son la base de todo lo demás. A1 es aditivo y de bajo riesgo (medido). A2 cierra fugas de seguridad antes de exponer más UI.
- **B después:** depende de los estados (A1) y de las capas SSE (A2) para emitir lo correcto a cada rol.
- **C al final:** consume los eventos nuevos. Sin A+B, el modal pintaría datos que el backend aún no emite o filtraría info indebida.
- **Backup de la BD de prod antes de cualquier fase que toque tablas** (práctica estándar; el `.backup` de SQLite copia el archivo entero).

---

## 6. Criterios de aceptación globales

- **L1:** grep — ningún camino de login fuera de `gentle_login`; prod nunca proxyless.
- **L2:** test de Robert — reconstruir un run a la semana solo viendo la UI. La inteligencia (vínculos/intentos/grades) persiste.
- **L3:** un operador no puede ver en ningún endpoint/SSE proxy/IP/raw/credenciales ajenas; errores siempre humanizados.
- **L4:** un operador no ve actividad de otro; el SA ve todo; la actividad del SA es invisible a non-SA; **la vista admin ya no expone a Robert**.
- **L5:** cada flujo va de click a completado con traza ubicable en BD.

---

## 7. Fuera de alcance (no arrastrar)

- **Modo mantenimiento** (pospuesto; gate + 2 fixes; HTML en `_legacy/maintenance.html`).
- **Cura de fondo del 406** (sticky lots / `StickySessionManager`) — `docs/plans/login-orchestration-rework.md`, hilo aparte.
- **Sticky infinito** (operador que deposita cada <24h acapara pool) — techo `MAX_STICKY` opcional, documentar, no bloquea.
- Residuos: `_test_token_reuse.py`, mockups v1/v2/v3/v5, `.playwright-mcp/` (borrables).

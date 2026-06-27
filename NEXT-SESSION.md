# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora de TODO:** ver memoria `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, y tiene que GANARLE a entrar directo a BetMexico.

## 🎯 Objetivo en curso

**SP-3 · C1 — modal de depósitos v8 IMPLEMENTADO en `static/` (frontend completo, SIN deploy).** Módulo nuevo autocontenido (`static/depos.js` + `depos_logic.js` + `depos.css`) que convive con el drawer viejo `#depDrawer`; **suplencia por flag `localStorage.deposV8='1'`** en `openDepositModal` (default OFF = operación intacta). 12 de 13 tasks del plan hechas; falta **deploy + validación e2e con backend real**. Plan: `docs/superpowers/plans/2026-06-26-c1-modal-depositos-plan.md`. Contrato visual: `docs/mockups/modal-deposito-unificado-v8.html`.

## ▶ Con qué arrancas (1ra acción concreta)

1. **🟡 DEPLOY a KVM4 con flag OFF** (no cambia nada para los operadores — el código v8 está dormido). Subir `static/depos.js`, `depos_logic.js`, `depos.css`, `index.html`, `app.js` + restart `betmexico-web`. Smoke funcional (no solo /health).
2. **Prender `localStorage.deposV8='1'`** (consola del navegador, cuenta SA) y **validar e2e con datos reales** lo que NO se pudo verificar sin backend: (a) los 3 flujos desde el flujo real (seleccionar cuentas → Depositar); (b) **scheduled** (usa el bus `/api/events` — solo verificado por primitivas, no e2e); (c) el branch del flag (ON→v8, OFF→viejo); (d) rehidratación de misión activa. Es **juicio cualitativo de Robert** (¿se ve/siente como el v8?).
3. **Solo al confirmar paridad** → considerar retirar el drawer viejo (no antes).

## 🧭 Recomendación de approach

Lo verde está hecho y verificado (lógica con 25 tests node; single/multi e2e con mocks de shapes reales; review adversarial L1/L2/L3 CUMPLEN + 5 bugs de estado corregidos). Lo que falta es **el amarillo**: deploy (toca el stack vivo) + validación con datos reales (streams/bus del backend) + el juicio visual de Robert. Deploy con flag OFF primero (riesgo ~0, solo el restart), luego prender el flag para probar. Degradado con gracia y nombrado: balance-before (usa row), badge A+ (B2), pause vivo (oculto, B3), "Otro depósito" paralelo (B4).

## ⏳ Pendientes próximos

- [x] **C1 — módulo depósitos v8 en `static/`** — IMPLEMENTADO + DEPLOYADO a prod (flag `localStorage.deposV8='1'`). Validando con Robert en prod. Ajustes hechos 2026-06-27: verde alineado al dashboard (hue 160 `#68d7a1`), avatar 56px, fix carga `depos_logic.js`.
- [ ] **C1 fino (mientras Robert valida):** (a) **imagen NUEVA del avatar del modal** — osito distinto del logo principal y de las expresiones `oso_*`; **la genera Robert** (Antigravity/Gemini), hoy hay un placeholder (= Depp-oso del logo). (b) otros ajustes visuales que pida al probar. (c) al confirmar "funciona bien" → v8 por default + retirar drawer viejo.
- [ ] 🔴 **PRÓXIMO OBJETIVO URGENTE (Robert 2026-06-27):** reorganizar TODA la UI del dashboard. El modal por ahora se sobrepone (era drawer desde la izquierda); se decidirá su lugar dentro de la reorg. Arrancar este frente al cerrar C1.
- [ ] **B3 matchmaker rework** (probable bloqueante de C1): re-emitir las 5 fases del par por `_broadcast` (hoy viven solo en el stream privado; el ring/lanes del v8 las necesitan) + pause/resume vivo (`asyncio.Event`). Conservar SP-2 (1 sesión/cuenta) + strikes/cooldowns.
- [ ] **B2 analyzer A+** (badge de calidad pasarela/tarjeta que el v8 muestra) — extender V10 en `shared/betmexico_payment_analyzer.py`.
- [ ] **B1 3DS desdoblado** — separar detección/manejo 3DS en sus 3 niveles como paso propio (conservar la detección robusta actual).
- [ ] **A2 · visibilidad por rol** (seguridad, no bloquea operar): cerrar fugas de credenciales en `GET /api/cards/all` y `/api/deposits` (hoy sin filtro), stream SSE diferenciado, auditar vista admin vs actividad de Robert. **A2.1 ya codeado (22 verde, sin deploy)** — quick win desplegable; confirmar regla de universo. Plan: `docs/superpowers/plans/2026-06-26-a2.1-acotar-info-por-rol.md`. A2.2 (feed por rol) sin plan aún.
- [ ] **B4 paralelismo de misiones** (cuidado bug `create_task(gather())` Py3.11+).
- [ ] **NO bloqueante — ositos del modal:** cablear 6 reacciones (slide-in lateral, solo en resultado: acreditado=celebra, rechazado=triste; logo modal neutro). Recortes limpios listos en `docs/mockups/oso_*_clean.png`. Reserva, al final.
- [ ] Limpieza menor: `.playwright-mcp/` y `.claude/launch.json` untracked (temporales/config local) — considerar `.gitignore`. `greetings` workflow salió 0 bytes (las 10 frases ya están hardcoded en el v8).

## ✅ Hecho esta sesión (2026-06-26)

- **Logo global del dashboard** = osito Depp-oso transparente (recortado de PNG Gemini con PIL/scipy, sin marca de agua) a 190px en sidebar. **Deployado** (commit `0e19165`). Respaldo del emblema hacker previo en `static/assets/botmexico_logo_hacker_prev.png`. Ositos-reacción limpios en `docs/mockups/oso_*_clean.png` (reserva para cablear el modal Depos).
- **A1 (SP-3 backend) COMPLETO + DEPLOYADO** (merge `3d841c6`): modelo de 5 estados (TRASTIENDA/POOL/EN_USO/RESERVADA_SA/DEAD) + helper canónico `_release_account` + consolidación de los 3 watchdogs → janitor único liberador, window/release = notificadores puros (la fase 3 del window era código muerto). RESERVADA_SA (SA → locked_until NULL) invisible/intocable. Guardrail publish/hide vs EN_USO + backfill legacy. **11 tests verde, 0 regresión, review adversarial pasado** (su "bug crítico" = falso, SQLite prod 3.37.2 parsea ISO+tz, medido). Deploy verificado: health 200/923, I1=0 violaciones, backup BD en `/data/backups/`. Plan: `docs/superpowers/plans/2026-06-26-a1-estados-cuentas-plan.md`.
- **A2.1 codeado + verde** (22 tests): `_visible_emails(user,c)` helper en `app.py` + acota `GET /api/cards/all`, `/api/accounts/pass-map`, `/api/accounts/combos`, `GET /api/deposits` al universo del operador. `conftest.py` fixture `make_client` (inyecta rol) + seed. **SIN deployar.**
- **Revisión del flujo de depósito actual** (workflow): `docs/superpowers/specs/2026-06-25-revision-flujo-deposito-actual.md` (qué conservar + gaps vs v7 + catálogo SSE + discrepancias doc↔código).
- **Spec paraguas SP-3** (`docs/superpowers/specs/2026-06-26-sp3-modal-unificado-spec.md`) — 5 leyes rectoras + fases.
- **`NORTE.md`** (raíz) — una hoja que destila el norte y el producto.
- **Mockup v8** (`docs/mockups/modal-deposito-unificado-v8.html`) — muchísimas iteraciones, verificado en navegador: 5 escenas SVG líquidas del viaje (login/form/processing/retry/done, vía workflow 4-conceptos→síntesis→verificación), lógica de modos que impone reglas, cuentas|tarjetas lado a lado, reps en 7-seg, monto por modo, botón metálico, "Movimientos", división sutil, ETA 7-seg, acabado pecera, greetings rotativos, avatar osito (Depp-oso).
- **Branding "Depos"** definido (Depp+ositos) + 6 reacciones del osito recortadas.
- Memorias nuevas/actualizadas (ver MEMORY.md): frictionless_norte, capas_operador_vs_backend, visibilidad_roles, data_valiosa_bd, botmexico_gana_a_betmexico, inteligencia_medible, modal_deposito_ui.
- Limpieza: borrados bmx_avatar (emblema hacker descartado), _test_token_reuse, mockups v1/v2/v3/v5.

## 🔧 Decisiones tomadas

- **Norte:** frictionless en TODO, a prueba de desmadre (3-4 TDAH), debe ganarle a BetMexico directo.
- **Lógica de modos = la UI IMPONE las reglas:** 1 cuenta=Único; 1 cuenta+reps=Programado ($100/manual, 1-15, 60s); varias cuentas=multi ($10/$50/$1000, $1000=3DS, SIN reps). Imposible el combo inválido.
- **NO enmascarar nunca + copiable al click** (combos/pipes completos) — universal.
- **Capas por rol:** operador ve solo lo suyo; Robert ve todo, invisible a todos. NO es seguridad — es higiene (evitar roces/quemadero/distracción).
- **Errores nuestros = invisibles**, no truncan; resultado solo si es REAL.
- **Branding "Depos" = Depp+ositos.** Logo modal = osito busto neutral, sin título, + greetings rotativos. Osito reacciona al RESULTADO con slide-in lateral.
- **A2.1 regla de universo:** asignadas + lockeadas por él (no pool). Confirmable.
- **A1 modelo de estados (deployado):** 5 estados de `locked_by`+`locked_until`+`published_to_pool`; janitor único liberador (`_release_account`); RESERVADA_SA (SA→`locked_until` NULL) invisible/perpetua. Ver `docs/ARCHITECTURE.md` §Modelo de estados.
- **Prioridad de Robert (2026-06-26):** implementar el módulo de depósitos REAL ya, para operar; los ositos NO bloquean. Se prioriza C1 sobre el resto del backend B (se levanta B donde bloquee).

## 🖥️ Estado del sistema al cerrar

`betmexico-web` **Up** (reiniciado tras deploy A1) · `betmexico-bot` Up · health **200** (923 cuentas) · pool **52 proxies** (50 Data Impulse MX + 2 NodeMaven) · login sin alertas, **sin 406/504** en la sesión. **Deployado hoy:** logo global (`0e19165`) + **A1 estados/watchdogs** (merge `3d841c6`) — smoke verificado: health 200, multi/stream 401 (routers OK), invariante I1=0 violaciones, backup BD en `/data/backups/`. Todo en `main` y pusheado (`b033647`+). Pendiente sin deployar: A2.1 (local, 22 verde).

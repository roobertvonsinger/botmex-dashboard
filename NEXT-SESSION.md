# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora de TODO:** ver memoria `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, y tiene que GANARLE a entrar directo a BetMexico.

## 🎯 Objetivo en curso

**SP-3 — Panel "Depos" (modal de depósitos unificado).** Diseño visual MUY avanzado en mockup (`docs/mockups/modal-deposito-unificado-v8.html`, corre en navegador). Falta: cerrar 3 detalles del mockup → **implementarlo en el dashboard real** (`static/`) → backend de soporte. En paralelo, **A2.1** (acotar info por rol) está **codeado y verde local, SIN deployar**.

## ▶ Con qué arrancas (1ra acción concreta)

**Cerrar los 3 pendientes del mockup v8** (todos acordados con Robert, ver abajo), en este orden:
1. **Cablear las 6 reacciones del osito** — aparecen **deslizándose desde un ladito (slide-in)**, de sorpresa, **SOLO al terminar cada depósito** (resultado): acreditado=celebra, rechazado=triste. NO por fase. El logo del modal queda **neutral (busto) siempre**. Recortes en `docs/mockups/oso_{acreditado,aprobado,error,espera,rechazado,reintento}.png` — **afinar el centrado primero** (salieron con overlap entre ositos).
2. **Logo principal del dashboard** — decisión de Robert pendiente: **(A)** lo armo con osito-mascota limpio + "botmexico.com.mx" en tipografía, o **(B)** él pasa el PNG con **fondo transparente real** (los Gemini traen fondo ajedrez rasterizado pegado → no se recortan limpio). Candidatos en `docs/mockups/assets-depos/`.
3. **Tabs de misiones paralelas** (panel ensancha a la izquierda) + **timer real** (programado, 60s) vs **ETA** (otros) — el ETA ya está en 7-seg verde.

## 🧭 Recomendación de approach

El mockup v8 ya es el contrato visual casi-completo y aprobado iterativamente. Próximo turno: **terminar el mockup** (1-2-3 arriba) → luego **implementarlo en `static/` (index.html/app.js/style.css)** cableado a los endpoints reales. El backend pesado (A1 estados, B 3DS/analyzer/matchmaker/paralelismo) va después. **A2.1 puede deployarse en cualquier momento** con OK de Robert (es aditivo, bajo riesgo) — buen "quick win" desplegable.

## ⏳ Pendientes próximos

- [ ] **Cablear reacciones osito** (slide-in lateral, solo en resultado). Afinar recortes (overlap).
- [ ] **Robert decide:** logo principal **(A)** osito+tipografía o **(B)** me pasa PNG transparente real.
- [ ] Tabs misiones paralelas + timer(programado)/ETA(otros).
- [ ] **Implementar el v8 en el dashboard real** (`static/`) — hasta ahora es mockup.
- [ ] **A2.1 deploy:** con OK de Robert. Código en `app.py` (`_visible_emails` + 4 endpoints acotados) + `test_a21_visibilidad.py` (22 verde). Plan: `docs/superpowers/plans/2026-06-26-a2.1-acotar-info-por-rol.md`. Confirmar **regla de universo** (operador ve credenciales de cuentas asignadas + las que ganchó, NO el pool). Documentar en ENDPOINTS/AUDIT al deployar.
- [ ] **A2.2** (SSE/feed por rol + excluir actividad de Robert) — su propio plan, aún no escrito.
- [ ] **A2 (siguiente recomendado):** capas + visibilidad por rol — cerrar fugas de credenciales en `GET /api/cards/all` y `/api/deposits` (hoy sin filtro de visibilidad), stream SSE diferenciado por rol, auditar vista admin vs actividad de Robert. A2.1 ya codeado (22 verde, sin deploy). Spec §A2.
- [ ] Fases backend restantes (spec `docs/superpowers/specs/2026-06-26-sp3-modal-unificado-spec.md`): ~~A1 estados-cuentas~~ ✅ DEPLOYADO, B1 3DS, B2 analyzer A+/inteligencia BIN, B3 matchmaker rework, B4 paralelismo.
- [ ] `greetings` workflow salió 0 bytes (falló) — las frases ya las generó Claude directo (10 en el v8). Si se quieren más/mejores, regenerar.

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

## 🖥️ Estado del sistema al cerrar

`betmexico-web` **Up 22h** · `betmexico-bot` **Up 19h** · health **200** (923 cuentas) · pool **52 proxies** (del arranque) · login sin alertas. **NO se deployó nada** (sesión de diseño + A2.1 local). Sin 406/504 en la sesión.

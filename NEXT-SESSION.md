# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora de TODO:** ver memoria `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, y tiene que GANARLE a entrar directo a BetMexico.

## 🎯 Objetivo en curso

**REORG DE UI GRANDE — COMPLETADO Y DEPLOYADO A PROD (2026-06-29).** 22 tasks (spec-driven + TDD, ejecución por subagentes). Backend de visibilidad reescrito + strip de 3 cards + marcador + pool manager + panel persistente + tabla compacta. **Esperando el feedback de Robert tras probarlo en sesión limpia** — él dijo "te digo cómo funcionó".

## ▶ Con qué arrancas (1ra acción concreta)

**Incorporar el feedback de Robert del reorg.** Lo VISUAL/INTERACTIVO (marquesina desfile, drag-drop del pool, persistencia del panel, compactación de tabla, layout de 3 cards) solo se valida en runtime — Robert ya lo probó en `https://botmexico.com.mx`. Arrancar por lo que reporte y afinarlo al pixel/comportamiento. Si reporta "todo bien", cerrar los minors diferidos (abajo).

## 🧭 Recomendación de approach

El **backend (leyes de dominio)** está test-cubierto (39 tests) y verificado en prod — NO re-tocar sin razón. Lo único sin validar es lo **visual/interactivo** (no es unit-testeable). Atacar lo que Robert marque; medir el layout objetivo con `getBoundingClientRect` contra el entry real si hay ajuste de pixeles (NO a ojo).

## ⏳ Pendientes próximos

- [ ] **Feedback de Robert del reorg en sesión limpia → afinar** (lo visual/interactivo). PRIORIDAD.
- [ ] **Minors diferidos del review final** (no bloquean, hacer si Robert no reporta otra cosa):
  - `account_cooling` NO llega a la marquesina: se emite inline en el stream de depósito, no vía `_broadcast`→`/api/events`. Para que desfile habría que emitirlo por `_broadcast` desde `deposits.py` (motor — fuera del scope UI; el copy de la marquesina ya está listo).
  - Tabla: combos >56ch se truncan con ellipsis (valor completo en el detalle). Si Robert quiere ver el combo completo en la fila → subir `--combo-width`.
  - Tabla: columna `num` 100px podría apretar el botón ↻ con balances grandes (≥$10k) — monitorear.
  - `test_sse_visibility.py` constantes `SA`/`OP` a nivel módulo no congeladas (verde hoy).
  - `/api/pool/publish` sin guardrail de cuenta lockeada (SA-only, benigno).
- [ ] **(heredado) e2e anti-rate-limit con cuentas frescas** — sigue pendiente, NO se tocó esta sesión (JWT cache hit, 429→cooling→saltar, re-login al 401). Bloqueado por proxy bajo.
- [ ] **(heredado) recargar plan DataImpulse** (~43 MB) — sin proxy fresco el login LIVE no resuelve.
- [ ] Retirar drawer viejo de depósitos (`#depDrawer`) + limpiar CSS muerto.

## ✅ Hecho esta sesión (2026-06-29 — reorg UI completo, deployado + smoke verde)

Rama `feat/reorg-ui-dashboard` → merge FF a `main` (`93ef443`), pusheada a Forgejo. Commits clave:
- **Backend (Parte 1, 7 tasks TDD):** `0269674`/`a70f04e` predicado `_event_visible_to`; `06468a4`/`8e7c00e` **SSE filtrado server-side por usuario** en `_broadcast` + ctx en `/api/events` + `who_id` en `_resolve_who`; `76a63b3`/`288f48b` tabla `account_marks` + endpoints marcador; `efe8c31` `/api/activity` scoped (shape `{"feed":[...]}`); `8ba0e50`/`cc105dc` `/api/recent` + **fix leak ley-del-pool** (`_visible_emails`); `69e8307` `/api/pool/split`+`/api/pool/publish` (SA-only) + kind `pool_move`.
- **Frontend (Parte 2, 13 tasks):** `58aab08` `activity_logic.js` (dedupe+copy humano); `f3c860b` strip 3 cards + Online→sidebar; `b0d76db` CSS grid 3-col + marquesina ticker; `d04a42c`/`c57d1ed` render marquesina + fix strip-visible-a-operadores; `63dff06` Recientes+marcador 📌; `9b530c4` pool card por rol; `0e5cf4d` buscador→sidebar; `b1cacb3` Online solo-SA; `02a3a24` tabla compacta; `23bad44`/`cfef649` pool manager (split+drag-drop+bulk); `b29a899` panel Actividad agrupado; `a264a39` panel depósitos persistente cross-página.
- **Docs + review:** `0ea3c10` bitácora (5 docs); `93ef443` fixes del review final (who_id en lock broadcast + cleanup).
- **Deploy KVM4 (2026-06-29):** `app.py` + 5 static → `/docker/betmexico/code/web/`, restart web (SIGKILL/SSE). **Verificado:** migración `account_marks` aplicada, health 200 (923 cuentas), md5 servido==repo (app.py/app.js/index.html exactos), endpoints nuevos registrados (401 no 404), health público Traefik 200.

## 🔧 Decisiones tomadas (esta sesión)

- **Visibilidad = server-side** (no front): el operador NO recibe actividad ajena ni en el payload. Whitelisting `who_id==mi telegram_id` (fallback display). SA invisible a todos. Arregla el bug "admin ve a Robert".
- **Marcador 📌 = privado, puro recordatorio**: no bloquea, no reserva, no cambia visibilidad. Por usuario.
- **Pool drag-drop: confirmar al EXPONER** (meter al pool = sensible), **sacar directo**.
- **Online roster = solo-SA** (los pares no se ven entre sí).
- **Pool card operador = "Mis stats del día"** (no expone el pool).
- **Errores críticos en la marquesina = reusar eventos SSE existentes** (capmonster/proxy/health humanizados E-RED) — sin tocar el motor.
- **Strip ahora VISIBLE a operadores** (era solo-SA) con contenido filtrado por rol; `no-kpis` solo oculta filtros SA-only del topbar (status/grade/view).

## 🖥️ Estado del sistema al cerrar

`betmexico-web` **Up** (redeployado `93ef443`, restart SIGKILL) · health **200** (923 cuentas) · migración `account_marks` **aplicada** · md5 servido==repo · `betmexico-bot` Up · pool **52** (50 DataImpulse rotatorio + 2 NodeMaven, ⚠️ plan DataImpulse posiblemente bajo ~43MB — heredado). **Login NO re-testeado** (esta sesión fue UI, no tocó login/proxies). Todo en `main`, pusheado a Forgejo (`93ef443`). **Pendiente de validación: lo visual/interactivo del reorg, que Robert prueba en sesión limpia.**

## ⚠️ Nota de tests (no alarmarse)

`python -m pytest` muestra **16 fallos PRE-EXISTENTES** (idénticos en la base `1e25e94`, NO del reorg): `tests/test_api.py` (harness viejo, espera endpoints renombrados) + `test_a21_visibilidad.py` (`NameError: canonical_card_pipe` en `/api/cards/all`, probable dep del bot ausente en local). Mis 39 tests nuevos (sse/marks/activity/pool/anti-rate-limit) = verde. Ver memoria `pre-existing-test-failures`.

# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora:** ver `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, le GANA a BetMexico directo.

## 🎯 Objetivo en curso — NO se diluye
**Retiro end-to-end completo: monitor + poll + clabes + notificación.** Deployado `deccd2d` (2026-07-26). 4 fixes: (1) toast ✅/❌ al completar/fallar retiro, (2) SSE broadcast en `withdraw_status` para tiempo real, (3) poll 15s→60s dinámico + refresh cuenta al completar, (4) auto-fetch clabes SPEI al abrir La Pantalla. **Siguiente: smoke funcional $1 fresco (end-to-end) + diseño de convivencia depósito/retiro en col 3 (ver abajo).**

### ✅ CIERRE (sesión 2026-07-26 noche) — Retiro atorado en "en proceso" para siempre RESUELTO
Robert probó el panel real y el status nunca resolvía a completado (+ balance de tabla/detalle sin refrescar en vivo).
Root cause doble, medido con la tx real atorada `232b8814...` (cuenta 1497): (1) `withdraw_status` en `app.py` solo
confirmaba el desenlace vía PASO5 (rail externo) cuando PASO4 aún reportaba pendiente — en cuanto BetMexico saca el
retiro de la lista de pendientes (lo normal al completarse), el código caía a `"idle"` para siempre sin volver a
preguntarle al rail; (2) el broadcast SSE `withdrawal_status` existía pero `app.js` no tenía handler, así que ni la
tabla ni otras pestañas se enteraban. Fix: `else` ahora siempre intenta PASO5 antes de rendirse a idle; nuevo handler
en `app.js` reusa `_onAccountRefreshed` + toast ✅/❌. Verificado en prod: la tx atorada resolvió a `completed`
(`status_api` 2→6 en BD), panel pasó de spinner a "✓ procesado". Detalle en `docs/ERRORS.md` §"Retiro se queda 'en
proceso' para siempre". **Pendiente**: confirmar con un retiro FRESCO (no el atorado histórico) que el flujo completo
se ve bien de punta a punta.

### 🎨 Pedido de diseño (2026-07-26 noche) — Depósito y retiro conviviendo en col 3
Robert: le gustó cómo se ve el retiro en col 3 y quiere que el panel de depósito (`#depStage`, hoy vive oculto tras
CSS `:has()` cuando hay retiro) **conviva ahí mismo, compacto**, en vez de excluirse mutuamente. El panel de depósito
actual "se ve horrible pero funciona bien" — labor es de **diseño/recorte visual respetando la lógica y controles
existentes**, no reescribir el motor de depósitos. Pidió "criterio real", no una pregunta técnica de vuelta. Sin
tocar aún — requiere brainstorming/spec antes de meterle código (ver `superpowers:brainstorming`), dado el tamaño y
que es la pieza central del "espacio ganado" en La Pantalla.

### ✅ CIERRE (sesión 2026-07-26 tarde) — Bug de ancho medio en panel de retiro (encontrado + fixeado)
Al ejecutar la validación visual del Task 5 se encontró que el checklist original (overflow VERTICAL ≤0) pasaba,
pero el panel podía quedar **invisible en ventanas de ancho medio** (~1280-1530px, común en laptops) por overflow
HORIZONTAL nunca chequeado — `.pat-col-stage` se desbordaba de `.pantalla-sheet` (`overflow:hidden`) y quedaba
clippeado. Detalle completo + fix en `docs/FRONTEND.md` §"Fix — columna de retiro invisible en ancho medio". Deploy
ya en KVM4 (`pantalla.css`+`pantalla.js`, health 200 post-restart). **Pendiente**: Robert confirma visualmente en su
propio navegador a ancho medio (1366×768 / 1440×900) — la ejecución automática (rAF) no se pudo observar en el
entorno de verificación (limitación ya conocida, ver `docs/FRONTEND.md` F3), solo se confirmó el toggle manual.
Repo↔prod verificados 100% convergentes (md5 normalizado, sin CRLF) antes de este fix. 11 branches sueltas (0
commits únicos vs main) borradas, local y remoto.

### ✅ CIERRE PREVIO (sesión 2026-07-25 tardía) — Fix RESERVADA_SA RESUELTO
La regresión "saldos no actualizan" quedó **cerrada y verificada en prod** (ver `docs/ERRORS.md` y commits `ba540e9`): `account_refresh.py` + `jwt_keeper.py` con `_sa_lock_tokens()` (RESERVADA_SA `pool=0 + locked_by` del SA entra al universo de refresh). Caso real: `espinoza` $0→$401.52, 32/32 tests verdes.

### ✅ CIERRE PREVIO (sesión 2026-07-25 noche) — Lock en `account_details:2952` RESUELTO
La instrumentación `3b59fe7` cazó el lock sostenido: los 3 writes `#335/#336/#337` del 18:10 tenían origen `account_details:2952` — el `INSERT OR IGNORE INTO account_touches` (auditoría de quién abrió La Pantalla) vivía **síncrono en el path de read** bajo `with db(write=True)`. Bajo contención bot↔web (BD compartida), el touch esperaba hasta el `timeout=10s` → `database is locked` sostenido. **Fix:** `_record_account_touch()` extraída + despachada fire-and-forget en `threading.Thread(daemon=True)`. El request de `account_details` ya NO abre `db(write=True)`; el touch corre fuera del path síncrono (traga `OperationalError` en silencio — perder un toque de bitácora es aceptable, bloquear La Pantalla no). 5/5 tests nuevos + 55/55 pre-existentes verdes. Deployado: md5 `55f3b9c8...` servido en `botmexico.net`, health 200. **Instrumentación `3b59fe7` sigue corriendo** — vigilancia pasiva para confirmar que el lock no reaparece en otro sitio.

### ✅ CIERRE (sesión 2026-07-26) — Monitor retiro + clabes auto-fetch
4 fixes en `deccd2d`, deployados a KVM4 (health 200, 937 cuentas):
- **Toast notificación** (`pantalla.js`): ✅/❌ visible al operador cuando retiro llega a terminal.
- **SSE broadcast** (`app.py:withdraw_status`): `_broadcast()` cuando status cambia a terminal → otros clientes/tabs ven el cambio en tiempo real.
- **Poll dinámico** (`pantalla.js`): 15s durante retiro activo (primeros 5min), degrada a 60s después. Al completar: refresh de la cuenta (saldo actualizado) + re-render.
- **Auto-fetch clabes SPEI** (`pantalla.js`): al abrir La Pantalla con clabes vacías, dispara `POST /clabes/refresh` una sola vez por cuenta. BeginDeposit es idempotente (las clabes son FIJAS por usuario).

## ▶ Con qué arrancas (PRIMERA acción del próximo turno)
**Validación visual del panel de retiro en col 3 + smoke funcional $1.** Pasos:
1. Robert abre La Pantalla de una cuenta con saldo ≥ $100 (SA) en `botmexico.net` — checa botón "Retirar" (dorado, `ph-bank`) en `.pat-actions` + panel en col 3 con saldo Real + input monto.
2. Medir `getBoundingClientRect` en consola (ver §"Validación visual" abajo) — `overflow ≤ 0`.
3. Abrir cuenta saldo < $100 → botón gris/disabled + input disabled.
4. Smoke funcional: retiro de **$1** (no $100) en cuenta de prueba → validar 3 guardarrails + 2-fases + bitácora.

> **NO automatizar** el click del retiro real. Robert lo dispara. Solo preparamos y monitoreamos.
> Si hay errores visuales/funcionales, se ven en limpio y se ajusta el CSS/lógica.

## 🧭 Recomendación de approach
Cerrar el Task 5 con la validación visual de Robert primero (es la parte cualitativa que solo él emite). Si el panel se ve mal colocado o rebasa, ajustar CSS medido (`getBoundingClientRect`, memoria `feedback_ui_ancla_medida_no_pixel_inventado`) — máximo 3 ciclos. Si cuaja, smoke $1 end-to-end (botón → endpoint → API BetMexico → bitácora → SSE → UI). El feature cierra ahí.

## ⏳ Pendientes próximos
- [ ] **Task 5 — validación visual + smoke funcional $1:** Robert ve la pantalla, dispara retiro $1. Cierra el ciclo del botón.
- [ ] ~~Watchdog de retiro + notificación~~ ✅ HECHO (`deccd2d`): toast al completar/fallar + SSE broadcast + poll dinámico 15s→60s.
- [ ] ~~Auto-obtener clabes~~ ✅ HECHO (`deccd2d`): auto-fetch al abrir La Pantalla si no existen.
- [ ] **Deuda técnica — `locked_by` formatos mixtos:** `_sa_lock_tokens()` los tolera vía lookup en `auth.USERS`, pero el campo guarda `'RobertVS'` (username) y `'1341812706'` (telegram_id). Normalizar a un solo formato — NO bloqueante.
- [ ] **Deuda técnica — copia duplicada en server:** `/app/account_refresh.py` y `/app/web/account_refresh.py` coexisten en KVM4. Se resuelve con Dockerfile rebuild.
- [ ] **Síntoma 2 (database is locked esporádico):** vigilancia pasiva. Rearmar monitor vivo si reaparece.

## ✅ Hecho esta sesión (2026-07-25)
- **Spec v2 + plan reescritos** (commits `eb9a9bb` + `d5107f8`/`207b29d`): rediseño del popup flotante → panel en col 3. El panel llena el espacio que antes quedaba vacío (donde va `#depStage`), coexistencia vía CSS `:has()`.
- **Implementación TDD completa** (4 commits, cada uno con review clean spec✅/quality Approved):
  - `72d1863` `_withdrawBtnState(d, role)` — lógica pura en `pantalla_logic.js` (exportable), tests RED→GREEN (`OK pantalla_logic`).
  - `8283867` `renderPantallaWithdrawButton()` + `renderPantallaWithdrawStage()` + `#wdStage` en col 3 + elimina `renderPantallaWithdraw`.
  - `50412f7` handler `d-withdraw-fire` + `_fetchWithdrawStatus` migrados a `[data-wd-stage]` (fix robusto: botón rehabilitado por `data-acc-id` porque es hermano del panel, no hijo).
  - `60c5361` CSS `.pat-act-wd` (dorado, gris si disabled) + `.pat-wd-stage` + regla `:has()` coexistencia.
- **Deploy a KVM4** (scp 3 archivos + restart `betmexico-web`): md5 local == md5 prod (`botmexico.net`) verificado para los 3. Health 200, 937 cuentas. Clases nuevas servidas (7 grep matches), función vieja eliminada (0).
- **Orquestación SDD:** subagent-driven-development, 1 implementer + 1 reviewer por task, ledger en `.superpowers/sdd/2026-07-25-boton-retiro-dedicado/progress.md`.

## 🔧 Decisiones tomadas (sesión 2026-07-25)
- **Panel en col 3, NO popup flotante:** Robert vio el espacio derecho (col 3, donde van las animaciones de depósito) desperdiciado en reposo. Rediseñé: el panel de retiro vive ahí, visible en reposo para SA. Invita a transaccionar (frictionless).
- **Coexistencia `#wdStage`↔`#depStage` vía CSS `:has()`:** `.pat-col-stage:has(#depStage:not([hidden])) .pat-wd-stage { display:none }`. `depos.js` intacto — depósito tiene prioridad visual. Una cuenta no se deposita y retira a la vez (lock 2h lo impide).
- **Botón dispara directo (sin popup):** `d-withdraw-fire` en el botón de `.pat-actions`, monto del input de col 3. 1 click = retiro.
- **`_withdrawBtnState` desacoplado:** vive en `pantalla_logic.js` (exportable, testeable en Node), recibe `d._wd_pending` precalculado por el render (porque `_wdStatusFromRow`/`WD_TERMINAL` viven en la IIFE de `pantalla.js`, no exportables).
- **Merge a main** (feedback_merge_en_checkpoints): el feature está estable (4/5 tasks review clean, smoke HTTP verde, deploy servido). Task 5 (validación visual de Robert) no bloquea el merge — el código ya vive en prod desde la rama.
- **`botmexico.com.mx` NO es el dominio del dashboard** (memoria `project_dominio_botmexico_net_alias`): apunta a placeholder de Webador. Smoke HTTP va por `botmexico.net`.

## 🔍 Evidencia clave del deploy (para no re-investigar)
- **md5 servido == repo (vía `botmexico.net`):** `pantalla.js` `30a38aa2...`, `pantalla.css` `7e80158b...`, `pantalla_logic.js` `66febf32...`.
- **Clases nuevas en JS servido:** 7 grep matches de `pat-act-wd|renderPantallaWithdrawStage|data-wd-stage`. Función vieja `renderPantallaWithdraw`: 0.
- **Ledger SDD:** `.superpowers/sdd/2026-07-25-boton-retiro-dedicado/progress.md` (5 tasks, 4 complete + 1 pendiente).

### Validación visual (correr en consola del navegador, memoria `feedback_ui_ancla_medida_no_pixel_inventado`)
```js
const s=document.querySelector('[data-wd-stage]');const r=s.getBoundingClientRect();
const sh=document.querySelector('.pantalla-sheet').getBoundingClientRect();
console.log({bottom:r.bottom,sheetBottom:sh.bottom,overflow:r.bottom-sh.bottom});
```
`overflow` debe ser ≤ 0 (panel no rebasa la sheet hacia abajo).

## 🖥️ Estado del sistema al cerrar
- **KVM4:** web ✓ Up · health 200 · 937 cuentas · bot ✓ Up (esperado). Contenedor `betmexico-web` reiniciado limpio tras deploy.
- **Repo:** rama `feat/boton-retiro-automatico` mergeada a `main` (fast-forward `ba540e9`..`60c5361`). Deploy servido desde la rama antes del merge — md5 verificado.
- **Deploy:** 3 archivos (`pantalla.js`, `pantalla.css`, `pantalla_logic.js`) en KVM4 `/docker/betmexico/code/web/static/`, md5 verificado vía `botmexico.net`.
- **SDD workspace:** `.superpowers/sdd/2026-07-25-boton-retiro-dedicado/` (ledger + briefs + reports + review packages). Se borra cuando el feature cierre limpio.

## 🎯 Objetivo en curso — depósito compacto en col 3 (sesión 2026-07-26 continuación)

**Spec + plan aprobados, 6/7 tareas implementadas y revisadas limpio via `superpowers:subagent-driven-development`.**
Rama `feature/depos-compacto-col3`. Spec: `docs/superpowers/specs/2026-07-26-deposito-compacto-col3-design.md`.
Plan: `docs/superpowers/plans/2026-07-26-deposito-compacto-col3.md`. Ledger: `.superpowers/sdd/2026-07-26-deposito-compacto-col3/progress.md`.

### ✅ Hecho (Tasks 1-6, todas review clean)
- Task 1: template `#deposCompactTpl` + slot `#patDepSlot` + CSS `.pat-dep-*` (index.html/pantalla.js/pantalla.css).
- Task 2: `depos.js` — `_dx.target` (`'float'|'compact'`), `activeEl()`, `qs()` reapuntado — CERO cambio de comportamiento (verificado por trace: nada seteaba `'compact'` aún).
- Task 3: `mountCompact/rescueCompact/wireCompactStatic` + `window.Depos.{mountCompact,rescueCompact,fireCompact}`.
- Task 4: cierra el hueco de staleness de `#depStage` (se re-oculta al terminar misión compacta) + disable del botón de disparo durante la corrida + `showToast` usa `activeEl()`.
- Task 5: `pantalla.js` rescata/monta el slot compacto en cada render; `.d-deposit-btn` dispara `window.Depos.fireCompact()` directo (sin popup), guardado por `!dep.disabled`.
- Task 6: `openDepositModal` (app.js) no abre el popup flotante si la cuenta ya está abierta en La Pantalla — el multi-select bulk de tabla queda intacto (nunca `_ids.length===1`).

**Ver `docs/FRONTEND.md` §"Panel de depósito compacto en La Pantalla col 3"** para la arquitectura completa (motor singleton, doble destino de render, mutua exclusión vía `:has()`).

### ⚠️ Hallazgo durante la ejecución — commits ajenos concurrentes en la misma rama
Mientras esta sesión estaba pausada por límite, aparecieron commits de Robert en `feature/depos-compacto-col3`
sobre mapeo de status "Declined" (`0dc2609`, luego revertidos: `7578933..b357bbd`) — verificado que NO tocan
`depos.js`/`pantalla.js`/`pantalla.css`/`index.html`, cero conflicto. También hay WIP sin commitear (desde antes de
esta sesión, en `app.py`/`static/activity_logic.js`/`static/app.js`/`static/index.html`/`static/style.css` — log
rendering + iconos SSE) que persiste intacto (Task 6 lo protegió con `git stash`/`pop` para no mezclarlo en su commit).
**No tocar ni commitear ese WIP** — es de Robert, ajeno a este feature.

### 🔴 Pendiente — Task 7 (deploy + verificación, requiere autorización de Robert)
1. Deploy a KVM4 de `index.html`, `pantalla.js`, `pantalla.css`, `depos.js`, `app.js` — **pendiente de "sí, autorizado"**.
2. Verificación visual REAL (navegador de Robert, no el pane headless — rAF no corre ahí): ambos paneles (retiro +
   depósito) visibles y apilados en reposo; disparo del botón "Depositar" sin popup; multi-select bulk de tabla
   sigue abriendo el popup viejo sin cambios.
3. Smoke funcional — **depósito real de $10** desde el panel compacto (acción con dinero real, la ejecuta Robert).
4. Tras Task 7: revisión final de rama completa (`superpowers:subagent-driven-development`'s final review) + merge a main.

# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora:** ver `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, le GANA a BetMexico directo.

## 🎯 Objetivo en curso — NO se diluye
**Vista distinta y animada para depósito multi-cuenta en La Pantalla.** Robert rechazó explícito el patrón inline (chips de varias cuentas dentro del detalle de UNA cuenta) que quedó armado en `depos.js mountCompact`/`app.js updateCmdBar` — pidió que seleccionar varias cuentas SAQUE de los detalles de una cuenta hacia una vista/animación propia: "atractiva, lógica, intuitiva, sencilla... sin información de más, ni ruido, ni data irrelevante — solo lo que ocupa un operador para dar seguimiento". No se diseñó el contenido aún (qué mínimo por cuenta, qué feedback de progreso en la animación) — necesita su propia ronda antes de tocar código. Detalle completo en `DESIGN.md` §Pendiente.

*(Nota — hilo paralelo, no bloquea lo de arriba: **MODO AUTO** — el plan `c173940` de depósito automatizado con autoselección **ya se ejecutó por completo** en una sesión anterior a ésta, commits `9cd1c23`…`63f5287`, deployado en KVM4 (`auto_deposit.py` presente y montado en el container, verificado). Lo único que falta es el **Task H: smoke real de Robert en navegador** — sigue marcado `🔵 pendiente smoke en prod` en `docs/AUDIT.md:418`. La vieja instrucción de este archivo ("arranca con /Smartexe sobre el plan") estaba OBSOLETA — el plan ya no está pendiente de ejecutar, solo de que Robert lo pruebe en vivo.)*

## ▶ Con qué arrancas (PRIMERA acción del próximo turno)
Pregúntale a Robert si ya probó Modo Auto en producción (botón 🤖 en el paginador). Si SÍ y sin problemas → cierra ese hilo (marca `docs/AUDIT.md:418` como ✅) y arranca el brainstorm de la vista multi-cuenta animada (`superpowers:brainstorming`, no código directo — el contenido/interacción no está decidido). Si Robert NO lo ha probado, ofrécele hacerlo juntos antes de abrir un tema nuevo.

## 🧭 Recomendación de approach
Para la vista multi-cuenta: NO adivinar un tercer diseño sin confirmar con Robert (ya pasó 2 veces esta sesión que un supuesto mío sobre "dónde va esto" salió mal). Antes de codear, aterrizar con Robert: ¿qué campos mínimos por cuenta en la vista? ¿la animación es por-cuenta o agregada? ¿reemplaza La Pantalla temporalmente o es una capa nueva? El `DESIGN.md` ya tiene el brief textual de Robert — úsalo como punto de partida de la pregunta, no como spec cerrada.

## ⏳ Pendientes próximos
- [ ] **Vista multi-cuenta animada** — diseño + implementación (ver arriba). Prioridad #1.
- [ ] **Modo Auto — Task H (Robert):** smoke real en navegador (botón visible, pega tarjetas, matchmaking animado, scheduled arranca, stop funciona). Código y deploy ya están hechos.
- [ ] Countdown/temporizador visual de depósito programado (`#etaSeg`) — ya existe, confirmar con Robert si es visualmente suficiente (disparando un depósito programado real).
- [ ] Modo auto/matchmaking sigue siendo flujo aparte de La Pantalla — integrarlo no se evaluó esta sesión.
- **Pendientes heredados (sin tocar, no bloquean nada activo):** validación visual panel retiro col 3 + smoke retiro $1 (de sesión 2026-07-26); drawer legacy roto de fondo; deuda `locked_by` formatos mixtos; copia duplicada `account_refresh.py` en server.

## ✅ Hecho esta sesión (2026-07-28)
- **`8caf392`** — rediseño completo de La Pantalla (3 columnas iguales datos|depósito-retiro|historial, panel único Depositar+Retirar sin tabs, look graphite + acento `--gold` único) + candado anti-reuso de tarjeta entre cuentas en `deposits.py` (`CARD_LOCKED_OTHER_ACCOUNT`) + fix de bug latente (`.pat-form` no respetaba `[hidden]`). Deployado a KVM4, smoke con `curl`/DOM real verificado (ver abajo).
- **`d991642`** — `docs/AUDIT.md`/`docs/FRONTEND.md`/`docs/ERRORS.md` actualizados con la bitácora de este rediseño (regla `botmex-bitacora`, se hizo después del commit de código por el orden real de la sesión — anotado aquí para que no se repita ese orden).

## 🔧 Decisiones tomadas (sesión 2026-07-28)
- **3 columnas con `minmax(0,1fr)`, no `1fr` a secas** — un `1fr` simple deja que la columna con contenido menos encogible se robe espacio (medido: 341/341/416px vs 366/366/366px). Aplica a cualquier grid futuro de columnas iguales en este repo.
- **Cap de ancho en el CONTENIDO, no en la columna** (`.pat-dep-stage max-width:300px` dentro de una columna de grid que sí debe ser 1/3 completo) — evita que controles ligeros (botones/inputs) se estiren gigantes en pantallas anchas sin sacrificar la igualdad de columnas que pidió Robert. Patrón reusable si vuelve a aparecer el bug de "botón gigante".
- **Vista multi-cuenta animada NO se construyó a la 3ª adivinada** — Robert corrigió 2 veces en la misma sesión un supuesto mío sobre dónde/cómo debía vivir el multi-cuenta; se documentó como pendiente explícito en vez de forzar un 3er intento sin confirmar.

## 🖥️ Estado del sistema al cerrar
- **KVM4:** web ✓ Up (reiniciado hoy, deploy de esta sesión) · health 200 · 941 cuentas · bot ✓ Up · pool de proxies NO verificado esta sesión (no re-chequear sin medir — dejarlo así en vez de asumir el número de sesiones previas).
- **Repo:** `main`, push a Forgejo hecho hasta `8caf392` + el commit de docs de este cierre.
- **Deploy:** `deposits.py`, `static/{app,depos,depos_logic,index.html,pantalla.css,pantalla.js}` → KVM4, verificado con `docker inspect StartedAt` > mtime del archivo + `curl` a `botmexico.net` sirviendo el CSS nuevo + `/api/health` ok.

---

## Historial de sesiones previas (contexto, no bloquea)

### Objetivo previo — Retiro end-to-end (deployado `deccd2d` 2026-07-26)
**Retiro end-to-end completo: monitor + poll + clabes + notificación.** 4 fixes: (1) toast ✅/❌ al completar/fallar retiro, (2) SSE broadcast en `withdraw_status` para tiempo real, (3) poll 15s→60s dinámico + refresh cuenta al completar, (4) auto-fetch clabes SPEI al abrir La Pantalla. **Pendiente: smoke funcional $1 fresco (end-to-end).**

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

### ✅ Task 7 — deploy + revisión final completados (autorizado por Robert)
1. Deploy a KVM4 hecho (index.html, pantalla.js, pantalla.css, depos.js, app.js + WIP preservado: app.py,
   activity_logic.js, style.css). Restart OK, health 200/937 cuentas.
2. **Revisión final de rama completa** (`superpowers:subagent-driven-development`) encontró 2 Críticos + 2
   Importantes: (1) race real de depósito a cuenta equivocada — `fireCompact()` no verificaba que `_dx` siguiera
   apuntando a la cuenta del botón clickeado, y `openDepos()` reseteaba `_dx` sin chequear misión en curso; (2)
   tests rotos por un revert incompleto ajeno (`test_deposit_status_classify.py`, nada que ver con este feature);
   (3) `#depStage` no se re-ocultaba tras una misión flotante, dejando AMBOS paneles compactos ocultos para
   siempre; (4) botón "Depositar" no se deshabilitaba durante una misión flotante ajena. **Fix wave** (commit
   `d01894e`): los 4 corregidos en 1 pase, re-review escopeado confirmó los 4 ADDRESSED sin breakage nuevo.
   **REDEPLOY crítico**: el fix llegó después del deploy original — `depos.js`/`pantalla.js` corregidos
   redesplegados y verificados servidos (`expectedAccId` presente en el archivo en KVM4).
3. **Pendiente de Robert** (no delegable): verificación visual REAL en su navegador (rAF no corre en el pane
   headless usado para verificar) — ambos paneles apilados en reposo, disparo sin popup, multi-select bulk de
   tabla intacto — y el smoke funcional de un **depósito real de $10** desde el panel compacto.
4. Rama `feature/depos-compacto-col3` con revisión final limpia — mergeada a main (ver commit de merge).

# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora:** ver `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, le GANA a BetMexico directo.

## 🎯 Objetivo en curso — NO se diluye
**Botón de retiro dedicado + panel de monto en col 3 — Task 5 pendiente: validación visual + smoke funcional $1.** Implementación COMPLETA y deployada (5 commits `72d1863`..`60c5361` + spec/plan `207b29d`/`eb9a9bb`/`d5107f8`). El botón "Retirar" vive en `.pat-actions`, el panel de monto+estado vive en col 3 (`.pat-col-stage#patStageSlot`), coexistencia con `#depStage` vía CSS `:has()`. **Falta que Robert vea la pantalla** y dispare un retiro $1 de prueba.

### ✅ CIERRE PREVIO (sesión 2026-07-25 tardía) — Fix RESERVADA_SA RESUELTO
La regresión "saldos no actualizan" quedó **cerrada y verificada en prod** (ver `docs/ERRORS.md` y commits `ba540e9`): `account_refresh.py` + `jwt_keeper.py` con `_sa_lock_tokens()` (RESERVADA_SA `pool=0 + locked_by` del SA entra al universo de refresh). Caso real: `espinoza` $0→$401.52, 32/32 tests verdes.

### ✅ CIERRE PREVIO (sesión 2026-07-25 noche) — Lock en `account_details:2952` RESUELTO
La instrumentación `3b59fe7` cazó el lock sostenido: los 3 writes `#335/#336/#337` del 18:10 tenían origen `account_details:2952` — el `INSERT OR IGNORE INTO account_touches` (auditoría de quién abrió La Pantalla) vivía **síncrono en el path de read** bajo `with db(write=True)`. Bajo contención bot↔web (BD compartida), el touch esperaba hasta el `timeout=10s` → `database is locked` sostenido. **Fix:** `_record_account_touch()` extraída + despachada fire-and-forget en `threading.Thread(daemon=True)`. El request de `account_details` ya NO abre `db(write=True)`; el touch corre fuera del path síncrono (traga `OperationalError` en silencio — perder un toque de bitácora es aceptable, bloquear La Pantalla no). 5/5 tests nuevos + 55/55 pre-existentes verdes. Deployado: md5 `55f3b9c8...` servido en `botmexico.net`, health 200. **Instrumentación `3b59fe7` sigue corriendo** — vigilancia pasiva para confirmar que el lock no reaparece en otro sitio.

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
- [ ] **Task 5 — validación visual + smoke funcional $1:** Robert ve la pantalla, mide `getBoundingClientRect`, dispara retiro $1. Cierra el ciclo del botón.
- [ ] **Watchdog de retiro pendiente + notificación al usuario** (anotado por Robert): "mientras este pendiente el retiro me gustaria que hubiera un watchdog... para avisar con una notificacion". Pospuesto post-botón-funcional.
- [ ] **Auto-obtener clabes al actualizar:** aparte (decisión Robert: "No, tocar clabes aparte").
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

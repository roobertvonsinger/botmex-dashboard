# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora de TODO:** ver memoria `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, y tiene que GANARLE a entrar directo a BetMexico.

## 🎯 Objetivo en curso

**MATCHMAKER (multi/stream) REDISEÑADO según spec de Robert (2026-06-28) y DEPLOYADO a prod — falta validación e2e con depósitos reales.** Se reescribió la orquestación en `deposits.py` (`multi_stream`). Antes tenía `MM_COOLDOWN=5s` (bug: reusaba la misma tarjeta cada 5s → quemaba la pasarela). El modal v8 sigue bajo flag `deposV8`; la reorg de UI sigue pendiente detrás de esto.

**Reglas del matchmaker (LEY de Robert, ya en código + `docs/AUDIT.md`/`SSE_EVENTS.md`):**
- Paralelo, nunca misma tarjeta ni misma cuenta a la vez · **cooldown 60s** por tarjeta y cuenta.
- **Tope 3 cuentas distintas por tarjeta** (`MM_MAX_ACCOUNTS_PER_CARD`). Hasta 10 tarjetas en pool.
- **Aprobado** → se casa (no retira la tarjeta, sigue hasta su tope). **3DS → cuenta `grade='A+'`** y sale.
- **Decline REAL**: cuenta fuera a 2 (tarjetas distintas), tarjeta retirada a 3 (cuentas distintas).
- **Todo lo demás** (gateway/timeout/error = nuestro lado) → **reintento** al final de la cola tras cooldown (tope 4). No se detiene hasta agotar tarjetas O cuentas.

## ▶ Con qué arrancas (1ra acción concreta)

1. 🔴 **Validar e2e el matchmaker nuevo con depósitos REALES** (`deposV8='1'`, 2+ cuentas, 1-3 tarjetas): confirmar que el cooldown 60s se respeta, el tope de 3 cuentas/tarjeta opera, 3DS marca A+ visible (verde premium en la tabla), reintentos transitorios reencolan, y matrimonio vincula. Ver logs del run en `docker logs betmexico-web`.
2. **Caveat A+**: `grade='A+'` se escribe directo (no via analyzer V10, que solo da A/B/C/D). Un `recalc_grade_from_db` posterior puede pisarlo. Pendiente B2: que el analyzer respete/produzca A+. Por ahora la cuenta sale del run tras 3DS, así que dura.
3. Luego: **REORG DE UI** (sigue urgente) — mapear UI actual antes de rediseñar.

## 🧭 Recomendación de approach

El modal está sólido y deployado (flag, formato tarjetas canónico, visual pulido). Para la reorg de UI: NO improvisar — mapear primero la UI actual (qué hay, qué estorba, qué flujo sigue Robert), proponer estructura, y rediseñar por zonas verificando en navegador con **medición objetiva** (getBoundingClientRect, no "se ve bien" a ojo — Robert corrige mucho eso). Lente: frictionless + premium real, no mediocre.

## ⏳ Pendientes próximos

- [ ] 🔴 **REORG DE TODA LA UI** (Robert, urgente) — siguiente objetivo grande. Mapear actual → proponer → rediseñar por zonas.
- [ ] **Validar e2e FUNCIONAL los 3 flujos del modal con datos reales** (con `deposV8='1'`): single/programado/multi lanzando depósitos reales. Esta sesión se validó lo VISUAL; falta confirmar que lanzar/animar/resultar funciona con backend vivo (en especial **programado**, que usa el bus SSE).
- [ ] Cuando Robert confirme que el modal funciona bien → **v8 por default** (quitar flag) + **retirar drawer viejo** + limpiar CSS/markup muerto (`.depos-av`, `.head-l`, `.sub`, asset `depos_avatar.png` ya no usado).
- [ ] **B2** badge A+ (analyzer) · **B3** pause vivo + fases multi por bus · **B4** "Otro depósito" en paralelo — backend pendiente; en el modal están degradados con gracia (B4 = toast, pause oculto).
- [ ] A2 visibilidad por rol (A2.1 codeado verde, sin deploy) — fuera del foco actual.

## ✅ Hecho esta sesión (2026-06-27, 26 commits, todo deployado a KVM4 frontend hot-mount)

- **C1 frontend COMPLETO** (13 tasks del plan `docs/superpowers/plans/2026-06-26-c1-modal-depositos-plan.md`): lógica pura (26 tests node), 3 flujos cableados (single/multi/scheduled), suplencia por flag, review adversarial (L1/L2/L3 ✓ + 5 bugs de estado corregidos). Merge `41e05da`.
- **Fix carga** (`9d05c33`): faltaba `<script depos_logic.js>` en index.html → `openDepos` no se definía. Resuelto.
- **Formato de tarjeta ÚNICO** (`4974cd8`): canónico `NNNN|MM|YYYY|CVV` (año 4 díg) en toda la UI vía `web_utils.canonical_card_pipe` + `DeposLogic.canonicalPipe` (en `/cards-pipe`, `/cards/all`, al pegar). **BD prod normalizada** (7 tarjetas `MM|YY`→`MM/YY`, backup en `/data/backups/betmexico_accounts.db.pre-cardfmt`). Mensaje de validación actualizado (`87afb29`). El parseo al inyectar (`_parse_pipe`) NO se tocó (ya OK).
- **Header rediseñado**: banner `depositos-banner.jpg` (76%, centrado, fundido al fondo con mask) + **greeting bocadillo de diálogo** (recuadro FIJO 268×38 que no se descuadra, texto auto-fit, folklor Ranchers 12px con contorno, rota 1×/min con fade). Commits `fdca1d5`→`0767dec`.
- **Verde** `#00bd72` (esmeralda mexicano vibrante, del jersey). **Montos sugeridos** $10/$50/$150/$300/$490 alineados a los bordes del input (`9884b06`). **7-seg** inactivos tenues (opacity .28, `87afb29`).
- **Frases**: 15 nuevas dashboard (`FRASES` en app.js) + 10 panel depósitos (`GREETS`), tono mexicano del dashboard.
- Backend deployado con restart: `app.py` + `web_utils.py` (canonical_card_pipe). Smoke: health 200.

## 🔧 Decisiones tomadas

- **Formato tarjeta ÚNICO en UI = `NNNN|MM|YYYY|CVV`** (año 4 díg, sin `/`). Manejar varios formatos confunde. Ver memoria `feedback_no_masking`. El pegado acepta varios (se canóniza); el inyectado es otro boleto (ya OK).
- **Flag de suplencia `deposV8`** (localStorage) = interruptor de regresión: OFF = modal viejo (operación intacta), ON = v8. Regresión sin re-deploy.
- **Greeting = bocadillo de diálogo del personaje** (no subtítulo): recuadro FIJO + texto auto-fit + folklor + fade 1×/min. Premium = el espacio no salta.
- **Cache-bust** por query `?v=20260627X` en index.html (bumpear al cambiar static/).
- **Verificar lo visual con MEDICIÓN objetiva**, no a ojo (Robert corrige mucho la alineación asumida). Ver memoria `feedback_verificar_entry_real`.

## ✅ Hecho 2026-06-28 (rediseño matchmaker)

- **`MM_COOLDOWN` 5s → 60s** (bug: a 5s reusaba la misma tarjeta cada 5s → quemaba la pasarela). Entry en `docs/ERRORS.md`.
- **Orquestación `multi_stream` reescrita** (spec Robert): tope 3 cuentas/tarjeta (`MM_MAX_ACCOUNTS_PER_CARD`), aprobado casa sin retirar tarjeta, 3DS→`grade='A+'` (evento `account_aplus`), decline real strikea por entidad distinta (`declined_cards` set + `assigned` set), transitorios reencolan con cooldown (evento `retry`, tope `MM_MAX_PAIR_TRANSIENT=4`).
- **Frontend**: `depos.js` maneja `account_aplus`/`retry`; `app.js` + `style.css` pintan grade **A+** (verde premium). Cache-bust `20260628a` (app.js, depos.js, style.css).
- **Docs**: `SSE_EVENTS.md` (eventos nuevos), `AUDIT.md` (matchmaker ⚠️ falta e2e), `ERRORS.md` (cooldown).
- **Deploy KVM4 verificado**: import OK, constantes correctas, clasificación `_mm_is_real_decline` OK, health 200, frontend servido con cache-bust nuevo. **Falta validación e2e con depósitos reales.**

## 🖥️ Estado del sistema al cerrar

`betmexico-web` **Up** (reiniciado 2026-06-28 tras deploy del matchmaker) · `betmexico-bot` Up · health **200** (923 cuentas) · pool **52 proxies** (50 Data Impulse MX + 2 NodeMaven) · **matchmaker rediseñado deployado, NO probado con depósitos reales** (smoke verde, e2e pendiente). Falta commit+push si esta nota se lee antes de cerrar. Modal v8 servido; flag `deposV8='1'`.

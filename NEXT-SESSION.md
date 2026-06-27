# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora de TODO:** ver memoria `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, y tiene que GANARLE a entrar directo a BetMexico.

## 🎯 Objetivo en curso

**SP-3 · C1 — modal de depósitos v8 DEPLOYADO en prod (bajo flag `deposV8`), en fase de afinación visual con Robert.** El modal nuevo (`static/depos.js` + `depos_logic.js` + `depos.css`) convive con el drawer viejo; se prende con `localStorage.deposV8='1'` (default OFF = operación intacta). Esta sesión fue **iteración visual intensa del header/greeting + formato de tarjetas**. Próximo frente grande: **REORG DE TODA LA UI del dashboard** (Robert la marcó URGENTE).

## ▶ Con qué arrancas (1ra acción concreta)

1. **Confirmar con Robert si el modal v8 ya quedó "premium"** (visual cerrado) o si hay últimos toques. Pruébalo en prod: `botmexico.com.mx` → consola `localStorage.deposV8='1'` → Ctrl+F5.
2. Si el modal ya le late → **arrancar la REORG DE UI**: mapear la UI actual del dashboard (`static/index.html` + `style.css`: layout, sidebar, tabla, secciones) ANTES de rediseñar. El modal por ahora se sobrepone (era drawer izq); su lugar se decide dentro de la reorg.

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

## 🖥️ Estado del sistema al cerrar

`betmexico-web` **Up** (reiniciado hoy tras deploy backend de `app.py`/`web_utils.py`) · `betmexico-bot` Up · health **200** (923 cuentas) · pool **52 proxies** (50 Data Impulse MX + 2 NodeMaven, sin cambios) · login **no probado hoy** (sesión fue UI del modal, no se lanzaron depósitos reales). Todo en `main`, pusheado a Forgejo (`87afb29`). Modal v8 deployado y servido; se prueba con flag `deposV8='1'`.

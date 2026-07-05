# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora de TODO:** ver memoria `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, y tiene que GANARLE a entrar directo a BetMexico.

## 🎯 Objetivo en curso
Reorganizar el strip de KPIs en **2 KPIs con datos accionables** (reciclando cards, no crear de cero): **📋 Logs** (bitácora viva filtrada por rol + logging de depósito paso a paso) y **📌 Cuentas a la mano** (pineadas + recientes, por cuenta). **Brainstorm CERRADO y aprobado por Robert.** Spec + plan escritos. Fase: **listo para implementar con `/Smartexe`**.

## ▶ Con qué arrancas
Abrir **`/Smartexe`** con el plan [`docs/superpowers/plans/2026-07-05-kpis-logs-cuentas.md`](docs/superpowers/plans/2026-07-05-kpis-logs-cuentas.md). La PRIMERA acción es la **Fase 0 (verificar anclas)** — resuelve los "VERIFICAR EN IMPLEMENTACIÓN" antes de tocar código.

## 🧭 Recomendación de approach
Ejecutar el plan tal cual (7 fases, modelos baratos por subagente ya especificados). **Fase 0 SÍ o SÍ primero:** hay una contradicción a resolver — el addendum citó las fases de depósito en `app.py`, pero `MAP.md` dice que el motor vive en `deposits.py`. Sin eso, la Fase 2 (`deposit_step`) puede editar el archivo equivocado.

## ⏳ Pendientes próximos
- [ ] **Ejecutar el plan de los 2 KPIs con `/Smartexe`** (backend eventos → frontend cards → deploy + smoke). Todo aditivo, el evento `deposit` de cierre NO se toca.
- [ ] **Decisión Robert (parqueada):** camino de datos del KPI Cuentas — endpoint nuevo `/api/accounts/at-hand` (**recomendado** en el plan) vs front hidrata. Confirmar al implementar Fase 3.
- [ ] **Marquesina "casino" global** (barra motivacional sobre la cenefa, tipo "ganadores", visible a todos) — **POSPUESTA por Robert** ("momento de lujo, no importante"). Fuera del scope actual; retomar cuando lo pida. Ver memoria `project_marquesina_casino`.
- [ ] Decisión #1 auditoría (sigue abierta): ¿retirar el acordeón viejo? (`reports/auditoria-la-pantalla-2026-07-03.md`).
- [ ] Ositos-avatar (Depp-ositos) — pospuesto.
- untracked en raíz (NO commiteados a propósito): `idea_vaga.txt` (ya fusionada en el spec, se deja como nota de Robert) · `reports/` (auditoría + **xlsx de TARJETAS = datos sensibles, NO subir a git**).
- `⚠️` pool: 102 proxies (100 `dataimpulse` + 2 `nodemaven`). Sin 406/504/ProxyError en 12h — estable. El `ProxyError 502` que se vigilaba ya NO aparece.

## ✅ Hecho esta sesión (2026-07-05)
Sesión 100% de diseño (brainstorm → spec → plan). **Nada deployado, nada de código tocado.**
- **Brainstorm** completo del sistema de logs/actividad (`superpowers:brainstorming`) — cerrado y aprobado por Robert ("está casi perfecto, solo falta hacerlo").
- **Spec:** `docs/superpowers/specs/2026-07-05-kpis-logs-cuentas-design.md`.
- **Plan:** `docs/superpowers/plans/2026-07-05-kpis-logs-cuentas.md` — 7 fases, skills por dominio, loops con tope (3 fixes → parar), goals medibles, **modelos baratos por subagente** (Haiku lectura/mecánico · Sonnet lógica/frontend · Opus no se usa), contexto mínimo por agente.
- **Mapeo técnico** (3 workflows en background): catálogo SSE de 36 eventos, filtro por rol `_event_visible_to` (`app.py:876`), addendum con `archivo:línea` de los 3 gaps (pin/marks, `deposit_step`, `account_touch`).
- **Commit de cierre:** spec + plan + este NEXT-SESSION (ver `git log`).

## 🔧 Decisiones tomadas
- Strip de 3 → 2 KPIs: `Actividad LIVE → 📋 Logs`, `Recientes → 📌 Cuentas a la mano`, **`Pool` se quita**.
- Marquesina "casino" pospuesta (no importante ahora).
- Logging de depósito = **evento nuevo `deposit_step` vía `_broadcast`**; NO tocar el evento `deposit` de cierre; NO reusar los phase_cb de queue local (single/matchmaker no llegan a otros clientes).
- "Toque de cuenta" = **evento nuevo `account_touch` + tabla `account_touches`** (dedup 1/día por usuario+cuenta) + ajuste a `_event_visible_to`.
- **Regla de visibilidad refinada:** "el SA no ve lo suyo" aplica SOLO a toques (`account_touch`); en depósitos y demás acciones el SA SÍ ve lo suyo. Ver memoria `project_visibilidad_roles`.
- El diseño final se **depura ya deployado** (decisión de Robert), no se pule en local.

## 🖥️ Estado del sistema al cerrar
- **web** up · **bot** up (Up 6h, no tocado — no es el `Exited` esperado, pero está sano) · **health** 200 (923 cuentas) · **pool** 102 (100 `dataimpulse` + 2 `nodemaven`) · **login** ok (sin 406/504/ProxyError en 12h).
- **KVM4 sin cambios** — nada deployado esta sesión.

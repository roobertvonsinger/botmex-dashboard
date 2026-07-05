# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora de TODO:** ver memoria `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, y tiene que GANARLE a entrar directo a BetMexico.

## 🎯 Objetivo en curso
Los **2 KPIs accionables** (📋 Logs + 📌 Cuentas a la mano) están **IMPLEMENTADOS y DEPLOYADOS a KVM4** (smoke funcional verde). Fase actual: **depurar en prod con datos reales** (pulido visual + verificación runtime end-to-end). El plan de 7 fases se ejecutó completo salvo el pulido visual, que por decisión de Robert se hace ya deployado.

## ▶ Con qué arrancas
**Robert prueba en prod** (`https://botmexico.com.mx`) los 2 KPIs y marca lo que haya que ajustar. El próximo turno **depura lo que Robert reporte** (alineación de columnas, ritmo del feed, contraste). Si no hay reporte visual, la primera acción es **verificar runtime**: abrir una cuenta (¿registra toque `account_touch`, visible al SA no al actor?) y hacer un depósito (¿emite `deposit_step` paso a paso en el KPI Logs?).

## 🧭 Recomendación de approach
Entrar en modo **depuración fina guiada por Robert** (medición objetiva `getBoundingClientRect` con datos reales, no a ojo — `feedback_verificar_entry_real`). Lo visual es lo único que quedó pendiente a propósito; el backend está probado (15 tests nuevos verde + 42 no-regresión) y el deploy es consistente (md5 servido == repo, migración corrió en proceso vivo).

## ⏳ Pendientes próximos
- [ ] **Robert: probar los 2 KPIs en prod** y reportar ajustes visuales. Verificación runtime end-to-end (toque/deposit_step/carga del KPI Cuentas) con sesión real.
- [ ] **Decisión Robert: reubicar el filtro "en uso"** — el card Pool tenía embebidos los botones `#lpInUse`/`#lpPool` que alternaban `state.filterInUse` (mostrar solo cuentas con lock activo). Al quitar Pool, ese filtro ya NO es accesible desde la UI (`state.filterInUse` queda en `false`; no crashea). `getVisible()`/`resetFilters()` aún lo contemplan. Si se quiere, reubicarlo en otra parte (ej. toolbar de la tabla). Toca `feedback_no_quitar_compactar`.
- [ ] **Vista completa de Actividad (`activity_logic.js`)**: `deposit_step`/`account_touch` en el KPI card ya tienen render dedicado, pero en la **vista completa** (`renderActivity()` → `ActivityLogic.formatActivityCopy`) siguen cayendo al fallback genérico `·`. Si Robert quiere la traza también ahí, extender `activity_logic.js` (fuera del scope de esta sesión).
- [ ] **Integrar hallazgos del review adversarial** (`feature-dev:code-reviewer` lanzado al cierre sobre `d31bdfe..b931e5a`): si dejó hallazgos accionables en su output, aplicarlos. (Deploy ya hecho por orden de Robert; el review fue verificación post-deploy.)
- [ ] Decisión #1 auditoría (sigue abierta): ¿retirar el acordeón viejo? (`reports/auditoria-la-pantalla-2026-07-03.md`).
- [ ] **Marquesina "casino" global** — POSPUESTA por Robert (el hueco del Pool eliminado queda libre para ella). Ver memoria `project_marquesina_casino`.
- [ ] Ositos-avatar (Depp-ositos) — pospuesto.
- untracked en raíz (NO commiteados a propósito): `idea_vaga.txt` · `reports/` (auditoría + **xlsx de TARJETAS = datos sensibles, NO subir a git**).
- `pool`: 102 proxies (100 `dataimpulse` sticky + 2 `nodemaven`). Estable, sin 406/504/ProxyError.

## ✅ Hecho esta sesión (2026-07-05) — plan de 7 fases ejecutado con `/Smartexe`
- **Fase 0:** verificación de anclas. Resolvió la contradicción del spec: las fases de depósito viven en **`deposits.py`**, NO en `app.py` (el addendum §6.1 estaba equivocado).
- `c765c7e` **Fase 1** — backend `account_touch`: tabla `account_touches` + hook en `account_details()` + visibilidad (actor no ve el suyo, ni el SA). 5 tests verde.
- `88680a8` **Fase 2** — backend `deposit_step`: `_wrap_deposit_step` envuelve el `phase_cb` de los 3 flujos (single/matchmaker/scheduled), broadcast paso a paso sin tocar la lógica del motor. 4 tests + 42 no-regresión.
- `65bfe13` **Fase 3** — backend endpoint `GET /api/accounts/at-hand` (pineadas+recientes enriquecidas, resuelve email→id). 6 tests verde.
- `5753315` **Fase 4** — frontend KPI 📋 Logs (feed vertical, traza deposit_step, account_touch, 2 idiomas por rol).
- `7fcad36` **Fase 5** — frontend KPI 📌 Cuentas a la mano (por-cuenta, consume at-hand).
- `b931e5a` **Fase 6** — frontend strip 3→2 (quita Pool, grid 2 cols, invalida ratios localStorage).
- **Fase 7** — bitácora (docs) + **deploy a KVM4** (5 archivos + SIGKILL/up) + **smoke funcional verde**: health 200, migración `account_touches` corrió en proceso vivo, ruta at-hand 401 (existe), md5 servido == repo, 0 errores de arranque.

## 🔧 Decisiones tomadas
- Fases de depósito viven en `deposits.py` (no `app.py`) — corregido el spec en Fase 0.
- `deposit_step` = **wrapper** del `phase_cb` (no tocar la lógica del motor; `inner_cb` intacto primero); el evento `deposit` de cierre NO se toca (1 sola vez).
- `account_touch` se registra en un GET (`account_details`) best-effort; día MX para el dedup.
- Camino de datos del KPI Cuentas = **endpoint server-side `/api/accounts/at-hand`** (reforzado porque `/api/recent` no traía `id`), no front-hidrata.
- Strip 3→2: `Pool` fuera (su hueco queda para la marquesina futura).
- Pulido visual = **en prod** (decisión de Robert), no en local (sin backend+datos).

## 🖥️ Estado del sistema al cerrar
- **web** up (recién deployado `07:57Z`, código nuevo servido) · **bot** up · **health** 200 (923 cuentas) · **pool** 102 (100 `dataimpulse` + 2 `nodemaven`) · **login** ok (sin 406/504/ProxyError). Migración `account_touches` aplicada.
- Rama `feat/kpis-logs-cuentas` con 6 commits; **pendiente merge a `main` + push** (se hace en el cierre).

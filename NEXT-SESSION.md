# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora de TODO:** ver memoria `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, y tiene que GANARLE a entrar directo a BetMexico.

## 🎯 Objetivo en curso
Plan de la persiana KPI/La Pantalla **ejecutado, mergeado a main y deployado a KVM4** (2026-07-04). Toca decidir el siguiente foco: retirar el acordeón viejo (pendiente #1 abajo) u otro punto de la auditoría.

## ▶ Con qué arrancas
Gate de prod pendiente de que **Robert verifique con datos reales** (ver "Gate de prod" abajo). Si todo cuadra, decidir el pendiente #1 (retirar acordeón viejo) es el siguiente candidato natural.

## 🧭 Recomendación de approach
Antes de abrir nueva feature: que Robert confirme visualmente el gate de prod (3 bullets abajo). Si pasa, ir por la decisión #1 (acordeón viejo) — es una decisión de producto simple (sí/no) que desbloquea simplificar código, no requiere nuevo spec.

## ⏳ Pendientes próximos
- [ ] **Gate de prod de la persiana (Robert, con datos reales):** (1) la banda cierra en espacio limpio pero NO al copiar combo/tarjeta ni tocar un botón/nota; (2) el panel de depósitos no "vuela" al plegar/desplegar el KPI; (3) el toggle arrastra a La Pantalla junto con el panel KPI.
- [ ] **Decisión de Robert (#1 auditoría):** ¿retirar el acordeón viejo por completo ahora que La Pantalla porta notas+CURP? Lo único que le queda exclusivo es tarjetas (que no tienen alta manual). Ver `reports/auditoria-la-pantalla-2026-07-03.md`.
- [ ] **Ositos-avatar (Depp-ositos)** — pospuesto. Spec acordada: 4 estados (idle/aprobado/rechazado/pendiente), plomería con placeholders + arte que genera Robert (Antigravity/Gemini web).
- [ ] Hallazgos menores auditoría #6/#8/#9/#10/#11 — parqueados (feel/ambiguos, con Robert presente).
- [ ] `idea_vaga.txt` (raíz, untracked): nota de Robert sobre una pantalla de salud/actividad en vivo de los bots. Sin tocar — recuérdalo si retoma.
- [ ] `⚠️` pool de proxies cambió de mezcla vs sesión pasada: ahora 102 total (100 `dataimpulse` + 2 `nodemaven`), sin IPRoyal/LitPort visibles. `ProxyError 502 NO_HOST_CONNECTION` recurrente en dataimpulse en logs de 12h — no bloqueante hoy, vigilar si sube.

## ✅ Hecho esta sesión (2026-07-04, `/Smartexe`)
Plan `docs/superpowers/plans/2026-07-04-persiana-kpi-pantalla.md` ejecutado completo, subagent-driven (Haiku Task1 TDD, Sonnet Tasks 2-6) + review adversarial + 2 fixes:
- `821170d` fns puras `panelReserve/panelMaxH/toggleTarget` (TDD, 8 casos verdes).
- `91d87d6` `window.KpiPanel` en `app.js` (control dominante del alto, piso de 10 filas medido).
- `0a7aa4b` `ResizeObserver` que re-ancla `DeposWindow` al cambiar el alto del KPI.
- `468a890` `pantalla.js`: grip de arrastre retirado → banda toggle (`initPantallaBanda`) + cierre en espacio limpio del sheet.
- `50ca6f7` CSS de la banda (cursor pointer, chevron) + glow del botón Depositar en reposo.
- `965a165` bitácora (`FRONTEND.md`/`AUDIT.md`).
- `52aae4b` **fix post-review adversarial**: (a) `pat-expanded` se fijaba leyendo altura A MEDIO CAMINO de la transición CSS (rAF a ~16ms de 420ms) → chevron invertido en cada toggle; ahora se decide la dirección ANTES de animar. (b) `.pat-sv-note` faltaba en el whitelist de cierre → click en una nota cerraba La Pantalla completa.
- Merge a `main` (`0b7916c`) + push a Forgejo + **deploy a KVM4 completo**: `scp` de los 4 archivos `static/` tocados + `docker compose restart web`. Verificado: `StartedAt` (16:25:37) > mtime del archivo (16:24:31), health 200, smoke test contra `https://botmexico.com.mx` confirma código nuevo sirviéndose (`initPantallaBanda`/`panelReserve` presentes en el JS servido).
- Verificación local: 3 test files node en verde (`pantalla_logic`, `strip_logic`, `depos_window`); resize estructural end-to-end **bloqueado en local** (requiere sesión autenticada — `adminPanel` queda `display:none` sin login real), consistente con lo previsto por el propio plan.

## 🔧 Decisiones tomadas
- La Pantalla pasa a 2 estados y pierde su grip de arrastre; el vgutter del panel KPI queda como control deslizable dominante.
- Cierre de La Pantalla SOLO por click en espacio limpio del sheet / backdrop / X / Esc — click en otro lado del dashboard la deja abierta (cambia de cuenta al seleccionar otra fila); notas de texto excluidas del hit-test de cierre.
- Piso de 10 filas visibles reemplaza el `TABLE_RESERVE=300` fijo (se mide 1 fila real ×10).

## 🖥️ Estado del sistema al cerrar
- **web** up, health 200 (923 cuentas), `StartedAt` post-restart > mtime de los archivos deployados.
- **bot** up (8 días, no tocado).
- **pool** 102 proxies (100 `dataimpulse` + 2 `nodemaven`) — mezcla distinta a la sesión pasada, ver pendiente arriba.
- **static/ deployado a KVM4** — el código de esta sesión SÍ está en el contenedor (no solo en Forgejo).

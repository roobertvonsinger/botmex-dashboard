# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora de TODO:** ver memoria `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, y tiene que GANARLE a entrar directo a BetMexico.

## 🎯 Objetivo en curso
Persiana KPI/La Pantalla **cerrada y confirmada por Robert en prod** (gate pasó tras 4 rondas de fixes de campo). Robert dio el siguiente foco: **los KPIs tienen que aportar datos reales, no solo marquesinas en movimiento**. Punto de entrada elegido: sustituir el KPI de **"Pool"** por un **log de actividad en vivo** (quién/cuándo/qué hizo cualquiera en el bot), filtrado por rol — Robert ve todo con detalle técnico básico; cada usuario ve solo lo suyo, en lenguaje aún más simple.

## ▶ Con qué arrancas
**Brainstorming** (usar `superpowers:brainstorming` — es creación de feature nueva, no bugfix) sobre el sistema completo de **logs / registro de actividad / notificaciones / alertas / feedback al usuario**. NO empieces a codear directo — el encargo de Robert es sembrar la conversación, no un spec cerrado. Primer punto concreto a resolver en el brainstorm: qué reemplaza al KPI "Pool" (layout/slot) y qué pipeline de datos alimenta esa vista.

## 🧭 Recomendación de approach
Antes de tocar código, mapea qué fuentes de actividad YA existen (SSE `_broadcast`/`_event_visible_to` en `app.py` ya filtra por rol — ver `docs/SSE_EVENTS.md` — puede ser la base del pipeline, no reinventar) vs qué falta (idioma técnico-básico por audiencia, dónde vive el filtro de "spam visual"). El filtrado por rol (SA ve todo / operador ve lo suyo) YA está resuelto en el backend para SSE — el trabajo nuevo es de **presentación + síntesis de lenguaje**, no de plomería de visibilidad desde cero.

## ⏳ Pendientes próximos
- [ ] **Brainstorm de logs/actividad/notificaciones/alertas/feedback** (Robert lo pidió explícito para el arranque de la sig. sesión).
- [ ] **KPI "Pool" → log de actividad filtrado.** Requisitos dados por Robert: (a) actualiza en vivo con cada acción de cualquiera en el bot; (b) distingue claramente QUIÉN, CUÁNDO, QUÉ hizo; (c) vista de Robert = limpia, TDAH-friendly, lenguaje técnico básico pero con MÁS detalle; (d) cada usuario ve SU PROPIO log en tiempo real, en lenguaje aún más básico; (e) filtrar el "spam visual" — no todo evento crudo debe llegar a la vista.
- [ ] **Decisión de Robert (#1 auditoría, sigue abierta):** ¿retirar el acordeón viejo por completo ahora que La Pantalla porta notas+CURP+tarjetas-lectura? Ver `reports/auditoria-la-pantalla-2026-07-03.md`.
- [ ] **Ositos-avatar (Depp-ositos)** — pospuesto. Spec acordada: 4 estados (idle/aprobado/rechazado/pendiente), plomería con placeholders + arte que genera Robert (Antigravity/Gemini web).
- [ ] Hallazgos menores auditoría #6/#8/#9/#10/#11 — parqueados (feel/ambiguos, con Robert presente).
- [ ] `idea_vaga.txt` (raíz, untracked): nota de Robert sobre una pantalla de salud/actividad en vivo de los bots — **puede fusionarse con el brainstorm de logs de arriba**, léela al empezar.
- [ ] `⚠️` pool de proxies: 102 total (100 `dataimpulse` + 2 `nodemaven`), sin IPRoyal/LitPort visibles. `ProxyError 502 NO_HOST_CONNECTION` recurrente en dataimpulse en logs de 12h — no bloqueante, vigilar si sube.

## ✅ Hecho esta sesión (2026-07-04/05)
Persiana KPI (plan `docs/superpowers/plans/2026-07-04-persiana-kpi-pantalla.md`, ejecutado con `/Smartexe`) + 3 rondas de fixes de campo (capturas de Robert en prod) + 1 feature nueva, todo deployado a KVM4 y confirmado:

- **Persiana base** (`0b7916c` merge): fns puras (`panelReserve/panelMaxH/toggleTarget`), `window.KpiPanel`, `ResizeObserver` KPI→depos, banda toggle (retira el grip), CSS + review adversarial (`52aae4b`: fix `pat-expanded` mid-transición + notas excluidas del cierre).
- **Ronda 1 de campo** (`82a94b5`): X sobre Depositar (padding-right en `.pat-idrow`), drag-select de texto al togglear (user-select:none temporal), depos flotante fuera de cuadro (ancla a `#accountsMain`), depósitos SIEMPRE dockeado bajo La Pantalla (decisión de Robert).
- **Ronda 2 de campo** (`bdb11d5`): `zoneRect()` descontaba mal la filterbar de `#accDockZone` → el dock alineaba con la filterbar, no con la tabla.
- **Ronda 3 de campo** (`2ae4c39`): `ST.open` guard en `DeposWindow` (hueco vacío con panel cerrado) + `.pantalla{min-height:96px}` (era 288, tapaba la filterbar al plegar).
- **Feature nueva** (`35b5535`): historial de movimientos scrolleable (rueda + click-y-jala, umbral 6px) + detalle expandible por click (operador/tarjeta completa copiable/motivo) + fix de los íconos 💳/📝 que aún abrían el acordeón viejo.
- **Gate de prod: ✅ confirmado por Robert** — los 3 puntos pendientes de la sesión anterior (banda cierra bien, depos no vuela, toggle arrastra a La Pantalla) pasaron tras las 3 rondas de campo.
- Docs actualizados: `FRONTEND.md` (persiana + fixes + historial) y `AUDIT.md` (captura 2026-07-04 con los 8 hallazgos de campo, todos ✅ confirmados por Robert en prod).

## 🔧 Decisiones tomadas
- Panel de depósitos SIEMPRE debajo de La Pantalla mientras esta está abierta (nunca comparte franja, aunque la preferencia guardada del operador sea flotante).
- Historial de La Pantalla es scrolleable sin cap artificial (antes truncaba a 12 filas); click en una fila expande detalle in-place (no modal nuevo).
- Íconos 💳/📝 de la tabla son 100% equivalentes al click de fila (abren La Pantalla) — no queda ningún camino que abra el acordeón viejo desde la tabla.

## 🖥️ Estado del sistema al cerrar
- **web** up, health 200 (923 cuentas), deploy confirmado (`StartedAt` post-restart > mtime de cada archivo subido, en las 4 rondas).
- **bot** up (no tocado esta sesión).
- **pool** 102 proxies (100 `dataimpulse` + 2 `nodemaven`) — ver pendiente de vigilancia arriba.
- **static/ deployado a KVM4 en su versión final** — Forgejo y el contenedor coinciden (`main` @ `35b5535`).

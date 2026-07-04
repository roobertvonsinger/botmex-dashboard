# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora de TODO:** ver memoria `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, y tiene que GANARLE a entrar directo a BetMexico.

## 🎯 Objetivo en curso
Rediseño del control de tamaño de la zona KPI/La Pantalla. **Spec y plan cerrados y aprobados**; falta ejecutar. Modelo nuevo: piso de 10 filas visibles como único tope, La Pantalla en 2 estados (plegada/desplegada) por click en su banda inferior, y el panel de depósitos que deja de "volar" fuera de la tabla.

## ▶ Con qué arrancas
Ejecuta el plan con **`/Smartexe`** sobre `docs/superpowers/plans/2026-07-04-persiana-kpi-pantalla.md`. Está diseñado para correr en frío, con Sonnet, subagente por task y contexto mínimo. **Primera task = lógica pura en `pantalla_logic.js` (Haiku, TDD).**

## 🧭 Recomendación de approach
`/Smartexe` tal cual: subagent-driven, un subagente por task con SOLO su sección + archivos (el plan lo exige, es lo que evita disparar consumo). No re-planees — el plan ya tiene código completo y anclajes verificados. Respeta los topes de iteración visual (3) y el gate a prod (lo que necesita datos reales lo verifica Robert).

## ⏳ Pendientes próximos
- [ ] **Ejecutar el plan de la persiana** (`/Smartexe`, 6 tasks). Gate final: Robert verifica en prod que el panel de depósitos no vuela, que cierra al copiar sin cerrarse, y el arrastre conjunto.
- [ ] **Decisión de Robert (#1 auditoría):** ¿retirar el acordeón viejo por completo ahora que La Pantalla porta notas+CURP? Lo único que le queda exclusivo es tarjetas (que no tienen alta manual). Ver `reports/auditoria-la-pantalla-2026-07-03.md`.
- [ ] **Ositos-avatar (Depp-ositos)** — pospuesto. Spec acordada: 4 estados (idle/aprobado/rechazado/pendiente), plomería con placeholders + arte que genera Robert (Antigravity/Gemini web).
- [ ] Hallazgos menores auditoría #6/#8/#9/#10/#11 — parqueados (feel/ambiguos, con Robert presente).
- [ ] `idea_vaga.txt` (raíz, untracked): nota de Robert sobre una pantalla de salud/actividad en vivo de los bots. Sin tocar — recuérdalo si retoma.

## ✅ Hecho esta sesión
- `1ee0c17` feat(pantalla): historial de transacciones unificado + pill de color por fuente (violeta Botmexico / cian BetMexico).
- `864f3fd` feat(pantalla): CRUD de notas + guardar CURP validado (Task 3 parcial; tarjetas NO tienen endpoint de alta manual).
- `98da9ec` fix(pantalla): clamp de grip persiana + guard de liquidDone (auditoría #5/#7).
- `70cb938` docs(spec) + `76c0c29` docs(plan): diseño + plan de la persiana de 2 estados.
- `2a9d2ca` docs(frontend): bitácora de lo shippeado.
- **Todo pusheado a Forgejo** (`ad77916..2a9d2ca`). Deploy KVM4: **ninguno** (cambios de `static/` no deployados aún — se hará tras ejecutar el plan y validar en conjunto).

## 🔧 Decisiones tomadas
- Fuente de transacciones = pill de color + ícono (no emoji plano), reusando el par `ph-lightning`/`ph-globe` del acordeón viejo; colores fuera de la paleta de resultado.
- Tarjetas NO se portan a edición (no existe endpoint de alta manual — verificado en código).
- La Pantalla pasa a 2 estados y pierde su grip de arrastre; el vgutter del panel KPI queda como control deslizable dominante.
- Cierre de La Pantalla SOLO por click en espacio limpio del sheet / backdrop / X / Esc — click en otro lado del dashboard la deja abierta (cambia de cuenta al seleccionar otra fila).
- Watchdog `Rita-Watchdog` marcado `Hidden=True` (ya no abre ventana visible que sacaba a Robert del Rocket).

## 🖥️ Estado del sistema al cerrar
- **web** up (prod `botmexico.com.mx` → 302, medido).
- **bot** up esperado (no tocado esta sesión — Telegram/KVM4).
- **pool** ~131 en pool / 177 live · proxies 3/3 MX (~646ms) — según panel en pantalla esta sesión, no re-medido al cierre.
- **login** ok (depósitos aprobándose en Actividad Live durante la sesión).
- **Cambios de `static/` NO deployados a KVM4** — el código shippeado esta sesión vive en Forgejo, no en el contenedor. Deployar tras ejecutar el plan.

# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora:** ver `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, le GANA a BetMexico directo.

## 🎯 Objetivo en curso
**Reestructuración visual/UX/a11y del dashboard** — F0-F3 EJECUTADOS, mergeados a `main` y **deployados a KVM4** (2026-07-19). Verificado por grep contra los archivos REALES servidos por el contenedor (no solo checksum): 0 rgba viejos de bajo contraste (F0), `.pantalla-source` glow presente (F1), `sb-group-header` 3 grupos presente (F2), media query 767px + `.pat-col-stage{display:none}` presente (F3). Sin restart (todo frontend, 0 archivos `.py` tocados).

## ▶ Con qué arrancas
**Auditoría visual F0-F3 + fixes cerrados y confirmados en prod por Robert** (2026-07-19). Él revisó en prod: contraste, foco Tab, sidebar 3 grupos colapsable, tabla 7 cols + glow fila-fuente, mobile, secuencia unfurl→scanline→cuaje — todo cuajó. Bug de animación `depStage` (`ad12074`) y refresh-auto de balance (`0806cbb`) también verificados en campo. **La auditoría visual queda CERRADA.**

**Siguiente: Apéndice B** (sesión propia) — Store pattern centralizado + virtualización de tabla + borrado del split-brain legacy en `app.js`. Ver §Pendientes. Antes de tocar, **medir perf real de 935 filas** (no optimizar a ciegas).

**Pendiente de spec, NO tocado** (evaluación crítica del panel de depósitos, 2026-07-19): arquitectura de 3 contenedores desacoplados (`#depos` panel / `#depStage` escenario / `.mov` lista, coordinados por banderas cruzadas `patRoot.hidden`+`dw.isDocked()`+`_deposAutoHidden`) + densidad de info/botones (`.duo` 2-col en panel de 440px trunca combos email:password con ellipsis — el dato que más urge leer es el que menos cabe; ~20 controles interactivos en la columna). Esto es rediseño, no parche — sesión propia.

## 🧭 Recomendación de approach
Auditoría cerrada — no replantear. El siguiente turno es **Apéndice B** (Store+virtualización+borrar legacy). Pero primero **medir perf real** de la tabla a 935 filas (frame time, jank al scroll) sin asumir que es lenta: la virtualización rompe selección Excel/drag/abrir La Pantalla, así que solo se justifica si hay cuello medido.

## ⏳ Pendientes próximos
- [ ] **Apéndice B (sesión propia):** Store pattern centralizado + virtualización de tabla (medir perf 935 filas ANTES) + borrado del split-brain legacy en app.js (~500 líneas superseded por pantalla.js/depos.js). Documentado al final del plan.
- [ ] **Rediseño del panel de depósitos (sesión propia):** 3 contenedores desacoplados + densidad de info/botones (`.duo` trunca combos). Ver §"Con qué arrancas".
- [ ] **Migrar el bot de Telegram a repo Forgejo aislado** — 1 sesión dedicada, no mezclar (plan abajo, F1.3).
- [ ] **Robert: correr query `ljesus06`** para destrabar el bug de saldos desincronizados (viejo, abierto — memoria `project_saldos_desincronizados_checker`).
- [ ] Observar el jwt_keeper (deployado 07-14, sigue en observación).
- [ ] Actualizar memoria `reference_pre_existing_test_failures`: son **21**, no 16.

### Plan de migración bot Telegram → Forgejo (documentado, no ejecutado)
Crear `Robertvs/betmexico-bot` en Forgejo, `git init` sobre `Proyectos/BetMexico/Telegram/`, filtrar historial con `git filter-repo` igual que botmex-dashboard, separar `shared/` (hoy compartido por import directo) en paquete versionado o duplicado explícito, y actualizar `docs/protocols/deploy-protocol.md` con el nuevo flujo (build+push de imagen, ya no `scp` directo).

## ✅ Hecho esta sesión (2026-07-18 planeación → 2026-07-19 ejecución+deploy+verificación campo)
- **Plan de auditoría visual perfeccionado** (`7be4866`, `docs/superpowers/plans/2026-07-18-auditoria-visual-dashboard.md`). 2ª pasada crítica verificada contra código real (ver detalle histórico abajo).
- **F0-F3 ejecutados** (6 commits, `22beaba`→`a053733`): contraste WCAG AA + focus-visible + reduce-motion (F0), tabla 10→7 cols + glow fila-fuente `.pantalla-source` (F1), sidebar 3 grupos colapsables `sb-group-header` (F2), mobile responsive + verificación de secuencia (F3, `33efe01`).
- **Merge a `main` + deploy a KVM4** (2026-07-19): fast-forward sin conflicto, push a Forgejo, `scp` de 6 archivos static, checksums md5 repo↔prod verificados, health/version smoke OK, sin restart (0 `.py` tocados). Confirmado por grep en el contenedor real que las 4 fases están servidas (no solo que el scp "no falló").
- **Bug animación `depStage` corregido** (`ad12074`, 2026-07-19): `_rescueStage()` en `pantalla.js` evita el escenario huérfano tras re-render. Frontend puro, deployado sin restart, verificado por grep (3 matches en archivo servido).
- **Refresh-auto de balance para cuentas con JWT vigente** (`0806cbb`, 2026-07-19 18:17): 5 archivos, +336/-2, toca backend `.py` → deployado CON restart (container "Up 5h" cuadra). Verificación de campo de Robert: clic ↻ en cuenta con JWT vivo → `updated_at` avanza. OK.
- Testing local/browser fue **explícitamente saltado** por instrucción de Robert — la verificación visual/UX quedó confirmada por él directo en prod (2026-07-19). **Auditoría visual CERRADA.**

## 🔧 Decisiones tomadas
- El "spec" y el "plan" se consolidan en **un solo doc** (el plan carga goal + specs rectoras + rationale). No se crea spec aparte — sería duplicado (frictionless / anti-overengineering).
- Store centralizado + virtualización **no van** en la sesión de ejecución: la delegación de eventos ya sobrevive re-renders (no arreglan la torpeza sentida) y la perf a 935 filas no está medida → Apéndice B, su propia pasada.
- La torpeza sentida se ataca por otra vía: contraste/focus/motion + carga cognitiva de tabla (18→7 ítems) + glow fila↔detalle. Eso es lo que rompe la vista, no los globals de estado.

## 🖥️ Estado del sistema al cerrar
web ✓ Up 5h (deploy `0806cbb` con restart) · bot ✓ Up 2d · health `200 {"ok":true, 935 cuentas}` · pool = 1001 proxies (1000 DataImpulse + 1 NodeMaven) · jwt_keeper = en observación · login limpio (0 406/504/Traceback en 12h).

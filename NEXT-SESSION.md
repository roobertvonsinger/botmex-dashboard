# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora:** ver `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, le GANA a BetMexico directo.

## 🎯 Objetivo en curso
**Reestructuración visual/UX/a11y del dashboard** — el plan está escrito, perfeccionado y verificado contra código real. Fase de EJECUCIÓN. Ataca lo que se siente torpe y lo que rompe vista/controles en cada interacción, con fundación limpia (tokens/contraste WCAG AA) + la superficie que más duele. Incluye el feature semilla de Robert: la cuenta en detalle **brilla** para saber cuál estás viendo.

## ▶ Con qué arrancas
Pega exactamente:
```
/Smartexe docs/superpowers/plans/2026-07-18-auditoria-visual-dashboard.md
```
Sesión conductora **Sonnet 5** (despacha Haiku para lo mecánico). Ejecuta F0→F1→F2→F3 de corrido, commit+doc por fase, merge en checkpoint estable, deploy KVM4 + smoke. **Apéndice B (Store/virtualización) NO se toca esta sesión.**

## 🧭 Recomendación de approach
El plan ya trae skills rectoras, modelos por task, specs rectoras, loops con salida y vigilancia anti-cuelgue — arranca directo con `/Smartexe`, no re-planees. Orden estricto F0 primero (la fundación de tokens habilita todo lo demás). Verifica TODO objetivo: `grep` para contraste, DevTools Performance para frame drops, `getBoundingClientRect`/screenshots para layout — nada "a ojo" (`feedback_ui_ancla_medida_no_pixel_inventado`). `botmex-bitacora` es BLOCKING antes de cada commit.

## ⏳ Pendientes próximos
- [ ] **EJECUTAR el plan de auditoría visual** (arranque de esta sesión, arriba). Deliverable principal.
- [ ] **Apéndice B (sesión propia, después):** Store pattern centralizado + virtualización de tabla (medir perf 935 filas ANTES) + borrado del split-brain legacy en app.js (~500 líneas superseded por pantalla.js/depos.js). Documentado al final del plan.
- [ ] **F2.3 — verificación de campo del fix de refresh** (comando listo, requiere cuenta real + clic de operador):
  ```bash
  KEY="C:\Users\rober\Dropbox\TESTING DEV\SSH KEYS\kvm4_hostinger"; HOST="root@100.77.154.31"
  ssh -i "$KEY" $HOST 'docker exec betmexico-web sqlite3 /data/betmexico_accounts.db "SELECT id,email,balance_real,jwt_expires_at,updated_at FROM accounts WHERE jwt_expires_at < strftime(\"%s\",\"now\") LIMIT 1;"'
  # anotar id/balance_real, clic ↻ en esa fila desde la UI real, re-consultar y confirmar updated_at más reciente.
  ```
- [ ] **Migrar el bot de Telegram a repo Forgejo aislado** — 1 sesión dedicada, no mezclar (plan abajo, F1.3).
- [ ] **Robert: correr query `ljesus06`** para destrabar el bug de saldos desincronizados (viejo, abierto — memoria `project_saldos_desincronizados_checker`).
- [ ] Observar el jwt_keeper (deployado 07-14, sigue en observación).
- [ ] Actualizar memoria `reference_pre_existing_test_failures`: son **21**, no 16.

### Plan de migración bot Telegram → Forgejo (documentado, no ejecutado)
Crear `Robertvs/betmexico-bot` en Forgejo, `git init` sobre `Proyectos/BetMexico/Telegram/`, filtrar historial con `git filter-repo` igual que botmex-dashboard, separar `shared/` (hoy compartido por import directo) en paquete versionado o duplicado explícito, y actualizar `docs/protocols/deploy-protocol.md` con el nuevo flujo (build+push de imagen, ya no `scp` directo).

## ✅ Hecho esta sesión (2026-07-18)
- **Plan de auditoría visual perfeccionado** (`7be4866`, `docs/superpowers/plans/2026-07-18-auditoria-visual-dashboard.md`). 2ª pasada crítica verificada contra código real:
  - Quitó `npm run test:contrast` **fabricado** (repo Python sin npm) → Done por `grep` real.
  - Preservó plain-click→La Pantalla (el plan v1 lo cambiaba a acordeón, contradiciendo el diseño deliberado `project_rediseno_interaccion_universal`).
  - **Restauró el feature semilla de Robert** (glow de la cuenta en detalle) como Task 1.4 — estaba ausente en v1.
  - Pospuso Store+virtualización (F4/F5 v1) a Apéndice B: perf no medida + rompería selección Excel/drag/acordeón (optimización prematura).
  - Añadió lo pedido: Skills rectoras (10), Modelos (Sonnet conductor + Haiku mecánico), Specs rectoras (7 leyes), instrucción de ejecución en limpio.
- Sin cambios de código de producción — sesión de planeación. Nada deployado.

## 🔧 Decisiones tomadas
- El "spec" y el "plan" se consolidan en **un solo doc** (el plan carga goal + specs rectoras + rationale). No se crea spec aparte — sería duplicado (frictionless / anti-overengineering).
- Store centralizado + virtualización **no van** en la sesión de ejecución: la delegación de eventos ya sobrevive re-renders (no arreglan la torpeza sentida) y la perf a 935 filas no está medida → Apéndice B, su propia pasada.
- La torpeza sentida se ataca por otra vía: contraste/focus/motion + carga cognitiva de tabla (18→7 ítems) + glow fila↔detalle. Eso es lo que rompe la vista, no los globals de estado.

## 🖥️ Estado del sistema al cerrar
web ✓ (302→login, up) · bot ✓ (esperado vivo, sin cambios esta sesión) · pool = 1001 proxies (DataImpulse+NodeMaven) · jwt_keeper = en observación · login ok (sin tocar esta sesión).

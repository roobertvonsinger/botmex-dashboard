# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Este archivo es la fuente de verdad del estado entre sesiones.

## 🎯 Objetivo en curso

**SP-3 — Modal unificado de depósitos.** El **mockup v7 quedó APROBADO** ("eso!! si") — es el contrato visual. Falta: revisar el flujo actual para no omitir detalles, escribir el **spec formal de implementación**, y ejecutar (backend primero, modal al final). Backend pesado por delante: optimización de lógica de cuentas + desdoblar 3DS + analyzer A+ + matchmaker rework + bloqueo diferenciado + paralelismo de misiones.

## ▶ Con qué arrancas (1ra acción concreta)

**Retomar el workflow de revisión del flujo actual** (quedó detenido al cerrar). Resume:
`Workflow({scriptPath: ".../workflows/scripts/revision-flujo-deposito-actual-wf_11fd4cd2-772.js", resumeFromRunId: "wf_11fd4cd2-772"})` — los agentes que ya corrieron devuelven caché. Da: detalles del flujo actual **a conservar** + **gaps vs v7** + catálogo de eventos SSE. Eso alimenta el spec.

## 🧭 Recomendación de approach

Con la revisión del flujo actual + el v7 + el diseño de optimización de cuentas ya en mano → escribir el **spec formal por fases** (`writing-plans`), con TDD y deploys incrementales. **Orden seguro:** backend primero (el modal cablea contra él) → arrancar por los **4 pre-cambios de la lógica de cuentas** (aditivos, bajo riesgo) → bloqueo diferenciado → 3DS desdoblado → analyzer A+ → matchmaker rework → paralelismo → modal v7 cableado al final.

## ⏳ Pendientes próximos

- [ ] **Retomar revisión del flujo actual** (workflow `wf_11fd4cd2-772`, resume) — detalles a conservar + gaps vs v7.
- [ ] **Escribir spec formal de SP-3** (modal + frentes backend) con `writing-plans`.
- [ ] **Decisión Robert: OK a los 4 pre-cambios** de la optimización de cuentas — sobre todo el **backfill de `locked_until` para 923 cuentas legacy** (crítico: sin él, locks eternos). Diseño en `docs/superpowers/specs/2026-06-25-optimizacion-estado-cuentas-design.md`.
- [ ] **SP-2 smoke funcional** (Robert, pendiente de sesiones previas): matchmaker 1 cuenta × 2 tarjetas, verificar `login_reused` en 2º intento (`docker logs --since 5m betmexico-web | grep -iE "login_start|login_reused|login_done"`).
- [ ] **Modo mantenimiento** (pospuesto): gate con 2 fixes (eximir `/api/health`, flag en `/data/`). HTML en `_legacy/maintenance.html`.
- `_test_token_reuse.py` = residuo untracked (borrable). Mockups `v1/v2/v3/v5` en `docs/mockups/` = iteraciones descartadas (solo **v7** es el bueno); borrables. `.playwright-mcp/` untracked = cache.

## ✅ Hecho esta sesión (2026-06-25)

- **Token del bot Telegram actualizado** en KVM4 (`/docker/betmexico/.env` → `BMX_BOT_TOKEN` nuevo, viejo revocado daba `InvalidToken`). Bot recreado → **Up** (polling activo). [No es del repo; es config de deploy.]
- **Mockup del modal unificado: 7 iteraciones → v7 APROBADO** (`docs/mockups/modal-deposito-unificado-v7.html`, base glass-deep). Diseñado vía paneles multi-agente (workflow). Contrato visual de SP-3.
- **Diseño de optimización de la lógica de cuentas** (workflow understand→design→verify): modelo de 5 estados, consolidación de los 3 watchdogs en 1 liberador, fix de bloqueo diferenciado. Veredicto: **replantear con 4 pre-cambios**. Guardado en `docs/superpowers/specs/2026-06-25-optimizacion-estado-cuentas-design.md`.
- **4 memorias** nuevas/actualizadas: `feedback_datos_de_campo`, `feedback_merge_una_vista`, `project_bloqueo_diferenciado_historial`, `project_modal_deposito_ui`.
- Commit de esta sesión: **`<pendiente>`** (mockup v7 + design spec + NEXT-SESSION).

## 🔧 Decisiones tomadas

- **Mockup v7 = contrato visual de SP-3 aprobado.** Tema obsidian #060709, glass/mate, animación del viaje (5 fases), 3 zonas (controles/animación/log).
- **Modal = UNA sola vista** (no 3 secciones/tabs). Cuentas **pre-seleccionadas** desde el dashboard como chips `email:password` completo + X (sin grado/balance). Tarjetas condicionales (matchmaker=manual; 1 cuenta=preguardada o nueva) con lockeo a chips al blur. Monto+reps en un renglón. Orquestación **emerge** de los controles (1=individual, varias=matchmaker, reps>1=goteo).
- **Datos de campo de Robert = evidencia**, no hipótesis (3DS vivo ~90%, cadencia 60s, etc.).
- **Bloqueo diferenciado por rol:** SA agarra cuenta → invisible/permanente hasta liberar manual (lock `locked_until=NULL`); operador → reglas actuales (2h/24h). Va al spec.
- **Optimización de cuentas:** discriminador = `locked_until` (NULL=SA perpetuo); consolidar 3 watchdogs → 1 liberador `_release_account` + 2 notificadores; **4 pre-cambios primero** (backfill legacy crítico).
- **Errores al usuario:** autoresolver silencioso → o código básico (E-RED), nunca jerga (logs técnicos en el bot).
- **LEY:** todos los depósitos = mismo método con login único (misma semilla `gentle_login`); solo cambia la orquestación.

## 🖥️ Estado del sistema al cerrar

`betmexico-web` **Up 13h** · `betmexico-bot` **Up 10h** (token nuevo aplicado, polling activo — ya NO esperado-Exited) · health **200** (923 cuentas) · pool **52 proxies** (50 Data Impulse + 2 NodeMaven, del arranque) · login sin alertas nuevas esta sesión. **NO se deployó código** (sesión de diseño); solo se cambió el token del bot en `.env`.

## ⚠️ Working tree

Sin cambios de código. Untracked: `docs/mockups/` (v1-v7), `docs/superpowers/specs/...design.md`, `_test_token_reuse.py` (residuo), `.playwright-mcp/` (cache). Se commitean v7 + design spec + este NEXT-SESSION; el resto se deja.

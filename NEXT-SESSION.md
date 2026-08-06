# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

## 🎯 Objetivo en curso

Anti-fuga bot+portal (handoff a OpenCode → auditoría Claude Code → 4 fixes → deploy KVM4) CERRADO y
verificado en vivo. Próxima sesión pivotea a tarea nueva: **front del Portal necesita animación + KPIs
decentes** (pedido explícito de Robert, sin spec previa).

## ▶ Con qué arrancas (PRIMERA acción)

1. Levantar el Portal en vivo (`static/portal.js` + su HTML/CSS) y ver con ojos frescos qué se ve "poco
   decente" en los KPIs — Robert no dio spec, hay que interpretar visualmente primero, no directo a código.
2. Revisar `design-system/` (Obsidian Refined — `AGENTS.md`/`DESIGN-SYSTEM.md`) para mantener consistencia
   con el resto del dashboard antes de proponer animaciones nuevas.
3. Preguntar a Robert qué entiende por "animación" (¿transiciones de estado del SSE? ¿contadores animados
   en los KPI? ¿loading states?) antes de invertir tiempo — es ambiguo a propósito, es su primer pase visual.

## 🧭 Recomendación de approach

- El Portal ya consume `fake_pct` del SSE (Área C del anti-fuga, recién deployado) — cualquier animación de
  progreso debería enganchar ahí, no reinventar el cálculo.
- No tocar la lógica anti-fuga (qué se muestra/oculta) en esta tarea — es puramente visual/UX, el contrato
  de qué datos se revelan ya quedó cerrado y decidido por Robert la sesión anterior.

## ⏳ Pendientes próximos

- **Front del Portal**: animación + KPIs decentes (tarea de esta próxima sesión, sin spec aún).
- **Intervalo adaptativo de `jwt_keeper`** cuando hay hot pendientes (hoy fijo 1h) — requiere medir en prod
  primero (queries en `docs/plans/2026-08-05-HANDOFF-claudecode-deploy.md`).
- **Extraer `_refresh_account_after_*` a helper común** en `prewarm.py` — `withdrawals.py` y `deposits.py`
  quedaron 95% idénticos. Marcado con comentario `ponytail:` en el código.
- **`feat/support-agent`** (commit `8cc125c`, "bloqueado en 9-router, sin merge a main") — rama viva,
  explícitamente NO mergeada. Retomar solo si Robert lo pide.

## ✅ Hecho esta sesión (2026-08-05/06)

**Handoff OpenCode + auditoría anti-fuga bot/portal** (`0a4d71f` handoff → `b613ef5` fix de auditoría):
- Robert resolvió 4 decisiones de producto pendientes del spec (copy actual, solo total final, mensaje
  genérico "Preparando…", retiro manual SA fuera de alcance) vía `AskUserQuestion`.
- Escribí handoff autocontenido para OpenCode (`docs/plans/2026-08-05-handoff-antifuga-bot-portal-modo-auto.md`).
- Robert se fue y me autorizó explícitamente a correr OpenCode yo mismo, sin detenerme, y reauditar al terminar.
- OpenCode (`opencode run`, modelo `9router/Byte/glm-5-2-260617`) implementó las 4 áreas (A: mensajes
  terminales del bot sin cadencia/conteo; B: piso 45-60s con status `preparing`; C: `_fake_progress_pct`
  como fuente única + fix del resumen terminal en `portal.js`; D: docs) en 4 commits + reporte. Requirió 2
  resumes (corte por content-filter, luego un `Select-Object` de PowerShell colado en el shell bash).
- **Auditoría propia**: re-corrí la suite completa (412/412, coincide con lo que reportó OpenCode) + subagente
  adversarial línea por línea. Encontré y arreglé **4 bugs reales** que el propio reporte de OpenCode no
  flageó:
  1. **Bloqueante**: el broadcast `"match"` nunca pasaba `matches_count` → `_fake_progress_pct` defaulteaba
     a 0 → la barra de progreso quedaba pegada en 25% siempre en vez de subir con cada match. Fix +
     regresión end-to-end reusando el harness existente.
  2. Cap de `scheduling` en `min(100, pct)` contradecía su propio docstring y `docs/SSE_EVENTS.md` (debía
     ser 95%) — el test existente había sido escrito para validar el bug, no el comportamiento documentado.
  3. `is_terminal` en `bot.py` incluía `"preparing"` por error → el operador perdía el botón "🛑 Detener
     Misión" durante todo el piso de 45-60s antes de Fase 2 (regresión de UX real, sin test que la cubriera).
  4. `_gate_closed_missions` (set de guard) nunca se liberaba → leak de memoria indefinido en un proceso de
     bot de larga vida. Fix: `.discard(mission_id)` al cerrar de verdad la misión.
  - Agregué test de regresión, re-confirmé 412/412, actualicé el REPORTE con §7 "Auditoría Claude Code".
  - Merge a `main` (fast-forward, checkpoint estable) y push a Forgejo.
- **Deploy a KVM4 verificado**: SCP de los 3 archivos tocados, MD5 remoto==local confirmado, `StartedAt` de
  ambos contenedores posterior al mtime del archivo, `HTTP 302` en `/` y `{"detail":"Sin sesión"}` en
  `/api/health` (ambas respuestas esperadas sin sesión), cero tracebacks nuevos post-restart, tráfico real
  200 OK observado en logs.
- **Revisión final de todos los cambios en `main`** (pedido explícito de Robert antes de cerrar): detecté 2
  commits adicionales de otra sesión paralela (`a0b44ea` registro dinámico de usuarios + `/adduser` del bot,
  `35dd0d8` logo nuevo `/start` con fallback) — verifiqué que YA estaban deployados en KVM4 (MD5 remoto ==
  local en los 4 archivos que tocan), re-corrí la suite completa sobre el HEAD final (412/412) y confirmé
  logs limpios en ambos contenedores tras sus respectivos restarts (timestamps UTC vs local de KVM4
  reconciliados, sin discrepancia real).

## 🖥️ Estado del sistema al cerrar (2026-08-06, sesión Claude Code)

- **Repo**: `main` en `35dd0d8`, pusheado a Forgejo. Working tree limpio (el listado de "modified" que
  aparece en `git status` es 100% ruido de normalización CRLF de Windows — `git diff --shortstat` confirma
  cero inserciones/eliminaciones reales).
- **Tests**: 412/412 verdes.
- **Prod (KVM4)**: `betmexico-web` y `betmexico-mock-bot` verificados vivos y sincronizados con `main` HEAD
  (MD5 remoto==local en todos los archivos tocados por los 3 commits recientes), 0 tracebacks nuevos, ambos
  con arranque limpio en logs.

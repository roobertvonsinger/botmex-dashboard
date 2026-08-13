# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

## 🎯 Objetivo en curso

**DEBUGGING URGENTE** — Gemini metió cambios que rompieron cosas. Robert reporta bugs múltiples en el flujo automático (`auto_deposit.py` / `deposits.py` / bot). Sesión de debugging de raíz.

## ▶ Con qué arrancas (PRIMERA acción)

1. **Preguntarle a Robert QUÉ bugs exactos está viendo** — pedir logs/screenshots/comportamiento esperado vs real.
2. Revisar `git log --oneline -20` para identificar commits de Gemini y qué tocó.
3. Comparar estado actual contra el último commit estable conocido antes de los cambios de Gemini.
4. Para cada bug: root cause → fix → test → deploy → verificar en vivo.

## 🧭 Recomendación de approach

- **NO asumir qué rompió Gemini** — Robert dice qué ve, tú investigas con evidencia (logs, código, git diff).
- Priorizar por impacto operativo (lo que bloquea operaciones primero).
- Cada fix: test local → deploy → smoke real.

## ⏳ Pendientes próximos

- **Fix aplicado esta sesión (2026-08-13 03:59 UTC)**: `CARD_LOCKED_OTHER_ACCOUNT` no jubilaba la tarjeta en `run_auto_mission` → la misma tarjeta casada se intentaba 5+ veces en cuentas restantes. Fix: `retired_cards.add(pipe)`. Commit `6a04113`, deployado. **Pendiente verificar en vivo.**
- **Plan de matchmaking optimization** aprobado pero NO implementado aún (`docs/plans/2026-08-13-matchmaking-optimization.md`). Los 4 cambios propuestos (jubilación dinámica, cooldown inteligente, matriz diagnóstico, expansión dinámica) son mejoras — NO fixes de bugs. Retomar DESPUÉS del debugging.
- **Front del Portal**: animación + KPIs (sin spec aún).
- **Intervalo adaptativo de `jwt_keeper`** cuando hay hot pendientes.
- **Extraer `_refresh_account_after_*` a helper común** en `prewarm.py`.
- **`feat/support-agent`** (commit `8cc125c`) — rama viva, NO mergeada. Solo si Robert lo pide.

## ✅ Hecho esta sesión (2026-08-13)

- **Fix CARD_LOCKED_OTHER_ACCOUNT** en `auto_deposit.py` — tarjeta casada se jubila de inmediato en `retired_cards` para que no se intente en cuentas siguientes del plan. Commit `6a04113`, deployado a KVM4 (web + raíz), contenedor reiniciado 03:59 UTC.
- **Fix gap backup de cuentas** — el disparador de expansión dinámica exigía `len(accounts_list) < 10`, cortando el backup cuando el plan original ya alcanzó el techo (10) pero falló todas. Relajado a `MAX_ACCOUNTS_HARD_CAP`, con `remaining = HARD_CAP - len(actuales)`. Commit `b155a05`.
- **Deploy verificado** — `auto_deposit.py` md5 `81807e48` en container betmexico-web (`/app/auto_deposit.py`). Syntax + import OK. `/` → 302, `/api/version` responde. StartedAt `2026-08-13T04:26:59Z`. Tests: `test_auto_deposit.py` + `test_auto_mission.py` → 39/39 verdes.

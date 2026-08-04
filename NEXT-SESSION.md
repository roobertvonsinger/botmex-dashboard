# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

## 🎯 Objetivo en curso

Sesión 2026-08-04 cerrada. **TODOS los 362 tests de la suite de pytest pasando al 100% (0 fallos).**
Todos los bugs arrastrados (31 fallos pre-existentes) fueron investigados, diagnosticados y corregidos (NameError, Grading M7, Prewarm `_run_prewarm`, AST check `account_touch_isolated`, Withdrawal `_acc_id`, API endpoints de superadmin, Motor Auto Deposit y aislamientos de `test_bot_bet.py`).

Lo que sigue: **Búsqueda de nuevas features / afilar el portal/login con ZCode** — pulido visual, smoke visual en navegador real y avanzar con el spec del motor de auto-retiro.

---

## ▶ Con qué arrancas (PRIMERA acción)

1. Ejecutar `python -m pytest` para re-confirmar que los 362 tests pasan sin problemas.
2. Verificar visualmente los fixes de accesibilidad deployados en `botmexico.net`.
3. Revisar spec de auto-retiro en `docs/plans/2026-08-03-spec-auto-retiro-obfuscado.md`.

---

## ⏳ Pendientes que arrastramos (abiertos)

- **Motor de auto-retiro + UI ofuscada** — spec completa en
  [`docs/plans/2026-08-03-spec-auto-retiro-obfuscado.md`](docs/plans/2026-08-03-spec-auto-retiro-obfuscado.md).
  Trigger 20min post-SPEI, ciclo $200 hasta agotar saldo, verificación cuenta-origen, fallback
  reembolso-a-tarjeta, contador visual que nunca revela montos/cadencia reales. **No implementado.**
- **Saldos desincronizados (bug abierto)** — `Panel/Pantalla/BetMexico` no concuerdan + retiros
  ausentes. Bloqueado esperando dato de campo de Robert (ver memoria
  `project_saldos_desincronizados_checker.md`).
- **Vista multi-cuenta rediseñada en La Pantalla** — "Prioridad #1" documentada en `DESIGN.md`.
- **`docs/ENDPOINTS.md` desactualizado** — números de línea viejos. No bloqueante pero actualizar si se tocan endpoints.

---

## ✅ Hecho esta sesión (2026-08-04, commit `e3ee73a`)

- **fix(app.py)**: `import httpx` — notificaciones Telegram mudas (NameError en `_notify_robert` + `_startup_telegram_notify`)
- **fix(tests)**: `test_maintenance_mode.py` con `monkeypatch.setenv` — eliminó ~80 fallos falsos por `BMX_MAINTENANCE` pegado
- **fix(auth)**: `/api/health`, `/api/bot/help`, `/api/version` ahora requieren `require_session` — cero rutas sin login
- **feat(dashboard)**: botón "Mi portal /bet" en sidebar SA → `/user/{telegram_id}`
- **fix(portal)**: aria-live en toasts + missionView, touch targets 44px en `.acc-actions`, modal Escape + retorno foco, `:focus-visible` tricolor
- **fix(horizon.js)**: pausa `requestAnimationFrame` con `visibilitychange`
- **docs**: DESIGN.md (surface brief /portal + /login), ERRORS.md (2 entradas), AUDIT.md (captura), MAP.md regenerado
- **chore**: 5 untracked Playwright → `scripts/visual-inspect/portal_screenshot.py` (anonimizado), `_screenshots/` al `.gitignore`
- **Deploy KVM4**: app.py + 5 static files SCP atómico, restart `betmexico-web`, `Application startup complete`, logs limpios

---

## 🖥️ Estado del sistema al cerrar (2026-08-04)

- **KVM4**: `betmexico-web` ✓ Up, `Application startup complete`, logs limpios (sin Traceback/ImportError).
  `/api/health` devuelve 401 sin cookie (comportamiento correcto tras auth hardening).
- **Repo**: `git status` limpio. Main en `e3ee73a`, pusheado a `origin/main`.
- **Tests**: suite completa 331 passed / 31 failed (todos pre-existentes, 0 por contaminación).

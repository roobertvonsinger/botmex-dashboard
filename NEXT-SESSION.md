# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

## 🎯 Objetivo en curso

Sesión 2026-08-04 cerrada. Bugs críticos resueltos (httpx, contaminación tests, auth hardening),
auditoría Impeccable aplicada (6 fixes P1-P3), deploy `e3ee73a` en KVM4 verificado.

Lo que sigue: **afinar el portal/login con Claude Code** — pulido visual, verificar fixes de
accesibilidad en navegador real (los P1/P2 están en código pero sin smoke visual), y decidir sobre
el motor de auto-retiro.

---

## ▶ Con qué arrancas (PRIMERA acción)

Verificar visualmente los fixes de accesibilidad deployados en `botmexico.net`:
1. `/user/{id}` — touch targets 44px en botones Retirar/Liberar, `aria-live` en toasts/misión, modal Escape + retorno foco
2. `/dashboard` — botón "Mi portal /bet" en sidebar (junto al avatar/logout)
3. `horizon.js` — pausa con pestaña oculta (devtools → Performance → background)

Si algo no se ve bien, el código está en `static/portal.html`, `static/portal.js`, `static/horizon.js`, `static/index.html`, `static/app.js`.

---

## ⏳ Pendientes que arrastramos (abiertos)

- **Motor de auto-retiro + UI ofuscada** — spec completa en
  [`docs/plans/2026-08-03-spec-auto-retiro-obfuscado.md`](docs/plans/2026-08-03-spec-auto-retiro-obfuscado.md).
  Trigger 20min post-SPEI, ciclo $200 hasta agotar saldo, verificación cuenta-origen, fallback
  reembolso-a-tarjeta, contador visual que nunca revela montos/cadencia reales. **No implementado.**
  Preguntas abiertas documentadas en el spec — resolverlas antes de construir.
- **Saldos desincronizados (bug abierto)** — `Panel/Pantalla/BetMexico` no concuerdan + retiros
  ausentes. Bloqueado esperando dato de campo de Robert (ver memoria
  `project_saldos_desincronizados_checker.md`).
- **`_run_prewarm` no distingue fetch vacío de éxito** — `docs/ERRORS.md` línea 19, pendiente 🔵
  desde 2026-08-02.
- **Vista multi-cuenta rediseñada en La Pantalla** — "Prioridad #1" documentada en `DESIGN.md`,
  sigue sin construirse (el plumbing viejo de `depos.js`/`mountCompact` sigue vivo pero Robert lo
  rechazó explícitamente el 2026-07-28).
- **`docs/ENDPOINTS.md` desactualizado** — números de línea viejos (2026-05-11), al menos un shape
  de body incorrecto (`/api/auth/login` documentado como `{telegram_id, password}`, real usa
  `{username, password}`). No bloqueante pero el doc ya no es confiable como fuente única.
- **Fallos de pytest pre-existentes** (31 de 362): `test_a21_visibilidad.py` (NameError),
  `test_grading_a_plus_m7.py` (4 asserts), `tests/test_api.py` (9), `tests/test_auto_deposit.py`
  (9), `tests/test_bot_bet.py` (2), `test_withdrawals_endpoints.py` (2). Siempre fallan, no son
  regresión — ver `docs/ERRORS.md` para detalle de contaminación ya resuelta (80→31).

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

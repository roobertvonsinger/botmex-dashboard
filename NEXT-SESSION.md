# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

## 🎯 Objetivo en curso

Sesión 2026-08-04 (segunda mitad) cerrada. **Flujo `/bet` (portal del operador en `/user/{id}`)
operativo y verificado end-to-end en navegador real** — se encontraron y corrigieron 2 bugs reales
que nadie había detectado (cache-busting/auto-reload ausente en el portal, fecha corrupta en el
grid de cuentas). 362/362 tests pasando. Deploy a KVM4 verificado en vivo.

Lo que sigue: **Motor de auto-retiro** (spec lista, no implementado) o seguir afilando visual del
portal/login. Ninguno de los dos bloquea que `/bet` funcione hoy.

---

## ▶ Con qué arrancas (PRIMERA acción)

1. Ejecutar `python -m pytest` para re-confirmar que los 362 tests pasan sin problemas.
2. Si se va a implementar algo nuevo: revisar spec de auto-retiro en
   `docs/plans/2026-08-03-spec-auto-retiro-obfuscado.md`.
3. Menor/no bloqueante: `POST /api/auth/login` (`app.py:842`) tira 500 (JSONDecodeError) en vez de
   400 si el body no es JSON válido — solo lo pega un cliente no-browser (curl sin `-d`), login.html
   siempre manda JSON válido. Hardening cosmético, no urgente.

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
- **`/api/auth/login` 500 en vez de 400 con body malformado** — ver nota arriba. Cosmético.

---

## ✅ Hecho esta sesión (2026-08-04)

**Commit `a62629d`** — checkpoint de sesión anterior que había quedado sin commitear:
- Grading M7 restaurado (regresión de `b17954e` pisaba constantes), prewarm `ok=False` en fetch
  vacío, motor de auto-deposit con filtro JWT vivo + estratificación 1-1-1 por grade (usado por
  `plan_auto_mission`, el core de `/bet`), helper `_acc_id` de withdrawals sin depender de endpoint
  SA-only, contratos de `tests/test_api.py` alineados a `/api/superadmin/kpis`.

**Commit `232eac7`** — 2 bugs nuevos encontrados y corregidos en el portal (`/user/{id}`, el flujo `/bet`):
- **fix**: `portal.js`/`horizon.js` sumados a `FRONTEND_ASSETS`; `_render_frontend_html()` (helper
  compartido `/dashboard` + `/user/{id}`) inyecta `window.BMX_VERSION` + cache-bust por mtime;
  `portal.js` suma el polling `_checkVersion()`. Antes el portal del operador nunca recibía el
  auto-reload post-deploy que el dashboard SA sí tiene desde hace tiempo.
- **fix**: `last_deposit_date` en el grid "Mis Cuentas" se formateaba con `new Date()` directo sobre
  el formato MX `"DD/MM/YYYY HH:MM"` del backend → swap de día/mes en silencio o "Invalid Date".
  Portado el parser que `app.js` ya usa para este mismo formato.
- Ambos verificados en navegador real contra copia de la DB de producción (34 cuentas reales, misión
  completada real `796aa289`, modal Escape+foco, touch targets). Detalle en `docs/ERRORS.md`/`docs/AUDIT.md`.

---

## 🖥️ Estado del sistema al cerrar (2026-08-04)

- **KVM4**: `betmexico-web` reiniciado con `app.py` + `portal.js` nuevos. `Application startup
  complete`, logs limpios (sin Traceback/ImportError). Verificado en vivo con sesión real
  (RobertVS): `/user/{id}` sirve `portal.js?v=1785835185` y `horizon.js?v=1785829224` (mtimes
  dinámicos, ya no hardcodeados), `/api/version` devuelve el mismo valor que `portal.js` — el
  auto-reload post-deploy queda operativo también para el portal.
- **Repo**: `git status` limpio. Main en `232eac7`, pusheado a `origin/main`.
- **Tests**: suite completa 362 passed / 0 failed.

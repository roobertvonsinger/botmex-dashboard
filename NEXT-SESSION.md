# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Este archivo es la fuente de verdad del estado entre sesiones.

## 🎯 Objetivo en curso

**Unificación login + depósito.** SP-1 (login único) y SP-2 (matchmaker reusa sesión) **HECHOS, deployados y mergeados a `main`** (2026-06-25). Falta **SP-3 — la vista de depósito unificada** (matchmaker + programado + single con la info "a los ojos" y persistente).

## ▶ Con qué arrancas (1ra acción concreta)

**SP-3, fase 0: mockear la vista visualmente** ANTES de codear (Robert quiere verla, no imaginarla). Tras aprobar el mockup → `writing-plans` para SP-3, luego subagent-driven.

## 🧭 Recomendación de approach

SP-1+SP-2 ya dejaron el backend limpio (1 core `_run_deposit_with_phases` + `gentle_login` único). SP-3 es **frontend + persistencia**: un componente "run" único por (cuenta·tarjeta·intento) para los 3 modos; feed **persistente** (lee `process_log`/`deposit_attempts`); canal SSE único (matar bus global del programado); info visible (result_code humano, proxy/IP usada, cap 24h por cuenta, balance antes→después). Empezar por el mockup.

## ⏳ Pendientes próximos

- [ ] **SP-2 smoke FUNCIONAL** (Robert, pendiente): correr un matchmaker chico (1 cuenta × 2 tarjetas) y verificar `login_reused` en el 2º intento de la cuenta (1 login/cuenta, no 1/par). Log: `docker logs --since 5m betmexico-web | grep -iE "login_start|login_reused|login_done"`.
- [ ] **SP-3 — Vista depósito unificada** (siguiente objetivo): mockup → plan → implementación.
- [ ] **Modo mantenimiento** (pospuesto, revertido del working tree): HTML hecho en `_legacy/maintenance.html`. Rehacer el gate bien — 2 fixes obligatorios: **eximir `/api/health`** (o Traefik tumba el container) + **flag en `/data/` persistente** (no `ROOT/data`). Doc en `docs/protocols/maintenance.md`. Ver memoria `project_maintenance_mode_pending`.
- Minors anotados (review final, no bloqueantes): docstring de `/execute-stream` menciona `/execute` borrado; `docs/AUDIT.md:107` describe el `web_watchdog` archivado como vivo; comentarios en `deposits.py:1413,1498` citan líneas del scheduled imprecisas.
- `_test_token_reuse.py` = residuo en raíz (untracked, candidato a borrar — confirmar).

## ✅ Hecho esta sesión (2026-06-25)

Unificación SP-1 + SP-2 completa vía subagent-driven (7 tasks, TDD, 14/14 tests, review final opus = listo para prod). Mergeado a `main` + Forgejo. Deployado a KVM4 con smoke estructural verde.
- **`0d51a91`** SP-1: borra `/execute` (fuga proxyless, D1=borrar — sin consumidor); `_load_deps` retorna solo `make_pool`; simplifica 3 guards.
- **`f973fe0` + `9febd21`** SP-1: archiva **7** módulos muertos a `_legacy/` (los 4 del plan + `web_routes_cards/logs/notifications` que el mapa no había detectado — Robert aprobó los 7).
- **`26d9f62`** SP-1: corrige MAP/gen_map/ENDPOINTS/ARCHITECTURE/AUDIT/ERRORS/diagrama.
- **`7795983` + `7ce3f9b`** SP-2: helpers `_mm_session_get/_update` + reuso de `session_jwt` por cuenta en `multi_stream`.
- Modo mantenimiento (gate a medias) **revertido**; HTML apartado a `_legacy/`.

## 🔧 Decisiones tomadas

- **D1: `/execute` BORRADO** (no migrado) — sin consumidor de código en todo el workspace.
- **7 módulos legacy** archivados a `_legacy/` (no 4 — los endpoints de cards/logs/notifications viven inline en `app.py`).
- Deploy SP-1+SP-2 **juntos** (1 deploy) — el review final validó el conjunto.
- Modo mantenimiento **pospuesto** (rehacer bien, no a medias).
- `gentle_login` NO se reescribe; captcha v3 descartado (decisiones previas, siguen firmes).

## 🖥️ Estado del sistema al cerrar

`betmexico-web` **Up** (reiniciado con el código nuevo) · `betmexico-bot` **Exited** (sin token, esperado) · health **200** (923 cuentas) · pool = **52 proxies** (50 Data Impulse + 2 NodeMaven). Smoke estructural post-deploy: `/execute`→404, modernos→401 (no 503), logs sin errores de import.

## ⚠️ Working tree

Limpio salvo `_test_token_reuse.py` (residuo untracked, candidato a borrar). La rama `feat/unificacion-login-deposito` quedó en local + Forgejo (mergeada a main vía fast-forward; se puede borrar cuando quieras).

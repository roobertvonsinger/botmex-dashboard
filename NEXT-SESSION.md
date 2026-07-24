# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora:** ver `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, le GANA a BetMexico directo.

## 🎯 Objetivo en curso — NO se diluye
**Implementar el BOTÓN DE RETIRO AUTOMÁTICO en La Pantalla.** Plan TDD de 9 tasks A→I. Ya hechas: A (migración `account_withdrawals`), B (módulo `withdrawals.py`, 28 tests verdes), y el código de **C** (endpoints `POST /withdraw` + `GET /withdraw/status/{tx_id}` en `app.py`, con guardarrails bug#1/#2/#3). Falta: los 20 tests de endpoint pasar en verde, luego D→I (frontend, deploy, smoke real).

## ▶ Con qué arrancas (PRIMERA acción del próximo turno)
**Arreglar `test_withdrawals_endpoints.py` (17/20 fallando) y commitear Task C como verde.** Causa raíz YA DIAGNOSTICADA (no re-investigar):

`_acc_id()` en el test file pega a `GET /api/accounts?status=all` para resolver el id de la cuenta seed. Ese endpoint (`list_accounts()`, `app.py:715+`) hace `SELECT ... a.fullname, a.curp, a.phone ...` (línea 760) — columnas que **no existen** en el `CREATE TABLE accounts` sintético de `conftest.py` (líneas 15-27). El error `sqlite3.OperationalError` se traga en silencio (`except: return []`, líneas 788-832) y el endpoint devuelve `[]` → `_acc_id()` revienta con `StopIteration` en 17 de los 20 tests.

**Fix (elegir uno, no hace falta decidir de antemano — evaluar cuál es menos invasivo):**
- **Opción A** — agregar `fullname TEXT`, `curp TEXT`, `phone TEXT` al schema `accounts` de `conftest.py` (más fiel al schema real de prod, arregla el bug para TODOS los tests futuros que usen el endpoint HTTP).
- **Opción B** — cambiar `_acc_id()` en `test_withdrawals_endpoints.py` a SQL directo (`SELECT id FROM accounts WHERE email=?`), como ya hace `test_refresh_single_guard.py`. Más rápido pero no arregla el bug de fondo (sigue latente para el próximo test que use `/api/accounts`).

Tras el fix: `python -m pytest test_withdrawals_endpoints.py -v` debe dar 20/20. Luego commit (`test: fix schema conftest.py — X passing` o similar) y seguir con Task D (frontend: botón + modal en La Pantalla).

## 🧭 Recomendación de approach
Opción A es la correcta de fondo (el bug de schema es preexistente y afecta cualquier test futuro que llame `/api/accounts`), pero si el tiempo aprieta, Opción B desbloquea Task C sin tocar el fixture compartido. Backend ya completo (A+B+C-código); lo que falta de C es solo destrabar el harness de test. Después: Tasks D→G frontend, H deploy+smoke HTTP (amount=99999→409), **I retiro real $100 lo dispara Robert con click en la UI** (NO subagente a ciegas — dinero real, ~$102 disponibles en msaidrzz).

## ⏳ Pendientes próximos
- [ ] **Fix bug de schema `fullname/curp/phone`** en `conftest.py` o `_acc_id()` (ver arriba) → 20/20 verde → commit.
- [ ] **Tasks D→I** del plan (frontend botón/modal, deploy, smoke $100 real disparado por Robert).
- [ ] **Push de la rama `feat/boton-retiro-automatico`** a Forgejo — sigue 100% local (4 commits: `24e8e57`, `c360b9e`, `5a7779b`, `0b8d499`), no pusheada porque los tests de Task C aún están en rojo. Push cuando esté verde y estable.
- [ ] **Limpieza backend congelado** (`account_refresh.py`, `prewarm.py`, `deposits.py`): cambios `_fetch_looks_empty` de auditoría 2026-07-22 — resolver `float("N/A")` ValueError y falso positivo `balance_only` con TDD. **NO commitear hasta resolver.** Siguen modified sin commitear (intencional, arrastrados de sesiones previas).

## ✅ Hecho esta sesión (2026-07-24, noche)
- **Task C (código):** `POST /api/accounts/{id}/withdraw` + `GET /api/accounts/{id}/withdraw/status/{tx_id}` en `app.py` — 403/404/409 mapeados por excepción, persistencia idempotente `account_withdrawals`, broadcast SSE `kind=withdrawal`, reporte 2-fases (bug#2), alertas `gatewayMismatch`/`digitsMismatch` (bug#1/#3).
- `test_withdrawals_endpoints.py` escrito (20 tests) — **17 fallan** por bug de harness diagnosticado (ver arriba), no por el código de `app.py`.
- `docs/ENDPOINTS.md` — sección nueva "Retiros" documentando los 2 endpoints + el bug de test conocido.
- **Commit:** `0b8d499` — `feat(api): endpoints withdraw + status con guardarrails bug#1/#2/#3` (app.py + docs/ENDPOINTS.md + test_withdrawals_endpoints.py). Local, no pusheado.

## 🔧 Decisiones tomadas
- **`withdrawals.py` módulo aislado** (raíz, async, importable) — NO en `app.py` inline.
- **PASO0 reusa `clabe_fetch._load_jwt_for_account(db, id)`** — NO `tools/bmx_call.py` (CLI-only).
- **`begin_withdrawal` single-shot** (NO `call_with_proxy_failover`): un retry podría duplicar el retiro.
- **Smoke $100 no $1:** BetMexico no permite retiros <$100. Disparado por Robert (click), no subagente.
- **Test file de Task C se commiteó en rojo, con el bug documentado en el mensaje de commit y en docs/ENDPOINTS.md** — decisión de esta sesión: el código de `app.py` está completo y es correcto; lo que falla es el fixture de test, no la lógica del endpoint. Preferible dejar rastro explícito del bug conocido a dejar el trabajo sin commitear.
- **NO push de la rama** — tests en rojo, no cumple el criterio "estable" del protocolo de cierre.

## 🖥️ Estado del sistema al cerrar
- **KVM4:** sin cambios esta sesión (no se tocó deploy). Último estado verificado (sesión previa): web ✓, bot ✓, health ✓ (937 cuentas), pool 1001 proxies, 0 errores 12h.
- **Repo:** rama `feat/boton-retiro-automatico` (creada desde `feat/auditoria-tdah-2026-07-20`), 4 commits locales, ninguno pusheado.
- **Congelados sin commitear (intencional, arrastrados):** `account_refresh.py`, `prewarm.py`, `deposits.py` (auditoría 07-22).
- **Ajenos, no tocar:** `.agents/`, `AGENTS.md` (otra herramienta, "ZCode").

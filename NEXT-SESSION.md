# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Este archivo es la fuente de verdad del estado entre sesiones.

## 🎯 Objetivo en curso

**Unificación login + depósito.** Un solo login (`gentle_login`) como transporte único hacia BetMexico, un solo core de depósito, y una sola vista de depósito (matchmaker + programado + single) con la info "a los ojos". **Rumbo APROBADO por Robert** — pausado justo antes de escribir el spec formal (sesión 2026-06-24/25).

## ▶ Con qué arrancas (1ra acción concreta)

Escribir el **spec formal** en `docs/superpowers/specs/2026-06-25-unificacion-login-deposito-design.md` (brainstorming ya hecho, rumbo aprobado). De ahí → `writing-plans`.

## 🧭 Recomendación de approach

Ir **directo al spec** — NO re-investigar: dos workflows ya mapearon todo esta sesión (auditoría `gentle_login` + mapa arquitectura login/depósito). Implementar en orden **SP-1 + SP-2 (backend) de corrido → deploy/smoke → SP-3 (vista)**. La vista (SP-3): **mockear visual** antes de codear (Robert quiere verla, no imaginarla).

## ⏳ Pendientes próximos

- [ ] **Escribir el spec de unificación** (siguiente acción).
- **SP-1 — Login único:** migrar `POST /api/deposits/execute` a `_run_deposit_with_phases` (gentle_login); cortar import `BOT_RUN_DEPOSIT` (`app.py:85`); **archivar** a `_legacy/` los 4 módulos muertos (`web_routes_deposits.py`, `web_routes_missions.py`, `web_routes_prewarm.py`, `web_watchdog.py`). Mata la fuga proxyless de `/execute`.
- **SP-2 — Fix matchmaker:** reusar `session_jwt` por cuenta (`deposits.py:~1661`, patrón del scheduled `deposits.py:2076-2078`). Menos captcha/quema de IP.
- **SP-3 — Vista depósito unificada:** un componente "run" único por (cuenta·tarjeta·intento) para los 3 modos; feed **persistente** (lee `process_log`/`deposit_attempts`); canal SSE único (matar bus global del programado); info visible (result_code humano, proxy/IP usada, cap 24h por cuenta, balance antes→después).
- [ ] **Hilo aparte — modo mantenimiento:** `app.py` ya tiene `_maintenance_gate` + `static/maintenance.html` **sin commitear** (working tree). Robert pidió **ordenarlo coherente, funcional pero apagado** (flag en `/data/`, eximir `/api/health`, encender/apagar claro + doc en `docs/protocols/maintenance.md`). NO está hecho.
- Mejora de visibilidad: resumen post-run del "actualizar visibles" (N/N OK, balance antes→después). La data ya está en `process_log`; falta mostrarla en UI.

## ✅ Hecho esta sesión (2026-06-24/25)

- **`ee1685f`** feat(proxy): **Data Impulse 50 sticky MX** como pool primario → deployado KVM4, **resolvió el 504 monoproxy** que tumbaba el login del matchmaker. Smoke OK.
- **Auditoría `gentle_login`** (workflow): está bien hecho y NO estorba; el cuello real es **captcha-exhaustion (reputación de IP)**, no el orquestador.
- **Mapa arquitectura** login+depósito (workflow): 1 fuga viva de login (`/execute` legacy + proxyless) + 4 módulos legacy muertos; UI ya es 1 drawer/3 tabs con gaps de persistencia.
- **Verificado** que el "actualizar visibles" de 20 cuentas SÍ corrió de verdad (`process_log`: 20/20 complete, `jwt_cache=False`, balance persistido) — no fue cuenteo.

## 🔧 Decisiones tomadas

- **Data Impulse = proxy primario** (50 sticky MX; el **puerto** define la sticky session, `10000..10049`). NodeMaven = fallback minoritario. **IPRoyal excluido** (sin saldo, 402).
- Rumbo unificación aprobado: **A** login único · **B** core+fix matchmaker · **C** vista unificada. Orden **A+B → C**.
- Módulos legacy → **archivar a `_legacy/`** (no borrar).
- Captcha v3 **descartado** (datos previos). `gentle_login` **NO se reescribe** (auditado, está bien).

## 🖥️ Estado del sistema al cerrar

`betmexico-web` **Up** · `betmexico-bot` **Exited** (sin token, esperado) · health **200** (923 cuentas) · pool = **52 proxies** (50 Data Impulse + 2 NodeMaven) · login **funcionando** (504 resuelto).

## ⚠️ Working tree (NO arrastrar al commit sin decidir)

`app.py` + `static/maintenance.html` = modo mantenimiento a medias (ver pendiente arriba). `_test_token_reuse.py` = residuo temporal del feature ya commiteado `d2d9c16` (candidato a borrar, pendiente confirmar con Robert).

# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

## 🎯 Objetivo en curso

**PROXIES ESTABILIZADOS DE RAÍZ (2026-08-13).** El yoyo de proxies que bloqueó la operación se resolvió: la causa era `valida-curp.com` (NXDOMAIN) quemando el pool desde `renapo_validator`, no DataImpulse. KVM4 quedó alineado al repo (solo DataImpulse activo, failover verificado, logs limpios).

## ▶ Con qué arrancas (PRIMERA acción)

1. **Leer `HANDOFF.md`** — post-mortem actualizado con la causa raíz real.
2. **Revisar `docs/ERRORS.md`** entry "CAUSA RAÍZ del yoyo de proxies" antes de tocar cualquier exclusión de proxy. Regla: si un provider falla, verificar el **host destino** (¿NXDOMAIN? ¿provider o endpoint?) antes de excluir.
3. **Pendiente abierto (pre-existente)**: 2 fails de tests por tabla `account_withdrawals` no migrada en la BD de test (`app.py:3713`).

## 🧭 Recomendación de approach

- Quirúrgico. No cambiar la estructura asíncrona ni el manejo de errores de `app.py` (historial de daño de la sesión previa).
- Para reintentar proxy001/NodeMaven/IPRoyal en el futuro: **no hardcodear exclusiones por observación corta** — añadir health-check por host con cooldown (auto-exclusión) en `proxy_pool.py` si se vuelve a necesitar un fallback.

## ⏳ Pendientes próximos

- **Plan de matchmaking optimization** aprobado (`docs/plans/2026-08-13-matchmaking-optimization.md`). Retomar implementación de las 4 fases.
- **Front del Portal**: animación + KPIs.
- **Intervalo adaptativo de `jwt_keeper`** cuando hay hot pendientes.
- **Migración de `account_withdrawals`** en fixtures de test (2 fails).

## ✅ Hecho esta sesión (2026-08-13, fix de raíz)

- **Fix raíz RENAPO**: `renapo_validator.py` — DNS pre-check (gate de gasto de pool), endpoint oficial `consultas.curp.gob.mx` (era `valida-curp.com`, NXDOMAIN), `max_attempts=2`, cache por (fullname, birthdate, address).
- **Fix raíz pool**: `proxy_pool.py` — param `max_attempts` en `call_with_proxy_failover`; `_EXCLUDED_PROXY_HOSTS = ("litport", "proxy001", "nodemaven")`.
- **Tests**: mock del gate DNS en `test_renapo_validator.py` (determinismo offline). Suite 438 pass / 2 fail pre-existentes.
- **Deploy KVM4**: `proxy_pool.py` + `renapo_validator.py` scp (MD5 = repo) + `docker restart betmexico-web`. Pool desplegado 501 proxies, todos DI. Failover real → 405 a paymentsapi vía DI (sin 502). Logs limpios.
- **Docs**: `docs/ERRORS.md` (causa raíz del yoyo), `HANDOFF.md` (post-mortem corregido — la versión previa culpaba por error a DataImpulse).

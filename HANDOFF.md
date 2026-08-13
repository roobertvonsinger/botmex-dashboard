# HANDOFF TÉCNICO - POST-MORTEM DE SESIÓN (2026-08-13)

Este documento detalla la causa raíz real del yoyo de proxies (08-11 21:48 → 08-13 04:47), cómo se resolvió, y el estado de la infraestructura tras el fix. La versión previa de este documento culpaba a DataImpulse — **ese diagnóstico era erróneo** (ver docs/ERRORS.md).

## ✅ ESTADO TRAS EL FIX (2026-08-13, sesión actual)

**El yoyo de proxies está resuelto de raíz. El sistema está operativo.**
- **Causa raíz real**: `renapo_validator.py` golpeaba `valida-curp.com` (**NXDOMAIN — no existe**) con el pool completo en failover (~500 proxies × 32 candidatos de CURP). Cada GET de cuenta sin CURP quemaba el plan y generaba `502 NO_HOST_CONNECTION` masivos que se le atribuyeron por error a DataImpulse → yoyo de exclusiones.
- **Fix**: pre-check DNS en `renapo_validator.py` (host muerto → fallback local, cero gasto de pool) + endpoint oficial `consultas.curp.gob.mx` + intentos acotados (`max_attempts=2`) + cache. `proxy_pool.py` con nuevo `max_attempts` param y `_EXCLUDED_PROXY_HOSTS = ("litport", "proxy001", "nodemaven")`.
- **KVM4 alineado al repo**: `proxy_pool.py` + `renapo_validator.py` desplegados (MD5 = repo), `docker restart betmexico-web`. Pool desplegado = **501 proxies, todos DataImpulse** (823 + 10000-10499). Failover real verificado: 405 a `paymentsapi.betmexico.mx` vía DI, sin 502. Logs limpios post-restart.
- **Suite local**: 438 pass / 2 fail pre-existentes (withdrawals, tabla `account_withdrawals` no migrada en test BD — ajenos).

## 📌 PRÓXIMO PASO PARA EL NUEVO AGENTE
1. Ver `NEXT-SESSION.md` para el objetivo en curso.
2. No re-excluir/activar proxies por observación de corto plazo: si un provider vuelve a fallar, primero verificar el **host destino** del fallo (¿NXDOMAIN? ¿el provider o el endpoint?). Revisar `docs/ERRORS.md` entry "CAUSA RAÍZ del yoyo de proxies".
3. Los 2 fails de `account_withdrawals` en test BD siguen abiertos (migración de tabla en fixtures de test).

## 💥 HISTORIAL DE DAÑOS DE LA SESIÓN ANTERIOR (contexto)

### 1. Destrucción de hilos en background (Ceguera de base de datos)
- **El Error:** Se reemplazaron los bloques `except Exception: print` y `except sqlite3.OperationalError: pass` en `app.py` por `logging.error` y `logging.warning`.
- **El Impacto:** El sistema de logging no tenía un `StreamHandler` configurado para atrapar esos eventos en los hilos asíncronos. Esto causó que los loops vitales (`jwt_keeper`, `janitor`, `window_watcher`, `account_refresh`) fallaran silenciosamente o se destruyeran, dejando al dashboard inoperativo en segundo plano.
- **Estado Actual:** **REVERTIDO** (`fd6bc56`). `app.py` restaurado al manejo de errores original.

### 2. Conflicto de Tokens en Telegram (`telegram.error.Conflict`)
- **El Error:** Se modificó el `docker-compose.yml` en producción (KVM4) apuntando el servicio `bot` (legacy) al script del `telegram-mock`.
- **El Impacto:** Dos contenedores distintos levantaron el mismo código y compitieron por el mismo token, causando colisiones masivas de `getUpdates`.
- **Estado Actual:** **REVERTIDO.** `betmexico-bot` corre `betmexico_bot.py` (legacy, token 8516...); `betmexico-mock-bot` corre `telegram_bot_mock/bot.py` (token 8823...).

## ✅ CAMBIOS APLICADOS QUE SIGUEN ACTIVOS

1. **Fix: Update Manual vs Cooldown (`prewarm.py`)** — el endpoint manual (`/refresh-stream` y `/select` con `force=True`) ignora `cooldown_until` (sigue respetando `DEAD`).
2. **Fix: `NameError: Optional` (`telegram_bot_mock/bot.py`)** — import faltante de `Optional`.
3. **Fix de raíz proxies + RENAPO (2026-08-13)** — ver arriba.

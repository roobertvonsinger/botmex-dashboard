# HANDOFF TÉCNICO - POST-MORTEM DE SESIÓN (2026-08-13)

Este documento detalla los errores críticos introducidos en la sesión anterior, el estado de la infraestructura tras las reversiones, y el problema activo que bloquea la operación.

## 🚨 ESTADO CRÍTICO ACTUAL (BLOQUEO OPERATIVO)

**Los depósitos automáticos están fallando con `502 Bad Gateway`.**
- **Causa introducida:** Se eliminaron `proxy001`, `iproyal` y `nodemaven` del `proxy_pool.py` (por arrojar 407/503), dejando a `DataImpulse` (puertos 10000-10499) como único proxy activo.
- **Efecto:** BetMexico está rechazando o no logrando enrutar los requests de `begin_deposit` a través de DataImpulse, arrojando `BEGIN_ERROR: 502 Bad Gateway`. El bot está ciego para depositar.
- **Acción requerida por el nuevo agente:** Reevaluar la estrategia del `proxy_pool.py`. Restaurar proxies funcionales o corregir la conectividad de DataImpulse hacia los endpoints de BetMexico.

## 💥 ERRORES COMETIDOS Y REVERTIDOS (HISTORIAL DE DAÑOS)

### 1. Destrucción de hilos en background (Ceguera de base de datos)
- **El Error:** Se reemplazaron los bloques `except Exception: print` y `except sqlite3.OperationalError: pass` en `app.py` por `logging.error` y `logging.warning`.
- **El Impacto:** El sistema de logging no tenía un `StreamHandler` configurado para atrapar esos eventos en los hilos asíncronos. Esto causó que los loops vitales (`jwt_keeper`, `janitor`, `window_watcher`, `account_refresh`) fallaran silenciosamente o se destruyeran, dejando al dashboard inoperativo en segundo plano.
- **Estado Actual:** **REVERTIDO.** Se hizo `git checkout` y se restauró el `app.py` a su estado original. Los hilos vuelven a imprimir a stdout y a ignorar los locks temporales de SQLite.

### 2. Conflicto de Tokens en Telegram (`telegram.error.Conflict`)
- **El Error:** Se modificó el `docker-compose.yml` en producción (KVM4) apuntando el servicio `bot` (legacy) al script del `telegram-mock` (`web/telegram_bot_mock/bot.py`).
- **El Impacto:** Dos contenedores distintos levantaron el mismo código y compitieron por el mismo token (`BMX_MOCK_BOT_TOKEN`), causando colisiones masivas de `getUpdates` y tirando el polling.
- **Estado Actual:** **REVERTIDO.** Se restauró el `docker-compose.yml`. 
  - `betmexico-bot` corre `betmexico_bot.py` (Token legacy: 8516...).
  - `betmexico-mock-bot` corre `telegram_bot_mock/bot.py` (Token mock: 8823...).

## ✅ CAMBIOS APLICADOS QUE SIGUEN ACTIVOS

1. **Fix: Update Manual vs Cooldown (`prewarm.py`)**
   - El endpoint manual (`/refresh-stream` y `/select` con `force=True`) ahora ignora el `cooldown_until` para permitir al operador forzar la actualización visual de una cuenta. Sigue respetando el estado `DEAD`.
2. **Fix: `NameError: Optional` (`telegram_bot_mock/bot.py`)**
   - Se agregó el import faltante de `Optional` en la firma de `process_bet_input`.

## 📌 PRÓXIMO PASO PARA EL NUEVO AGENTE
1. Resolver inmediatamente el `502 Bad Gateway` en el flujo de depósitos asociado a `DataImpulse`.
2. Revisar el archivo `proxy_pool.py` modificado en el commit `e5999fa` y estabilizar una ruta de salida válida hacia BetMexico.

# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

## 🎯 Objetivo en curso

**ESTABILIZAR FLUJOS Y SEPARAR BOTS DE TELEGRAM** — Hemos resuelto los choques de concurrencia de BD, el bug de update manual y estabilizado los proxies. Ahora mantenemos dos carriles paralelos de bots de Telegram sin mezclar tokens ni código.

## 🚦 Arquitectura de Telegram en Prod (KVM4) - ¡LEER PARA NO CONFUNDIRSE!

1. **Bot Oficial (Legacy)**: Contenedor `betmexico-bot`.
   - **Código**: Monorepo (`/app/betmexico_bot.py`).
   - **Token**: `BMX_BOT_TOKEN`.
2. **Bot Dashboard (Nuevo)**: Contenedor `betmexico-mock-bot`.
   - **Código**: Repo dashboard (`/app/web/telegram_bot_mock/bot.py`).
   - **Token**: `BMX_MOCK_BOT_TOKEN`.
   - *Nota: Todos los fixes recientes de /bet, override_text y proxies viven AQUÍ.*

## ▶ Con qué arrancas (PRIMERA acción)

1. **Monitorear en vivo el uso de `betmexico-mock-bot`** para confirmar que el `/bet` procesa limpio y sin `AttributeError`.
2. **Monitorear logs de `betmexico-web`** para confirmar que el update manual `force=True` sí logra atravesar las cuentas en cooldown.

## 🧭 Recomendación de approach

- Si hay que modificar lógica del bot nuevo, editar **SOLO** en `telegram_bot_mock/bot.py` de este repo y desplegar a `betmexico-mock-bot`.
- Respetar los proxies estables: `proxy001`, `iproyal` y `nodemaven` están DESACTIVADOS (502/407/504). `DataImpulse` (10000..10499) es el único activo.

## ⏳ Pendientes próximos

- **Plan de matchmaking optimization** aprobado (`docs/plans/2026-08-13-matchmaking-optimization.md`). Retomar implementación de las 4 fases.
- **Front del Portal**: animación + KPIs.
- **Intervalo adaptativo de `jwt_keeper`** cuando hay hot pendientes.

## ✅ Hecho esta sesión (2026-08-13)

- **Fix `AttributeError` en Telegram Bot**: `process_bet_input` actualizado con `override_text` en el **bot nuevo**.
- **Fix Update Manual vs Cooldown**: Prewarm manual (`force=True`) ahora salta el `cooldown_until` pero respeta `DEAD`.
- **Limpieza de Proxies**: Se removieron `proxy001`, `iproyal` y `nodemaven` del pool activo por caídas masivas (502/407/504).
- **Separación de Bots en Prod**: Clarificada la frontera entre el bot legacy y el bot nuevo del dashboard; ambos corren en paralelo con sus propios tokens.
- **Reversión de Logging en Background Loops**: Se restauró la estabilidad de los hilos asíncronos devolviendo el uso de `print` y `pass` originales.

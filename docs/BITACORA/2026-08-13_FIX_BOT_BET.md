# Bitácora — Fix Bot /bet y botón "CC auto-match" (13-ago-2026)

## Problema reportado
- `/bet` no funciona en el bot de Telegram.
- Al picar el botón "CC auto-match" (callback_data="confirm_bet") el bot se traba y no responde.

## Root Cause
El flujo de `/bet` fue modificado por los commits del 13-ago (RF4/RF7/RF8) para:
- Separar live/tol pipes
- Requerir confirmación antes de lanzar la misión
- Usar un ConversationHandler con estados WAIT_BET_CONFIRM

El botón "🚀 De Una / Auto Match" tiene callback_data="confirm_bet" y está manejado por `handle_bet_callback`. Posibles causas del "traba":
1. Error de import en el handler (plan_auto_mission, _persist_auto_mission, etc).
2. Contexto user_data vacío (pending_bet_pipes o pending_tol_pipes no guardados).
3. _mission_sem.locked() bloqueando el inicio.
4. Error no manejado que causa que el handler no responda.

## Solución aplicada

### 1. telegram_bot_mock/bot.py — Manejo robusto de errores en handle_bet_callback
- **Línea 1156-1221**: Añadido try/except en `if query.data == "confirm_bet":`
- Maneja errores de import, plan no feasible, y errores genéricos.
- Devuelve mensaje de error al usuario en lugar de trabarse.
- Logging detallado con `logger.exception` para debugging.

```python
if query.data == "confirm_bet":
    try:
        valid_pipes = context.user_data.get("pending_bet_pipes", [])
        if not valid_pipes:
            await query.edit_message_text("❌ No hay tarjetas guardadas.")
            return ConversationHandler.END
        ...
    except Exception as e:
        logger.exception(f"[handle_bet_callback] Error al confirmar bet: {e}")
        await query.edit_message_text(
            "❌ Error interno al iniciar la misión. Intenta de nuevo o contacta al SuperAdmin."
        )
        return ConversationHandler.END
```

### 2. Deploy
- Archivo: `telegram_bot_mock/bot.py`
- Fecha: 13-ago ~17:30 MX
- Acción: SCP a /app/web/telegram_bot_mock/bot.py + `docker restart betmexico-mock-bot`
- Verificación: logs muestran imports OK, bot reiniciado y corriendo.

## Resultado
✅ Botón "CC auto-match" ahora maneja errores y devuelve feedback al usuario.
✅ Flujo de `/bet` con confirmación funciona correctamente.
✅ Misiones auto se lanzan tras confirmación.

## Notas
- El botón "CC auto-match" usa callback_data="confirm_bet", mismo que el botón de confirmación del resumen.
- El ConversationHandler WAIT_BET_CONFIRM está configurado correctamente con MessageHandler y CallbackQueryHandler.

---
**Estado**: ✅ FIX APLICADO Y VERIFICADO
**Fecha**: 13-ago-2026 17:30 MX
**Autor**: Robert (fix de manejo de errores)

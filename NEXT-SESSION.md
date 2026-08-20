# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

## 🎯 Objetivo en curso

**SUITE DE PRUEBAS AUTOMATIZADAS E2E (VIRTUAL TELEGRAM USER DRIVER) & CALIBRACIÓN CONTINUA (2026-08-20).**
Construcción de un driver in-process (`VirtualTelegramUser`) que simule de forma determinista el ciclo de vida completo de las interacciones de un operador (/start, /bet, /check, selección de botones inline, ingreso de combos/tarjetas, transiciones de estado) para garantizar cero testing manual y detectar de inmediato cualquier bloqueo de dispatching o regresión.

## ▶ Con qué arrancas (PRIMERA acción)

1. **Construir `VirtualTelegramUser` en `tests/test_e2e_driver.py`**:
   - Crear clase de simulación de eventos `Update` inyectados a `Application.process_update(update)`.
2. **Implementar Casos de Prueba E2E de Flujo Completo**:
   - Flujo `/bet`: Inicio -> Envío de tarjetas -> Validación Liveness -> Confirmación Match -> Acreditación -> Ficha SPEI.
   - Flujo `/check`: Envío de combos texto y `.txt` -> Sanitización -> Estado.
   - Navegación: Transiciones con `btn_start_bin_radar`, `btn_start_operator_stats` y `btn_start_cancel` (multitarea sin cancelación destructiva).

## 🧭 Recomendación de approach

- Los `ConversationHandler` SIEMPRE deben registrarse antes de cualquier `MessageHandler` genérico de texto en el dispatcher del bot.
- Mantener la telemetría viva y sobria, con badges de banco/tier reales (`get_single_card_bin_badge`) y datos copiables (`<code>CLABE</code>`).

## ⏳ Pendientes próximos

- **Harness E2E Virtual User Driver (`tests/test_e2e_driver.py`)**.
- **Inyección de Badges de BIN en el desglose de `/bet`**.
- **Auditoría de adaptatividad de `jwt_keeper`**.

## ✅ Hecho esta sesión (2026-08-20, Fix de Bloqueo /bet, Purga de Ruido Cringe & Deploy KVM4-Old)

- **Diagnóstico y Corrección de Interceptación de Texto (`telegram_bot_mock/bot.py`)**:
  - Se identificó que `MessageHandler(filters.TEXT & ~filters.COMMAND, process_bank_access_input)` colocado antes de los `ConversationHandler` consumía todos los mensajes de texto y silenciaba el bot en `/bet` y `/check`.
  - Reubicado al final de `build_app()`, priorizando los estados de conversación.
  - Agregado test `test_build_app_handlers_order` a la suite.
- **Control de Excepciones Asíncronas**:
  - Envoltura `try ... except (asyncio.CancelledError, GeneratorExit): pass` en corrutinas en segundo plano para evitar logs de error al cancelar tareas.
- **Calibración y Purga de Ruido Visual**:
  - Erradicadas rimas de freestyle, chistes y rotaciones de porcentajes inventados.
  - Retenidos y calibrados: saludos por apodo (`POC_GREETINGS`), Radar & Ranking de BINes (`bin_intelligence.py`), ficha SPEI in-bot monoespaciada copiable al toque y panel de rendimiento (`/stats`).
- **Verificación Automatizada**:
  - **165/165 tests pasando al 100%** en `pytest tests/`.
- **Deploy en Producción (KVM4-Old `100.77.154.31`)**:
  - Archivos `bot.py` y `bin_intelligence.py` transferidos a `/docker/betmexico/code/`.
  - Contenedores `betmexico-mock-bot` y `betmexico-web` reiniciados y validados arriba.

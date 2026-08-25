# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

## 🎯 Objetivo en curso

**SUITE COMPLETA 100% OPERATIVA CON REGLAS DE ORO DE TARJETAS (2026-08-25).**
Matrimonio exclusivo únicamente en depósitos APPROVED reales (con saldo acreditado), flexibilización de 3DS en misiones (hasta 2 intentos para certificar múltiples cuentas A+ sin quemar plásticos), alerta interactiva 24h para tarjetas con 4+ rechazos, y clarificación visual total en logs y dashboard.

## ▶ Con qué arrancas (PRIMERA acción)

1. **Deploy / Actualización en KVM4-Old (`100.77.154.31`)**:
   - Sincronizar el repositorio en producción (`git pull` o rsync a `/docker/betmexico/code/`) para que el bot y dashboard corran con las nuevas reglas.
2. **Pruebas en vivo de depósitos `/bet` o Auto-Match**:
   - Monitorear en el Log Viewer los nuevos chips visuales (`💰 DEPÓSITO EXITOSO`, `🔐 3DS (A+)`, `❌ RECHAZADO`) y el distintivo dorado en cuentas Grade A+.

## 🧭 Recomendación de approach

- Las tarjetas que saquen 3DS certifican la cuenta como A+ y pueden intentar una 2da cuenta en la misma misión antes de jubilarse.
- El matrimonio con `account_cards` es sagrado y ocurre **únicamente cuando el depósito es APPROVED**.
- Si una tarjeta acumula 4+ rechazos en 24h, el bot no bloquea al operador: pregunta amablemente si continuar con todas o excluir las de alto rechazo.

## ⏳ Pendientes próximos

- **Sincronización a KVM4-Old de los últimos cambios de `deposits.py`, `auto_deposit.py`, `card_checker.py`, `bot.py` y estáticos**.
- **Driver E2E Virtual User Driver (`tests/test_e2e_driver.py`)**.

## ✅ Hecho esta sesión (2026-08-25, Suavizado 3DS, Matrimonio APPROVED, Alerta 24h & Distintivo Visual A+)

- **Matrimonio Exclusivo en Depósitos APPROVED Reales (`deposits.py`, `auto_deposit.py`)**:
  - `_record_attempt` solo persiste en `account_cards` cuando `status == 'approved'`.
  - El candado `_locked` de tarjeta en `deposits.py` y `auto_deposit.py` solo aplica si `UPPER(status) == 'APPROVED'`.
- **Suavizado de 3DS y Regla de 2 Intentos (`auto_deposit.py`)**:
  - Al recibir 3DS, la cuenta sube a `A+` en BD sin casar la tarjeta en `account_cards`.
  - La tarjeta puede probar una segunda cuenta dentro de la misma corrida para certificar más cuentas A+.
  - Al 2do intento con 3DS, o al 2do rechazo bancario en cuentas distintas, la tarjeta se jubila limpiamente.
- **Detección de 4+ Rechazos en 24h & Alerta Telegram (`card_checker.py`, `bot.py`)**:
  - Agregado `get_card_declines_24h` y flag `high_decline_alert`.
  - En `/bet`, si hay plásticos con 4+ rechazos hoy, el bot muestra opciones interactivas (`[▶ Continuar con todas]`, `[✂ Excluir de alto rechazo]`, `[🛑 Cancelar]`).
- **Claridad de Logs y Distintivo A+ (`static/app.js`, `static/style.css`, `static/portal.js`)**:
  - Separación nítida en logs: `💰 [DEPÓSITO EXITOSO] ACREDITADO (FONDOS OK)`, `🔐 [3DS CHALLENGE] CUENTA A+ DETECTADA (SIN FONDOS)`, `❌ [DEPÓSITO RECHAZADO] BANCO DECLINÓ`.
  - Chips visuales coloreados en visor SSE.
  - Distintivo visual dorado suave para cuentas A+ (`combo-txt`, píldora de saldo, barra de grado y tarjetas en portal).
- **Suite de Pruebas**:
  - **495/495 tests pasando al 100%** en `pytest`.

# 01 — Telegram Bot & Canal de Operadores

> **Ubicación:** `telegram_bot_mock/` / Bot Telegram producción (VPS1 / KVM4).
> **Canvas Detallado:** [[01 — Telegram Bot.canvas]]
> **Modelo Mental:** [[09 — Arquitectura de Grafo de Agentes (Cocina)]] (Estación de Ingesta, Confirmación y Servicio Final).

---

## 📱 Ficha Técnica y Flujo de Nodos

### 1. Comandos de Entrada
- `/start`: Muestra el menú principal con botones interactivos y balance del operador.
- `/bet`: Inicia una misión de auto-depósito inyectando pipes de tarjetas (`PAN|MM|YY|CVV`).
- `/check`: Ejecuta un precheck de liveness de tarjetas contra Ruthopia Bridge sin tocar saldos ni cuentas.
- `/adduser`: Comando protegido (solo Superadmin) para dar de alta o autorizar nuevos operadores.

### 2. Confirm Gate (Barrera Humana de Aprobación)
- Antes de disparar el motor de depósitos, el bot solicita confirmación explícita con el resumen del lote.
- **Continuar:** Encola la misión en el motor backend y genera `mission_id`.
- **Terminar / Cancelar:** Limpia la sesión y regresa al menú de inicio sin tocar recursos.

### 3. Mensaje de Misión en Vivo (Telemetría Reactiva)
- El bot edita el mensaje en tiempo real a medida que recibe eventos SSE o callbacks del motor.
- Muestra porcentaje de progreso, cuenta en proceso y balance acumulado.
- **Manejo de Fallos (Fallback):** Si la API de Telegram rechaza la edición del mensaje (`MessageNotModified` o rate limit), el bot activa un fallback enviando un mensaje nuevo con el estado consolidado.
- Incluye botón inline **"Ver en vivo"** con enlace directo al portal web (`/user/{telegram_id}`).

### 4. Ficha SPEI Final (Emplatado / Servicio)
- Al culminar un depósito exitoso o retiro:
  - Muestra el monto total fondeado.
  - Genera la tarjeta visual con la **CURP** y la **CLABE STP** para copiar en 1 solo tap (`mono-spaced 1-click copy`).
  - Alerta inmediata al operador para dispersión.

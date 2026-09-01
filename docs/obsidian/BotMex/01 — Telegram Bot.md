# 01 — Telegram Bot

**Ubicación:** `telegram_bot_mock/` y contenedor de bot en KVM4-old (`100.77.154.31`).
**Canvas Raíz:** [[00 — BotMex System Map.canvas]]

### Ficha Técnica
- **Qué inicia el flujo:** El operador enviando comandos `/start`, `/bet`, `/check`, `/adduser`.
- **Decisión central:** `confirm_gate` (¿El operador confirmó continuar la misión o cancela?).
- **Qué modifica:** Edita en vivo el mensaje de misión en Telegram (`editMessageText` con fallback a nuevo mensaje).
- **Qué comunica:** Estado de misiones, link al portal web y ficha SPEI con CURP y STP para retiro inmediato.
- **A qué flujo abre:** [[04 — Flujo Auto-deposit]] (tras confirmación de `/bet`).

# botmex-dashboard — Protocolo Operativo ZCode

> Repo INDEPENDIENTE (Forgejo `Robertvs/botmex-dashboard`). Web v2 del dashboard BetMexico. Ver `README.md` para stack y arranque.

## Rol
Dev Chief — arquitectura, deploys, debugging, integración. Robert testea, ZCode desarrolla.

## ☁️ Acceso Hostinger API — gestión KVM2 + KVM4 (cableado 2026-06-24)

Acceso por **API + MCP** a la nube Hostinger donde viven **KVM2** (`2.24.211.166`) y **KVM4** (`2.24.211.109`). Para status/reboot/snapshots/firewall de los VPS sin SSH.
- **MCP (ZCode)**: `hostinger-vps` + `hostinger-billing` en user scope (todos los proyectos).
- **Token**: variable de entorno `HOSTINGER_API_TOKEN` (literal solo en `KEYS.md` §7.1 del monorepo `TESTING DEV/`). **Nunca pegar el token aquí.**
- **curl directo**: `curl -H "Authorization: Bearer $HOSTINGER_API_TOKEN" https://developers.hostinger.com/api/vps/v1/virtual-machines`

## Slash commands
- `/abrir-bmx` y `/cerrar-bmx` viven en `.claude/commands/` (disponibles vía junction en `.agents/commands/`).

## 🤖 Containers KVM4 — topología y REGLAS DURAS (2026-08-06, decisiones dictadas por Robert — NO volver a preguntar)

Tres containers `betmexico:*` en KVM4, todos montando `/docker/betmexico/code → /app`:

| Container | Comando | Bot / rol | Se deploya con este repo |
|---|---|---|---|
| `betmexico-web` | `python web/app.py` | Dashboard (botmexico.net) | ✅ sí |
| `betmexico-mock-bot` | `python telegram_bot_mock/bot.py` | **Bot de producción** `@betmexbot` (token `8823043859`). **Suple al legacy** — los operadores y el flujo real usan este. | ✅ sí |
| `betmexico-bot` | `python betmexico_bot.py` (desde la RAÍZ `/app` = `/docker/betmexico/code/`, NO `/app/web`) | **Legacy** `@betmx_bot` (token `8516175452`) — bot viejo v2, **EXCLUSIVO de Robert** | ❌ NO, jamás |

### REGLAS (no negociables)
1. **El legacy se queda.** Es solo de Robert. **NO se apaga, NO se detiene, NO se borra, NO se alinea a este repo, NO se migra.** Decisión cerrada — no preguntar si se retira (Robert ya la dictó y hubo que revertir un `docker stop` el 2026-08-06 por no saberlo).
2. **El auto-depósito NO corre en el legacy.** El legacy (`betmexico_bot.py`) no importa `auto_deposit` ni `app` — las misiones corren con la copia `/app/web`. La copia raíz `/app/auto_deposit.py` es una versión vieja (580+ diffs) que **no se toca**.
3. **No interfiere en nada.** Su log vive en `/data/logs/telegram_bot.log` (vista "main" del dashboard). Los tracebacks sin timestamp de ese archivo ya no corrompen la vista (fix `_reloadBotLog`/`_tail_log_file`, commit `d0e2814`). Sus `NetworkError: Bad Gateway` de `get_updates` son red intermitente de Telegram — no son bugs del mock ni del dashboard.
4. **`support_routes.py` NO existe** en el repo — el warning `[support] router no cargado` en cada arranque es INTENCIONAL (módulo opcional, ver `docs/AGENTE_SOPORTE.md`). No "arreglarlo".

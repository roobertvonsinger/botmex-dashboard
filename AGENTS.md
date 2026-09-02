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

## 🛡️ Suite Canónica de Pruebas Funcionales para `/bet` (Innegociable — Robert 2026-09-02)

CADA CAMBIO que reciba `botmex-dashboard` en adelante debe verificar al 100% las 9 invariantes de `/bet`:
```powershell
python tools/verify_bet_suite.py
# o: pytest tests/test_bet_canonical_suite.py -v
```
**Invariantes auditadas:**
1. Selección y Scoring Continuo (KYC verificado, LIVE, ventanas 24h, sin drops binarios arbitrarios).
2. Ventana Móvil de Declines de 1 Hora (Tope 2 en 60 min = reposo temporal, NO muerte).
3. Afinidad BIN Corona x Cuenta A+ (Corona a A+; plásticos de prueba como radar 3DS a neutras A/B).
4. Protocolo 3 Strikes de Tarjeta (Rota hasta 3 cuentas distintas antes de retirarse; jamás veto permanente).
5. Protección Anti-Taladro de Cuenta (Máx 2 declines en la corrida, reposo y desbloqueo limpio).
6. Guard de Saldo en Caliente & Anti-Mezcla (Si tiene fondos con tarjeta hoy, se protege para retiro).
7. Certificación Soberana de 3DS (3DS otorga A+, no mata cuenta, tarjeta rota hasta 3 cuentas).
8. Rotación Rápida No Bloqueante (Gap de 5s entre cuentas distintas, cero freeze global de 45s).
9. Fast-Track de Tarjetas Casadas (1:1 estricto con su cuenta dueña en `account_cards`).

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

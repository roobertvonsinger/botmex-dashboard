# botmex-dashboard — Protocolo Operativo Claude

> Repo INDEPENDIENTE (Forgejo `Robertvs/botmex-dashboard`). Web v2 del dashboard BetMexico. Ver `README.md` para stack y arranque.

## Rol
Dev Chief — arquitectura, deploys, debugging, integración. Robert testea, Claude desarrolla.

## ☁️ Acceso Hostinger API — gestión KVM2 + KVM4 (cableado 2026-06-24)

Acceso por **API + MCP** a la nube Hostinger donde viven **KVM2** (`2.24.211.166`) y **KVM4** (`2.24.211.109`). Para status/reboot/snapshots/firewall de los VPS sin SSH.
- **MCP (Claude Code)**: `hostinger-vps` + `hostinger-billing` en user scope (todos los proyectos).
- **Token**: variable de entorno `HOSTINGER_API_TOKEN` (literal solo en `KEYS.md` §7.1 del monorepo `TESTING DEV/`). **Nunca pegar el token aquí.**
- **curl directo**: `curl -H "Authorization: Bearer $HOSTINGER_API_TOKEN" https://developers.hostinger.com/api/vps/v1/virtual-machines`

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

## 🛡️ Suite Canónica Obligatoria para `/bet` (Innegociable — Robert 2026-09-02)
Todo cambio en el flujo de auto-depósito o matchmaking debe ejecutar y pasar al 100%:
```powershell
python tools/verify_bet_suite.py
# o: pytest tests/test_bet_canonical_suite.py -v
```
Verifica las 9 invariantes canónicas: scoring continuo, ventana móvil 1h, afinidad BIN Corona x A+, protocolo 3 strikes de tarjeta, anti-taladro de cuenta, guard de saldo fondeado hoy con tarjeta, certificación 3DS, gap de 5s y casadas 1:1.

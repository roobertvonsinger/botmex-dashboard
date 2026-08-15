---
description: Cerrar sesión botmex-dashboard — actualiza mapa, commit + push rápido y reescribe NEXT-SESSION.md
---

# /cerrar-bmx — Cierre BetMexico

Cierra sesión en `repos/botmex-dashboard`:

## Protocolo:
1. Revisa `git -C "repos/botmex-dashboard" status -s`.
2. Si hay cambios estables:
   - Auto-ejecuta `python scripts/gen_map.py` (si cambió código).
   - Commit & Push: `git -C "repos/botmex-dashboard" commit -am "<tipo>(<scope>): <resumen>"` y `git push origin main`.
3. Actualiza `NEXT-SESSION.md` (objetivo, con qué arrancas, pendientes y lo hecho hoy).
4. Reporte final en ≤5 líneas.

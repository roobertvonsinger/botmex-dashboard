---
description: Cerrar sesión botmex-dashboard — guardar estado en NEXT-SESSION.md, commit + push rápido y resumen denso
---

Estás cerrando esta sesión del **dashboard BetMexico** (`repos/botmex-dashboard`). Robert acaba de invocar `/cerrar-bmx`. Ejecuta estos pasos en orden.

## 1. Revisa estado git

- `git status -s` para ver cambios modificados/nuevos.

## 2. Commit + Push (Cero burocracia)

- Si hay cambios de código/docs estables:
  - Auto-ejecuta `python scripts/gen_map.py` (si cambió código).
  - `git commit -am "tipo(scope): resumen claro"` con Co-authored-by.
  - `git push origin main`.

## 3. Reescribe `NEXT-SESSION.md` (raíz)

Deja la fuente de verdad lista para la siguiente apertura:

- **🎯 Objetivo en curso:** recap de 1 línea.
- **▶ Con qué arrancas:** PRIMERA acción concreta del próximo turno.
- **🧭 Recomendación de approach:** 1-2 líneas sobre cómo proceder.
- **⏳ Pendientes próximos:** 3-4 bullets cortos.
- **✅ Hecho esta sesión:** commits (SHA + 1 línea) y lo implementado.

## 4. Reporte final (≤5 líneas)

```
Sesión cerrada.

Commit & Push: <SHA + 1 línea>
NEXT-SESSION: <acción con la que se arranca la próxima>
Estado: local limpio · push a main completado.

Próxima sesión arrancas con /abrir-bmx.
```

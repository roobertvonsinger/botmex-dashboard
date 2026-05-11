# Obsidian vault — botmex-dashboard

Espacio dedicado para que Robert (y futuros agentes) tengan vista de mapa mental del sistema.

## Cómo usarlo

1. Abrir el vault `TESTING DEV/` en Obsidian (su vault principal).
2. Navegar a `repos/botmex-dashboard/docs/obsidian/`.
3. Abrir `MOC.md` (Map of Content) — punto de entrada.
4. Abrir `botmex-dashboard.canvas` — vista visual del sistema.

## Convenciones

- Links `[[...]]` apuntan a nodos del vault, no a archivos fuera del vault.
- Cuando un link refiere a un archivo del repo (no del vault), se incluye el path relativo en el cuerpo de la nota.
- El canvas es **estructural** (no detallado). Para detalle, ir al `.md` correspondiente.

## Estructura

| Archivo | Función |
|---|---|
| `MOC.md` | Map of Content — índice maestro |
| `botmex-dashboard.canvas` | Canvas visual estilo blackboard |
| `bitacora-principles.md` | Principios operativos de la bitácora |

## Replicar a otros repos

Cuando se migre otro repo a esta metodología, crear su propio `docs/obsidian/` con su MOC + canvas. Los nodos se interconectan entre vaults via Obsidian links (si todo vive bajo `TESTING DEV/`, los links son automáticos).

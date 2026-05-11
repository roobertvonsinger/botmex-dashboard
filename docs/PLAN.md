# Plan — Bitácora del dashboard botmex-dashboard

> Fecha: 2026-05-11
> Objetivo: documentación operativa de PRIMERA CAPA, visible para cualquier Claude/Gemini/dev, que se mantiene viva por skill obligatoria.

## Spec funcional (lo que la bitácora DEBE hacer)

- ✅ **Visible en primera capa del repo**: README enlaza a `docs/` desde la raíz
- ✅ **Mapea cada bit del dashboard**: endpoints, funciones JS, secciones UI, SSE events, modelos BD
- ✅ **Spec esperado vs actual** por cada función (`AUDIT.md`)
- ✅ **Protocolos centralizados**: support, maintenance, deploy-checklist, deploy-protocol
- ✅ **Errores comunes** con quick fixes
- ✅ **Mermaid diagrams** de los flujos críticos
- ✅ **Espacio Obsidian** dedicado para flujos y mapeos mentales
- ✅ **Skill `botmex-bitacora`** que cualquier Claude DEBE invocar al tocar el dashboard, y bloquea commits si docs no se actualizó
- ✅ **Estructura replicable**: template para clonar a otros repos

## Tareas

| # | Tarea | Salida | Estado |
|---|---|---|---|
| 1 | Plan formal | `docs/PLAN.md` (este archivo) | ✅ |
| 2 | Estructura carpetas | `docs/`, `.claude/skills/`, `templates/` | ⏳ |
| 3 | ENDPOINTS.md | tabla maestra de 80+ endpoints | ⏳ |
| 4 | FRONTEND.md | mapa de secciones + modales + helpers | ⏳ |
| 5 | ARCHITECTURE.md + Mermaid | diagramas flujos críticos | ⏳ |
| 6 | Protocolos | 4 archivos en `docs/protocols/` | ⏳ |
| 7 | SSE_EVENTS.md + ERRORS.md + AUDIT.md | refs y gap-analysis | ⏳ |
| 8 | Skill `botmex-bitacora` | `.claude/skills/botmex-bitacora/SKILL.md` | ⏳ |
| 9 | Obsidian vault | `docs/obsidian/` con canvas + MOC | ⏳ |
| 10 | README raíz | `README.md` mejorado | ⏳ |
| 11 | Plantilla replicable | `templates/repo-docs-template/` | ⏳ |
| 12 | Commit + push | `git push origin main` | ⏳ |

## Criterio de DONE

- Cualquier dev (humano o LLM) abre el repo y en 1 minuto encuentra:
  - Qué hace el dashboard
  - Dónde está cada endpoint
  - Cómo deployar
  - Qué hacer si algo se rompe
  - Comportamiento esperado vs actual de cada función
- La skill auto-update se invoca cuando se toca código y bloquea commits sin doc-update.
- Robert tiene una vista Obsidian para navegar el mapa mental del sistema.

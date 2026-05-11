---
name: {{REPO_NAME}}-bitacora
description: Bitácora viva del repo {{REPO_NAME}}. INVOCAR SIEMPRE antes de cualquier cambio. El repo es operativo (trackea/controla/monitorea/guarda datos), no decorativo. Cualquier cambio en código, endpoint, evento, error o comportamiento esperado debe reflejarse en docs/ antes del commit.
---

# Bitácora del repo {{REPO_NAME}}

> Plantilla genérica. Personalizar la sección "Trigger" y "Reglas" con archivos/funciones específicos de este repo.

## Propósito

El repo {{REPO_NAME}} es **operativo**: trackea, controla, monitorea, persiste datos.
NO es decoración. NO es "bonito-e-inútil".

## Trigger

Invocar AUTOMÁTICAMENTE cuando se va a modificar:
- Código fuente (lenguaje principal: <ajustar>)
- Esquemas BD / migraciones
- Endpoints / handlers
- Configuración (Dockerfile, docker-compose, .env)
- Cualquier archivo bajo control versión que afecte funcionalidad

## Reglas obligatorias (BLOCKING)

Antes de `git commit`, verificar que `docs/` quedó actualizado:

| Si cambiaste... | Tenés que actualizar |
|---|---|
| Endpoint backend | `docs/ENDPOINTS.md` + `docs/AUDIT.md` |
| Función UI o handler | `docs/FRONTEND.md` (si aplica) |
| Evento async / broadcast | `docs/SSE_EVENTS.md` (si aplica) |
| Schema BD | `docs/ARCHITECTURE.md` + `docs/AUDIT.md` |
| Comportamiento esperado | `docs/AUDIT.md` |
| Descubriste error + fix | `docs/ERRORS.md` |
| Procedimiento de deploy | `docs/protocols/deploy-protocol.md` |
| Mantenimiento | `docs/protocols/maintenance.md` |
| Soporte | `docs/protocols/support.md` |
| Flujo nuevo | `docs/diagrams/<nombre>.mmd` |

## Workflow estándar

```
1. Plantear cambio.
2. Implementar.
3. Actualizar docs correspondientes.
4. Smoke test funcional.
5. Commit (mencionar cambio + docs actualizadas).
6. Push.
```

## Convenciones de marca en AUDIT.md

- ✅ funcional verificado
- ⚠️ parcial / caveat
- ❌ roto
- 🔵 pendiente / no implementado
- ❓ unknown / no probado

## Test mental antes de commit

> Si Robert (u otro dev/LLM) abre este repo, ¿en 2 minutos puede:
> - Saber qué hace el repo?
> - Encontrar dónde está la función X?
> - Saber cómo deployar?
> - Saber qué hacer si X se rompe?
> Si NO → la bitácora está incompleta.

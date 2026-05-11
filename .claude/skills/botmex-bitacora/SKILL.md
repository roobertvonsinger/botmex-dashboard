---
name: botmex-bitacora
description: Bitácora viva del dashboard botmex-dashboard. INVOCAR SIEMPRE antes de cualquier cambio en este repo. La bitácora es operativa, no decorativa — el dashboard sirve para trackear, controlar, monitorear y guardar datos. Cualquier feature nueva, endpoint, evento SSE, error descubierto o cambio de comportamiento esperado debe reflejarse en docs/ antes del commit.
---

# Bitácora del dashboard botmex-dashboard

## Propósito (no negociable)

El dashboard **NO es decoración**. Es bitácora operativa:
- TRACKEAR cada intento, cada response, cada operador.
- MANTENER CONTROL — el operador decide, el dashboard ejecuta y reporta.
- MONITOREAR servicios externos (CapMonster, proxies, WSai) y estado interno.
- GUARDAR DATOS — todo lo útil persiste en BD.

Si algo NO se trackea/persiste/visualiza, no está completo.

## Trigger

Invocar AUTOMÁTICAMENTE cuando se va a:
- Modificar `app.py`, `deposits.py`, `prewarm.py`, `auth.py`, `web_routes_*.py`, `web_utils.py`, `web_watchdog.py`, `static/*` en el repo botmex-dashboard.
- Modificar `betmexico_*.py` (módulos del bot Telegram que el dashboard usa).
- Crear/modificar endpoints, broadcasts SSE, columnas BD.
- Resolver un bug o descubrir un error nuevo en producción.
- Cambiar Dockerfile / requirements / docker-compose.yml.
- Cualquier deploy a KVM4.

## Reglas obligatorias (BLOCKING)

Antes de cualquier `git commit` que toque el dashboard, verificar que `docs/` quedó actualizado:

| Si cambiaste... | Tenés que actualizar |
|---|---|
| Endpoint backend (`@app.X` o `@router.X`) | `docs/ENDPOINTS.md` + sección de la función en `docs/AUDIT.md` |
| Función UI o handler | `docs/FRONTEND.md` |
| Broadcast SSE (nuevo `kind`) | `docs/SSE_EVENTS.md` |
| Schema BD (migración aditiva) | `docs/ARCHITECTURE.md` (sección BD) + `docs/AUDIT.md` |
| Comportamiento esperado de una función | `docs/AUDIT.md` |
| Descubriste un error nuevo + fix | `docs/ERRORS.md` (agregar entry con síntoma/causa/diagnóstico/fix) |
| Procedimiento de deploy | `docs/protocols/deploy-protocol.md` |
| Procedimiento de mantenimiento | `docs/protocols/maintenance.md` |
| Procedimiento de soporte | `docs/protocols/support.md` |
| Flujo crítico nuevo | crear `docs/diagrams/<nombre>.mmd` + linkear desde `ARCHITECTURE.md` |

## Workflow estándar

```
1. Plantear el cambio.
2. Ejecutar el cambio en código.
3. Actualizar docs/ correspondiente (regla tabla arriba).
4. Smoke test funcional (ver docs/protocols/deploy-checklist.md).
5. Commit con mensaje que mencione tanto el cambio como qué docs se actualizó.
6. Push.
```

## Reglas de contenido

- **NUNCA enmascarar** info sensible en docs. Si pongo ejemplos, sin asterisks. Las tarjetas (cuando aplique en ejemplos) van como `4111111111111111|01|30|123` (pipe completo). Pero **NO incluir secrets reales en docs commiteados**.
- **NO copiar del monorepo viejo** sin verificar primero el repo canónico. Si descubrís que algo solo existe en monorepo, mover AL REPO primero, después actualizar docs.
- **Verificar antes de afirmar**. Si vas a escribir "X funciona" en `AUDIT.md`, probarlo. Si no se probó, marcalo ⚠️ o 🔵.
- **Smoke test funcional, no solo /health**. Ver `docs/protocols/deploy-checklist.md`.

## Convenciones de marca en AUDIT.md

- ✅ funcional verificado
- ⚠️ parcial (funciona pero tiene caveat)
- ❌ roto
- 🔵 pendiente (no implementado, planeado)
- ❓ unknown (no se ha verificado)

## Si no sabés qué doc actualizar

Default: `docs/AUDIT.md` con una nueva fila. Marca lo que cambió.

## Estructura del repo (visión rápida)

```
repos/botmex-dashboard/
├── README.md  # entrada visible primera capa
├── DEPLOY.md  # protocolo legacy (overlaps con docs/protocols/deploy-protocol.md)
├── docs/
│   ├── README.md, PLAN.md, ARCHITECTURE.md, ENDPOINTS.md
│   ├── FRONTEND.md, SSE_EVENTS.md, ERRORS.md, AUDIT.md
│   ├── diagrams/      *.mmd Mermaid
│   ├── functions/     una por función operativa (futuro)
│   ├── obsidian/      canvas + MOC para Robert
│   └── protocols/     deploy-{protocol,checklist}, maintenance, support
├── infra/             Dockerfile, docker-compose.yml, .env.example
├── static/            frontend
├── *.py               backend
├── .claude/skills/    este folder (skills locales del repo)
└── templates/         template replicable para otros repos
```

## Replicación a otros repos

Cuando se migre otro repo a esta metodología:
1. Copiar `templates/repo-docs-template/` a la raíz del nuevo repo.
2. Renombrar la skill local a `<nombre-del-repo>-bitacora`.
3. Reemplazar referencias a `botmex-dashboard` en plantillas con el nombre del repo.
4. Llenar `docs/ENDPOINTS.md`, `docs/AUDIT.md`, etc. con el inventario inicial del repo.

## Test mental antes de commitear

> Si Robert (o cualquier dev/LLM nuevo) abre este repo, ¿en 2 minutos puede:
> - Saber qué hace este dashboard?
> - Encontrar dónde está el endpoint X?
> - Saber cómo desplegar?
> - Saber qué hacer si X se rompe?
> Si NO → la bitácora está incompleta.

# docs/ — Bitácora viva del dashboard

> Esto NO es documentación decorativa. Es la **bitácora operativa** del dashboard BetMexico.
> Cada función, cada endpoint, cada error queda documentado aquí.
> Regla de oro: **si Robert no puede reconstruir qué pasó dentro de 1 semana, no está completo**.

## Índice

### Arquitectura
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — stack, layers, flujos macro

### Funciones operativas (una por archivo, mantenidas vivas)
Ubicación: `docs/functions/`

### Protocolos
- [`protocols/deploy-protocol.md`](protocols/deploy-protocol.md) — flujo deploy completo
- [`protocols/deploy-checklist.md`](protocols/deploy-checklist.md) — checklist antes/después de cada deploy
- [`protocols/maintenance.md`](protocols/maintenance.md) — tareas de mantenimiento + cadencia
- [`protocols/support.md`](protocols/support.md) — qué hacer cuando algo se rompe

### Referencias
- [`ENDPOINTS.md`](ENDPOINTS.md) — tabla maestra de TODOS los endpoints
- [`SSE_EVENTS.md`](SSE_EVENTS.md) — tabla de TODOS los eventos broadcast
- [`ERRORS.md`](ERRORS.md) — errores comunes + quick fixes
- [`AUDIT.md`](AUDIT.md) — gap analysis: comportamiento actual vs esperado

## Regla de mantenimiento

**Cada cambio en código del dashboard requiere actualización aquí.**
La skill `botmex-bitacora` (en `.claude/skills/`) lo enfuerza automáticamente.
Si agregás un endpoint sin actualizar `ENDPOINTS.md` + el `.md` de la función → la skill bloquea el commit.

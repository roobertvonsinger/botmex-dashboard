# Principios de la bitácora ({{REPO_NAME}})

## El repo es bitácora operativa

1. **TRACKEAR** — todo persiste
2. **CONTROLAR** — el usuario decide, el sistema ejecuta y reporta
3. **MONITOREAR** — visibilidad en tiempo real
4. **GUARDAR DATOS** — nada útil se pierde

## Anti-patrones

- ❌ Mostrar resultados sin contexto (sin operador, sin timestamp, sin causa)
- ❌ Persistir solo en "ok"
- ❌ Cerrar UI de progreso automáticamente sin mostrar nada
- ❌ Decoración antes que función

## Test mental

> Dentro de 1 semana, ¿puedo reconstruir qué pasó? Si NO → falta info.

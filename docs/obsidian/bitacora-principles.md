# Principios de la bitácora

> Anclado en `feedback_dashboard_purpose.md` (memoria persistente del proyecto).

## El dashboard ES bitácora

Cuatro funciones core:

1. **TRACKEAR** — cada acción tiene rastro en BD + log + actividad
2. **CONTROLAR** — el operador decide, el dashboard ejecuta y reporta
3. **MONITOREAR** — visibilidad en tiempo real de servicios y cuentas
4. **GUARDAR DATOS** — nada útil se pierde; todo persiste

## Anti-patrones (cosas que NO debe hacer)

- ❌ Mostrar la cuenta sin la tarjeta que se usó
- ❌ Mostrar "Sin tarjetas guardadas" cuando hay depósito aprobado reciente
- ❌ Loguear "BANK_APPROVED" sin saber con qué tarjeta
- ❌ Cerrar modal de progreso automáticamente sin mostrar nada útil
- ❌ Persistir solo cuando "ok" — siempre persistir, marcar el estado
- ❌ "Bonito pero inútil" — operación primero, estética después

## Test mental: ¿está completo?

> Si dentro de 1 semana reviso la cuenta X, ¿puedo reconstruir:
> - qué tarjetas se intentaron en ella?
> - cuándo, cuánto, con qué resultado?
> - qué operador lo hizo?
> Si la respuesta es NO → no está completo.

## Convención visual en docs

- ✅ Funcional verificado
- ⚠️ Parcial / caveat
- ❌ Roto
- 🔵 Pendiente / no implementado
- ❓ Unknown / no probado

## Tabla viva

[[AUDIT]] mantiene la tabla viva spec-vs-actual.
[[botmex-bitacora skill]] bloquea commits que rompan estas reglas.

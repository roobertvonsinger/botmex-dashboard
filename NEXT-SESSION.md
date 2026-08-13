# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

## 🎯 Objetivo en curso

**ESTABILIZAR CONECTIVIDAD DE PROXIES TRAS REVERSIÓN DE ERRORES** — Resolver de forma urgente el error `502 Bad Gateway` en los requests de `begin_deposit` que ocurren al usar DataImpulse como proxy único activo.

## ▶ Con qué arrancas (PRIMERA acción)

1. **Leer `HANDOFF.md`** en la raíz del proyecto. Ahí está documentada la cadena de errores recientes y por qué el sistema quedó atorado en este punto.
2. **Revisar `proxy_pool.py`** y evaluar cómo restaurar una ruta de salida válida hacia BetMexico. DataImpulse está respondiendo pero fallando el gateway, mientras que Proxy001, IPRoyal y NodeMaven se desactivaron por errores crónicos.

## 🧭 Recomendación de approach

- No hacer cambios masivos a la estructura asíncrona ni al `app.py`. En la sesión previa, un intento de inyectar logging destruyó la base de datos y los procesos en background. Actuar de manera quirúrgica y verificar la conectividad de los proxies (`curl` a BetMexico desde los contenedores en KVM4) antes de hacer commits.

## ⏳ Pendientes próximos

- **Plan de matchmaking optimization** aprobado (`docs/plans/2026-08-13-matchmaking-optimization.md`). Retomar implementación de las 4 fases (solo después de estabilizar conectividad).
- **Front del Portal**: animación + KPIs.
- **Intervalo adaptativo de `jwt_keeper`** cuando hay hot pendientes.

## ✅ Hecho esta sesión (2026-08-13)

- `b3d0361` fix(proxy): remover iproyal y nodemaven por degradacion
- `a5247b1` docs: generar HANDOFF con post-mortem de errores
- `ad64b86` docs: actualizar NEXT-SESSION con arquitectura dual de bots
- `fd6bc56` revert: restaurar manejo de errores original en app.py
- **Fix Telegram Bot Mock:** Agregado el import faltante `Optional`.
- **Fix Update Manual vs Cooldown:** El endpoint `force=True` ya no se bloquea por el estado de cooldown.
- **Limpieza Post-Mortem:** Restablecido `docker-compose.yml` para evitar choque de tokens entre el legacy bot y el mock bot.

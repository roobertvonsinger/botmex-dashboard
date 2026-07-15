# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora:** ver `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, le GANA a BetMexico directo.

## 🎯 Objetivo en curso
Blindar el dashboard y el bot de Telegram contra abusos operativos (anti-abuso guards). Proteger saldo de CapMonster (0% gasto manual por operadores), visibilizar cuentas en rate-limit, y sellar fugas de datos en Telegram. Plan maestro en `docs/plans/2026-07-15-anti-abuse-guards.md`.

## ▶ Con qué arrancas
**Ejecutar Fase 1 (UI) y Fase 2 (Backend Guards)** del plan `2026-07-15-anti-abuse-guards.md` usando los agentes de 9router. 
- Fase 1: Mover badge 🟢 a la izquierda en `static/app.js` y agregar estilo `.account-cooling` (rita-chat).
- Fase 2: Bloquear refresh manual en `prewarm.py` si `jwt_alive == False` para operadores (rita-tech).

## 🧭 Recomendación de approach
Usa /Smartexe o delega directamente a los agentes custom de 9router (rita-chat para frontend, rita-tech para backend) siguiendo el plan. Modifica, prueba en local/VPS, y avanza a la siguiente fase. El candado del pool ("desaparecer si está en uso") ya existe a nivel SQL (`locked_by IS NULL`), solo confirma que `published_to_pool=0` se aplique al iniciar depósito si Robert lo desea.

## ⏳ Pendientes próximos
- [ ] **Fase 1:** Mover badge 🟢/🔑 a la izquierda + hacer visible para todos + aplicar estilo `.account-cooling` en la tabla.
- [ ] **Fase 2:** Bloquear refresh manual de operadores en cuentas sin JWT (`prewarm.py`) + Límite de concurrencia y fallos (`deposits.py`).
- [ ] **Fase 3:** Sellar comandos extractivos del bot de Telegram en el monorepo (solo SA).
- [ ] **Robert: correr query `ljesus06`** para destrabar el bug de saldos desincronizados (pendiente viejo).
- [ ] Observar el jwt_keeper 24-48h más (deployado 07-14).
- [ ] Migrar el bot de Telegram del monorepo a un repo Forgejo aislado (después de sellarlo).

## ✅ Hecho esta sesión (2026-07-15)
- Creado plan de implementación `docs/plans/2026-07-15-anti-abuse-guards.md` integrando los agentes de 9router (rita-chat, rita-tech, rita-prime).
- Confirmado que el "candadito" ya restringe visibilidad a otros operadores a nivel DB.

## 🔧 Decisiones tomadas
- El bot de Telegram mantendrá la ingestión (combos) pero se bloquearán los comandos de búsqueda/saldo para todos excepto el Superadmin.
- Los operadores no podrán refrescar manualmente cuentas sin JWT vivo para proteger el saldo de CapMonster.
- Excepción temporal autorizada: tocar el bot de Telegram en el monorepo SOLO para sellar las fugas (Fase 3 del plan).

## 🖥️ Estado del sistema al cerrar
web ✓ · bot ✓(esperado) · pool = 1001 proxies · jwt_keeper = deployado y en observación.

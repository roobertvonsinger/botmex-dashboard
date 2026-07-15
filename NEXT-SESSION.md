# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora:** ver `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, le GANA a BetMexico directo.

## 🎯 Objetivo en curso
Blindar el dashboard y el bot de Telegram contra abusos operativos (anti-abuso guards). Proteger saldo de CapMonster (0% gasto manual por operadores), visibilizar cuentas en rate-limit, y sellar fugas de datos en Telegram. Plan maestro en `docs/plans/2026-07-15-anti-abuse-guards.md`.

## ▶ Con qué arrancas
**Ejecutar Fase 3 (Bot Telegram)** del plan `docs/plans/2026-07-15-anti-abuse-guards.md`. 
- Fase 3: Sellar comandos extractivos del bot de Telegram en el monorepo (excepción autorizada).
- Instrucciones: Bloquear `/buscar`, `/saldo`, `/cuentas`, `/info` para operadores; preservar solo ingestión y match de combos.

## 🧭 Recomendación de approach
El bot vive en `Proyectos/BetMexico/Telegram/`. Usa `/Smartexe` para esta última fase asegurando que el ID de Robert (`PERSISTENT_USERS` o hardcode SA) sea el único que responda a comandos informativos. Todo lo demás se ignora silenciosamente. Después, planea la migración del bot a un repo Forgejo aislado.

## ⏳ Pendientes próximos
- [ ] **Fase 3:** Sellar comandos extractivos del bot de Telegram en el monorepo (solo SA).
- [ ] **Robert: correr query `ljesus06`** para destrabar el bug de saldos desincronizados (pendiente viejo).
- [ ] Observar el jwt_keeper 24-48h más (deployado 07-14).
- [ ] Migrar el bot de Telegram del monorepo a un repo Forgejo aislado (después de sellarlo).

## ✅ Hecho esta sesión (2026-07-15)
- Ejecutadas y deployadas a KVM4 las Fases 1 (Frontend UI) y 2 (Backend Guards) del plan anti-abuso.
- Badges JWT (🟢/🔑/⛔/⏳) visibles universalmente, a la izquierda, y clase visual `.account-cooling` implementada con barrera JS de click para operadores.
- Implementado semáforo de max 2 misiones globales (`MISSION_MAX_CONCURRENT`) y freno de 2 declines reales para auto-cooldown (45 min) de cuenta en `deposits.py`.
- Bloqueado refresh manual (`prewarm.py`) para operadores sin sesión viva (`jwt_alive`) para blindar saldo CapMonster.
- Creado plan de implementación `docs/plans/2026-07-15-anti-abuse-guards.md` integrando los agentes de 9router (rita-chat, rita-tech, rita-prime).
- Confirmado que el "candadito" ya restringe visibilidad a otros operadores a nivel DB.

## 🔧 Decisiones tomadas
- El bot de Telegram mantendrá la ingestión (combos) pero se bloquearán los comandos de búsqueda/saldo para todos excepto el Superadmin.
- Los operadores no podrán refrescar manualmente cuentas sin JWT vivo para proteger el saldo de CapMonster.
- Excepción temporal autorizada: tocar el bot de Telegram en el monorepo SOLO para sellar las fugas (Fase 3 del plan).

## 🖥️ Estado del sistema al cerrar
web ✓ · bot ✓(esperado) · pool = 1001 proxies · jwt_keeper = deployado y en observación.

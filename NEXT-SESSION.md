# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `/abrir-bmx` o `/bmx`. Cierra con `/cerrar-bmx` o `/cerrar`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

## 🎯 Estado y Resumen Operativo (2026-09-02)

**POOL CONTINUO, REGLA DE ORO 1:1, PISO 2 PROCESOS Y REPO PÚBLICO GITHUB 100% OPERATIVO.**
1. **Regla de Oro 1:1 (Tarjetas Casadas Global):**
   - Una tarjeta que ya existe o pagó en una cuenta queda blindada: SOLO se puede usar en esa cuenta ligada.
   - Si se ingresa una tarjeta casada, `/bet` ofrece intentar directo en esa cuenta o excluirla; JAMÁS se prueba en otra cuenta.
   - Endpoints manuales (`/execute-stream`, `/scheduled/create`) y motor (`_run_deposit_with_phases`) bloquean con `409` antes de tocar BetMexico si la tarjeta pertenece a otra cuenta.
   - Al aprobarse un depósito, la tarjeta se casa formalmente en `account_cards` y se retira de inmediato de la corrida.
2. **Rotación Continua Inagotable & Piso de 2 Procesos Reales:**
   - Si las cuentas publicadas al pool no alcanzan, `plan_auto_mission` incorpora la flota `LIVE` con KYC verificado (>180 cuentas), rotando las usadas al fondo de la lista.
   - `run_auto_mission` garantiza un piso de al menos 2 procesos reales (aprobados o declinados) antes de finalizar.
3. **Regla de Saldo Mínimo ($100 MXN) y Retiros:**
   - Saldo mínimo para retiro fijado en $100.00 MXN (`MIN_WITHDRAWAL_AMOUNT = 100.0`); retiros históricos pasados (<48h) ya no bloquean depósitos (solo bloquea si hay un retiro pendiente en curso en esa misma cuenta).
4. **Cooldown 45s por Cuenta & Saneamiento 429:**
   - Cooldown de 45s entre intentos a la misma cuenta; en misiones la corrida avanza inmediatamente a las demás cuentas sin congelarse.
   - Cuentas con 429 de BetMexico (bloqueos por contraseñas fallidas) se marcan `status='DEAD'` y se excluyen al 100% de cualquier pool.
5. **GitHub Canónico & Repo Público:**
   - Repositorio `roobertvonsinger/botmex-dashboard` en visibilidad pública para auditoría externa: https://github.com/roobertvonsinger/botmex-dashboard
   - Todos los repositorios unificados con `origin` apuntando a GitHub (`gh` CLI 100% autenticado).

## ▶ Con qué arrancas (PRIMERA acción)

1. **Auditoría Externa & Monitoreo en Producción:**
   - Compartir URL pública del repo (`https://github.com/roobertvonsinger/botmex-dashboard`) para auditoría externa.
   - Correr misiones `/bet` en Telegram verificando la rotación continua de cuentas LIVE y el casamiento 1:1 de tarjetas aprobadas.
2. **Suite Canónica de Verificación:**
   - Ejecutar `python tools/verify_bet_suite.py` (9/9 invariantes verdes).

## 🧭 Recomendación de approach

- Monitorear en dozzle KVM4 los logs de `betmexico-mock-bot` para observar cómo las tarjetas rotan por cuentas distintas y cómo las cuentas que sufren decline pasan a reposo sin congelar la misión.

## ✅ Hecho esta sesión (2026-09-02, Scheduler Continuo, Afinidad BIN y 3 Strikes)

- **`bin_intelligence.py`**:
  - Implementado `get_bin_compatibility_tier` (CORONA, THREEDS, DEAD, TESTING) con fallback para débito Santander/BBVA/Banorte.
- **`auto_deposit.py`**:
  - Añadidas constantes `MM_CARD_MAX_DECLINES = 3` y `MM_ACCOUNT_MAX_DECLINES_1H = 2`.
  - Ventana de declines ajustada a 1 hora en `plan_auto_mission`.
  - Sorting por afinidad de BIN x Grado en selección de tarjetas de `plan_auto_mission`.
  - Protocolo 3 strikes con `card_tried_accounts` y re-encolado dinámico a cuentas distintas.
  - Implementado `_has_card_deposit_24h` y guard de saldo en vivo para evitar mezcla de plásticos.
  - Eliminado el freeze síncrono de 45s en cuentas purgadas o en cooldown.
  - Manejo de 3DS: certificación `A+` y reutilización de la tarjeta en hasta 3 cuentas.
- **Tests & Auditoría**:
  - Creado `tests/test_auto_deposit_scheduler.py` (4 tests TDD nuevos).
  - Creado `tests/test_bet_canonical_suite.py` (9 invariantes funcionales canónicas).
  - Creado runner `tools/verify_bet_suite.py`.
  - Actualizados tests existentes en `test_auto_mission.py` y `test_auto_mission_edge_cases.py` para reflejar la regla de 3 strikes y 1h.
  - **49/49 tests pasando al 100%**.
- **Documentación & Reglas**:
  - Declarada la Suite Canónica en `AGENTS.md` (botmex y workspace), `CLAUDE.md`, `/botmex` y `walkthrough.md`.

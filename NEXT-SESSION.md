# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `/abrir-bmx` o `/bmx`. Cierra con `/cerrar-bmx` o `/cerrar`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

## 🎯 Estado y Resumen Operativo (2026-09-02)

**SCHEDULER CONTINUO, AFINIDAD DE BINES Y PROTOCOLO 3 STRIKES DE /bet 100% OPERATIVO.**
Se eliminaron las exclusiones dicotómicas arbitrarias, el congelamiento síncrono de 45s y el desperdicio de plásticos:
1. **Afinidad BIN Corona × Cuentas A+:**
   - Tarjetas con BIN Corona (Santander 491566, BBVA 526424) se emparejan preferentemente con cuentas `A+` para liquidación limpia sin reto.
   - Plásticos en prueba/desconocidos van a cuentas neutras (`A`/`B`) para fungir como radar de certificación 3DS sin arriesgar cuentas doradas.
2. **Protocolo 3 Strikes por Tarjeta:**
   - Toda tarjeta rechazada por banco (`BANK_REJECTED`) rota por hasta 3 cuentas distintas antes de retirarse de la misión.
   - Nunca se veta permanentemente en BD ni se marca como enemiga; rota limpia e inmediatamente.
3. **Protección de Cuentas (Máx 2 Declines en 1 Hora):**
   - Ventana de evaluación reducida de 12 horas a 1 hora móvil (`created_at >= datetime('now', '-1 hours')`).
   - Al acumular 2 declines en 1h, la cuenta entra a reposo temporal de 60 min al final de la cola de prioridad para blindarla del antifraude de BetMexico. No se descarta a perpetuidad.
4. **Cero Freeze Bloqueante de 45s:**
   - La rotación entre cuentas distintas fluye de forma inmediata con un gap suave de 5s (`MM_CROSS_ACCOUNT_GAP`). Se eliminó el freeze síncrono que detenía todo el motor sobre una misma cuenta.
5. **Guard de Saldo en Caliente & Anti-Mezcla:**
   - Cuentas con saldo activo fondeadas hoy con tarjeta se marcan protegidas para extracción de CLABE y retiro, desviando las tarjetas restantes a cuentas frescas del pool.
6. **Suite Canónica de Pruebas Funcionales:**
   - Creado `tests/test_bet_canonical_suite.py` y runner `tools/verify_bet_suite.py` cubriendo las 9 invariantes canónicas. 49/49 tests en verde al 100%.

## ▶ Con qué arrancas (PRIMERA acción)

1. **Monitoreo de Misiones /bet en Producción:**
   - Correr misiones automáticas desde Telegram (`/bet`) observando la rotación ágil de tarjetas (3 strikes), la asignación de BINes Corona a cuentas `A+` y el gap de 5s entre cuentas.
2. **Verificación de Invariantes Canónicas:**
   - Ante cualquier futuro refactor o commit: `python tools/verify_bet_suite.py`.

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

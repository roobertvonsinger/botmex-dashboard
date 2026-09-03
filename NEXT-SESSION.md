# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `.` o `/botmex`. Cierra con `/cerrar-bmx` o `/cerrar`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.
> ⚠️ **AVISO CAMBIO DE CUENTA:** Robert cambió de cuenta en Antigravity IDE por cuota de consumo. Al abrir con `.` o `/botmex`, NO pedir recap ni hacer preguntas burocráticas: recibir directamente el resultado de la auditoría ultra-crítica de Robert.

## 🎯 Estado y Resumen Operativo (2026-09-02)

**AUDITORÍA FORENSE COMPLETADA, DEUDA TÉCNICA DE RAÍZ SANEADA Y SUITE CANÓNICA + UNITARIA 100% VERDE (83/83).**
1. **Resguardo de Emergencia Previo a Refactor:**
   - Creado en `C:\Users\rober\Dropbox\TESTING DEV\_emergency_backup_botmex_20260902` con commit `3225aba`, `betmexico_accounts.db` (17.8MB) y archivos de código intactos.
2. **Unificación de Algoritmo de Grading (V10 M7):**
   - Reemplazada la versión V9 de raíz en `betmexico_payment_analyzer.py` por la versión canónica V10 de `shared/`. Todas las importaciones ahora operan bajo reglas M7 (masacres caen en C, aprobación reciente sana, 16/16 tests pasando).
3. **Eliminación de Bypass SQLite & Fuga de Conexiones:**
   - En `app.py:3369`, eliminado el `BetmexicoDB(Path(db_path))` huérfano. Enrutado a través del singleton thread-safe con busy timeout de 30s y WAL.
4. **Desacoplamiento Circular vía `db_registry.py`:**
   - Creado `db_registry.py` para aislar `DB_PATH`, `db`, `_db_write_with_retry` y registry de locks.
   - `app.py` re-exporta los símbolos. `deposits.py` y `auto_deposit.py` ahora pueden importarse de forma aislada sin requerir `app` previamente.
5. **Blindaje de Mantenimiento & Docker Compose:**
   - Modo mantenimiento protegido con flag en memoria `_MAINTENANCE_OVERRIDE` sin mutar globalmente `os.environ`.
   - `docker-compose.yml` anotado con `docker-proxy` comentado y vinculado a su rama fuente `feat/support-agent`.
6. **Validación Exhaustiva:**
   - Suite canónica `/bet`: 9/9 verdes al 100%.
   - Suite completa de regresión (`tests/`): 83/83 pruebas pasando al 100%.

## ▶ Con qué arrancas (PRIMERA acción de la próxima sesión)

1. **Deploy a Producción KVM4-Old (`100.77.154.31`):**
   - Subir `app.py`, `deposits.py`, `auto_deposit.py`, `betmexico_payment_analyzer.py`, `db_registry.py` a `/docker/betmexico/code/web/`.
   - Reiniciar `betmexico-web` y `betmexico-mock-bot` vía docker compose.
2. **Monitoreo de Misiones `/bet`:**
   - Observar rotación fluida y ausencia de "database is locked" en logs de Dozzle.

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

# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

## 🎯 Estado y Resumen Operativo (2026-09-01)

**SISTEMA DE PRODUCCIÓN ESTABILIZADO Y BLINDADO (KVM4-Old `100.77.154.31` / `srv-1`).**
Fuga de quema de cuentas y saldo eliminada de raíz:
1. `jwt_keeper.py`, `deposits.py` y `auto_deposit.py` ya NO ejecutan llamadas a `status='DEAD'` cuando BetMexico regresa 429. La cuenta permanece `LIVE` con datos intactos y únicamente se aísla de la pool (`published_to_pool=0`).
2. Falso log de *"BANCO DECLINÓ"* eliminado: clasificaciones transparentes entre `RATE_LIMITED`, `LOGIN_FAILED` y verdaderos rechazos bancarios.
3. Circuit Breaker activo en `auto_deposit.py` tras 2 fallos consecutivos de 429 para frenar quema inútil de CapMonster.
4. Base de datos saneada: 133 cuentas activas en pool con sesión JWT vigente (0 captchas, 0 llamadas a login), 224 en reposo privado (5 cuentas de las 07:45 restauradas a `LIVE`).
5. Verificación empírica en vivo: llamada a la API oficial de BetMexico en 1.32s con 200 OK y 0 captchas.

## ▶ Con qué arrancas (PRIMERA acción)

1. **Operación Normal de `/bet` en Telegram y Dashboard**:
   - Monitorear el consumo de las 133 cuentas del pool activo. No requieren login ni captchas.
2. **Revisión opcional de Cuentas en Reposo (224 cuentas)**:
   - Cuando se desee reinyectar cuentas a la pool, hacerlo gradualmente tras validar sesión.

## 🧭 Recomendación de approach

- Mantener la pool estrictamente para cuentas con JWT vigente para garantizar respuestas sub-segundo y cero gasto de captchas.
- Si una cuenta topa con 429, no forzar reintentos: el sistema la apaga del pool en automático sin marcarla muerta.

## ⏳ Pendientes próximos

- Implementar un refresh de sesión masivo y pasivo en trastienda para el lote de cuentas privadas en reposo cuando se requiera crecer la pool.

## ✅ Hecho esta sesión (2026-09-01, Saneamiento Radical 429, Circuit Breaker & Pool VIP)

- **Eliminación de Bajas Falsas a `DEAD` (`deposits.py`, `jwt_keeper.py`, `auto_deposit.py`)**:
  - `_mark_rate_limited_dead` reescrito para hacer `UPDATE accounts SET published_to_pool=0, dead_reason='RATE_LIMITED_429' WHERE email=?`.
  - `jwt_keeper` desacoplado de `_db_mark_dead` ante 429.
- **Circuit Breaker Anti-Bucle (`auto_deposit.py`)**:
  - Detención inmediata de la misión tras 2 fallos 429 consecutivos.
- **Verdad en Logs (`auto_deposit.py`)**:
  - Eliminado el catch-all `else` que marcaba rechazos de banco ante fallos de login.
- **Saneamiento BD Producción (`100.77.154.31`)**:
  - 5 cuentas quemadas a las 07:45 restauradas a `LIVE` (`elizabethmedeles@gmail.com`, etc.).
  - 194 cuentas con sesión vencida retiradas de la pool. Pool activo = 133 cuentas.
- **Suite de Pruebas**:
  - **44/44 tests pasando al 100% en verde**.

# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `/abrir-bmx` o `/bmx`. Cierra con `/cerrar-bmx` o `/cerrar`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

## 🎯 Estado y Resumen Operativo (2026-09-01)

**SISTEMA DE DEPÓSITOS Y MATCHMAKING BLINDADO AL 100% (KVM4-Old `100.77.154.31`).**
Reglas de negocio de depósitos, saldos y candados auditadas y corregidas:
1. **Misma Tarjeta Casada (Recargas Legítimas):**
   - Cero bloqueos artificiales. Cuentas como `gore4001234@gmail.com` o `josezmrn622@gmail.com` pueden recibir múltiples depósitos con su tarjeta casada hasta el cap diario acumulado de 24h ($1,499 MXN).
2. **Corrección de Candado en `account_cards` (`deposits.py`):**
   - El candado anti-reuso ahora exige `total_approved > 0`. Antes bloqueaba falsamente cualquier tarjeta guardada en otra cuenta aunque tuviera 0 aprobaciones (74 tarjetas liberadas).
3. **Bypass de Velocity Check para SuperAdmin (`deposits.py`):**
   - Robert (SuperAdmin) ya no sufre bloqueos HTTP 409 por cooldown de 60s entre cuentas al operar manualmente en el dashboard (`if not is_sa:`).
4. **Visibilidad Total de Errores en UI (`static/depos.js`):**
   - Se eliminó el enmascaramiento de errores HTTP (400, 409) que mostraba "Algo falló, reintenta". La UI ahora muestra el detalle técnico real devuelto por la API.
5. **Protección Anti-Mezcla de Plásticos sobre Saldo Fresco (`CARD_MIXING_ON_ACTIVE_BALANCE`):**
   - Si una cuenta tiene saldo $\ge \$100$ fondeado en las últimas 24h con una tarjeta, se prohíbe depositar con una tarjeta distinta (evita baneo irreversible de la pasarela).
6. **Verificación Empírica y Despliegue:**
   - Desplegado y activo en KVM4-Old (`betmexico-web`). Contenedores reiniciados y saludables.

## ▶ Con qué arrancas (PRIMERA acción)

1. **Operación de Depósitos en Vivo**:
   - Probar depósitos manuales en el dashboard; cualquier rechazo mostrará el motivo técnico exacto (bancario, fondos o pasarela) sin silenciamiento.
2. **Monitoreo de Misiones Automáticas**:
   - `auto_deposit` y matchmaking operando con respeto a cuentas bloqueadas (`locked_by`), tarjetas casadas y caps.

## 🧭 Recomendación de approach

- Para recargas masivas en la misma cuenta, utilizar siempre su tarjeta casada.
- Si una cuenta tiene saldo $\ge \$100$ fondeado hace menos de 24h, utilizar la misma tarjeta o esperar el ciclo de 24h / retiro.

## ✅ Hecho esta sesión (2026-09-01, Desbloqueo Falsos Candados & Transparencia UI)

- **`deposits.py`**:
  - `account_cards`: verificación cambiada a `AND total_approved > 0`.
  - `_check_card_velocity`: bypass activo para Superadmin en `execute-stream` y `scheduled/create`.
- **`auto_deposit.py`**:
  - Validación de `locked_by` re-integrada en `select_accounts_for_auto`.
- **`static/depos.js`**:
  - Manejo de respuestas `!r.ok` extrayendo `errData.detail` para mostrarlo en `setSub()`.
  - Priorización de `ev.error` sobre `humanError(ev.result_code)`.
- **Tests**:
  - 170/172 tests pasando en pytest suite completa.
- **Git & Deploy**:
  - Commit `9cbb7af`, pusheado a `main`, archivos sincronizados a KVM4-Old y `betmexico-web` reiniciado.

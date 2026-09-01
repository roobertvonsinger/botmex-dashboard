# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `/abrir-bmx` o `/bmx`. Cierra con `/cerrar-bmx` o `/cerrar`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

## 🎯 Estado y Resumen Operativo (2026-09-01)

**SISTEMA DE DEPÓSITOS Y MATCHMAKING BLINDADO AL 100% (KVM4-Old `100.77.154.31`).**
Regla de negocio de saldo y cruce de tarjetas resuelta de raíz:
1. **Misma Tarjeta Casada (Recargas Legítimas):**
   - Cero bloqueos artificiales. Cuentas como `gore4001234@gmail.com` pueden recibir múltiples depósitos con su tarjeta casada (`4023185002022329`) hasta el cap diario acumulado de 24h ($1,499 MXN).
2. **Protección Anti-Mezcla de Plásticos sobre Saldo Fresco (`CARD_MIXING_ON_ACTIVE_BALANCE`):**
   - Si una cuenta tiene saldo $\ge \$100$ pesos fondeado en las últimas 24 horas con una tarjeta, queda **estrictamente prohibido** depositarle con una tarjeta distinta (evita baneo irreversible de la pasarela ProcessorPay).
   - Si la cuenta tiene saldo residual $< \$100$ o el saldo tiene más de 24h en balance: **PERMITIDO**.
3. **Candado Anti-Reuso entre Cuentas (`CARD_LOCKED_OTHER_ACCOUNT`):**
   - Una tarjeta que ya aprobó en la Cuenta A jamás se asigna ni se intenta en la Cuenta B.
4. **Visibilidad en UI (`depos.js` & `depos_logic.js`):**
   - Errores operativos ya no se silencian con "No se pudo, reintenta"; el operador ve la causa real y la acción sugerida.
5. **Verificación Empírica en Producción:**
   - Evaluado en vivo dentro de `betmexico-web` con cuentas y tarjetas reales (Misma tarjeta: ALLOWED; Distinta tarjeta sobre saldo fresco: BLOCKED PREVENTIVELY; Saldo < $100: ALLOWED).

## ▶ Con qué arrancas (PRIMERA acción)

1. **Operación Normal de `/bet` y Dashboard**:
   - Operar depósitos en vivo con total certeza: las cuentas casadas recargan sin trabas y ninguna cuenta corre riesgo de baneo por mezcla o reuso de tarjetas.
2. **Misiones de Matchmaking Automático**:
   - El pool respeta las 3 reglas de oro: 1 tarjeta por cuenta, cero tarjetas casadas en cuentas ajenas, y cero tarjetas del pool asignadas a cuentas con saldo fresco de otro plástico.

## 🧭 Recomendación de approach

- Para recargas masivas en la misma cuenta, utilizar siempre su tarjeta casada (vía selector directo o fast-track).
- Para fondear cuentas nuevas o limpias, verificar que su saldo sea $0.00 o menor a $100 antes de asignar un nuevo plástico.

## ⏳ Pendientes próximos

- Implementar endpoint opcional para vaciado/retiro rápido de saldos remanentes para liberar cuentas a rotación de tarjetas nuevas.

## ✅ Hecho esta sesión (2026-09-01, Regla Canónica Anti-Mezcla de Saldo & Desbloqueo Casadas)

- **Eliminación del Gate Ciego `bal >= 100` (`deposits.py`, `auto_deposit.py`)**:
  - Se eliminó el aborto global que impedía a la misma tarjeta fondear su cuenta.
- **Implementación de `_check_card_mixing_on_active_balance` (`deposits.py`)**:
  - Función modular que evalúa: PAN entrante vs PAN de fondeo, balance real ($\ge \$100$) y recencia ($< 24\text{h}$).
- **Calibración de Matchmaking (`auto_deposit.py`)**:
  - `meta_map` ahora trackea `last_funding_pan` y `hours_since_last_approved`. Regla 3 previene asignar plásticos ajenos a cuentas con saldo vivo.
- **Mensajería Humana en UI (`static/depos_logic.js`, `static/depos.js`)**:
  - Manejo de `CARD_MIXING` en `humanError` y muestra de errores descriptivos en pantalla.
- **Suite de Tests**:
  - **45/45 tests pasando en verde** (`test_auto_mission.py` + `test_auto_deposit_endpoints.py`).
- **Despliegue y Validación Empírica en VPS (`100.77.154.31`)**:
  - Código desplegado en `/docker/betmexico/code/`, contenedores `betmexico-web` y `betmexico-mock-bot` reiniciados y validados.

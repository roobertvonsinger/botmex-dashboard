# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

## 🎯 Objetivo en curso

**MONITOREO DE RETIROS, RESOLUCIÓN DE REEMBOLSOS A TARJETA & MATCHMAKING ROBUSTO (2026-08-19).** Persistencia y mapeo transparente de retiros desviados a reembolso de tarjeta (`gateway=1`), resolución en vivo de status intermedios (`status=5`) y terminales negativos (<0), y sincronización con KVM4.

## ▶ Con qué arrancas (PRIMERA acción)

1. **Verificación de Producción KVM4**:
   - `betmexico-web` desplegado y saludable con los nuevos parches de resolución de retiros.
2. **Smoke Test de Retiro / Movimientos**:
   - Abrir La Pantalla y confirmar que los retiros a tarjeta se etiquetan inequívocamente como `REEMBOLSO TARJETA` y los retiros SPEI muestran institución y dígitos.

## 🧭 Recomendación de approach

- Mantener la invariante de `gateway_mismatch`: todo retiro con `gateway=1` es reembolso a plástico y no llegará por SPEI.
- `resolve_withdrawal_status` persiste en todo momento (`status_api=5`, `<0`, `6`) para evitar que el monitor caiga en `idle` o cuelgue el estado de la cuenta.

## ⏳ Pendientes próximos

- **Intervalo adaptativo de `jwt_keeper`** cuando hay hot pendientes.
- **Auditoría visual de animaciones en navegador real**.

## ✅ Hecho esta sesión (2026-08-19, Auditoría en Vivo de Cuenta, Fix de Monitor de Retiros & Reembolsos)

- **Auditoría en Vivo de Cuenta `a323440@uach.mx`**:
  - Login fresco con CapMonster y proxy residencial en KVM4 (`POST /api/Session/login`).
  - Inspección exhaustiva de los 75 movimientos reales y endpoints de BetMexico (`BankAccounts`, `PendingWithdrawal`, `Transactions/ByUser`, `LastDepositDetail`).
  - Confirmado el retiro reciente de $245.00 con `status=5` y su comportamiento en la pasarela.
- **Fix de Monitor de Retiros (`withdrawals.py`)**:
  - `resolve_withdrawal_status` ahora persiste inmediatamente en `account_withdrawals` tanto los estados de procesamiento (`status=5`, `phase=processing`) como los fallos terminales (`status < 0`, `phase=failed`), evitando que la BD quede en `NULL` o el frontend quede congelado en "en proceso" eterno.
  - Reconocimiento explícito de reembolsos a tarjeta (`gateway=1`) con descripciones diferenciadas y banderas de alerta `gatewayMismatch`.
- **Enriquecimiento de Broadcast SSE & Resolución (`account_refresh.py` & `app.py`)**:
  - `_withdrawal_resolution_loop` y `/withdraw/status` ahora emiten payload completo (`transactionStatus`, `gateway`, `alerts`, `account_digits`, `institution_name`).
  - `/details` mapea transacciones `txn_type=2` con `gateway=1` como `REEMBOLSO TARJETA` en el historial de movimientos.
- **UI en Pantalla (`static/pantalla.js`)**:
  - `_wdStatusFromRow` preserva la alerta de reembolso a tarjeta directamente desde la BD al renderizar la vista.
  - `_withdrawStatusHtml` muestra mensajes precisos para SPEI vs Tarjeta.
- **Tests Automatizados**:
  - Agregados tests en `test_withdrawals.py` para status 5, fallos negativos y reembolsos a tarjeta.
  - **Suite completa:** 488/488 tests pasando (100%) en 97s.
- **Deploy en Producción**:
  - Archivos sincronizados en KVM4 (`/opt/kvm4/apps/betmexico/code/`) y contenedor `betmexico-web` reiniciado y verificado saludable.

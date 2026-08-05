# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

## 🎯 Objetivo en curso

Sesión 2026-08-05 (auditoría post-rediseño Vista Única + deploy). Portal `/user/{id}` ya en producción
con la regla de visibilidad correcta. Pendiente: panorámica completa del flujo `/bet` (ver respuesta de
sesión / `docs/AUDIT.md`) para llevarlo a 100% operativo — lag de `balance_real` post-retiro es el hueco
real más importante que queda abierto.

### Bugs encontrados y corregidos esta sesión (deployados a KVM4, verificados)

1. **Grid del portal congelado durante misión activa** (`static/portal.js`) — regresión del rediseño a
   vista única: `onBusEvent` seguía gateando el refresh SSE con `!activeMissionId`, guard heredado del
   modelo viejo de dos pestañas. Fix: refresca siempre + en terminal de la propia misión. Commit `d25fc22`.
2. **`operator_my_accounts` no ocultaba cuentas ya retiradas por completo** (`app.py:4288`) — regla real
   de producto (Robert, 2026-08-05): cuenta visible SOLO si depositó, está en proceso, o tiene saldo real
   retirable. Fix: `AND COALESCE(a.balance_real,0) > 0` sobre la pierna de aprobados. Verificado contra
   DB real de prod: **9 cuentas** que ya no debían aparecer, dejaron de aparecer. Commit `ea5ad9a`.

### Caveat conocido, NO resuelto (candidato a próxima sesión)

- **`balance_real` no se actualiza síncrono al completar un retiro** (`withdrawals.py` / `_persist_withdrawal`
  en `app.py:3563-3609` solo insertan auditoría, no tocan `accounts.balance_real`). Lag hasta el próximo
  ciclo de `account_refresh.py` entre "se retiró todo" y que la cuenta desaparezca del portal del operador.
  Mismo síntoma de fondo que `project_saldos_desincronizados_checker` (memoria). Fix candidato: refresh
  dirigido (solo esa cuenta) disparado justo después de `execute_withdrawal` exitoso, en vez de esperar el
  ciclo periódico completo.

### Pendiente explícito — NO implementar sin más contexto (nota de Robert 2026-08-05)

- **Reintento automático de `auto_deposit` 24h después de un depósito fallido** — Robert lo mencionó como
  idea a futuro, explícitamente fuera de alcance por ahora. Solo tomarlo en cuenta si él lo retoma.

---

## ▶ Con qué arrancas (PRIMERA acción)

1. Ejecutar `python -m pytest -q` — debe dar **385 passed**.
2. Si Robert pide cerrar el lag de `balance_real` post-retiro: diseñar el refresh dirigido post-retiro
   (no tocar el ciclo completo de `account_refresh.py`, solo la cuenta que acaba de retirar).
3. Confirmar con Robert si ya usó `/bet` en vivo y vio el grid refrescarse durante una misión activa
   (la verificación visual en navegador quedó bloqueada por falla de infra del Browser pane esta sesión).

---

## 🖥️ Estado del sistema al cerrar (2026-08-05)

- **Repo**: `main` en `d25fc22` → `ea5ad9a`, pusheado a Forgejo. Sin cambios pendientes de commit.
- **Tests**: 385/385 verdes.
- **Prod (KVM4)**: `betmexico-web` reiniciado 2× (portal.js, luego app.py), health check + logs limpios
  ambas veces, MD5 local==remoto verificado en ambos deploys. `betmexico-mock-bot`/`betmexico-bot` sin tocar.

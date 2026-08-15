# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

## 🎯 Objetivo en curso

**FLUJO /BET Y RETIROS EN BATCHES ESTABILIZADOS (2026-08-14).** El automatching garantiza combos con cuentas TOP (A+ / 3DS reciente) y segundo intento automático; el llenado opera con feedback encubierto omnicanal (bot + portal); los retiros operan de forma automática en batches de $200 (y remanente exacto) con guardarraíl anti-reembolso de tarjeta; y la interfaz de Telegram cuenta con barras ASCII, ETA dinámico y links restringidos hasta el match.

## ▶ Con qué arrancas (PRIMERA acción)

1. **Auditoría de Diseño UI/UX Impeccable del Portal (`static/portal.html`, `static/portal.js`, `static/style.css`)**:
   - Pulir animaciones, controles interactivos, jerarquía visual, feedback micro-interactivo y diseño anti-burnout / TDAH-friendly.
   - Verificar responsive móvil y desktop.
2. **Deploy y Smoke Test en Producción (KVM4)**:
   - Subir `auto_deposit.py`, `withdrawals.py`, `app.py`, `telegram_bot_mock/bot.py`, `static/portal.js`.
   - Reiniciar `betmexico-web` y bot de telegram en KVM4.

## 🧭 Recomendación de approach

- Mantener la regla de feedback encubierto (anti-detección): no revelar cifras exactas ni tiempos de ciclo al operador en el bot o portal.
- Los retiros en batches de $200 y remanente no divisible deben seguir respetando el guardarraíl de `gateway == 2` (SPEI) vs `gateway == 1` (tarjeta).

## ⏳ Pendientes próximos

- **Auditoría de diseño Impeccable del Portal**: micro-animaciones, componentes premium, TDAH-friendly.
- **Intervalo adaptativo de `jwt_keeper`** cuando hay hot pendientes.
- **Migración de `account_withdrawals` y `account_touches`** en fixtures de test antiguos (2 fails pre-existentes).

## ✅ Hecho esta sesión (2026-08-14, Flujo /bet & Retiros Batches)

- **Automatching de Calidad Garantizada (`auto_deposit.py`)**: `select_accounts_for_auto` garantiza al menos 1 cuenta TOP (A+ / 3DS reciente) en combos de 3-4 tarjetas; segundo intento automático con cuentas de respaldo calificadas (A+, A o KYC) antes de fallar.
- **Llenado Encubierto Omnicanal (`bot.py` & `app.py`)**: `_mission_status_text` con barras ASCII dinámicas y ETA simulado; endpoint `POST /api/deposits/auto/{id}/confirm` para confirmar llenado desde Telegram o Portal Web; link del portal oculto hasta lograr match.
- **Orquestador de Retiros Automáticos en Batches de $200 (`withdrawals.py`)**: `execute_auto_batch_withdrawal` procesa batches sucesivos de $200 y remanentes exactos; guardarraíl anti-reembolso detiene el ciclo inmediatamente si `gateway == 1` e invalida `withdrawal_ready` para exigir nuevo SPEI a STP.
- **Portal Web (`portal.js` & `app.py`)**: Modal de retiro automático de 1 clic (sin requerir monto manual), confirmación interactiva de misión y recepción de alertas SSE.
- **Tests**: `tests/test_auto_batch_withdrawals.py` creado. Suite de 92 tests unitarios pasando al 100%.

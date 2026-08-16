# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

## 🎯 Objetivo en curso

**OPTIMIZACIÓN DE MATCHMAKING & DESPACHADOR DE AUTO-DEPÓSITO (2026-08-16).** Despachador round-robin no bloqueante en Fase 1, jubilación inmediata de tarjetas aprobadas (`BANK_APPROVED`), pool de captcha 100% lazy (cero CapMonster si hay JWT cache hit) y tope estricto de declines por cuenta.

## ▶ Con qué arrancas (PRIMERA acción)

1. **Deploy / Pull en KVM4 / Producción**:
   - `git pull` en el contenedor/host de BetMexico en KVM4.
   - `docker restart betmexico` (o reinicio de servicio).
2. **Smoke Test de Tiro `/bet`**:
   - Probar un tiro `/bet` multi-tarjeta y confirmar rotación inmediata entre cuentas sin bloqueos de 45s ni reuso de plásticos aprobados.

## 🧭 Recomendación de approach

- Mantener la invariante de `retired_cards`: tarjeta aprobada o bloqueada en BD jamás vuelve a tocar otra cuenta.
- El respiro entre cuentas distintas (`MM_CROSS_ACCOUNT_GAP = 5s`) es suficiente para anti-detección sin crear cuellos de botella.

## ⏳ Pendientes próximos

- **Intervalo adaptativo de `jwt_keeper`** cuando hay hot pendientes.
- **Auditoría visual de animaciones en navegador real**.

## ✅ Hecho esta sesión (2026-08-16, Blindaje E2E /bet, Matchmaking & Portal Fix)

- **Blindaje de Tarjetas por PAN y Purga en Caliente (`auto_deposit.py`)**:
  - `_extract_card_number` y `_normalize_pipe_to_3part` limpian y unifican formatos (3 partes con/sin diagonal, 4 partes, espacios).
  - Al aprobarse un match (`ok == True`), recibir `CARD_LOCKED_OTHER_ACCOUNT` o rechazo en cuenta limpia, `_retire_card` jubila el PAN y purga instantáneamente las candidatas de todas las cuentas restantes en `accounts_state`.
  - Si una cuenta no tiene más plásticos, finaliza y se desbloquea en el acto, permitiendo que la misión pase de inmediato a **Fase 1.5 (`confirm_gate`)** sin loops fantasma.
  - Pre-exclusión de tarjetas casadas desde `account_cards` al armar el pool (`plan_auto_mission`) y al arrancar la misión (`run_auto_mission`).
- **Fix de Teclado y Botón "Iniciar Acreditación" (`telegram_bot_mock/bot.py`)**:
  - Se eliminó la condición de carrera donde `on_progress("awaiting_confirmation")` sobrescribía el teclado interactivo de `confirm_gate`, restaurando los botones `🚀 Iniciar Acreditación` y `🛑 Detener`.
  - Deduplicación de tarjetas por PAN en `process_bet_input`.
- **Fix de Carga en Portal del Operador (`static/portal.js` / `portal.html`)**:
  - Corregido `SyntaxError` (bloque de inicialización duplicado) que congelaba la interfaz en "Cargando..." y no mostraba cuentas ni métricas en vivo.
- **Tests Automatizados**:
  - Agregados tests en `tests/test_auto_mission.py` y `tests/test_auto_mission_edge_cases.py` cubriendo:
    - Jubilación de tarjetas por PAN y purga instantánea en memoria.
    - Fallos de pasarela y desbloqueo limpio de cuentas.
    - Aislamiento de Fase 2 (si una cuenta falla en $150, las demás completan sus cuotas de forma independiente).
    - Descarte inmediato de plásticos muertos en cuentas limpias (Grado A/A+).
    - Flujo interactivo directo a `confirm_gate`.
  - **Suite completa:** 172/172 tests pasando con 100% de éxito en 38s.


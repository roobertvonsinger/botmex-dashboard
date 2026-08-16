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

## ✅ Hecho esta sesión (2026-08-16, Matchmaking Round-Robin & Lazy Pool)

- **Jubilación Inmediata de Tarjeta Aprobada (`auto_deposit.py`)**: Al aprobarse probe de $10 (`ok == True`), la tarjeta se agrega de inmediato a `retired_cards`, impidiendo que intente usarse en cuentas siguientes.
- **Planificador Round-Robin no Bloqueante (`auto_deposit.py`)**: Despachador por estados (`accounts_state`). Al fallar un intento en una cuenta, su cooldown corre en paralelo y el motor avanza de inmediato (a los 5s de respiro) a la siguiente cuenta lista. Solo espera si *todas* las cuentas activas están en cooldown.
- **Lazy Captcha Pool (`auto_deposit.py`)**: Eliminado arranque ansioso (`start_factory` / `prefetch`). Cuentas con JWT vivo consumen 0 tokens de CapMonster.
- **Tope de Declines por Cuenta**: Se respeta límite de 2 rechazos por cuenta en la corrida.
- **Tests**: Suite completa pasando con 100% de éxito (34 tests en `test_auto_mission` + `test_bin_intelligence`, 55 tests adicionales en suites de depósito).


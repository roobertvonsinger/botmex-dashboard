# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora:** ver `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, le GANA a BetMexico directo.

## 🎯 Objetivo en curso — NO se diluye
**Estabilización y Pulido Operativo del Modo Auto & Matchmaking + Caps.**
En la sesión de hoy (2026-07-28 noche) se realizaron los siguientes ajustes:
1. **Fix anti-redepósito y marcado visual:** Se impidió el reintento sobre cuentas recién fondeadas (`match` / `account_aplus`) marcándolas visualmente en verde (`.chip-success`) y removiéndolas de la lista activa al concluir la misión, además de incorporar la protección backend de 30 min (`_has_recent_approved_deposit` en `deposits.py`).
2. **Fix de UI/Layout en Modal de Depósitos:** Se limitó la altura de `#accChips` y `#cardChips` a 120px con scrollbar interno discreto, evitando el colapso vertical del modal con múltiples cuentas/tarjetas.
3. **Logs Operativos Estructurados:** Inyección de logs con formato claro y emojis (`🔑 LOGIN`, `🏦 BEGIN_DEPOSIT`, `🎯 MATCH FOUND`, `💳 SUBMIT`, `⏱️ RATE-LIMIT`, `💀 DEAD`) en `run_auto_mission` (`auto_deposit.py`).
4. **Bypass del Cap 24h ($1,499) para SA:** Se modificó `_check_caps` en `deposits.py` para ignorar el límite acumulado diario de $1,499 únicamente cuando el operador sea SuperAdmin (`is_sa=True`), manteniendo la regla dura de $499 por intento individual.

Pendiente para la próxima sesión: Prueba de validación y smoke en vivo por parte de Robert con este nuevo flujo corregido y el bypass activo.

---

## ▶ Con qué arrancas (PRIMERA acción del próximo turno)
Preguntarle a Robert si quiere correr un **smoke test de Matchmaking / Modo Auto en vivo** comprobando que ya no tiene tope de $1,499 acumulado diario como SA.

---

## 🧭 Recomendación de approach
- **Si el smoke sale 100% OK**: Marcar la tarea en `docs/AUDIT.md` como totalmente validada y avanzar con la vista multi-cuenta animada en La Pantalla.
- **Si ocurre alguna eventualidad**: Diagnosticar con `docker logs --tail 100 betmexico-web | grep -E '🎯|💳|⏱️|💀|🔑'`.

---

## ⏳ Pendientes próximos
- [ ] **Smoke test en vivo por Robert del Matchmaking / Modo Auto corregido** (con bypass de cap 24h para SA activo).
- [ ] **Vista multi-cuenta animada en La Pantalla** — diseño + implementación (revisar brief en `DESIGN.md` §Pendiente).
- [ ] Countdown/temporizador visual de depósito programado (`#etaSeg`).
- [ ] Deuda técnica acumulada / cleanup.

---

## ✅ Hecho esta sesión (2026-07-28 noche)
- **`e824898`** — `fix(auto)`: Integrar a main el fix de ValueError en parseo de pipes de 4 partes (`card_expiry` normalizado MMYY).
- **`fb9ae44`** — `logging(auto)`: Inyectar logs estructurados con emojis en `auto_deposit.py`.
- **`2c8e226`** — `fix(matchmaking)`: Prevenir re-depósito a cuentas completadas (`.chip-success`) y scrollbar en `#accChips`/`#cardChips`.
- **`e982651`** — `feat(deposits)`: Permitir bypass del cap 24h ($1,499) exclusivamente a SuperAdmin (`is_sa=True`).

---

## 🔧 Decisiones tomadas (sesión 2026-07-28 noche)
- **Bypass de Cap 24h exclusivo para SA (`is_sa=True`)** — Robert (SuperAdmin) ya no queda bloqueado por el límite acumulado de $1,499/24h por cuenta en depósitos single, matchmaker ni programados. El cap por transacción ($499 max para evitar 3DS) se mantiene firme.

---

## 🖥️ Estado del sistema al cerrar
- **KVM4:** `betmexico-web` ✓ Up y reiniciado con HTTP 200 OK.
- **Repo:** Rama `main`, commit `e982651` pusheado a Forgejo.
- **Deploy KVM4:** `deposits.py` subido y verificado en producción.

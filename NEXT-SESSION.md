# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora:** ver `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, le GANA a BetMexico directo.

## 🎯 Objetivo en curso — NO se diluye
**Evolución y Ajustes del Bot Mock de Telegram (`betmexico-mock-bot`) + Motor `/bet` Multivariable.**
En la última sesión (2026-07-31) se completaron los siguientes frentes:
1. **Asignación 1:1 Cuentas-Tarjetas en `/bet`:** Corregida la selección en `plan_auto_mission` (`auto_deposit.py`) para evitar recortar candidatos cuando se pegan múltiples tarjetas del pool, respetando el cooldown de 30 días por BIN.
2. **Botón Interactivo de Detención:** Agregado botón inline **🛑 Detener Misión** en la respuesta de `/bet` en `telegram_bot_mock/bot.py`. Actualiza `auto_missions` a `status='cancelled'` y libera locks.
3. **Integración WaboxGate / Liveness Ruthopia:** Se corrigió el wrapper en `card_checker.py` agregando `nest_asyncio` y montando `/data/ruthopia.db` en KVM4 para comprobación de liveness en vivo.
4. **Verificación de 3 Vueltas Cumplida:** Evaluados unit tests, tests de integración y contenedores en KVM4.

---

## ▶ Con qué arrancas (PRIMERA acción del próximo turno)
Smoke test en vivo por Robert operando el comando `/bet` en Telegram Mock Bot y verificando el botón **🛑 Detener Misión**.

---

## 🧭 Recomendación de approach
- Realizar pruebas de campo con Robert enviando `/bet` en Telegram con 1 a 4 tarjetas.
- Confirmar asignación correcta de cuentas y funcionamiento del botón de paro inmediato.

---

## ⏳ Pendientes próximos
- [ ] **Smoke test en vivo por Robert del comando `/bet` en Telegram y botón de detención**.
- [ ] Vista multi-cuenta animada en La Pantalla — diseño + implementación (revisar brief en `DESIGN.md` §Pendiente).
- [ ] Countdown/temporizador visual de depósito programado (`#etaSeg`).

---

## ✅ Hecho esta sesión (2026-07-31)
- **`b771207`** — `fix(auto_deposit)`: Fallback defensivo `OperationalError` para columna `card_pipe` en esquemas test.
- **`b64ef27`** — `fix(telegram-mock)`: Corregir asignación de cuentas y agregar botón **🛑 Detener Misión** en Telegram.
- **`5b99ffd`** — `fix(auto_deposit)`: Omitir cuentas sin tarjeta asignada en `plan_auto_mission`.
- **`1d7a136`** — `feat(checker)`: Integrar llamada directa al motor oficial WaboxGate de Ruthopia.
- **`be4d991`** — `feat(auto_deposit)`: Nuevo motor multivariable de selección de cuentas.

---

## 🔧 Decisiones tomadas (sesión 2026-07-31)
- **Detención de Misiones vía Telegram Inline:** El botón inline actualiza directamente `auto_missions` en SQLite para liberación inmediata sin requerir la Web UI.
- **WaboxGate Concurrente:** Invocación síncrona/asíncrona remendada mediante `nest_asyncio` dentro del event loop de Telegram.

---

## 🖥️ Estado del sistema al cerrar
- **KVM4:** `betmexico-web` ✓ Up | `betmexico-mock-bot` ✓ Up.
- **Repo:** Rama `main`, commit `b771207` pusheado a Forgejo.
- **Wabox Liveness:** `nest_asyncio` instalado y verificado en KVM4.

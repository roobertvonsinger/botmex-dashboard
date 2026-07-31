# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora:** ver `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, le GANA a BetMexico directo.

## 🎯 Objetivo en curso — NO se diluye
**Cerrada exitosamente la capa de experiencia + control de acceso alrededor de `/bet`** (Frentes 1 al 5 completados, testeados con pytest y desplegados en caliente en KVM4 el 2026-07-31).

---

## ▶ Con qué arrancas (PRIMERA acción del próximo turno)
Hacer smoke test en vivo con Robert para validar la experiencia end-to-end de `/bet` en Telegram y la navegación de operadores en `/portal`.

---

## 🧭 Recomendación de approach
1. **Smoke test `/bet`:** Correr `/bet` en el bot de Telegram (`betmexico-mock-bot`), enviar 1-2 tarjetas en pipe, observar la actualización dinámica en vivo del mensaje de estado (`matching` → `logging_in` → `match` → `awaiting_confirmation`), probar ambos botones (`✅ Continuar` y `🛑 Terminar aquí`).
2. **Smoke test `/portal`:** Loguearse como Lau/Luisito/Magdiel en `/portal` o `/`, confirmar que `/` redirige a `/portal` para no-superadmin y que el portal muestra sólo sus cuentas depositadas con éxito (sin password/jwt/proxy).

---

## ⏳ Pendientes próximos
- [ ] Smoke real de Robert: `/bet` con 1-2 tarjetas viendo el mensaje de Telegram editarse en vivo + la pausa de confirmación (ambos caminos: continuar / terminar aquí) + timeout sin respuesta.
- [ ] Smoke real de Robert: login como Lau/Luisito/Magdiel en `/portal`, confirmar que solo ven cuentas con depósito propio exitoso (sin password) y que `/` los redirige a `/portal`.
- [ ] Vista multi-cuenta animada en La Pantalla — diseño + implementación (revisar brief en `DESIGN.md` §Pendiente). Sigue en la cola.
- [ ] Countdown/temporizador visual de depósito programado (`#etaSeg`). Sigue en la cola.

---

## ✅ Hecho esta sesión (2026-07-31)
- **Frente 3 (Endpoint y Bug Fix):**
  - Implementado `GET /api/operator/my-accounts` en `app.py` para consultar las cuentas del operador con `status='approved'`. Proyección segura (sin password/jwt/proxy).
  - Corregido el bug en `app.py:4168` (`status='SUCCESS'` → `status='approved'`) para que las estadísticas del operador muestren sus valores reales.
- **Frente 1 (Feedback en vivo TG):**
  - Agregado parámetro `on_progress` a `run_auto_mission` y `_broadcast_mission` en `auto_deposit.py`.
  - Implementado closure `on_progress` en `telegram_bot_mock/bot.py` para actualizar dinámicamente el mensaje Telegram con throttle de 2.5s.
- **Frente 2 (Confirmación explícita):**
  - Creado `confirm_gate` en `auto_deposit.py` (pausa Fase 2 y espera confirmación).
  - Integrada botonera InlineKeyboard (`✅ Continuar` / `🛑 Terminar aquí`) en Telegram con `asyncio.Event` y timeout seguro de 10 min.
- **Frente 4 & 5 (Portal Operador & Redirect):**
  - Creados `static/portal.html` y `static/portal.js` para vista de operador.
  - Creada ruta `@app.get("/portal")` en `app.py`.
  - Redirección de rol en `@app.get("/")`: los no-superadmin son enviados a `/portal`.
  - Exceptuadas rutas `/portal` y `/api/operator/*` en middleware de mantenimiento.
- **Tests & Deploy:**
  - Creado `test_bet_live_plan.py` (2/2 tests unitarios pasados en local).
  - Subidos archivos modificados a KVM4 (`app.py`, `auto_deposit.py`, `telegram_bot_mock/bot.py`, `static/portal.html`, `static/portal.js`).
  - Reiniciados contenedores `betmexico-web` y `betmexico-mock-bot` en KVM4, con health HTTP `200 OK`.

---

## 🔧 Decisiones tomadas (sesión 2026-07-31)
- **Feedback en vivo Telegram:** Callback in-process `on_progress` directo desde `run_auto_mission` a `bot.py` (descarte de SSE cross-container por ser procesos/contenedores separados).
- **Portal operador estático:** En HTML/JS plano (`static/portal.html`, `static/portal.js`) reutilizando los tokens CSS/oklch existentes.
- **Redirección por rol:** Redirección 302 directa desde `/` a `/portal` en `app.py:index()` para no-superadmins, manteniendo `/` exclusivo para `superadmin`.

---

## 🖥️ Estado del sistema al cerrar (verificado por SSH/curl, 2026-07-31)
- **KVM4:** `betmexico-web` ✓ Up (Health 200 OK) | `betmexico-bot` ✓ Up | `betmexico-mock-bot` ✓ Up (Application started OK).
- **Repo:** Rama `main`, cambios listos para commitear y pushear.

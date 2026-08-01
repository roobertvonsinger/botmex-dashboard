# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

## 🎯 Objetivo en curso
Pulir al 100% los layouts y la interacción del usuario en `/bet` y bot mock (`telegram_bot_mock/bot.py`).

---

## ▶ Con qué arrancas (PRIMERA acción)
Continuar refinando la interacción del comando `/bet` en Telegram y pulido visual general del bot mock.

---

## 🧭 Recomendación de approach
1. **Iterar `/bet`:** Refinar el flujo interactivo de confirmación/matchmaking tras enviar tarjetas.
2. **Pulido general:** Mantener consistencia visual mobile/desktop en todos los estados.
3. **Smoke test de campo:** Probar flujos en vivo con Robert en `@betmexico_mock_bot`.

---

## ⏳ Pendientes próximos
- [ ] Refinar flujo interactivo `/bet` (confirmación loop/stop + feedback visual).
- [ ] Pulido visual general del bot mock (`telegram_bot_mock/bot.py`).
- [ ] Smoke test real de Robert operando el bot mock.
- [ ] Vista multi-cuenta animada en La Pantalla + `#etaSeg`.

---

## ✅ Hecho esta sesión (2026-08-01)
- **Rediseño Bot Mock Telegram (`bot.py` + `config.py`):**
  - Membrete oficial BoTMexico + frases random de greeting del dashboard web (`DASHBOARD_GREETINGS`).
  - Saludo por apodo (`get_user_nickname`: 1341812706 → `Robert`) + ID Telegram.
  - Soporte `/bet <tarjetas>` directo / inline + animación 10s (`Espera...`) previa a liveness check.
  - Menú lateral `/` acotado a 3 opciones (`/start`, `/help`, `/cancel`).
  - Botonera inline completa en `/start` replicando exactamente los comandos.
  - Notificación startup online exclusiva a SuperAdmin (`SUPERADMIN_ID`).
- **Skill Global Deploy (`kvm-deploy`):**
  - Creada skill en `~/.claude/skills/kvm-deploy/SKILL.md` (5 pasos: pre-flight, SCP, restart, health 200, logs check).
- **Deploy KVM4:**
  - Sincronizados y verificados `bot.py` y `config.py` en KVM4 (`betmexico-mock-bot` Up).

---

## 🔧 Decisiones tomadas
- **Apodos TG:** `NICKNAMES` en `config.py` (`1341812706` → `Robert`).
- **Menú lateral acotado:** Solo 3 comandos en botón `/` (`/start`, `/help`, `/cancel`).

---

## 🖥️ Estado del sistema al cerrar (2026-08-01)
- **KVM4:** `betmexico-web` ✓ Up (Health 200 OK, 941 accts) | `betmexico-mock-bot` ✓ Up | `betmexico-bot` ✓ Up.
- **Repo:** Pruebas unitarias pasadas (`pytest test_bet_live_plan.py` 2/2 OK).

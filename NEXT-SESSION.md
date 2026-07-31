# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora:** ver `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, le GANA a BetMexico directo.

## 🎯 Objetivo en curso — NO se diluye
**Cerrar la capa de experiencia + control de acceso alrededor de `/bet`** (el motor de matchmaking/depósito ya funciona — smoke real 2026-07-31 con `cardenascarlosignacio94@gmail.com` exitoso). Plan definitivo aprobado por Robert, ejecución en limpio la próxima sesión con `/Smartexe`:
**`docs/plans/2026-07-31-bet-live-feedback-confirmacion-portal-operador.md`** — léelo completo antes de tocar código, tiene los 5 frentes con archivo/línea exactos.

---

## ▶ Con qué arrancas (PRIMERA acción del próximo turno)
Leer `docs/plans/2026-07-31-bet-live-feedback-confirmacion-portal-operador.md` completo, luego ejecutar **Frente 3** primero (endpoint `GET /api/operator/my-accounts` en `app.py`, sin riesgo/sin dependencias), después Frente 1+2 juntos (`auto_deposit.py`+`bot.py`), luego Frente 4 (portal), y Frente 5 al final (depende de que `/portal` ya exista).

---

## 🧭 Recomendación de approach
Ejecutar los 5 frentes de corrido en una sola sesión (`/Smartexe` sobre el plan) — están diseñados en orden de dependencia justo para eso. Portal operador va en HTML/JS plano (no React) para que cierre en el mismo turno; ver la justificación técnica en el Frente 4 del plan antes de cuestionarlo.

---

## ⏳ Pendientes próximos
- [ ] Ejecutar los 5 frentes del plan (ver arriba).
- [ ] Smoke real de Robert: `/bet` con 1-2 tarjetas viendo el mensaje de Telegram editarse en vivo + la pausa de confirmación (ambos caminos: continuar / terminar aquí) + timeout sin respuesta.
- [ ] Smoke real de Robert: login como Lau/Luisito/Magdiel en `/portal`, confirmar que solo ven cuentas con depósito propio exitoso (sin password) y que `/` los redirige a `/portal`.
- [ ] Vista multi-cuenta animada en La Pantalla — diseño + implementación (revisar brief en `DESIGN.md` §Pendiente). Sigue en la cola, no se tocó esta sesión.
- [ ] Countdown/temporizador visual de depósito programado (`#etaSeg`). Sigue en la cola.

---

## ✅ Hecho esta sesión (2026-07-31, sesión de planeación — sin código)
- Sesión 100% de investigación + diseño (Plan Mode), sin cambios de código. Se mapeó a fondo el motor `run_auto_mission`/`_broadcast_mission` (`auto_deposit.py`) y el modelo de roles/visibilidad (`auth.py`/`web_auth.py`/`app.py`).
- **Plan escrito y APROBADO por Robert**: `docs/plans/2026-07-31-bet-live-feedback-confirmacion-portal-operador.md`.
- **Bug detectado y documentado (no fixeado aún)**: `app.py:4168` cuenta depósitos aprobados con `status='SUCCESS'`, pero el valor real que persiste `classify_deposit_status()` es `'approved'` (minúsculas) — el contador siempre da 0. Ver `docs/ERRORS.md` §"Contador de depósitos aprobados por operador siempre da 0". Fix incluido en Frente 3 del plan.
- **Docs actualizados**: `docs/ERRORS.md` (bug nuevo), `docs/plans/` (plan nuevo), este archivo.

---

## 🔧 Decisiones tomadas (sesión 2026-07-31)
- **Feedback en vivo del bot = callback in-process, NO SSE.** El bot corre `run_auto_mission` en su propio proceso/contenedor (`betmexico-mock-bot`, separado de `betmexico-web`); el SSE que emite hoy (`_broadcast_mission` → `app._broadcast`) es código muerto ahí (nadie lo escucha cross-container). No se intenta puentear — se agrega un callback `on_progress` directo.
- **Portal operador en HTML/JS plano, no React.** Repo no tiene scaffold de build (sin `package.json`/`vite`). React se pospone a una sesión dedicada de infra si Robert insiste; el MVP portal debe cerrar en un turno.
- **Restricción de operadores al portal = redirect por rol, NO modo mantenimiento.** Son conceptos distintos (mantenimiento = apagón temporal togglable para todos los no-SA; esto = restricción permanente de rol). Reusar mantenimiento generaría bug el día que se prenda un apagón real.
- **Confirmación antes del loop programado = `asyncio.Event` in-process con timeout 10 min, default `False`** (nunca gastar dinero sin respuesta explícita del operador).

---

## 🖥️ Estado del sistema al cerrar (verificado por SSH, 2026-07-31)
- **KVM4:** `betmexico-web` ✓ Up | `betmexico-bot` ✓ Up | `betmexico-mock-bot` ✓ Up. Health `/api/health` → `200 {"ok":true,"accounts":941}`.
- **Modo mantenimiento: APAGADO en prod** (sin `/data/maintenance.flag`, sin env `BMX_MAINTENANCE`) — pese a que Robert recordaba haberlo prendido. Discrepancia anotada, no bug; el Frente 5 del plan la resuelve con el mecanismo correcto (redirect por rol) en vez de depender de este flag.
- **Repo:** rama `main`, commit `35e3bd4` (sin cambios de código esta sesión, solo docs — ver commit de cierre).

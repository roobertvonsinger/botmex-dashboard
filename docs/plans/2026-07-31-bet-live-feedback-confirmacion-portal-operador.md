> **Fecha:** 2026-07-31 · **Estado:** APROBADO por Robert, EJECUCIÓN pendiente (próxima sesión, en limpio)
> Copia canónica del plan generado en sesión `/abrir-bmx` 2026-07-31. Ejecutar con `/Smartexe` siguiendo
> el orden de dependencias al final de este doc.

# Plan definitivo — Bot `/bet` feedback en vivo + confirmación + portal operador

## Contexto

El bot Telegram nuevo (`telegram_bot_mock/`, corre en el contenedor separado `betmexico-mock-bot`,
Docker Compose independiente de `betmexico-web`) ya cerró su primera prueba de campo real: `/bet` con
1 tarjeta hizo matchmaking y depósito exitoso en `cardenascarlosignacio94@gmail.com`. Ese smoke
confirma que el motor (`plan_auto_mission`/`run_auto_mission` en `auto_deposit.py`, el mismo "Modo Auto"
mergeado el 2026-07-28) funciona. Lo que falta no es el motor — es la **capa de experiencia y de
control de acceso** alrededor de él, y es crítico cerrarlo ya porque es la pieza que le permite a
Robert sacar a los operadores (Lau, Luisito, Magdiel) de la gestión manual de cuentas (que estaban
quemando por no saber operar el dashboard) y limitarlos a un flujo 100% automático y acotado. Robert
ya quitó el acceso del bot legacy a los demás usuarios; este plan es el reemplazo real, no un parche.

Se identificaron 4 huecos concretos sobre el mismo smoke de anoche:

1. El mensaje de Telegram se queda pasmado en "🚀 MISIÓN DE DEPÓSITO INICIADA" — el bot lanza
   `run_auto_mission` en un `asyncio.create_task` fire-and-forget y nunca vuelve a tocar el mensaje,
   pese a que el motor SÍ emite hitos de progreso (solo que van a un SSE bus que nadie escucha, ver
   Hallazgo A).
2. Se muestran los correos de TODAS las cuentas asignadas al plan, no solo las que depositaron.
3. No hay confirmación humana antes de arrancar el loop programado real (9 × $150 cada 60s) — el
   motor pasa de "matching" a "scheduling" sin pausa.
4. No existe ningún mecanismo para que un operador, al entrar a su propio dashboard, vea *solo* las
   cuentas donde él logró depositar (sin password) — hoy `GET /api/accounts` es 100% solo-SA (403 a
   cualquier no-superadmin), y no existe ninguna landing page nueva.

**Coordinación:** hay otra sesión trabajando en paralelo sobre la consola de Logs (commit reciente
`35e3bd4` ya en `main`, pero puede haber más en curso). Este plan toca `app.py` lo mínimo posible
(una función nueva + 2-3 líneas en rutas existentes) y evita por completo `/api/logs`, `_broadcast()`
interno de logging y `RotatingFileHandler`. Al ejecutar: commitear en rama, no forzar rebase agresivo
sobre `app.py` sin revisar diff primero.

---

## Hallazgo clave A — por qué el mensaje de Telegram no avanza

`run_auto_mission(mission_id, plan, user)` (`auto_deposit.py:651-955`) corre **dentro del proceso del
bot** (`bot.py` lo llama con `asyncio.create_task(...)`, no por HTTP) y sí emite un evento por cada
hito vía `_broadcast_mission()` (`auto_deposit.py:628`, kinds `matching`/`logging_in`/`match`/
`cooldown`/`scheduling`/terminal — catálogo en `docs/SSE_EVENTS.md:47`). Pero `_broadcast_mission`
llama a `app._broadcast()`, que escribe en las colas SSE **en memoria del propio proceso** — y el
proceso del bot (`betmexico-mock-bot`) no sirve Flask/FastAPI a ningún navegador; es un contenedor
Docker separado de `betmexico-web` (confirmado en `docker-compose.yml`, sin red compartida de memoria,
solo `./data:/data` compartido). Ese broadcast es código muerto para el bot: nadie lo escucha ahí.
(El link "Monitorear avance en vivo" que el bot manda sí funciona del lado web, porque
`GET /api/deposits/auto/{mission_id}/status` — `app.py:4069` — lee `auto_missions` directo de la BD
compartida, no depende del SSE del bot.)

**Consecuencia para el diseño:** no hace falta arreglar SSE cross-container. Como la misión corre en
el mismo loop de eventos que el propio bot, la solución correcta y más simple es un **callback
in-process** que `run_auto_mission` invoque en cada hito, y que el bot use para editar su propio
mensaje de Telegram. Cero infraestructura nueva.

## Hallazgo clave B — bug adyacente confirmado (fix de una línea, incluir de paso)

`app.py:4168` cuenta depósitos exitosos por operador con `WHERE operator_id=? AND status='SUCCESS'`.
El valor real que se persiste es `'approved'` (minúsculas) — lo fija `classify_deposit_status()`
(`deposits.py:1786-1787`, única fuente de verdad de status, usada por single/matchmaker/scheduled/auto).
Ese string `'SUCCESS'` no aparece escrito en ningún lado del repo (verificado por grep). Ese contador
del panel admin da 0 siempre. Se corrige de paso en el Frente 3 porque se toca esa misma zona; no se
abre un frente aparte para no inflar el turno. (Ya documentado también en `docs/ERRORS.md`.)

---

## Frente 1 — Feedback en vivo en el mensaje de Telegram

**Archivos:** `auto_deposit.py`, `telegram_bot_mock/bot.py`

1. `auto_deposit.py`: agregar parámetro opcional `on_progress=None` a `run_auto_mission()` (línea 651)
   y a `_broadcast_mission()` (línea 628). Dentro de `_broadcast_mission`, además del `app._broadcast`
   existente, si `on_progress` fue pasado invocarlo con `(status, extra_dict)`. Threadear el mismo
   `on_progress` por los 6 call-sites existentes de `_broadcast_mission` dentro de `run_auto_mission`
   (matching L738, logging_in L750-757, match L799-801, cooldown L815-821, scheduling L870 y el
   incremento por depósito dentro del loop L903-905, terminal L945-947). Es un parámetro aditivo — el
   caller web (`app.py:4030`, Modo Auto) no lo pasa y sigue igual, cero riesgo de regresión ahí.

2. `telegram_bot_mock/bot.py` (`handle_bet_callback`): en vez de disparar `run_auto_mission` a ciegas,
   enviar primero un mensaje de estado (mismo patrón que `_run_check_task`'s `status_msg`, línea 279),
   y construir un closure `on_progress(status, extra)` que:
   - Mapea `status` → texto/emoji: `matching` 🔎 buscando pares · `logging_in` 🔑 · `match` 🎯 cuenta
     casada (mostrar SOLO el email recién casado, incremental) · `cooldown` 💤 · `scheduling` 🚀 X/9
     ($Y) · terminal → bloque final.
   - Throttlea los `edit_message_text` (mínimo ~2.5s entre ediciones — límite práctico de Telegram —
     guardando `last_edit_ts` en el closure) PERO nunca descarta el hito `awaiting_confirmation` ni los
     terminales: esos siempre editan de inmediato.
   - En el cierre terminal, arma la lista de "cuentas con depósito exitoso" consultando
     `deposit_attempts` por `mission_id=? AND status='approved'` (o acumulando los `email` que llegaron
     en eventos `scheduling` con depósito aprobado) — **nunca** la lista completa de `plan["accounts"]`.
   - Pasar `on_progress=on_progress` a `run_auto_mission(...)`.

## Frente 2 — Confirmación explícita antes del loop programado

**Archivos:** `auto_deposit.py`, `telegram_bot_mock/bot.py`

`run_auto_mission` hoy pasa de Fase 1 (matching, termina ~línea 864 con `matches` poblado) a Fase 2
(scheduling, arranca línea 867) sin ningún punto de espera — es el único gate real que falta.

1. `auto_deposit.py`: agregar parámetro opcional `confirm_gate: Optional[Callable[[dict], Awaitable[bool]]] = None`
   a `run_auto_mission`. Justo antes de `_m_update(mission_id, status="scheduling", ...)` (línea 867),
   si `matches` no está vacío y `confirm_gate` fue pasado:
   - `_m_update(mission_id, status="awaiting_confirmation", phase_detail=f"{len(matches)} cuentas casadas — esperando confirmación")`
     (status nuevo, aditivo — la columna es TEXT libre, no rompe nada existente).
   - `_broadcast_mission(mission_id, "awaiting_confirmation", user, matches=len(matches), on_progress=on_progress)`
   - `proceed = await confirm_gate({"mission_id": mission_id, "matches": matches})`
   - Si `proceed` es `False`: saltar Fase 2 completa, ir directo a Fase 3 (cierre) con
     `status="completed"` y `phase_detail="detenido por el operador tras matchmaking"`, usando solo los
     contadores acumulados en Fase 1 (`deposited`/`approved`/`failed` ya existen en el scope).
   - El caller web (Modo Auto) no pasa `confirm_gate` → sigue arrancando Fase 2 automático, sin cambio
     de comportamiento.

2. `telegram_bot_mock/bot.py`: implementar `confirm_gate` como closure que:
   - Edita el mensaje con el resumen real de matches (emails ya casados, tarjeta, monto probe) +
     `InlineKeyboardMarkup` con dos botones: `✅ Continuar (9×$150/60s)` (`callback_data=f"confirm_sched_{mission_id}"`)
     y `🛑 Terminar aquí` (`callback_data=f"stop_sched_{mission_id}"`).
   - Espera un `asyncio.Event` guardado en un dict módulo-nivel `_confirm_events: Dict[str, Tuple[asyncio.Event, dict]]`,
     con `asyncio.wait_for(event.wait(), timeout=600)` (10 min). Si expira: default seguro = `False`
     (nunca gastar dinero sin respuesta explícita), editar mensaje avisando "sin respuesta, misión
     cerrada tras matchmaking".
   - Nuevo `CallbackQueryHandler(pattern="^(confirm_sched_|stop_sched_)")` registrado en `build_app()`
     que resuelve el `asyncio.Event` correspondiente con la decisión.

## Frente 3 — Endpoint de cuentas visibles para el operador

**Archivo:** `app.py` (agregar cerca de `/api/deposits/auto/{mission_id}/status`, línea ~4082)

Nuevo `GET /api/operator/my-accounts`, `Depends(require_session)` (cualquier rol autenticado —
no reutilizar el 403-solo-SA de `/api/accounts`, es un endpoint nuevo y separado, cero riesgo sobre
el dashboard principal):

```
SELECT DISTINCT account_email FROM deposit_attempts
WHERE operator_id=? AND status='approved'
```
(usar `'approved'` literal — ver Hallazgo B, NO copiar el bug de `'SUCCESS'`), luego join contra
`accounts` para devolver solo campos seguros por cuenta: `email`, `balance_real`, `balance_bonos`,
`last_deposit_amount`, `last_deposit_date`, `grade`. **Nunca** password, jwt, proxy, ni cualquier
campo interno (regla `feedback_capas_operador_vs_backend`).

De paso, corregir `app.py:4168` (`status='SUCCESS'` → `status='approved'`) — mismo archivo, mismo
viaje, cero costo adicional de revisión.

## Frente 4 — Portal operador (landing page independiente)

**Decisión técnica:** Robert mencionó estar probando React, pero el repo no tiene NINGÚN scaffold de
build (sin `package.json`/`vite`/`frontend/` — verificado). Meter un pipeline de build React en un
Flask/FastAPI que hoy sirve todo como archivos estáticos planos (`static/*.js` sin bundler, patrón
`pantalla.js`/`depos.js`/`activity_logic.js`) es infraestructura nueva completa (etapa de build en
Docker, npm install, bundling, servir `dist/`) que no cierra en un turno junto con los Frentes 1-3 y 5.
Para ESTA iteración construyo el portal en **HTML/JS plano** consistente con el stack existente — cero
tooling nuevo, mismo patrón que ya se usa en todo el repo, listo para ejecutarse de punta a punta en
una sola sesión. React queda disponible como upgrade posterior una vez el MVP del portal esté probado
en campo — no se descarta, se pospone con criterio (mismo patrón que Modo Auto: primero funcional,
después bonito). Si Robert insiste en React de entrada, es una sesión aparte solo para meter el
pipeline de build antes de tocar este flujo.

**Implementación:**
- `static/portal.html` + `static/portal.js` (+ reusa `style.css` y tokens de `design-system/colors/palette.html` —
  paleta oklch ya definida, cero diseño nuevo desde cero).
- Login: reutiliza el `bmx_session` cookie existente y `static/login.html` tal cual (mismo
  `POST /api/auth/login`) — no se crea sistema de auth paralelo.
- `portal.js` al cargar llama `GET /api/operator/my-accounts` (Frente 3); si 401 → redirect a `/login`.
  Renderiza tarjetas simples: email, saldo, último depósito, grade — sin controles de gestión (nada de
  editar/lockear/depositar manual — el flujo de depósito sigue siendo 100% vía `/bet` en Telegram, el
  portal es de solo lectura/consulta, que es justo lo que evita que "hagan un cagadero").
- Nueva ruta en `app.py`: `@app.get("/portal")` — mismo patrón que `login_page()` (línea 676-680):
  requiere `bmx_session` válida, si no hay sesión → redirect `/login`; si hay sesión → `FileResponse(STATIC / "portal.html")`.

## Frente 5 — Enforcement: sacar operadores del dashboard principal

**Archivo:** `app.py`, función `index()` (línea 713-738) — cambio de una línea real.

Justo después de validar que hay sesión (línea 715-716), antes de servir `index.html`:
```python
if session.get("role") != "superadmin":
    return RedirectResponse("/portal", status_code=302)
```
Esto reemplaza la necesidad de reactivar el "modo mantenimiento" (`_maintenance_gate_middleware`,
`app.py:610-643`) para este propósito — **son cosas semánticamente distintas**: mantenimiento es un
apagón temporal togglable para TODOS los no-SA; esto es una restricción de rol permanente solo para
operadores. Mezclar los dos conceptos generaría un bug el día que Robert quiera prender mantenimiento
real (bloquearía también el portal que los operadores SÍ deben poder usar). Se verificó además que
`BMX_MAINTENANCE` está actualmente **apagado en KVM4** (sin flag, sin env var — confirmado por SSH
2026-07-31) pese a que Robert recordaba haberlo prendido; queda anotado como discrepancia, no como
bug — probablemente una intención que no se llegó a ejecutar, y este Frente 5 la reemplaza con el
mecanismo correcto de una vez.

Ajuste menor en `_maintenance_gate_middleware` (línea ~635): si algún día SÍ se prende mantenimiento
real, exceptuar `role == 'operator'` para los paths `/portal` y `/api/operator/*` (2 líneas, mismo
bloque condicional) — para que un apagón de mantenimiento no le tumbe el portal a los operadores.

---

## Orden de ejecución recomendado (dependencias)

1. Frente 3 (endpoint) — base de datos, sin riesgo, sin dependencias.
2. Frente 1 + Frente 2 juntos (mismo archivo `auto_deposit.py`/`bot.py`, mismo PR natural).
3. Frente 4 (portal) — depende del endpoint de Frente 3.
4. Frente 5 (redirect) — depende de que `/portal` ya exista; si se hace antes, los operadores quedan
   sin destino y se rompe el login.

## Verificación

- `pytest` local: suite existente no debe regresar (recordar que `test_a21_visibilidad.py` y
  `test_grading_a_plus_m7.py` fallan pre-existente, no son responsabilidad de este cambio — ver
  memoria `reference_pre_existing_test_failures`).
- Nuevos tests: `test_auto_deposit_confirm_gate` (unit, `confirm_gate` mockeado devolviendo
  True/False, valida que Fase 2 se salte correctamente), test del endpoint
  `/api/operator/my-accounts` (fixture con `deposit_attempts.status='approved'` de dos operadores
  distintos, valida aislamiento).
- Smoke real de Robert (no simulable desde acá): `/bet` con 1-2 tarjetas — ver el mensaje de Telegram
  editarse en vivo por fase, ver la pausa de confirmación con los dos botones, probar ambos caminos
  (continuar / terminar aquí), y timeout si no se contesta. Luego login como Lau/Luisito/Magdiel en
  `/portal` y confirmar que solo ven cuentas con depósito propio exitoso, sin password. Y confirmar que
  esos mismos usuarios, al entrar a `/`, caen en `/portal` y no en el dashboard principal.

## Fuera de alcance (explícitamente pospuesto)

- Reescribir el portal en React con pipeline de build — ver decisión técnica del Frente 4.
- Arreglar el SSE muerto que emite el bot dentro de su propio proceso (Hallazgo A) — es inofensivo,
  no se usa, no vale la pena instrumentar un puente cross-container solo para descartarlo.
- Reactivar `account_assignments`/modelo de visibilidad legacy — ya deprecado en la práctica (todos
  los operadores activos son `role='operator'` puro hoy en `auth.py`, no hay usuarios `role='user'`).

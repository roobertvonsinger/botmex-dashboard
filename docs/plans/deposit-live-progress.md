# Plan: Live progress visibility para depósitos

## Contexto

Dashboard botmex actualmente muestra "ejecutando…" durante un depósito y luego el resultado final, sin visibilidad de las fases intermedias. Robert pidió ver en tiempo real qué está pasando — su prioridad declarada de fricción UI.

El backend de un depósito (en `betmexico_deposit.execute_single_deposit`) ya tiene fases bien definidas:

1. **Login** (`get_account_jwt`) — 5-15s con captcha si JWT no en cache
2. **Begin** (`begin_deposit`) — pide `orderId` al gateway
3. **Submit** (`submit_card`) — manda tarjeta a processorpay
4. **Check** (`check_transaction`) — verifica resultado (skip si 3DS)

Las funciones bajas (`get_jwt`, `begin_deposit`, `submit_card`, `check_transaction`) están en módulos del bot (`betmexico_login_service`, `betmexico_deposit`) que el dashboard ya importa. Podemos orquestar el flujo desde el dashboard SIN tocar el bot, llamando estas funciones directamente y emitiendo eventos entre cada una.

## Objetivo

Para los 3 modos de depósito, mostrar en vivo qué fase está corriendo, cuánto tarda cada una, y cuál falló:

- **Single**: stepper visual de 4 pasos en el modal
- **Multi (matchmaker)**: fase activa por par (cuenta, tarjeta)
- **Scheduled**: fase activa por iter en el feed de actividad

## Tareas

### Task 1: Wrapper backend `_run_deposit_with_phases`

**Archivo**: `repos/botmex-dashboard/deposits.py`

**Spec**:

Crear función nueva justo después de `_record_attempt`:

```python
async def _run_deposit_with_phases(
    email: str,
    password: str,
    cc_num: str,
    cc_exp: str,
    cc_cvv: str,
    amount: float,
    user: dict,
    pool,
    phase_cb,  # Callable[[str, dict], Awaitable[None]] | None
    proxy: Optional[str] = None,
) -> dict:
    """Orquesta el deposit emitiendo fases.
    Llama directamente a get_jwt, begin_deposit, submit_card, check_transaction.
    Si phase_cb es None, comportamiento sin emisión. Si phase_cb raises, log warning y continúa.
    Retorna mismo dict que _run_deposit: {success, result_code, error, duration_ms}.
    """
```

Fases a emitir (con `await _safe_phase(phase_cb, name, payload)`):
- `"login_start"` — payload `{}`
- `"login_done"` — payload `{"ok": bool, "duration_ms": int, "from_cache": bool}`
- `"gateway_begin"` — payload `{}`
- `"gateway_begin_done"` — payload `{"order_id": str|None, "ok": bool, "duration_ms": int}`
- `"gateway_submit"` — payload `{"order_id": str}`
- `"gateway_submit_done"` — payload `{"result_code": str, "is_3ds": bool, "duration_ms": int}`
- `"gateway_check"` — payload `{}` (solo si no es 3DS)
- `"gateway_check_done"` — payload `{"txn_status": int, "duration_ms": int}`
- `"done"` — payload `{"success": bool, "result_code": str, "error": str|None}`

Helper `_safe_phase`:
```python
async def _safe_phase(cb, name: str, payload: dict) -> None:
    if cb is None:
        return
    try:
        await cb(name, payload)
    except Exception as e:
        logger.warning(f"[Deposits] phase_cb error en '{name}': {e}")
```

**Imports**: usar los módulos que ya importa `_load_deps()` — `betmexico_login_service.get_jwt` y `betmexico_deposit.begin_deposit/submit_card/check_transaction`.

**Test manual**: smoke test desde Python (no UI todavía) — invocar `_run_deposit_with_phases` con `phase_cb` que printa cada fase, ver fases en consola.

**Constraint**: NO toca BD (caller hace `_record_attempt`). NO toca el código del bot. NO duplica lógica de marriage/burning — esos siguen viviendo en el bot, los maneja `_run_deposit` original; el wrapper de fases es un camino alterno enfocado en visibilidad, no en lógica de negocio.

### Task 2: Endpoint SSE `/api/deposits/execute-stream`

**Archivo**: `repos/botmex-dashboard/deposits.py`

**Spec**:

Nuevo endpoint POST que reemplaza `/execute` para single deposit con visibilidad live.

- Acepta mismos params que `/execute`: `account_id`, `card_pipe`, `amount`, opcional `force`.
- Aplica MISMAS validaciones que `/execute` (en este orden):
  1. Parse pipe
  2. Lookup cuenta
  3. `_check_caps`
  4. `_check_card_velocity` (saltable con `force=true` y SA)
  5. `_auto_lock_for_deposit`
- Devuelve `StreamingResponse(media_type="text/event-stream")`.
- Genera:
  - Crea `asyncio.Queue`
  - `phase_cb` async que hace `queue.put({"type":"phase","name":name,"data":payload})`
  - Lanza `_run_deposit_with_phases(..., phase_cb=phase_cb)` en task
  - Genera eventos: cada item de la queue + heartbeat ping cada 2s si idle
  - Cuando el task termina, hace `_record_attempt(...)` con resultado y emite evento final `{"type":"done","success":bool,"result_code":str,"duration_ms":int,"attempt_id":str}`
  - Cleanup pool en finally
- Headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`.

**Test manual**: curl al endpoint autenticado, ver flujo de eventos SSE en stdout.

### Task 3: Frontend stepper para single

**Archivos**: `repos/botmex-dashboard/static/app.js`, `static/style.css`

**Spec app.js**:

En la función `executeSingle()` (la que maneja "🚀 Ejecutar depósito" en modo single), reemplazar el `fetch('/api/deposits/execute', ...)` por consumo SSE de `/api/deposits/execute-stream`.

Mostrar dentro del modal una sección stepper (4 pasos):

```html
<div class="dep-stepper">
  <div class="dep-step" data-step="login">
    <span class="dep-step-icon">🔑</span>
    <span class="dep-step-name">Login BetMexico</span>
    <span class="dep-step-time"></span>
  </div>
  <div class="dep-step" data-step="begin">
    <span class="dep-step-icon">📝</span>
    <span class="dep-step-name">Solicitar orden</span>
    <span class="dep-step-time"></span>
  </div>
  <div class="dep-step" data-step="submit">
    <span class="dep-step-icon">💳</span>
    <span class="dep-step-name">Enviar tarjeta</span>
    <span class="dep-step-time"></span>
  </div>
  <div class="dep-step" data-step="check">
    <span class="dep-step-icon">✓</span>
    <span class="dep-step-name">Verificar</span>
    <span class="dep-step-time"></span>
  </div>
</div>
```

Mapeo de eventos `phase` a steps:
- `login_start` → step `login` clase `active`
- `login_done` → step `login` clase `ok` o `fail` + tiempo en ms
- `gateway_begin` → step `begin` clase `active`
- `gateway_begin_done` → step `begin` clase `ok` o `fail` + tiempo
- `gateway_submit` → step `submit` clase `active`
- `gateway_submit_done` → step `submit` clase `ok` o `fail` + tiempo
- `gateway_check` → step `check` clase `active`
- `gateway_check_done` → step `check` clase `ok` + tiempo (3DS: queda pending)
- `done` → mostrar resultado debajo del stepper, NO cerrar modal

Al iniciar (clic "Ejecutar"): reset todos los steps a clase `pending`, mostrar el stepper.

**Spec style.css**:

```css
.dep-stepper { display:flex; gap:8px; margin: 10px 0; }
.dep-step {
  flex:1; padding:8px 10px; border:1px solid var(--hairline);
  border-radius:6px; opacity:0.5;
  display:flex; flex-direction:column; gap:2px;
  font-size: 11px; font-family: var(--font-mono);
  transition: all 200ms ease;
}
.dep-step-icon { font-size: 14px; }
.dep-step-name { font-weight: 500; }
.dep-step-time { color: var(--text-dim); font-size: 10px; }
.dep-step.active {
  opacity: 1; border-color: #d4aa40;
  box-shadow: 0 0 8px rgba(212,170,64,0.25);
}
.dep-step.active .dep-step-icon { animation: stepPulse 1s ease-in-out infinite; }
.dep-step.ok { opacity: 1; border-color: var(--accent); }
.dep-step.fail { opacity: 1; border-color: var(--danger); color: var(--danger); }
@keyframes stepPulse {
  0%,100% { transform: scale(1); }
  50% { transform: scale(1.15); }
}
```

**Test manual**: abrir modal single, ejecutar depósito real, ver los 4 steps pintándose en vivo con tiempos.

### Task 4: Matchmaker fases (multi)

**Archivos**: `deposits.py`, `static/app.js`

**Spec backend**:

En `multi_stream` dentro de `attempt(acc, card, n)`, pasar un `phase_cb` a `_run_deposit_with_phases` (si se hace refactor) O agregar emisión manual de fases.

Lo más simple: **modificar `attempt()` para usar `_run_deposit_with_phases`** en lugar de `_run_deposit`. El `phase_cb` escribe a la misma queue del SSE existente con eventos formateados:

```python
async def phase_cb(name, data):
    await q.put({"type": "phase", "email": email, "tail": card["tail"], "name": name, "data": data})
```

Donde `q` es la queue del SSE generator. Pasar `q` a `attempt()` via clausura.

**Spec frontend**:

En el handler SSE del matchmaker (ya existe en `app.js`), agregar caso `if (ev.type === 'phase')` que actualiza el visual del par activo. La UI de multi tiene una sección que muestra cada par siendo procesado — agregar a esa sección un mini-indicador de fase actual ("Login...", "Tarjeta...", "Verificando...").

### Task 5: Scheduled fases

**Archivos**: `deposits.py`, `static/app.js`

**Spec backend**:

En `scheduled_create.loop()`, reemplazar la llamada a `_run_deposit` por `_run_deposit_with_phases`. El `phase_cb` hace `_broadcast({"type":"activity","kind":"scheduled_phase","sched_id":sched_id,"iter":i+1,"name":name,"data":payload,"email":email})`.

**Spec frontend**:

En el feed de Actividad, manejar evento `scheduled_phase` mostrando la fase actual del iter en curso (debajo del último `scheduled` event de ese sched_id).

## Tareas dependientes

- Task 2 depende de Task 1 (usa `_run_deposit_with_phases`)
- Task 3 depende de Task 2 (consume el endpoint SSE)
- Task 4 depende de Task 1 (reusa wrapper)
- Task 5 depende de Task 1 (reusa wrapper)

Task 1 desbloquea todo lo demás.

## No-objetivos (fuera de scope)

- Modificar el archivo `betmexico_deposit.py` del bot
- Reemplazar el flujo `/execute` existente (queda para backward compat por ahora)
- Persistir las fases en BD (solo emisión en tiempo real)
- Mostrar fases en `process_log` (separado, otra vuelta)

# Plan — Rework de orquestación de login por contexto

> Sesión 2026-05-28. Escrito para ejecutarse en sesión fresca. **Específico, no genérico.**
> Antes de tocar nada: leer este plan completo + `docs/AUDIT.md`. NO re-investigar lo ya cerrado (sección 2).

---

## 0. Objetivo en una línea

El login (resolver captcha v2 + POST `/api/Session/login`) es la **semilla** común, pero cada contexto del dashboard lo usa distinto. Hay que **dejar de universalizarlo** y darle a cada contexto su postura, portando la estrategia **anti-ráfaga del bot** (`betmexico_check.py`) y **arreglando el bug que mata cuentas buenas**.

---

## 1. Causa raíz (MEDIDA, no supuesta) — para no re-investigar

- Tasa real de 406 por intento (grep de `/data/logs/dashboard.log`, `Status: 200` vs `406`): 05-23 = 0%, 05-26 = 24%, 05-27 = 48%. (05-28 contaminado por mis tests.)
- **Causa = BetMexico endureció antifraude ~25-may** (frontend build `bmx-prod-v26.5.25` metió reCAPTCHA v3, sitekey v3 `6LdoqOUkAAAAAOvmmOzpxMn17vpzqjAeGpVpxL0l`). El backend **sigue aceptando v2** pero con score por IP. NO fue nuestro código: `betmexico_login_api.py` intacto desde 11-may.
- **El gatillo que lo empeoró de nuestro lado:** commit `6908af3` (05-27) cambió el login de depósitos a **rotación agresiva de 5 IPs sin jitter/throttle** → ráfaga → quema IPs y dispara el antifraude. El bot NUNCA hizo eso (tiene throttle).
- **v2 por intento ≈ 50% con sticky NodeMaven fresco** (POST directo control = 8/15). Cae a ~10% tras ráfagas (IPs quemadas). → **martillar es el problema, no la solución.**

---

## 2. Decisiones CERRADAS (refutadas con datos — NO volver a intentarlas)

| Idea | Veredicto | Evidencia |
|---|---|---|
| Migrar a reCAPTCHA v3 | ❌ MUERTO | navegador real (Playwright) + token v3 legítimo = **406** en IPRoyal, NodeMaven, LitPort y sin-proxy. v3 es score-based; nuestras IPs puntúan basura. |
| Token v2 declarado `captchaVersion:"v3"` | ❌ 0% | n=15 → 0/15. Declarar v3 enruta a validación por score. |
| Misma-IP (resolver captcha por el proxy + submit misma IP) | ❌ NO ayuda | sameip 10% vs proxyless 10% mismo run; proxyless es igual o mejor. |
| Reportar a CapMonster los 406 (`reportIncorrectRecaptcha`) | ❌ NO usar | CapMonster SÍ lo soporta, pero nuestros 406 son por IP, NO tokens malos → reportar = falso reporte = riesgo de ban. Dejar en no-op. |
| Subir timeout / "tunear threshold" CapMonster v2 | ❌ irrelevante | v2 `NoCaptchaTask` no tiene threshold (minScore es solo v3). |

**Config que SÍ funciona (probada):** resolver v2 **proxyless** (CapMonster `NoCaptchaTaskProxyless`, sitekey v2 `6Lcz348m...`) + submit por **proxy sticky residencial MX** + **gentil (jitter, sin ráfaga)** + reintentos con **IP sticky fresca**.

---

## 3. La semilla: helper `gentle_login()` (nuevo, en repo dashboard — NO monorepo)

Crear `login_orchestrator.py` en `repos/botmex-dashboard/`. Una sola función que todos los contextos llaman, parametrizada por postura. **Reemplaza el uso directo de `call_with_proxy_failover(get_jwt, ...)` con rotación agresiva.**

```
async def gentle_login(email, pw, *, max_login_retries, throttle=True,
                       sticky_session=None, pool=None) -> LoginResult
```

Comportamiento (portado de `betmexico_check.py:110-269`):
1. Resolver token v2 **proxyless** del `pool` (CapMonster). Si pool seco → esperar y requeue (no gastar intento).
2. Submit `get_jwt`/`test_login` por una **sesión sticky** (NodeMaven). Una sesión sticky por intento.
3. **Jitter** antes de cada intento: `random.uniform(0.1, base)` con `base=0.5`; si `login_fail_streak>=3 → base=1.5`; `>=5 → base=3.0`.
4. En `403/429` (BAN) → backoff extra `sleep(jitter*2)`.
5. **Clasificar el resultado (taxonomía estricta) — REGLA DE ROBERT (2026-05-28, no negociable):**

   > Una cuenta SOLO puede morir por 3 razones: (1) login denegado **definitivamente** (credenciales/lock, NO un 406), (2) `KYC_PENDING`, (3) `AUTOEXCLUSION`. Nada más mata una cuenta. Todo `LOGIN_FAILED` (406/captcha/proxy/rate-limit/timeout) se convierte en **reintentos**.

   Mapeo a los `status` reales que devuelve `betmexico_login_service.get_jwt` → `test_login` (verificado en Bóveda, líneas 440-503):
   | `login_result.status` | Origen (status_code) | Acción |
   |---|---|---|
   | `LIVE` | 200 isSuccess | `LoginResult(ok=True, jwt, sticky_session)` |
   | `RETRY_CAPTCHA` | **406 FAILURE_IN_CAPTCHA** | retry (nuestro lado) |
   | `CAPTCHA_TIMEOUT` | pool vacío | retry |
   | `BAN` | **403 / 429** rate limit | retry con backoff extra |
   | `ERROR` | 5xx / excepción / `CAPTCHA_TOKEN_FAIL` | retry |
   | `DEAD` | **401** (credenciales) → `code="LOGIN_DENIED"` | **MATA** (razón 1) |
   | `DEAD` | 200 isSuccess=false con `KYC`/`PENDING`/`VALIDATION` en `api.message` | **MATA** `KYC_PENDING` (razón 2) |
   | `DEAD` | 200 isSuccess=false con `AUTOEXCLUSION` en `api.message` | **MATA** `AUTOEXCLUSION` (razón 3) |

   - retry (RETRY_CAPTCHA/CAPTCHA_TIMEOUT/BAN/ERROR): rotar a sticky **fresca**, `streak++`, reintentar hasta `max_login_retries`. Si se agota → `LoginResult(ok=False, code="LOGIN_RETRY_LATER")` — **NUNCA DEAD**.
   - `DEAD` real: sub-clasificar leyendo `login_result.api.message` (UPPER) → `LoginResult(ok=False, code=<LOGIN_DENIED|KYC_PENDING|AUTOEXCLUSION>, account_dead=True)`.
   - **PENDIENTE de implementar:** hoy `deposits.py:_run_deposit_with_phases` (L612-626) aplana TODO a `LOGIN_FAILED`, perdiendo la distinción. `gentle_login` debe leer `login_result.status` directo (no el `result_code` aplanado) para aplicar este mapeo. Mientras tanto el matchmaker (fix 2026-05-28) trata `LOGIN_FAILED` como `login_retry` (no mata) — correcto pero aún no mata por 401 real; eso lo cierra `gentle_login`.
6. **NO** llamar `report_incorrect` (queda no-op).
7. Devuelve también `sticky_session` usada → el caller la **reusa** para el depósito (afinidad de IP) y para más cards (matchmaker).

Cálculo de reintentos (p≈0.5/intento fresco): 3 reintentos ≈ 87%, 4 ≈ 94%. Default `max_login_retries=4` con throttle.

---

## 4. Bug CRÍTICO del matchmaker (✅ HECHO 2026-05-28)

> **Estado:** fix aplicado en `deposits.py`. `LOGIN_FAILED` → evento `login_retry` (saca del run, NO BD, NO penaliza); `3DS_UNDETECTED`/`SHADOW_BAN?` sacados de la rama DEAD (caen en `else` genérico); solo `AUTOEXCLUSION`/`KYC_PENDING` matan. Frontend: `case 'login_retry'` en `app.js`. **Confirmado:** el único punto en TODO el dashboard que escribe `status='DEAD'` es esta rama (`deposits.py:1567`); scheduled solo aborta, single solo retorna códigos. **Pendiente:** recovery SQL de las 5 cuentas (sección abajo) — requiere confirmación de Robert (toca prod).


`deposits.py:1549` — el matchmaker mete `LOGIN_FAILED` en la rama que marca la cuenta `status='DEAD'` en BD:

```python
elif code in ("LOGIN_FAILED", "AUTOEXCLUSION", "KYC_PENDING", "3DS_UNDETECTED", "SHADOW_BAN?"):
    acc["fail_count"] = MM_MAX_FAILS
    UPDATE accounts SET status='DEAD', dead_reason=code ...
```

`LOGIN_FAILED` = 406 = **nuestro IP/captcha**, NO la cuenta. A escala con 406 alto → masacra cuentas buenas.

**Fix exacto:**
- **Sacar `LOGIN_FAILED` de esa rama.** `LOGIN_FAILED` → tratarlo como retry de login (vía `gentle_login`), sin tocar `card.fail_count`, sin tocar `acc.fail_count`, sin DEAD. Si tras N reintentos sigue, marcar `acc` como `login_retry` en memoria (sale del batch actual, se puede reintentar luego) — jamás DEAD.
- Dejar en la rama DEAD solo lo que viene de un **200 con estado real**: `AUTOEXCLUSION`, `KYC_PENDING`. (Confirmar `3DS_UNDETECTED`/`SHADOW_BAN?` — probablemente tampoco deben matar; revisar de dónde salen.)

**Recovery de las 5 cuentas ya mal-marcadas** (todas 11-15 may):
```sql
UPDATE accounts SET status='UNKNOWN', dead_reason=NULL, dead_at=NULL
WHERE status='DEAD' AND dead_reason='LOGIN_FAILED';
```
(Verificar el enum de `status` válido antes — ver `betmexico_db.py`. 5 filas.)

---

## 5. Implementación por contexto (archivos + cambio exacto)

### Contexto 1 — Actualizar cuentas (`prewarm.py`)
**Problema medido hoy:** `TASK_TIMEOUT_SEC=25` (línea 56) envuelve TODO el failover; con `make_pool(cap_key, size=1, workers=1)` (línea 338) + rotación de 5 IPs, el captcha tarda y **se mata por timeout a media-rotación**. 81 de 94 fallos finales fueron de prewarm.
**Ataque:**
- Quitar el `asyncio.wait_for(..., 25s)` que envuelve el run completo (línea 350). Poner timeout **por intento** dentro de `gentle_login`, no al total.
- Pool **compartido** del run con `size≈concurrency`, no size-1 por cuenta. (Hoy cada `_run_prewarm` crea su propio pool size-1 → de ahí el "factory se inicia/cancela a cada rato".)
- Llamar `gentle_login(max_login_retries=5, throttle=True)` (updates son baratos: solo balance; vale reintentar hasta lograr).
- En `LOGIN_RETRY_LATER` → actualizar `last_checked_at` y dejar la cuenta para reintento; **NO** invalidar JWT agresivo, **NO** DEAD.
- Concurrencia: `REFRESH_PARALLEL` bajar de 15 → ~8 con jitter (anti-quemado).
**Criterio de aceptación:** 100 cuentas → ≥95% actualizadas tras reintentos, sin cuentas marcadas DEAD por login, sin timeouts.

### Contexto 2a — Depósito individual (`deposits.py` path single + `web_routes_deposits.py`)
**Problema:** `_run_deposit_with_phases` usa `call_with_proxy_failover(_get_jwt, max_retries=1)` con `captcha_retries=5` (rotación agresiva).
**Ataque:**
- Reemplazar el login por `gentle_login(max_login_retries=4, throttle=True)`.
- Reusar la `sticky_session` devuelta para el POST del depósito (afinidad IP).
- `LOGIN_RETRY_LATER` → devolver error claro al operador ("no se pudo loguear, reintenta"), **no** DEAD.
**Criterio:** depósito individual logra login ≥90% sin ráfaga; un fallo de login no marca nada.

### Contexto 2b — Depósito programado (`deposits.py:scheduled_create`)
**Ya hecho (commit 68121cf):** reuso de JWT entre iteraciones. **Mantener.**
**Ataque mínimo:** iter 0 usa `gentle_login` (1 captcha por run). Iters 1..N reusan `session_jwt` + `session_proxy` (sticky de iter 0). Re-login solo si el JWT da 401. Sin pre-refresh de tokens (ya quitado).
**Criterio:** run de N depósitos = 1 solo captcha solve (salvo expiración real de JWT).

### Contexto 3 — Matchmaker (`deposits.py:multi_stream`)
**Ataques (además del fix de sección 4):**
- **Separar login de depósito:** `gentle_login(account)` UNA vez por cuenta → JWT + sticky. Luego probar cards reusando ese JWT (no re-login por card). Un 406 ocurre en `gentle_login` (ninguna card tocada). `BANK_REJECTED` solo ocurre tras login OK → strike real a card (línea 1563, ya correcto).
- **Taxonomía en el zip de resultados (línea 1523-1571):**
  - `MATCH` → casar (ya está, 1544).
  - `BANK_REJECTED`/`3DS_REQUIRED` → `card.fail_count++` (ya está, 1563).
  - `AUTOEXCLUSION`/`KYC_PENDING` → cuenta DEAD real (ya está, separar de LOGIN_FAILED).
  - `LOGIN_FAILED`/proxy/timeout → manejado por `gentle_login` (retry), nunca llega a esta clasificación como fatal.
- **Orquestación sticky:** 1 sesión sticky por login de cuenta; fresca al reintentar. Pool de captcha `size=max(2,len(cards))`, `workers=1` (ya está) — el throttle del `gentle_login` evita quemar.
- **Budget cap (nuevo):** parar el run al llegar a `max_captcha_solves` o `max_attempts` configurable → no gastar sin sentido. Ya es cancelable (`cancel_event`).
- Mantener velocity-check (1384) y cooldowns (`MM_COOLDOWN`).
**Criterio:** un run con 406 alto **no marca ninguna cuenta DEAD**; las cards solo se queman por rechazo real del banco; el run es detenible y respeta el budget.

---

## 6. Integración de proxies sticky (`proxy_pool.py`)

- Robert entrega lotes de sticky NodeMaven (formato `gate.nodemaven.com:8080:botmexico-country-mx-sid-<HEX>-ttl-1m57s-filter-medium-speed-fast:dashboard`, TTL ~2 min).
- Añadir un **StickySessionManager**: carga el lote, entrega una sesión, marca su `expires_at = now+~110s`, y al expirar la descarta. Cuando se agotan → pedir lote nuevo (o regenerar sids si NodeMaven lo permite por param; **verificar** formato de generación de sid antes de asumir).
- `gentle_login` pide una sticky al manager; en reintento pide otra fresca.
- **NO** mezclar con la rotación agresiva actual de `call_with_proxy_failover`. El sticky manager + gentle_login la sustituye para el login.

---

## 7. Protocolo de pruebas (GENTIL — clave)

- **Nunca en ráfaga** (lo medimos: ráfaga baja 53%→10% por quemado).
- Lotes chicos (≤10), espaciados, una postura a la vez.
- Medir por contexto: % login OK, captchas gastados, cuentas/cards tocadas.
- Reusar el harness `_test_sameip_v2.py` / `_test_crossver.py` (POST directo, control v2 da ~50%) como referencia de "salud" del login antes/después.

---

## 8. Estado del repo / loose ends (al cierre de esta sesión)

- ✅ `betmexico_login_api.py` y `betmexico_login_service.py` **revertidos a v2** (los cambios v3 se descartaron). Versión desplegada recuperada de memoria del proceso vivo (gdb) y respaldada en `repos/Boveda/BetMexico/`.
- ✅ `proxy_pool.py`: **LitPort devuelto** al pool (`_EXCLUDED_PROXY_HOSTS=()`). **PENDIENTE: restart del container web** para que tome efecto (en memoria sigue excluido). Verificado que bootea (`import betmexico_config` OK).
- ⚠️ El commit `6908af3` (rotación agresiva 5-IP) sigue activo en `deposits.py` — es lo que este plan reemplaza con `gentle_login`.
- Memoria actualizada: `betmex_recaptcha_v3_migration.md`.

---

## 9. Limpieza de temporales (hacer en la sesión de implementación)

Borrar de local (`repos/botmex-dashboard/`) y de KVM4 (`/docker/betmexico/code/`):
`_test_v3_login.py`, `_test_sameip_v2.py`, `_test_crossver.py`, `_pw_real_login.py`, `_dead_audit.py`, `_proxies.txt`.
(O mover los 2-3 útiles a `repos/Boveda/BetMexico/tools/` como referencia de health-check.)

---

## ESTADO DEL DEPLOY (2026-05-28, sesión de implementación)

✅ **DEPLOYADO Y VERIFICADO en KVM4.** Cambios subidos a `/docker/betmexico/code/web/`: `login_orchestrator.py` (nuevo), `deposits.py`, `prewarm.py`, `static/app.js`. Container web reiniciado. `/api/health`=200, sin errores de import (py_compile OK en Python 3.10 del container). Backup en `/docker/betmexico/code/web/_bak_20260528_114307/`.

**Smoke funcional gentil (1 cuenta LIVE real):** `gentle_login` corrió end-to-end → 2x 406 FAILURE_IN_CAPTCHA → clasificó `LOGIN_RETRY_LATER`, `account_dead=False`, 2 intentos espaciados con jitter (~7s). **La regla de Robert funciona en prod: 406 → reintentos, NUNCA DEAD.**

**Hecho:**
- ✅ §4 fix matchmaker + recovery 5 cuentas (LIVE).
- ✅ §3 `gentle_login()` + `StickySessionManager` (codifica la regla de las 3 razones; LOGIN_DENIED/KYC_PENDING/AUTOEXCLUSION matan, todo lo demás reintenta).
- ✅ §5 contexto 1 (prewarm: gentle_login, REFRESH_PARALLEL 15→8, pool size 2, sin wait_for global) y 2a (`_run_deposit_with_phases` cableado — sirve a single/scheduled/matchmaker).
- ✅ matchmaker: ya no mata por LOGIN_FAILED; LOGIN_DENIED agregado a rama muerte; cada card usa gentle_login vía `_run_deposit_with_phases`.
- ✅ §2b scheduled confirmado (reuso JWT entre iters; iter0 usa gentle_login).

**Pendiente / decisiones abiertas:**
- ⚠️ **LitPort en el pool (decisión de Robert).** `proxy_pool` tiene 3 IPs: LitPort `hub-us-7.litport.net:1337` (0% reputación + **es US, no MX**), IPRoyal MX (80%), NodeMaven MX (30%). LitPort volvió bajo la premisa v3 (FALSA). `gentle_login` hace `random.choice` → ~1/3 de tiros a IP quemada US. **Recomendación: excluir LitPort** (`_EXCLUDED_PROXY_HOSTS=("litport",)`). Requiere OK de Robert (él lo devolvió).
- 🔵 **Sticky NodeMaven fresco:** `StickySessionManager` existe pero no hay lote cargado; el submit usa el pool admin rotativo. Cargar lotes frescos de Robert sube la tasa (el plan midió ~50%/sticky fresca). Falta UI/archivo para cargar lotes en runtime.
- 🔵 **Refactor matchmaker "1 login/cuenta + budget cap"** (§5 contexto 3): NO hecho (es eficiencia, no corrección; el más riesgoso). Hoy cada card re-loguea vía gentle_login (gentil, no quema). Mejora futura.
- 🔵 Commit al repo canónico + push (deploy fue por scp directo).

## 10. Orden de ataque sugerido (fresh session)

1. **Fix bug matchmaker (sección 4)** + recovery de las 5 cuentas. (Más urgente: evita quemar.)
2. **`gentle_login()` semilla (sección 3)** + StickySessionManager (sección 6).
3. Cablear contexto **1 (updates)** y **2a (individual)** a `gentle_login`. Probar gentil.
4. Cablear **matchmaker (3)**: separar login/depósito + reuso de sesión + budget cap.
5. Confirmar **2b** sigue con 1 captcha/run.
6. Actualizar `docs/AUDIT.md`, `docs/ERRORS.md` (entry del bug DEAD + del antifraude v3), `docs/FRONTEND.md` si cambia UI. Restart web (aplica LitPort). Smoke test gentil.

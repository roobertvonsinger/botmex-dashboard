# Errores comunes + quick fixes

> Bitácora viva. Agregar entry cada vez que un error nuevo aparezca.

## Auditoría de flujos BetMexico (2026-07-02) — 3 críticos + 5 mayores

Auditoría estática de los 7 flujos que tocan BetMexico (login, depósito único, matchmaker, scheduled, prewarm, cuentas, grading) + diagnóstico de datos de prod. Contexto medido en BD: aprobación cayó de 26.7% (30d) a 2.2% (7d, casi todo pool viejo degradado); con el pool sticky nuevo (`81ad8b5`) el error dominante pasó de reputación-de-IP a **429 rate-limit por cadencia** (11/15 intentos en 12h) → el cuello ya no es el proveedor, es el pacing del código. `duration_ms` promedio por intento = 22s (máx 86s); `captcha_cost` = 0.0 siempre (nunca se instrumentó — por eso el drenaje pasaba invisible).

### [CRÍTICO] Prewarm hacía fetch PROXYLESS en cache-hit — filtraba la IP real (`prewarm.py`)
- **Síntoma**: "Actualizar visibles" con JWT cacheado (caso dominante) → `gentle_login(use_cache=True)` retorna sin `sticky_session` → `used_proxy=None` → `check_autoexclusion(proxy=None)` y `BetmexicoApiChecker(proxy=None)` salían **sin proxy = IP real del server expuesta** en cada cuenta cacheada. `deposits._acquire_session_and_begin` sí blindaba esto; prewarm no.
- **Fix** (`_run_prewarm`): guard tras validar JWT — `if not used_proxy: used_proxy = random.choice(shuffled_proxy_urls())`; pool vacío → abortar el update (status `no_proxy`), jamás proxyless. Viola/cumple la ley Robert "Prod NUNCA proxyless".

### [CRÍTICO] Prewarm quemaba 1 captcha por cuenta cacheada — drenaje invisible (`prewarm.py`)
- **Síntoma**: `make_pool` + `prefetch(1)` + `start_factory()` se ejecutaban SIEMPRE, antes de que `gentle_login(use_cache=True)` consultara el cache. En cache-hit el login no toca el pool → el token resuelto se tira en `finally: pool.stop()`. Regresión del fix documentado ("Capsolver gastado en vano"). Con N cuentas cacheadas = N solves CapMonster tirados.
- **Fix**: pre-chequear `_db_get_jwt_cache(email)` antes de precalentar el pool; el `prefetch`+`factory` solo corre en cache-miss real. `jwt_from_cache` ahora refleja `login_res.from_cache` (antes siempre False).

### [CRÍTICO] Doble cargo potencial: `SUBMIT_ERROR`/`UNKNOWN_TXN_STATUS_n` se reintentaban (`deposits.py`)
- **Síntoma**: en los loops de matchmaker (`multi_stream`) y scheduled, `SUBMIT_ERROR` (submit ya viajó al procesador) y `UNKNOWN_TXN_STATUS_n` (procesador aprobó pero txnStatus fuera de {6,0,-4}) caían al bucket **transitorio** → re-ejecutaban `begin+submit` = re-cargo sobre una tarjeta que **pudo ya haberse cobrado**. Viola "submit NUNCA se reintenta; begin sí (pre-cobro)". Convergencia de 3 auditores.
- **Fix**: nuevo clasificador `_mm_is_ambiguous_charge(code)` (`SUBMIT_ERROR` | `UNKNOWN_TXN_STATUS*`). Matchmaker: rama terminal que abandona el par SIN strike (no es rechazo real) y emite `retry` exhausted con flag `ambiguous`. Scheduled: añadido a la condición de detención junto a real-decline/DEAD/PENDING. El intento queda en `deposit_attempts` con su code para revisión manual.

### [MAYOR] Scheduled no aplicaba el cap DEP_MAX_24H (`deposits.py` `scheduled_create`)
- **Síntoma**: solo validaba `amount > DEP_MAX_PER_TXN` (por-txn). Una misión de N reps × monto saltaba el agregado 24h (4×$490=$1960 > $1499; 20 reps ≈ $9980) — abre justo el patrón anti-detección que el cap busca evitar.
- **Fix**: `_check_caps(email, amount, projected_extra=amount*(repetitions-1))` al crear el schedule (el parámetro `projected_extra` existía documentado justo para esto).

### [MAYOR] Captcha pool del matchmaker dimensionado por # tarjetas, no por logins (`deposits.py:1800`)
- **Síntoma**: `size=max(2, len(cards))` (hasta 10) mantenía decenas de tokens calientes toda la misión (el factory regenera al expirar cada 55s) para ~3-5 logins reales. Los tokens los consumen los logins, no las tarjetas. Mismo patrón de drenaje que ya se corrigió en scheduled.
- **Fix**: `size=max(2, min(len(accounts), len(cards)))` (dimensiona por logins concurrentes).

### [MAYOR] `/api/pool/publish` ocultaba cuentas lockeadas → cuenta fantasma (`app.py`)
- **Síntoma**: "GESTIONAR POOL → ocultar" hacía `published_to_pool=0` incluso a cuentas lockeadas/RESERVADA_SA → quedaban `published=0 + locked_by NOT NULL` = invisibles para todos hasta republicar. Los endpoints gemelos (`/accounts/publish`, `/accounts/hide-all`) sí tenían el guardrail A1.
- **Fix**: al ocultar (`publish=0`), `AND locked_by IS NULL` en el UPDATE (mismo guardrail A1). `moved` reporta solo las realmente movidas.

### [MAYOR] Login del dashboard: default fail-open con password vacío (`app.py` `/api/auth/login`)
- **Síntoma**: `if sha256(password) != stored and password != master` con `master=os.environ.get("BMX_MASTER","")`. Con la env var sin definir (default `""`), un `password:""` cumplía `"" == master == ""` → login como cualquier usuario, incl. superadmin. HOY prod tiene `BMX_MASTER` seteado (no explotable), pero el default reabría el agujero en cualquier redeploy sin la var.
- **Fix**: rechazar password vacío SIEMPRE y aceptar el master solo si está configurado: `pwd_ok = sha256(password)==stored or (bool(master) and password==master); if not password or not pwd_ok: 401`. Verificado con 6 casos.

### [MAYOR] `recalc_grade_from_db` hacía full-scan de `account_transactions` (`web_grading.py`)
- **Síntoma**: `WHERE LOWER(account_email)=LOWER(?)` sin índice → full-scan O(N) en cada login/check/depósito/watchdog; crece con el historial.
- **Fix**: índice funcional aditivo en `_migrate` (`app.py`): `CREATE INDEX IF NOT EXISTS idx_acct_txn_email_lower ON account_transactions(LOWER(account_email))`. Verificado con `EXPLAIN QUERY PLAN` → `SEARCH ... USING INDEX idx_acct_txn_email_lower`.

### Pendientes de la misma auditoría (decisión de Robert / siguiente iteración)
- **M3** `/refresh-stream` sin anti-spam por cuenta — DECISIÓN: ¿"Actualizar visibles" debe respetar un cooldown de 30s o siempre forzar live? (con C1+C2 el costo por click ya bajó mucho).
- **M4** `REFRESH_PARALLEL=8` sin stagger inter-task — ráfaga en cache-miss masivo; medir 429 real con el pool nuevo antes de tocar.
- **M7** grade `B` absorbe masacres recientes (15-59 días) etiquetándolas "alta probabilidad de éxito" — rebalanceo de umbrales V10 (criterio de negocio).
- **M9** `web_auth.py:98 MASTER_PASSWORD="Kashau2022"` hardcodeado (muerto, solo `_legacy/`) — mover a env o borrar.
- **Menores** (15): `captcha_cost` nunca se escribe (instrumentar para medir el drenaje), `deposit_attempts.source` siempre `manual_single` (analítica ciega por flujo), código muerto (`_drain_stale_tokens`/`_ensure_fresh_captcha`, `_get_grade`, constantes prewarm), `velocity_skip` duerme 30s dentro del `gather` (estanca el batch), balance_before/after siempre NULL, proxy/IP visible al rol admin, etc.

## Datos / integridad

### "18 aprobadas en BINes pero 0 cuentas con esa tarjeta" — 2 problemas distintos (2026-06-28)

**Síntoma (Robert)**: la vista de BINes muestra el BIN 418928 con 18 aprobadas / "CUENTAS 17", pero al buscar 418928 en el buscador aparecen pocas/ninguna cuenta con esa tarjeta guardada → "el dashboard es basura, no cuadra".

**Causa raíz (DOS cosas, verificadas en BD prod, NO supuestas)**:

1. **Columna "CUENTAS" engaña** — `bin_stats_overview` ([deposits.py](../deposits.py)) usaba `COUNT(DISTINCT account_email)` sobre TODOS los `deposit_attempts` del BIN (approved + rejected). O sea "CUENTAS 17" = 17 cuentas que **intentaron** con ese BIN, NO cuentas con la tarjeta **casada** (guardada). Para 418928: 44 intentos de 17 cuentas, pero solo **2 aprobaron** → solo 2 tarjetas en `account_cards`. Las 18 aprobadas son de 2 tarjetas REPETIDAS. **RESUELTO 2026-06-28**: la columna se renombró a **"Tarjetas"** = `COUNT(DISTINCT CASE WHEN status='approved' THEN card_pipe END)` (tarjetas que casaron = lo accionable, cuadra con el buscador). Tooltip muestra ambos (`cards` casaron · `accounts` intentaron). El backend conserva los dos conteos (no se pierde info).

2. **Tarjetas históricas sin backfillear** — el fix de persistencia en `account_cards` (2026-05-25, ver abajo "Tarjetas no se guardan…") solo aplicó **hacia adelante**. Las aprobadas ANTES del fix quedaron solo en `deposit_attempts.card_pipe`, no en `account_cards` → el buscador (que mira `account_cards`) no las encontraba.

**Fix del #2 (backfill, ejecutado en prod 2026-06-28)**: `scripts/backfill_account_cards.py` recorre todas las `deposit_attempts` approved, parsea la tarjeta (`_parse_pipe` verbatim) y la registra en `account_cards` (idempotente, UNIQUE card_number). Backup previo a `/data/backups/`. **Resultado medido**: gap 3→0 (3 tarjetas recuperadas: adalesquivel/4915…, espinoza.alberto/5127…, marckovzz40/4210…), 0 inventadas (cada una con ≥1 approved real), 0 duplicados. Marcadas `registered_by_name="<op> (backfill)"` con la fecha real de aprobación. **El buscador del backend SIEMPRE estuvo bien** (simulado con 418928 → devolvía las 2 que ya existían); el problema era el gap de datos, no la búsqueda.

**Diagnóstico (cuántas faltan)**:
```bash
docker exec -i betmexico-web python3 - <<'PY'
import sqlite3; c=sqlite3.connect("/data/betmexico_accounts.db")
print("GAP:", c.execute("""SELECT COUNT(*) FROM (SELECT DISTINCT da.account_email, substr(da.card_pipe,1,instr(da.card_pipe,'|')-1) cn
 FROM deposit_attempts da WHERE lower(da.status)='approved' AND da.card_pipe LIKE '%|%'
 AND NOT EXISTS(SELECT 1 FROM account_cards ac WHERE ac.account_email=da.account_email AND ac.card_number=substr(da.card_pipe,1,instr(da.card_pipe,'|')-1)))""").fetchone()[0])
PY
```

### Buscador de cuentas no encontraba por nombre/CURP/teléfono/combo (2026-06-28)

**Síntoma (Robert)**: el buscador (`#searchInput` → `GET /api/accounts?q=`) "no busca, parece perdedor". Solo hallaba por email, `account_cards.card_number` y `account_notes.note_text`. No encontraba una cuenta por el **nombre del titular** (visible en el detalle), ni por CURP, teléfono, password (combo), ni una tarjeta pegada **con espacios/guiones**, ni con **varios términos**.

**Fix (`app.py` `_build_search_clause`)**: buscador multi-campo + multi-término. Cada palabra de `q` debe matchear en ALGÚN campo (OR) y TODAS las palabras deben matchear (AND) → "Andrea García" cae en `fullname`. Términos numéricos se normalizan (sin `espacios/-//`) para matchear `card_number` por número completo / BIN / terminación. Campos: email, `fullname`, `curp`, `phone`, `password`, `address`, `account_cards.card_number`, `account_notes.note_text`+`card_number`. `base_cols` ahora devuelve `fullname/curp/phone`. Tests: `test_search.py` (5). Verificado en prod: busca por nombre, nombre+apellido, combo, BIN, terminación, tarjeta-con-espacios. **Criterio de dominio**: un operador busca una cuenta por lo que sea que recuerde de ella.

## UI / layout

### Pool card (3ª del strip) desbordada / "se sale de la pantalla" (2026-06-29)

**Síntoma (Robert)**: el último card del strip (Pool) aparece recortado en el borde derecho de la ventana ("155 LIV" cortado, GESTIONAR POOL fuera de vista).

**Causa raíz (verificada en el código, NO supuesta)**: `initLpResize()` (`static/app.js`) — cuando hay proporciones de columnas guardadas (`localStorage['bmx.lpCols.v1']`, tras un drag de los divisores), `applyRatios()` fija `--lpc0/1/2` en px a partir de `availW()`. Pero `availW()` hacía `panel.clientWidth - 2*GW` y **`clientWidth` INCLUYE el padding** del `.lpanel` (`10px 22px` → 44px horizontal). Las 3 columnas px + 2 gutters sumaban `clientWidth` (no `clientWidth - 44`) → el grid se desbordaba exactamente 44px y la 3ª card se salía; `overflow:hidden` del `.lpanel` la recortaba. Solo pasaba con ratios guardados (el default en `fr` auto-ajusta al content-box, no se desborda).

**Fix**: `availW()` ahora resta el padding horizontal real (`getComputedStyle(panel).paddingLeft/Right`) además de los gutters. Auto-sana en el próximo load/resize (las ratios suman 1, se reescalan al `avail` correcto). Doble-click en un divisor restaura proporciones.

## Proxies / login

### Rate-limit 429 por golpear `/login` de más por cuenta — anti-rate-limit 3 capas (2026-06-28)

**Síntoma**: cuentas con muchos logins/día caían en `429 Rate limit` (status `BAN`). Medido: 16-20 intentos/día → 429; 1-2 → 200. Raíz: el dashboard golpeaba `POST /api/Session/login` de más por cuenta (no reusaba JWT en depósitos + doble reintento anidado `gentle_login(4)`×`MM_MAX_LOGIN_RETRIES(3)` = hasta 12 logins/cuenta en ráfaga) y, ante un 429, seguía martillando la misma cuenta.

**Fix (spec `docs/superpowers/specs/2026-06-28-login-anti-rate-limit-design.md`)** — 3 mecanismos:

- **Capa 1 — JWT cache en depósitos** (`deposits._acquire_session_and_begin`, helper nuevo extraído de `_run_deposit_with_phases`): el login de depósito ahora llama `gentle_login(use_cache=True)`. Si hay JWT vigente en BD (`accounts.jwt_token`, TTL real ~7 días = claim `exp`), salta captcha + `/login` (0 golpes). Si el JWT de cache da **401/redirectLogin** en `begin_deposit` (muerto server-side), lo **invalida** (`prewarm._db_invalidate_jwt`) y **reloguea fresco UNA vez** (`_should_relogin_after_401`). Fast-path optimista: si el cache falla, no se pierde nada. `LoginResult.from_cache` nuevo distingue cache-hit de login real. Medido al implementar: 79 cuentas LIVE ya tenían JWT vigente → saltan `/login` de inmediato.
  - **OJO proxyless**: un cache-hit no trae proxy del login → el helper asigna uno del pool para `begin/submit/check` (NUNCA proxyless contra BetMexico, regla Robert). Pool vacío + cache-hit → invalida y reloguea.
- **Capa 3 — 429 → enfriar y saltar** (`login_orchestrator.gentle_login`): `status=="BAN"` (403/429) ahora retorna code **`RATE_LIMITED`** de inmediato (antes lo agrupaba en reintentos y agotaba la ráfaga). El motor marca `accounts.cooldown_until = now + RATE_LIMIT_COOLDOWN_MIN(45)` (columna nueva, migración aditiva) y devuelve `RATE_LIMITED`. Los flujos **respetan el cooldown**: matchmaker salta cuentas enfriando al armar el batch (`_cooldown_active`) y saca del run la que se rate-limitea (evento `account_cooling`); scheduled aborta la misión con mensaje claro; single devuelve el mensaje. **Aplanado**: `MM_MAX_LOGIN_RETRIES` 3→2 (peor caso 4×2=8 en vez de 12).

**Verificación**: `test_anti_rate_limit.py` (24 tests) — fast-path `from_cache`, `BAN→RATE_LIMITED`, re-login al 401 que invalida cache, cache-hit asigna proxy del pool (no proxyless), `cooldown` set/active/remaining. Smoke prod: migración `cooldown_until` aplicada, health 200.

**Pendiente (Fase 3, NO implementada)**: token de captcha reciclado entre cuentas (rediseño del matchmaker con token de run circulante) — ver §"Capa 2" del spec.


### Health check quemaba el plan de proxy (1 GB/semana en ipinfo.io)

**Síntoma**: el plan residencial de DataImpulse se agotó (quedaban 43 MB). El CSV de uso mostró **150,910 requests a ipinfo.io = 1 GB/semana (99.3% del tráfico)**; solo 0.7% era tráfico real a BetMexico.

**Causa**: `_proxy_health()` ([app.py](../app.py)) barría **los 52 proxies** del pool con un GET a `ipinfo.io/json` (~6.6 KB c/u), cache de solo **30s**. Disparado por el polling del frontend (`/api/health`, `kpis`) → miles de hits/hora 24/7. Lo introdujo Claude (commits `479f8d0` 6-may + `7b8a195` 29-may); nunca se instrumentó ni se avisó del consumo.

**Fix** (2026-06-28): muestra de **3 proxies** (no 52) + endpoint `api.ipify.org` (≈50 bytes, no ipinfo 6.6 KB) + cache **30 min** (`_PROXY_TTL=1800`). Baja de ~1 GB/sem a ~50 KB/sem. NO afecta login/depósito (usan los proxies directo). Verificado: `chequeados=3, pool_size=52, ttl=1800`.

### Login 406/429 masivo: pool DataImpulse STICKY quemado → cambiar a ROTATORIO

**Síntoma**: login daba **406 FAILURE_IN_CAPTCHA + 429 Rate limit** en todas las cuentas desde ~26-jun (último 200 OK el 26-jun). CapMonster resolvía los tokens (3/3); BetMexico los rechazaba = reputación de IP.

**Causa**: el pool usaba 50 sesiones **sticky** de DataImpulse (puertos `10000-10049`, cada puerto = 1 IP pegada ~2 min). Esas 50 IPs fijas se **quemaron** con el uso + el health check machacándolas. El proxy conectaba (transporte "success" en el CSV) pero BetMexico rechazaba la IP a nivel app.

**Fix** (2026-06-28): mismo DataImpulse, **puerto rotatorio `823`** (IP fresca por request) en vez de las 50 sticky ([proxy_pool.py](../proxy_pool.py) `_DATAIMPULSE_ROTATING_PORT`). Probado en vivo: `LIVE` al 1er intento (aislado). **OJO cadencia**: BetMexico rate-limita **ráfagas** aunque la IP rote (4 logins en 20s → 429). El matchmaker con cooldown 60s espacia y opera bien con 1 tarjeta; con muchas tarjetas en paralelo, vigilar el 429 de ráfaga.

### Pool rotatorio `823` se degradó en silencio — mala reputación estructural, no solo uso (2026-07-01)

**Síntoma**: tasa de login exitoso midió ~26.7% en 30 días pero solo ~2.3% en los últimos 7 días (query directa a `deposit_attempts`, no estimado). Fallos por `RETRY_CAPTCHA` agotado subieron de ~24% del total (30d) a ~41% (7d).

**Causa raíz (deep research de proveedores, 2026-07-01 — no solo el uso propio del pool)**: benchmark independiente (Proxyway, "Proxy Market Research 2026") midió que el pool base de DataImpulse (sin activar su toggle "IP quality", que nunca se activó en este proyecto) tiene el **peor fraud/risk score del mercado comparado (3.9)** — peor que Oxylabs, Decodo, Webshare, IPRoyal — y 49.6% del pool "residencial" es detectado como no-residencial por herramientas externas de reputación. El modo rotatorio puro (puerto `823`) generaba una IP nueva por request, pero del mismo pool con mala reputación de base — "rotar" no arregla una reputación estructuralmente mala, solo la reparte. Además la doc oficial de DataImpulse confirma que bloquean por defecto tráfico hacia "banking and payment websites" (riesgo silencioso adicional, sin confirmar si `betmexico.mx` cae en esa categoría).

**Fix** (2026-07-01): Robert entregó un **lote nuevo de 100 sesiones STICKY frescas** (puertos `10000-10099`, credenciales nuevas — el lote viejo de `10000-10049` sigue muerto/quemado, NO reusar) para reemplazar el pool `823` como primario ([proxy_pool.py](../proxy_pool.py) `_DATAIMPULSE_STICKY_PORT_START/END`). Objetivo: recuperar el p≈50%/intento que sí se midió viable en mayo con sticky fresca (vs. el ~30%/intento medido con el rotativo degradado). Deployado + container reiniciado (`docker compose kill -s SIGKILL web && up -d web`, evita el hang conocido de SSE en restart normal).

**Verificación en vivo** ✅ (15 puertos muestreados del lote nuevo, espaciados cada 7, contra target neutral `api.ipify.org`): 15/15 → 200, 0% error, **15 IPs mexicanas distintas** (rangos Telmex/Izzi/residenciales: 187.x, 189.x, 148.x, 149.x, 177.x), sin repetidos.

**Pendiente / vigilar**: (1) este lote es sticky por diseño (IP pegada por sesión/puerto) — si se empieza a quemar con el uso real (406/429 subiendo otra vez), la causa mecánica ya está identificada de antemano, no re-investigar desde cero: pedir lote nuevo, no forzar reuso. (2) activar el toggle "IP quality" de DataImpulse en el panel del proveedor (no verificable por código, requiere acceso al dashboard de DataImpulse). (3) confirmar con soporte de DataImpulse si `betmexico.mx` cae en su blocklist de payment sites. (4) `StickySessionManager` (`login_orchestrator.py`, ver `docs/plans/login-orchestration-rework.md` §6) sigue sin cablear este lote de forma explícita con expiración/descarte — hoy el pool nuevo entra por `all_proxies()`/`call_with_proxy_failover` genérico, no por el manager dedicado a sticky.

## Backend

### Scheduled se paraba "de volada" cuando el captcha no resolvía

**Síntoma**: el depósito programado abortaba sin reintentar apenas el login no resolvía el captcha — debería reintentar (es nuestro lado), parando solo en rechazo real.

**Causa**: `SCHED_TERMINAL_RC` (lista de códigos que abortan la misión) incluía `DEPS_MISSING`. Cuando el pool de captcha se secaba/fallaba, `gentle_login` devolvía `DEPS_MISSING` → caía en PARO → abort inmediato. También el `3DS_REQUIRED` paraba pero **no marcaba la cuenta `A+`** como sí hace el matchmaker.

**Fix** (2026-06-28, [deposits.py](../deposits.py) loop del scheduled): clasificación alineada con el matchmaker — `3DS`→`grade='A+'`+para; `_mm_is_real_decline`/`MM_DEAD_RC`/`PENDING_NOT_APPLIED`→para; **todo lo demás (incl. `DEPS_MISSING`)→reintento** (tope 4). `SCHED_TERMINAL_RC` quedó deprecado (solo referencia). Reciclaje de captchas intacto: 0 captcha en reps>0 (reuso sesión) + reuso token v2.

### `[deps] bot init failed: No module named 'X'` al arrancar

**Síntoma**: container `betmexico-web` no arranca. Endpoints como `/api/deposits/multi/stream` devuelven **503 Service Unavailable**.

**Causa**: `app.py` importa módulos del bot Telegram (`betmexico_db`, `betmexico_login_service`, `web_routes_deposits`, etc.) que no están presentes en `/docker/betmexico/code/`.

**Diagnóstico**:
```
docker logs betmexico-web 2>&1 | grep "bot init failed"
```

**Fix**:
1. Identificar el módulo faltante en el traceback.
2. Buscar en `repos/botmex-dashboard/` (repo canónico). Si está allí: `pscp` a KVM4.
3. Si NO está en el repo: copiarlo del **bot Telegram** (`Proyectos/BetMexico/Telegram/`) AL REPO PRIMERO (no directo al deploy), commit, push, luego pscp.
4. Restart: `docker compose restart web`.

**Histórico**: pasó 2026-05-11. Faltaban `web_routes_*.py`, `web_utils.py`, `web_watchdog.py`, `web_auth.py`, `tzdata` package.

---

### Spike de 406 FAILURE_IN_CAPTCHA en login (depósitos + actualización de cuentas)

**Síntoma**: muchos logins fallan con `[API] Status: 406` / `RETRY_CAPTCHA`. Tasa real por intento subió 0% (05-23) → 24% (05-26) → 48% (05-27). Pasa en updates y depósitos.

**Causa raíz (medida, NO supuesta)**: BetMexico endureció su antifraude ~25-may (frontend build `bmx-prod-v26.5.25` agregó reCAPTCHA **v3**). El 406 es rechazo por **reputación de IP / score**, disfrazado de fallo de captcha. NO fue cambio nuestro (`betmexico_login_api.py` intacto desde 11-may). El commit `6908af3` (rotación agresiva de 5 IPs) lo empeoró: martillar **quema IPs**.

**Descartado con datos** (NO reintentar): migrar a v3 (0% aun con navegador real Playwright); token v2 declarado `captchaVersion:"v3"` (0%); misma-IP solve+submit (10%, peor); reportar a CapMonster (riesgo de ban, los 406 no son tokens malos).

**Fix**: quedarse en v2; **dejar de martillar** y portar la estrategia gentil del bot (`betmexico_check.py`: jitter + throttle por `captcha_fail_streak` + backoff 403/429); resolver v2 proxyless + submit por sticky residencial MX fresco; reintentos gentiles (p≈50%/intento fresco → 4 intentos ≈ 94%). **Plan completo: `docs/plans/login-orchestration-rework.md`.**

**Causa concreta encontrada 2026-05-29 (commit `2d469a8`)**: el IPRoyal del pool (`proxy_pool.EXTRA_ADMIN_PROXIES`) estaba mal configurado con `_country-mx_city-ciudadobregon_streaming-1` (puerto 11200) = **IP PEGADA a Ciudad Obregón** → una sola IP que se quemó y daba 84% de 406 (medido: 26×406 vs 5×200). Robert dio el correcto: **puerto 11201 + `_country-mx_streaming-1` (sin city)** = rotación nacional MX, IP fresca por intento. Resultado inmediato: 406 cayó a ~40% y 100% de cuentas lograron LIVE (4/4). LECCIÓN: un proxy "residencial MX" con `city`/`streaming` fijo NO rota → se quema igual que una IP estática. Para BetMexico hay que usar rotación nacional. Además el matchmaker ahora reintenta `LOGIN_FAILED` `MM_MAX_LOGIN_RETRIES=3` veces (antes descartaba al primer 406).

---

### Token v2 de CapMonster desperdiciado: 1 token quemado por cada reintento de login

**Síntoma**: cada 406 `RETRY_CAPTCHA` durante el login gastaba un token nuevo de CapMonster. En un login que reintenta 4 veces = 4 tokens solicitados (3 "tirados").

**Causa**: `gentle_login` reintentaba llamando `get_jwt(..., max_retries=1)`, y `get_jwt` saca **un token nuevo del pool** en cada llamada (`betmexico_login_service.py` L94 `pool.get_token`). El token del intento previo se descartaba.

**Insight (Robert, 2026-06-01)**: un 406 `FAILURE_IN_CAPTCHA` **NO consume el token v2**. BetMexico rechaza el request (por reputación de IP o por esperar otra versión) **antes de mandarlo a verificar con Google**, así que el token sigue vivo su TTL (~120s). No hay por qué tirarlo.

**Fix (2026-06-01, deploy scp + restart)**: `login_orchestrator.py` — `gentle_login` ahora llama `betmexico_login_api.BetmexicoApiChecker.test_login` directo **reusando el mismo token** entre reintentos (solo rota IP + jitter). Pide un token nuevo solo si: no hay, edad ≥ `_TOKEN_REUSE_MAX_AGE` (100s) o se reusó ≥ `_TOKEN_MAX_REUSES` (8, auto-cura defensiva por si en prod resultara que sí se consume). JWT cache fast-path y REGLA DE ROBERT (solo LOGIN_DENIED/KYC/AUTOEXCLUSION matan) intactos. Prefetch de pool subido a 2 en programado/single (spare caliente).

**Caveat medido**: el test del 2026-06-01 (`_test_token_reuse.py`, cuenta `olimpo.flor`) cuadró LIVE **al primer intento proxyless** → NO llegó a observar un 406 que reusar. El reuso es bajo riesgo (peor caso = comportamiento viejo, pero ahorra solves); la supervivencia-al-406 aún **no está confirmada en prod**. Verificar en `dashboard.log` cuando vuelvan los 406: buscar `token reusado Nx` con N>0 en un `LIVE`. Dato extra: el pool de proxies salió **vacío** en el container y proxyless cuadró igual (coincide con "v2 proxyless").

---

### Movimientos del modal: las horas "nuestras" salían +6h (corregido 2026-05-28)

**Síntoma**: en el modal de detalle (sección MOVIMIENTOS), las transacciones propias (ícono rayo, `source=dashboard`) aparecían 6 horas adelante vs la página real de BetMexico. Ej: depósito mostrado a las 08:09 cuando la página lo muestra a 02:09. Las de BetMexico (`source=betmex`, globo) salían bien → "algunas bien, otras no".

**Causa raíz (verificada con BD prod, NO supuesta)**: `deposit_attempts.created_at` se guarda en **UTC naïve** (`'2026-05-28 08:09:43'`, confirmado: ≈ `date -u` del host, no la hora CST del container). `account_transactions.txn_date` de BetMexico ya viene en **hora MX naïve** (confirmado: SPEI en BD coinciden con la franja de la página). El frontend (`parseTs` en `app.js`) trata **todo** timestamp naïve como hora local MX → las UTC salían +6h. Además el sort por `when` mezclaba UTC y MX → orden inconsistente entre fuentes.

**Fix**: `app.py` (endpoint de detalle, armado de `movimientos`) convierte SOLO `created_at` de UTC→MX con `zoneinfo America/Mexico_City` (fallback `-6h`; MX no tiene DST desde 2022) antes de mandarlo en `when`. `txn_date` queda intacto (ya MX). Helper `_utc_to_mx()`. Bonus: el sort vuelve a ser correcto (ambas fuentes en MX).

---

### El matchmaker marca cuentas BUENAS como DEAD cuando falla el login (corregido 2026-05-28)

**Síntoma**: cuentas válidas quedan `status='DEAD'` con `dead_reason='LOGIN_FAILED'` y ya no se reintentan.

**Causa raíz**: `deposits.py` (matchmaker `multi_stream`) metía `LOGIN_FAILED` en la misma rama que `AUTOEXCLUSION`/`KYC_PENDING` y persistía `status='DEAD'` en BD.  
Pero `LOGIN_FAILED` = 406/captcha/proxy = fallo de **nuestra infraestructura**, nunca de la cuenta.  
Agravante: `LOGIN_FAILED` es el ÚNICO código que el matchmaker puede producir (`AUTOEXCLUSION`, `KYC_PENDING`, `3DS_UNDETECTED`, `SHADOW_BAN?` nacen en `web_routes_deposits.py` y nunca llegan a `multi_stream`). O sea esa rama mataba cuentas buenas el 100% de las veces que se activaba. Con la tasa de 406 alta (may 2026), a escala masacraba.

**Daño documentado**: 5 cuentas marcadas DEAD innecesariamente (11–15 may 2026):
- `fcojavii2662@gmail.com`
- `azul_171175@live.com`
- `memo.teo10@gmail.com`
- `danoscene@gmail.com`
- `silcas22@gmail.com`

**Diagnóstico**:
```bash
sqlite3 /data/betmexico_accounts.db \
  "SELECT email, dead_reason, dead_at FROM accounts WHERE status='DEAD' AND dead_reason='LOGIN_FAILED'"
```

**Fix aplicado** (`deposits.py` L1550-1558, 2026-05-28):
- `LOGIN_FAILED` ya NO toca BD ni `dead_reason`.  
- Emite evento SSE `type:'login_retry'` con `{email, code, tail, attempt}`.  
- Marca `acc["login_retry"]=True` y `acc["fail_count"]=MM_MAX_FAILS` en memoria (solo sale del run actual — no persiste).  
- `3DS_UNDETECTED` / `SHADOW_BAN?` salieron de la rama DEAD → caen en el `else` genérico (strike a tarjeta + cuenta, no DEAD).  
- Solo `AUTOEXCLUSION` y `KYC_PENDING` siguen marcando `status='DEAD'` persistente.

**Regla de Robert (2026-05-28, no negociable)**:  
Una cuenta solo muere por (1) 401 credenciales/lock definitivo, (2) KYC_PENDING, (3) AUTOEXCLUSION.  
Todo lo demás — incluido cualquier LOGIN_FAILED (406/captcha/proxy/BAN-429/timeout) — se convierte en REINTENTOS, jamás DEAD.

**Recovery SQL ejecutado en prod KVM4** (backup previo en `/docker/betmexico/data/backups/`):
```sql
UPDATE accounts
SET status='LIVE', dead_reason=NULL, dead_at=NULL
WHERE status='DEAD' AND dead_reason='LOGIN_FAILED';
-- Filas afectadas: 5
```

**Histórico**: detectado 2026-05-28. Raíz introducida en el diseño inicial del matchmaker. Ver también `docs/plans/login-orchestration-rework.md` §4.

---

### Las tarjetas no se persisten en `account_cards` después de un depósito aprobado

**Síntoma**: depósito BANK_APPROVED en `deposit_attempts` pero `account_cards` para esa cuenta = 0 rows. El panel detalles muestra "Sin tarjetas guardadas".

**Causa raíz**: el módulo `betmexico_db.py` usa **ruta relativa** (`DB_FILE = Path("betmexico_accounts.db")`) → resuelve a `/app/betmexico_accounts.db` (BD fantasma) dentro del container, mientras la BD real está en `/data/betmexico_accounts.db`.

**Diagnóstico**:
```
docker exec betmexico-web find / -name 'betmexico_accounts.db' 2>/dev/null
```
Si ves 2 archivos → la fantasma está creándose y desviando escrituras.

**Fix** (aplicado 2026-05-11):
- `Proyectos/BetMexico/Telegram/betmexico_db.py:26` debe ser:
  ```python
  import os as _os
  DB_FILE = Path(_os.environ.get("BETMEX_DB", "betmexico_accounts.db"))
  ```
- `.env` debe tener `BETMEX_DB=/data/betmexico_accounts.db`.
- Borrar la fantasma: `docker exec betmexico-web rm -f /app/betmexico_accounts.db` (verificar antes que esté vacía o tenga solo datos huérfanos).

---

### Tarjetas no se guardan en `account_cards` tras APPROVED por single moderno / multi / scheduled (2026-05-25)

**Síntoma**: el operador deposita exitosamente con una tarjeta nueva. La próxima vez que abre la cuenta, la tarjeta NO aparece en "💳 Tarjetas guardadas" y tiene que volverla a pegar manualmente. Solo persiste en `deposit_attempts.card_pipe`, no en `account_cards`.

**Causa raíz**: tres endpoints distintos comparten el wrapper `_run_deposit_with_phases` ([deposits.py:490](../deposits.py)):
- `POST /api/deposits/execute-stream` (single moderno)
- `POST /api/deposits/multi/stream` (matchmaker)
- `POST /api/deposits/scheduled/create` (programado)

Ese wrapper **NO** llama a `db.register_card_to_account`. Solo el legacy `_run_deposit` del bot (usado por `/api/deposits/execute` legacy, no consumido por el UI moderno) lo hace. El persister centralizado `_record_attempt` ([deposits.py:391](../deposits.py)) escribía en `deposit_attempts` con `card_pipe` pero ignoraba `account_cards`. El AUDIT viejo marcaba esa fila como ✅ pero era falso para los 3 endpoints modernos.

**Fix aplicado** (2026-05-25):
- Bloque dedicado en `_record_attempt` ([deposits.py:441-477](../deposits.py)):
  - Si `status == "approved"` y hay `card_pipe`: parsea pipe → `(cc_num, cc_exp, cc_cvv)`, busca password de la cuenta vía `app.db()`, resuelve nombre del operador desde `web_auth.WEB_USERS_RAW`, llama `db.register_card_to_account` (idempotente por UNIQUE card_number).
  - 3DS_REQUIRED NO guarda (la tarjeta no se acreditó). Regla operativa Robert: solo APPROVED real cuenta como tarjeta marriage.
  - Cubre los 3 endpoints en un solo punto.

**Diagnóstico**:
```bash
docker exec betmexico-web sqlite3 /data/betmexico_accounts.db \
  "SELECT a.email, a.cards_count, COUNT(da.id) as approved_attempts FROM accounts a
   LEFT JOIN deposit_attempts da ON da.account_email=a.email AND da.status='approved'
   GROUP BY a.email HAVING approved_attempts > 0 AND a.cards_count = 0"
```
Si hay rows → cuentas que tenían approved attempts pero 0 cards (regresión histórica). Para retro-poblar: correr un script que recorra `deposit_attempts` con status=approved y haga register_card_to_account por cada row.

---

### `_sse_queues` siempre vacío durante broadcasts del scheduled — clients=0 fantasma (2026-05-26)

**Síntoma**: el frontend SE conecta al SSE (`/api/events`), el browser reporta la conexión activa, pero NUNCA recibe los eventos `scheduled_*` del schedule que disparó. El watchdog 30s del frontend dispara la alerta "⚠️ Sin señal del backend".

**Causa raíz**: `app.py` se cargaba **DOS VECES** en `sys.modules` con nombres distintos:
- `__main__` — instancia creada cuando uvicorn arranca con `python web/app.py` (entry point del Dockerfile).
- `app` — instancia creada cuando `deposits.py`, `prewarm.py`, etc. hacen `from app import _broadcast`. Python no encuentra `app` en sys.modules y reimporta el archivo.

Aunque ambas instancias apuntan al mismo `/app/web/app.py`, son módulos Python distintos con namespaces independientes. Cada uno tiene su propio `_sse_queues` (list separada).

**Consecuencia**: El endpoint `/api/events` está registrado en la app FastAPI de `__main__`, así que los clientes SSE se agregan a `__main__._sse_queues`. Pero `_broadcast` invocado desde `deposits.scheduled_create.loop()` empuja a `app._sse_queues` (otra lista, siempre vacía). Los eventos se "broadcastean" pero ningún cliente está suscrito a esa queue.

Verificación runtime:
```python
import app as a1
import web.app as a2  # o cualquier path que encuentre el mismo file
assert a1 is a2  # FALSE — son módulos distintos
assert a1._sse_queues is a2._sse_queues  # FALSE — listas distintas
```

**Fix aplicado** (2026-05-26, [app.py:18](../app.py)): alias en sys.modules apenas arrancamos como __main__:
```python
if __name__ == "__main__":
    sys.modules.setdefault("app", sys.modules[__name__])
```

Cuando `deposits.py` luego hace `from app import _broadcast`, Python encuentra `app` ya en sys.modules y reutiliza la instancia de `__main__`. Una sola lista `_sse_queues`, todos los broadcasts encuentran clientes.

**Diagnóstico que confirmó el bug**: instrumenté `_broadcast` y `_sse_generator` con `id(q)` (identidad de la queue) y `all_ids = [id(x) for x in _sse_queues]`. Pre-fix los logs mostraban:
- Conexión: `q_id=134005432697216 all_ids=[134005432697216]`
- Broadcast (mismo proceso, segundos después): `clients=0 q_ids=[]`

El cliente seguía conectado al server (no había log de desconexión), pero el `_broadcast` veía otra lista vacía. Post-fix los `q_ids` del broadcast coinciden con el `q_id` del client conectado.

---

### Modal Programado se queda "Preparando intento 1 de 10…" por 30s+ sin actualizar (2026-05-25)

**Síntoma**: el operador lanza una misión Programada de N depósitos. El panel premium muestra `0/N` con el texto "Preparando intento 1 de N…" y NO cambia durante medio minuto o más. El depósito sí está corriendo en backend (los `deposit_attempts` se persisten), pero el feed live del modal no responde.

**Causa raíz (dos componentes)**:

1. **Pool warm-up invisible**: `scheduled_create.loop()` espera `await pool.start_factory()` y `pool.prefetch(1)` antes de iterar — 5-15s sin ningún `phase_cb` emitido. El frontend no tiene señal de vida durante esa ventana → operador ve "Preparando…" estático y asume backend muerto.

2. **Race condition de `sched_id`**: si el captcha pool ya estaba warm, el primer `phase_cb("login_start", ...)` puede dispararse en <100ms — antes de que la respuesta HTTP de `/scheduled/create` haya retornado al frontend y `_schedShow(sched_id, ...)` haya seteado `_schedActive`. La guarda en `_schedOnPhase` (`if (!_schedActive ...) return`) descartaba silenciosamente el evento. Los siguientes eventos SÍ entraban, pero el operador veía el primer iter sin transición visual.

**Fix aplicado** (2026-05-25):

Backend ([deposits.py:1610-1625](../deposits.py)):
- Heartbeat `kind:scheduled_started` broadcasted **inmediatamente** dentro de `loop()`, ANTES de `pool.start_factory()`. Confirma backend vivo en <50ms.

Frontend ([static/app.js:3545-3625](../static/app.js)):
- **Buffer**: si `scheduled_phase/scheduled/scheduled_aborted/scheduled_cancelled` llega con `_schedActive=null`, se acumula en `_schedPendingEvents` y se reproduce desde `_schedShow` cuando el state está listo.
- **Hint rotator** (`_schedHintTimer`): durante el pool warm-up el texto cicla cada 3.5s: `⚡ Calentando captcha pool` → `🔑 Solicitando token CapMonster` → `🚀 Levantando worker` → `⏳ Esperando primer login`. Se cancela al recibir el primer `scheduled_phase` real.
- **Watchdog 30s** (`_schedWatchdogTimer`): si no llega ningún `scheduled_phase` en 30s desde `_schedShow`, alerta al operador: `⚠️ Sin señal del backend (>30s). La misión sigue corriendo, pero el feed live no responde.` Permite distinguir "pool lento" de "SSE muerto" en producción.

**Diagnóstico runtime**:
```js
// En consola del navegador durante un Programado:
console.log('_schedActive:', _schedActive, 'pending:', _schedPendingEvents.length);
```
- Si `_schedActive=null` y misión activa → race fix no corrió (revisar versión deploy).
- Si pending > 0 al final → buffer ayudó, eventos huérfanos.

---

### Cuentas muestran balance/depósito/check desactualizados después del prewarm

**Síntoma**: pulsar "Actualizar visibles" consume Capsolver pero el dashboard sigue mostrando balance viejo, sin fecha de último depósito y `last_checked_at` que no avanza.

**Causa (3 bugs combinados)**:

1. **`_db_upsert_balance` incompleto** (bug en versión desplegada): sólo actualizaba `balance_real` y `balance_total` (que podía llegar NULL si la API no lo calcula). Nunca escribía `balance_bonos`, `last_deposit_amount`, ni `last_deposit_date`.

2. **Capsolver gastado en vano**: `pool.prefetch(1)` resolvía un captcha ANTES de chequear si el JWT seguía en cache. Si el JWT era válido, el captcha prefetchado se descartaba.

3. **`ok=True` falso cuando `details=None`**: si el fetch fallaba (timeout 18s, API sin datos, JWT rechazado), `_run_prewarm` igual retornaba `{"ok": True}` → frontend leía el row viejo como "actualizado". `last_checked_at` nunca se escribía → anti-spam (30min) no detectaba el intento → retry inmediato.

**Fix aplicado** (`prewarm.py`, 2026-05-13):
- `_db_upsert_balance`: calcula `balance_total = bal_real + bal_bonos`, escribe `balance_bonos`, escribe `last_deposit_*` cuando la API los trae válidos.
- `_run_prewarm`: chequea `_db_get_jwt_cache` ANTES de `make_pool/prefetch`. JWT vigente → fetch directo, 0 Capsolver. JWT de cache rechazado por BetMexico → invalida el cache (`jwt_token=NULL`) para forzar login real la próxima vez.
- `_run_prewarm`: retorna `ok=False` cuando `details is None`. Siempre escribe `last_checked_at` (incluso en timeout) para activar el anti-spam.

**Diagnóstico rápido**:
```bash
docker exec betmexico-web sqlite3 /data/betmexico_accounts.db \
  "SELECT phase, COUNT(*) FROM process_log WHERE process_type='prewarm' GROUP BY phase"
```

---

### `tzdata` falta / `apt-get install tzdata` bloquea el build

**Síntoma**: `ZoneInfoNotFoundError: 'No time zone found with key America/Mexico_City'` al cargar `betmexico_login_api.py`. O `docker build` se queda colgado en `Configuring tzdata` esperando input.

**Causa**: imagen base `mcr.microsoft.com/playwright/python` **NO incluye** `tzdata` ni el módulo Python `playwright` por defecto.

**Fix**: el Dockerfile DEBE tener:
```dockerfile
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=America/Mexico_City
RUN ln -fs /usr/share/zoneinfo/America/Mexico_City /etc/localtime && \
    apt-get update && apt-get install -y --no-install-recommends tzdata && \
    dpkg-reconfigure -f noninteractive tzdata && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    ... \
    'tzdata' \
    'playwright>=1.49.0'
```

`DEBIAN_FRONTEND=noninteractive` es **obligatorio** o el build se cuelga.

---

### Container restart se queda en "Deactivating" mucho tiempo

**Síntoma**: `docker compose restart web` tarda más de 30s, status muestra "Restarting".

**Causa**: conexiones SSE abiertas (`/api/events`) bloquean el shutdown ordenado de uvicorn.

**Fix**:
```bash
docker compose kill -s SIGKILL web
docker compose up -d web
```

---

### `/api/deposits/multi/stream` 200 OK pero matchmaker no avanza

**Síntoma**: el endpoint responde, pero el frontend nunca recibe eventos en el `EventSource`.

**Causa**: pool de captcha falla en obtener tokens (CapMonster sin saldo o key inválida).

**Diagnóstico**:
```bash
curl -X POST https://api.capmonster.cloud/getBalance -H 'Content-Type: application/json' \
  -d '{"clientKey":"<KEY>"}'
```

**Fix**:
- Si balance < $5 → recargar
- Si error `ERROR_KEY_DOES_NOT_EXIST` → actualizar `.env` con nueva key

---

### Login a BetMexico devuelve 403 RATE_LIMITED después de varios intentos

**Síntoma**: log dice `[BAN] 403 Rate limit: <email>`. Login deja de funcionar para esa cuenta temporalmente.

**Causa**: BetMexico rate-limita IPs/cuentas que hacen muchos logins seguidos.

**Fix**:
- Esperar 10-30 minutos
- Rotar proxy: `POST /api/admin/refresh-proxy` (SA)
- Verificar que `betmexico_login_api` usa el proxy MX (sufijo `_country-mx` en proxy URL)

---

### Cuentas autoexcluidas se colaban como LIVE y fallaban con críptico `BEGIN_ERROR` (corregido 2026-05-29)

**Síntoma**: depósito (programado/single/matchmaker) sobre una cuenta autoexcluida fallaba en `gateway_begin` con `BEGIN_ERROR` en ~0–2s, sin avisar al operador qué pasó. La cuenta seguía apareciendo LIVE (como "basura" en la lista) y se reintentaba.

**Causa raíz (verificada con login fresco real, NO supuesta)**: la API de login de BetMexico (`/api/Session/login`) devuelve `isSuccess=True` + JWT **incluso para cuentas autoexcluidas** → `gentle_login` las clasifica `LIVE`. La restricción solo se manifiesta al depositar: `begin_deposit` (paymentsapi) devuelve `401 {"redirectLogin":true}`. El campo de autoexclusión SÍ viene en el perfil (`GET https://betmexico.mx/api/Users/{userId}` → `data.autoexclusion = {exclusionMonth, resumeExclusionDate}`), pero el extractor del bot (`fetch_account_details_parallel`) lo ignora.

**Fix aplicado** (commit `99d1523`, todo en el repo dashboard — el monorepo NO se tocó, solo se leyó):
- `autoexclusion.py` (nuevo): `check_autoexclusion(jwt, proxy)` consulta `/api/Users/{userId}` con el JWT que el dashboard ya tiene tras `gentle_login` y devuelve la info si `resumeExclusionDate` es futura. `mark_account_autoexcluded()` → `status='DEAD'`, `dead_reason='AUTOEXCLUSION hasta DD/MM/YYYY (N meses)'`.
- **Update** (`prewarm._run_prewarm`): gate tras login → autoexcluida pasa a DEAD y sale de la vista (`list_accounts` filtra `status='LIVE'`).
- **Depósito** (`deposits._run_deposit_with_phases`): gate tras login, ANTES de `begin_deposit` → `AUTOEXCLUSION` + DEAD + mensaje con fecha. Cubre los 3 flujos (comparten el wrapper). Fallback: un `401 redirectLogin` en `begin_deposit` re-verifica autoexclusión. Body crudo de `begin_deposit` ahora se loguea (antes se perdía).
- Frontend: misión abortada y feed muestran el `reason` explícito, no el code pelón.

**Regla de Robert (2026-05-29)**: autoexclusión = una de las 3 razones de muerte → DEAD es correcto y persistente.

**Diagnóstico**:
```bash
docker exec betmexico-web sqlite3 ... # (no hay sqlite3 en el container; usar python3)
docker exec betmexico-web python3 -c "import sqlite3;c=sqlite3.connect('/data/betmexico_accounts.db');print(c.execute(\"SELECT email,status,dead_reason FROM accounts WHERE dead_reason LIKE 'AUTOEXCLUSION%'\").fetchall())"
```

---

### Programado quemaba captcha toda la misión aunque reusara la sesión (corregido 2026-05-29)

**Síntoma**: una misión Programada (1 tarjeta, N reps, reuso de JWT) seguía resolviendo tokens CapMonster cada ~55s durante todos los minutos del run, aunque solo la iter 0 hace login.

**Causa raíz**: `scheduled_create.loop()` arranca `pool.start_factory()`, cuyo `_factory_loop` mantiene el pool lleno a `max_pool` indefinidamente: cada token expira a los `TOKEN_MAX_AGE=55s` y el factory lo regenera. Las iters 1..N reusan `session_jwt` (0 captcha), pero el factory seguía produciendo. Una misión de 9 reps (~9 min) resolvía ~9 tokens innecesarios.

**Fix** (`deposits.py`, commit `99d1523`): tras capturar la sesión en iter 0 (`session_jwt`), `await pool.stop()` (idempotente) y `pool=None`. El factory sólo vive durante el login inicial (donde sí se necesita para reintentos de `gentle_login`); después se apaga. 1 token por misión en vez de ~N.

---

### Movimientos/balance no se actualizaban tras un intento de depósito (corregido 2026-05-29)

**Síntoma**: tras depositar (aprobado o rechazado), el panel de detalle seguía mostrando movimientos/saldo viejos hasta picar "Actualizar visibles" manual.

**Causa raíz**: las transacciones solo se capturaban en el LOGIN (que ocurre ANTES del depósito) → el intento recién hecho nunca se reflejaba. En programado, las iters con reuso de sesión (`persist_login_data=False`) ni refrescaban.

**Fix** (`deposits.py`, commit `99d1523`): helper `_refresh_account_after_deposit()` corre al final de `_run_deposit_with_phases` (los 3 flujos): reusa el JWT del login (sin captcha) para `fetch_account_details_parallel(fetch_mode="full")` y persiste balance+txns+grade vía los persisters de `prewarm`. Emite SSE `account_refreshed`; el frontend repinta la fila y, si el detalle de esa cuenta está abierto, recarga los movimientos sin cerrar el panel. Costo: +2–5s por intento (sin captcha).

---

### El programado abortaba la misión entera ante fallos TRANSITORIOS (corregido 2026-05-29)

**Síntoma**: misiones programadas de N reps morían en la iter 1-2 con `✗ Misión abortada — BEGIN_ERROR` (504 Gateway Timeout) o `— LOGIN_FAILED` (406 FAILURE_IN_CAPTCHA), sin reintentar. Robert: *"¿por qué chingados se detiene si falla el login? eso ya lo habíamos ajustado"*.

**Causa raíz**: el loop del scheduled hacía `if not ok: scheduled_aborted; break` ante **cualquier** falla. El ajuste previo (commit `78b4628`) fue solo para el MATCHMAKER (no marcar DEAD por `LOGIN_FAILED`); el programado seguía abortando. Un `504` del gateway de pagos o un `406` de captcha — ambos **infraestructura NUESTRA, no la cuenta** — mataban la misión completa.

**Fix** (`deposits.py` + `static/app.js`, commit `951c449`):
- **`begin_deposit` con retry** (`_run_deposit_with_phases`, los 3 flujos): es PRE-COBRO (paso 1, antes de `submit_card`) → reintentarlo NO duplica cargos. Ante `50x`/`timeout`/`connection` reintenta `BEGIN_MAX_ATTEMPTS=3` con backoff 6s. `_is_transient_gateway_error()` excluye 401/redirectLogin (eso es sesión/autoexclusión).
- **Loop del programado reescrito (`for`→`while`)**: cuenta reps **EXITOSAS**. Ante fallo TRANSITORIO (todo lo que NO está en `SCHED_TERMINAL_RC`) reintenta la **misma rep** hasta `SCHED_MAX_TRANSIENT_RETRIES=4` con backoff `25s` (enfría IP en 406), **sin abortar**. Si la sesión reusada muere (401) reactiva el pool para re-login. Solo detienen razones REALES: `BANK_REJECTED`, `BANK_REJECTED_AFTER_APPROVE`, `3DS_REQUIRED`, `AUTOEXCLUSION`, `KYC_PENDING`, `LOGIN_DENIED`, `PENDING_NOT_APPLIED`, `DEPS_MISSING`.
- **Frontend**: evento `scheduled_retry` → panel muestra `🔁 Reintentando intento N (x/4)` + rastro en timeline + label en feed. No se queda pegado.

**Regla de Robert (2026-05-29)**: errores de NUESTRA infraestructura (captcha/proxy/gateway/login 406) = REINTENTOS, jamás detener. Igual principio que `gentle_login` y el matchmaker. Solo el estado REAL de BetMexico (tarjeta rechazada, autoexclusión, KYC, credenciales) detiene.

---

### Login masivo cae en `402 Payment Required` — proxy IPRoyal sin saldo (2026-06-23)

**Síntoma**: ráfaga de logins fallando, ~50% con `[ERROR] test_login: 402 Payment Required` (sin un `[API] Status:` previo), el resto alternando `406 FAILURE_IN_CAPTCHA` y `429 Rate limit`. `gentle_login` agota los 4 intentos → `LOGIN_RETRY_LATER`. Robert preguntó alarmado si el dashboard estaba logueando **proxyless**.

**Causa raíz (verificada con curl directo, NO supuesta)**: el proxy **IPRoyal** (`geo.iproyal.com:11201`, en `proxy_pool.EXTRA_ADMIN_PROXIES`) **se quedó sin saldo**. Rechaza cada CONNECT con:
```
> CONNECT api.ipify.org:443 HTTP/1.1
< HTTP/1.1 402 Payment Required
< X-Response-Origin: proxy-server      ← el propio proxy, no BetMexico
* CONNECT tunnel failed, response 402
```
El 402 se levanta como **excepción durante el CONNECT** (antes de llegar a BetMexico) → cae en el `except Exception` de `betmexico_login_api.test_login` que loguea `[ERROR] test_login: {e}`. Por eso NO hay `[API] Status: 402` previo (contraste: 406/429 sí muestran `[API] Status:` porque la request sí llegó). El pool del dashboard hace `random.choice` entre 2 proxies (IPRoyal + NodeMaven; LitPort ya estaba excluido), así que ~50% de los intentos caían en IPRoyal y morían al instante.

**Proxyless descartado (importante)**: NO se estaba logueando sin proxy. `gentle_login` tiene `allow_proxyless=False` por default ([login_orchestrator.py:213](../login_orchestrator.py)) y bloquea el submit si el pool no da proxy ([login_orchestrator.py:302](../login_orchestrator.py)) → `LOGIN_RETRY_LATER`. Confirmado además por ausencia de cualquier log `SIN PROXY disponible`. La IP real del server nunca se expuso.

**Fix aplicado** (2026-06-23, `proxy_pool.py`): IPRoyal agregado a `_EXCLUDED_PROXY_HOSTS = ("litport", "iproyal")`. `all_proxies()` lo filtra → el pool queda solo con **NodeMaven** (instrucción de Robert: "redirige el tráfico por NodeMaven"). Los 402 desaparecen.

**Caveat**: con IPRoyal fuera, el pool queda con **un solo proxy** (NodeMaven). Si NodeMaven se cae o se queda sin saldo, el pool queda vacío → `gentle_login` bloquea (LOGIN_RETRY_LATER, NUNCA proxyless). El **406/429 de NodeMaven sigue siendo problema de fondo** (reputación IP vs antifraude BetMexico — ver entries de 406 arriba); excluir IPRoyal solo elimina el desperdicio del 402, no arregla el 406.

**Reversión**: cuando se recargue saldo en IPRoyal, quitar `"iproyal"` de la tupla. Verificar antes:
```bash
curl -sv -x "http://USER:PASS@geo.iproyal.com:11201" https://api.ipify.org 2>&1 | grep -iE "HTTP/|402"
# Debe dar HTTP 200, no 402.
```

**Diagnóstico** (para distinguir 402-proxy de 402-otro en el futuro):
```bash
# Probar cada proxy del pool directo:
curl -sv -m 20 -x "<proxy_url>" https://api.ipify.org 2>&1 | grep -iE "CONNECT|402|Payment|X-Response-Origin"
# 402 + X-Response-Origin: proxy-server  →  proxy sin saldo
```

---

### Login no procesa: `httpx.ProxyError: 504 Gateway Timeout` — pool quedó monoproxy (NodeMaven) (2026-06-24)

**Síntoma**: matchmaker / depósito multicuenta nunca completa login. Ráfaga nocturna (2026-06-25 01:01–02:00 UTC, 42 eventos) de:
```
File "/app/betmexico_login_api.py", line 443, in test_login
File "/app/betmexico_login_api.py", line 528, in _login_api   (resp = await client.post(...))
httpx.ProxyError: 504 Gateway Timeout
```
`gentle_login` rota IP, agota los intentos → `LOGIN_RETRY_LATER`. (El contenedor `betmexico-bot` aparecía `Exited(1)`, pero es **a propósito** — sin token Telegram; NO relacionado con el login del dashboard.)

**Causa raíz (verificada con sonda en vivo desde el contenedor, NO supuesta)**: tras excluir IPRoyal (402, 2026-06-23) y LitPort, el pool quedó con **un solo proxy**: NodeMaven (`gate.nodemaven.com:8080`), que da **504 Gateway Timeout intermitente ~22% (2/9 requests, ~10s)** en el CONNECT/upstream de su propio gateway. Prueba de que NO es BetMexico: el 504 golpea hasta `api.ipify.org` (target neutral). Como es el único proxy, cada "rotación" de `gentle_login` cae en el MISMO gateway flaky → sin IP alterna → agota intentos. Es exactamente el **caveat monoproxy** que predecía la entry del 402 (arriba).

**Modo dominante distinto del 504**: en 24h el fallo de login dominante fue **406 FAILURE_IN_CAPTCHA (46) + 429 (22)**, no el 504 (10). El 406 = reputación de IP de NodeMaven (quemada) vs antifraude BetMexico.

**Fix aplicado** (2026-06-24, `proxy_pool.py`): agregado **Data Impulse** (50 sticky residenciales MX premium) como proxy **primario** (`DATAIMPULSE_PROXIES`). Mecanismo: host/user/pass fijos, el **puerto** define la sticky session → `10000..10049` = 50 IPs MX distintas (~2 min c/u); `__cr.mx` en el username = país MX. `all_proxies()` ahora combina `bot + EXTRA_ADMIN_PROXIES + DATAIMPULSE_PROXIES`. NodeMaven se mantiene como fallback minoritario (~2/52) por diversidad de proveedor; IPRoyal sigue excluido (sin saldo).

**Verificación en vivo** ✅ (6 puertos desde `betmexico-web`, 2026-06-24): 12/12 → 200, **0% 504**, IPs MX reales y distintas (177.225.x, 187.190.x, 201.141.x, 45.177.x), latencia 620-1150ms, `betmexico.mx/login` 200. Rompe el monoproxy y aporta 50 IPs frescas contra el 406.

**Pendiente**: el 406 por reputación se mitiga con IPs frescas, pero la cura de fondo es cargar lotes sticky frescos en runtime (`StickySessionManager`, ver `docs/plans/login-orchestration-rework.md`). Medir la tasa real de 406/429 con Data Impulse en producción.

**Diagnóstico** (distinguir 504-proxy de 504-BetMexico):
```bash
# Sonda neutral por el proxy sospechoso desde el contenedor:
docker exec -i betmexico-web python3 -c "import httpx;print(httpx.get('https://api.ipify.org',proxy='<proxy_url>',timeout=20).status_code)"
# 504 contra ipify (target neutral)  →  es el GATEWAY del proxy, no BetMexico.
```

---

## Frontend

### Logout del sidebar nunca estuvo cableado + topbar huérfana tras mover el buscador (2026-06-29)

**Síntoma (Robert)**: tras el reorg, al mover el buscador al sidebar, la topbar quedó casi vacía con la 🔔 (notificaciones) y el ⏻ (cerrar sesión) huérfanos arriba-derecha empujando las cards hacia abajo. Además el sidebar se salía de la pantalla (status + usuario/logout cortados abajo, exigiendo scroll).

**Causa raíz (verificada en código)**: el handler de logout (`app.js`) estaba cableado a `$$('.ico-btn[title="Salir"], .power')` — pero el botón de cerrar sesión del SIDEBAR (`.sb-user .ico-btn`) tiene `title="Cerrar sesión y salir"` (NO matchea `[title="Salir"]`), así que **el único logout funcional era el `.power` de la topbar**. El botón del sidebar nunca cerró sesión. Y `--topbar-h: 56px` reservaba una barra que, tras mover el buscador, quedó vacía en desktop empujando las cards.

**Fix (commit `bff8657`, deployado + md5 verificado)**:
- Quitados `.bell` (`#bellBtn`/`#bellBadge`) + `.power` de la topbar (redundantes: Notificaciones en el nav izq; logout en el sidebar). `renderNotifBadge` guarda `#bellBadge`; `#bellBtn?.addEventListener` con optional chaining.
- **Logout RECABLEADO** a `.sb-user .ico-btn` (selector `$$('.sb-user .ico-btn, .ico-btn[title="Salir"], .power')`).
- `.topbar` colapsada en desktop (`height:0`), restaurada en el `@media` mobile (para el hamburger).
- Sidebar compactado ~120px (brand/greet/sections/nav/online/status), logo 190→158px, para entrar sin scroll. Cache-bust `20260629b`.

**Pendiente**: confirmar en la pantalla de Robert (sesión limpia) que el sidebar entra completo sin scroll; si aún se sale, compactar más (logo / bloque Online).

### Panel de depósitos v8 — 5 bugs de cableado de eventos (code review 2026-06-28)

**Contexto**: tras hacer v8 el modal DEFAULT (commit `ae40021`), un code review por dominio del cableado `depos.js`↔`deposits.py` halló 5 bugs que NO estaban en el motor sino en cómo el frontend consume los eventos. La lógica pura (`depos_logic.js`) estaba sana (tests verde); los bugs vivían en los handlers DOM (sin cobertura por el DOM). Fix en `depos.js`/`depos_logic.js`/`depos.css` + cache-bust `?v=20260628e`.

1. **Programado: off-by-one — terminaba una rep ANTES y ocultaba la última.** El backend emite `iter` 1-indexed (`iter_num = completed+1`, deposits.py:2186/2266); `_schedOnBus` lo trataba como 0-indexed y volvía a sumar 1 (`s.iter+1`, `s.done = ev.iter+1`). Con `if (s.done >= s.total) schedFinish()` → reps=2 terminaba el panel en 1/2; reps=5 en 4/5; la última rep corría invisible (el bus ya cerró por el `interval` 60s). Conteo siempre +1. **Simulado** antes/después. **Fix**: tratar `ev.iter` como 1-indexed (`s.iter`/`s.done = ev.iter`).
2. **Matchmaker: `account_cooling` sin handler → fila colgada.** El anti-rate-limit Capa 3 emite `account_cooling` tras un `trying` (deposits.py:1938). El switch de `runMulti` no tenía ese case → la fila `_mmRows[email]` (creada por `trying`) nunca se resolvía (dot dorado "en curso" permanente) Y el operador no veía el enfriamiento. Es exactamente el punto (b) del e2e anti-rate-limit ("la fila no se queda colgada") → el e2e habría "fallado" por el frontend, no por el motor. **Fix**: `case 'account_cooling'` → estado `skip` "en pausa ~Nm".
3. **Matchmaker: `velocity_skip` (y `error`) dejaban fila colgada.** Mismo patrón (regresión del gotcha histórico ya resuelto en el matchmaker viejo): hacían `break` sin limpiar `_mmRows`. **Fix**: `velocity_skip`→`skip` "saltada"; `error`→borra la fila.
4. **Single: el balance "después" mostraba provisional, pisaba el fresco.** Orden real: `account_refreshed` (bus, deposits.py:1272) llega ANTES del `done` del stream (deposits.py:1420, el wrapper espera `await deposit_task` que incluye el refresh) → el frontend pintaba el balance real y luego el `done` lo pisaba con `fromBal+amount` (L2 quiere fresco). **Fix**: flag `_dx.balRefreshed` — el provisional no pisa si ya llegó el real.
5. **Multi: el preset $1000 SIEMPRE fallaba.** `multi_stream` valida `amount > DEP_MAX_PER_TXN($499)` → HTTP 400 (deposits.py:1641), pero el preset multi ofrecía `1000`. **Fix**: preset `490` (alineado al cap), quitado el tip "3DS" (ningún preset ≤499 garantiza 3DS sin medir). **Pendiente decisión Robert**: si se quiere un preset que fuerce 3DS de verdad (>499) hay que subir `DEP_MAX_PER_TXN` (valor operacional anti-detección).

**Menor no tocado**: `#modeText` lo busca `refreshMode()` (depos.js) pero NO existe en `#deposTpl` → el label de modo ("Programado · N · cada 60s") no se muestra. Agregar el elemento toca layout sensible (Robert lo cuida al pixel) → pendiente de decidir DÓNDE va, no se metió a ciegas.

### El feed de actividad muestra 2 entradas por 1 mismo depósito fallido

**Causa**: scheduled aborted dispara 2 broadcasts (`kind:scheduled` + `kind:scheduled_aborted`).

**Workaround**: ignorar visualmente — es 1 solo intento real (confirmar con `docker logs | grep TARGET <email>` cuenta apariciones reales).

**Fix pendiente**: consolidar en 1 evento o agrupar en UI por `sched_id + iter`.

---

### El modal de depósito programado se cierra automáticamente

**Causa**: `setTimeout(() => closeDepositModal(), 1500)` en `executeScheduled()` (app.js:3148 - LEGACY).

**Fix aplicado 2026-05-11**: quitado el auto-close. El modal queda abierto, el usuario lo cierra cuando quiere. Mensaje en `#depResult` indica "Sigue el progreso en el feed de Actividad".

---

### Tarjetas no aparecen en el panel detalles aunque hay depósitos exitosos

Ver "Las tarjetas no se persisten" arriba (mismo bug raíz).

---

### Cuentas no quedan reservadas al depositar (otros operadores las siguen viendo)

**Síntoma**: dos operadores trabajan la misma cuenta sin saberlo → conflict en BetMexico (sesiones simultáneas → bans).

**Causa**: el flujo de depósito (single/multi/scheduled) no aplicaba `locked_by` automáticamente. El lock era solo manual vía botón "Lock" del cmdBar.

**Fix aplicado 2026-05-11**:
- `deposits._auto_lock_for_deposit(account_id, operator_id, user, hours)` ejecuta UPDATE en `accounts.locked_by/locked_at/locked_until` al inicio de cada deposit
- Llamado desde `/api/deposits/execute` (2h), `/api/deposits/multi/stream` (2h por cuenta), `/api/deposits/scheduled/create` (4h)
- Rechaza con 409 si está lockeada por otro operador (SA puede override)
- Filtro en `/api/accounts`: non-SA solo ve cuentas con `locked_by IS NULL` o `locked_by = <my_tg_id>`
- Broadcast SSE `kind:lock` con `auto:true` para distinguir lock manual vs automático

**Histórico**: commit `<TBD>` 2026-05-11.

---

### Feed de Actividad muestra 2 entradas idénticas por cada depósito

**Síntoma**: el feed muestra 2 rows con mismo email/monto/timestamp/estado.

**Causa**: 2 funciones escribían a `deposit_attempts` en paralelo:
1. `web_routes_deposits._persist_final` → `db.log_attempt` (info completa)
2. `deposits._record_attempt` → INSERT directo (sólo con `card_pipe`)

Cada deposit creaba 2 rows → 2 events SSE → 2 filas en el feed.

**Fix aplicado 2026-05-11**:
- `_record_attempt` ya NO escribe — solo broadcastea SSE (1 sola vez)
- `_persist_final` ahora recibe y guarda `card_pipe` en la columna
- BD: limpiados duplicados existentes con query agrupada por `(email, amount, status, minute)`

**Histórico**: introducido con la migración inicial (2 paths heredados). Resuelto en commit `4ce207b`.

---

## Matchmaker live-progress (Task 4)

### `velocity_skip` deja rows en spinner permanente

**Síntoma**: en el panel matchmaker (multi), tras un `VELOCITY_SKIP` la tarjeta y la cuenta involucradas quedan con spinner girando hasta que un evento futuro las toque.

**Causa**: `handleMmEvent` no tenía `case 'velocity_skip'`. El `trying` previo ya dejó `card.status='busy'` y `acc.status='busy'`, y nadie las regresaba a `idle`.

**Fix** (2026-05-15, commit post-`f4c68e8`): agregado handler en `static/app.js` que pone ambos en `idle`, limpia `busyEmail/busyTail` + `currentPhase`, y agrega línea al feed con el `wait_sec`.

---

### Sub-indicador de fase desaparece cuando otro par dispara `_mmRender`

**Síntoma**: en matchmaker con 2+ pares concurrentes, el texto en `.mm-pair-phase` ("🔑 Login…", "💳 Tarjeta…") aparece y desaparece intermitentemente.

**Causa**: `_mmRender` hace `innerHTML = cardsHtml` — destruye el DOM y lo re-crea desde el modelo (`_mm.cards` / `_mm.accounts`). El texto inyectado por `_mmSetPairPhase` solo vivía en el DOM, no en el modelo, así que cualquier evento que dispare `_mmRender` (otro par, otro `trying`, etc.) lo borraba.

**Fix** (2026-05-15): `_mmSetPairPhase` ahora persiste el texto como `card.currentPhase` y `acc.currentPhase`. `_mmRender` inyecta este valor en el HTML inicial de filas `busy`. Eventos terminales (`match`, `rejected`, `account_dead`, `velocity_skip`, `done`) limpian `currentPhase = ''` para no mostrar texto stale en una segunda ronda.

---

### SSE drain loop sin heartbeat — proxies cierran conexión en captchas largos

**Síntoma**: en captchas que tardan 30s+, el cliente recibe `net::ERR_INCOMPLETE_CHUNKED_ENCODING` o el stream queda colgado. nginx/traefik cierran por timeout sin tráfico.

**Causa**: en `deposits.py` `multi_stream`, el drain loop del `gather_task` hacía `except asyncio.TimeoutError: pass` — 0 bytes enviados por SSE mientras los attempts corrían en paralelo.

**Fix** (2026-05-15): el `except asyncio.TimeoutError` ahora emite `yield ": ping\n\n"` (SSE comment heartbeat — no es un event, no afecta al cliente JS, pero mantiene la conexión activa contra proxies).

---

### `CancelledError` perdido en finally del execute-stream → activity feed loses entries

**Síntoma**: en escenarios de client-disconnect (browser cerrado mid-depósito), el feed de actividad pierde la entrada aunque el depósito haya completado en backend.

**Causa**: en `deposits.py` `/execute-stream`, el bloque de rescate de result hacía:
```python
try:
    result = deposit_task.result() or {}
except Exception:
    result = {}
```
`asyncio.CancelledError` es `BaseException`, no `Exception` (Python 3.8+). El except no lo atrapa, el resto del finally no corre, `_record_attempt` nunca se llama.

**Fix** (2026-05-15, v20260515f): cambiar a `except BaseException:` solo en ese rescate. El resto del código sigue con `except Exception` (intencional para no tragar CancelledError donde sí debe propagar).

---

### `gateway_check_done` rojo aunque depósito aprobado

**Síntoma**: el step `check` del stepper queda rojo mientras el banner final dice "Aprobado". Visualmente contradictorio.

**Causa**: `check_transaction` puede devolver `txn_status=0` (procesando) en depósitos ya aprobados. La condición frontend `txn_status === 1 || === 2` marcaba fail. La aprobación real viene de `result_code == "BANK_APPROVED"` en `gateway_submit_done`.

**Fix** (2026-05-15, v20260515f): `_handleExecStreamEvent` ahora solo marca fail si `d.check_error` está presente; `txn_status` es informativo. Adicionalmente, en el evento `type='done'` con `success: true`, se fuerza el step `check` a ok como reconcile final.

---

### Multi `done` event nunca emitido si el generator explota

**Síntoma**: en multi (matchmaker), si el generator lanza excepción, el finally limpia el pool pero el cliente nunca recibe `done`. Las pair rows (cards/accounts) quedan stuck con spinner hasta recargar la página.

**Causa**: el `yield {'type':'done'}` estaba FUERA del `try/finally` en `multi_stream`. Cualquier excepción dentro del try saltaba directo al finally sin pasar por el yield.

**Fix** (2026-05-15, v20260515f):
1. Backend: mover el `yield done` DENTRO del try. Agregar `except Exception` que emite `{'type':'fatal','run_id','error'}` antes del finally.
2. Frontend (`app.js`): agregar flag `_mmGotDone` en el SSE consumer. Si el stream cierra sin `done|fatal|cancelled`, limpiar busy → idle preventivo en cards/accounts y mostrar toast "Conexión interrumpida — selección reseteada".

---

### Botón ↻ de fila salta debajo del saldo cuando el monto tiene 4+ dígitos

**Síntoma**: en la tabla principal, cuando una cuenta tiene saldo `$1,234.56` o más, el botón ↻ (refresh individual) se mueve a la línea siguiente, ensanchando la fila y rompiendo la alineación con el resto de filas.

**Causa**: `#accTable td.num` tenía `width: 92px`. El monto en mono `$X,XXX.XX` + botón (22px + 6px margen) excede 92px → flex wrap natural del navegador empuja el botón abajo.

**Fix** (2026-05-21, `static/style.css:1075`):
```css
#accTable th.num, #accTable td.num { width: 128px; min-width: 128px; white-space: nowrap; }
```
- Sube el ancho a 128px (cabe `$99,999.99` + botón ↻).
- `white-space: nowrap` es la red de seguridad: aunque el contenido crezca, el botón nunca salta de línea (el cell se desborda en horizontal en su lugar, lo cual es muy preferible al wrap vertical).

**Histórico**: detectado 2026-05-21 por Robert tras ver saldos altos en la operación diaria.

---

### JWT cache rancio NUNCA se invalida — captcha desperdiciado en cada refresh

**Síntoma**: una cuenta con JWT cacheado que BetMexico ya rechazó silenciosamente sigue intentando login con ese mismo JWT cada refresh. La API devuelve `details` vacío, el balance no se actualiza, pero `last_checked_at` sí — el operador no nota nada salvo que el balance está stale.

**Causa**: en `prewarm.py:_run_prewarm` la variable `jwt_from_cache` se inicializa en `False` y nunca se asigna `True`. El bloque `if jwt_from_cache: _db_invalidate_jwt(email)` era código muerto desde el commit inicial.

**Fix** (2026-05-21, [prewarm.py:398](prewarm.py#L398)): quitar el guard `if jwt_from_cache`. Ahora cuando `details` viene vacío, el JWT cacheado se invalida incondicionalmente y el próximo refresh hace login real.

**Histórico**: detectado por code review 2026-05-21 (Batch 1 holistic).

---

### `/api/prewarm/refresh-stream` no cancela tasks si el cliente desconecta

**Síntoma**: el operador cierra el browser mid-refresh masivo → hasta 15 tasks `_run_prewarm` siguen corriendo en background, gastando captchas de CapMonster cuyo resultado nadie lee.

**Causa**: el async generator no llamaba `await request.is_disconnected()` durante el loop principal.

**Fix** (2026-05-21, [prewarm.py:655](prewarm.py#L655)): chequeo al inicio de cada iteración del `while done_count < len(accs)`. Si disconnected → cancelar todas las tasks pending → break.

---

### `_record_attempt` NO se llamaba si el cliente desconectaba mid-deposit (single)

**Síntoma**: depósito iniciado vía `/api/deposits/execute`, el operador cierra la pestaña o falla la red mid-deposit. Si BetMexico ya aprobó el cargo, la tarjeta se "quema" sin que la BD tenga row en `deposit_attempts` → invisibilidad total.

**Causa**: el handler tenía `except Exception as e:` alrededor de `_run_deposit`. `asyncio.CancelledError` deriva de `BaseException` (Py 3.8+), no de `Exception`, así que no entraba al except y el `_record_attempt` que vivía dentro de él nunca corría.

**Fix** (2026-05-21, [deposits.py:616](deposits.py#L616)):
- `except BaseException as e:` captura ambos.
- `_record_attempt` movido al `finally` (siempre corre).
- Re-raise post-finally: `Exception` → `HTTPException(500, ...)` (preserva contrato con frontend), `CancelledError` → propagación bare.
- Mismo patrón aplicado a iteración de scheduled ([deposits.py:1324](deposits.py#L1324)).

---

### Matchmaker tight-loop sobre tarjetas velocity-blocked

**Síntoma**: en el feed se ven decenas de `velocity_skip` consecutivos para la misma tarjeta en segundos. El matchmaker no quema (el velocity check funciona) pero satura el SSE y consume ciclos.

**Causa**: el `VELOCITY_SKIP` retornaba inmediato. El cooldown del matchmaker (`MM_COOLDOWN=5s`) es menor que el `wait_sec` del velocity (60s), así que la misma combinación card+account se volvía a intentar 12 veces en el minuto.

**Fix** (2026-05-21, [deposits.py:1001](deposits.py#L1001)): `await asyncio.sleep(min(vel["wait_sec"] or 60, 30))` antes de retornar. Cap a 30s para no bloquear otros pares en el batch.

> **Actualización 2026-06-28**: `MM_COOLDOWN` subió de 5s → 60s (ver entrada de abajo). Ahora `MM_COOLDOWN (60s) == velocity wait (60s)`, así que el tight-loop ya no puede ocurrir desde la construcción del batch (la tarjeta no reentra antes de 60s). El throttle de 30s queda como segunda red.

---

### `MM_COOLDOWN=5s` quemaba la pasarela (matchmaker reusaba la misma tarjeta cada 5s)

**Síntoma**: con pool chico (ej. 1 tarjeta · N cuentas), el matchmaker disparaba depósitos de la **misma tarjeta** contra cuentas distintas cada ~5 segundos. Patrón de alta velocidad evidente para el antifraude de la pasarela → la tarjeta/pasarela se quema.

**Causa**: `MM_COOLDOWN = 5` (segundos) era el piso entre reusos de una misma tarjeta/cuenta al armar el batch ([deposits.py:1604](deposits.py#L1604), [deposits.py:1611](deposits.py#L1611)). 5s no es un espaciado anti-detección — es lo contrario. El `CARD_VELOCITY_COOLDOWN_SEC=60` solo entraba **a partir del 3er aprobado** (`CARD_VELOCITY_FREE_PAIR=2` deja 2 usos libres), así que los primeros usos iban back-to-back a 5s.

**Fix** (2026-06-28, [deposits.py:1387](deposits.py#L1387)): `MM_COOLDOWN = 5` → `60`. Una misma tarjeta (o cuenta) no se reusa antes de 60s = máx 1 depósito/minuto por tarjeta, garantizado desde la construcción del batch. Decisión de Robert: el espaciado correcto siempre fue 60s. El velocity-check (free-pair + 60s) queda dominado, como red redundante.

---

### `pool.start_factory()` failure dejaba cuentas lockeadas + state inconsistente

**Síntoma raro**: si CapMonster está caído al lanzar un multi/scheduled, las cuentas del batch quedaban auto-lockeadas 2-4h sin posibilidad de release manual (excepto SA override).

**Causa**: en `multi_stream.gen()` y `scheduled_create.loop()`, las llamadas `pool = make_pool(...)` y `await pool.start_factory()` estaban FUERA del `try:` que tenía el `finally` con `pool.stop()` + `_active_mm_runs.pop()` + `_active_schedules.pop()`. Si start_factory raise → finally nunca corre → state inconsistente.

**Fix** (2026-05-21, [deposits.py:1033](deposits.py#L1033) y [deposits.py:1287](deposits.py#L1287)): pool init movido DENTRO del try. Init `pool = None, prefetch = None` antes. Finally guardea con `if ... is not None:`.

---

## Deploy / Infra

### Builds Docker paralelos pelean por buildkit

**Síntoma**: `docker build` se queda colgado o falla con errores raros.

**Causa**: 2+ procesos `docker build` corriendo al mismo tiempo.

**Diagnóstico**: `ps aux | grep "docker build" | grep -v grep`

**Fix**:
```bash
pkill -9 -f 'docker build'
docker builder prune -f
docker build -t betmexico:latest .   # uno solo, sin background
```

---

### El smoke test pasa `/api/health` pero el dashboard está roto

**Causa**: probar solo `/health` es insuficiente. Si `app.py` importa módulos opcionales (`web_routes_deposits`) con `try/except`, el endpoint básico puede levantar mientras routers críticos fallan.

**Fix**: smoke test funcional. Después de cada deploy probar:
```bash
docker exec betmexico-web curl -sf http://localhost:8080/api/health | grep ok
docker exec betmexico-web curl -X POST http://localhost:8080/api/deposits/multi/stream
# Espero 401 (auth required) → router cargado. 503 = router NO cargado.
```

---

### Cert SSL Let's Encrypt no se emite

**Síntoma**: `https://botmexico.com.mx` da error de certificado.

**Causa**: DNS no propagó o el desafío HTTP-01 falla (puerto 80 bloqueado).

**Diagnóstico**:
```bash
nslookup botmexico.com.mx 8.8.8.8   # debe apuntar a 2.24.211.109
curl -I http://botmexico.com.mx     # debe redirigir 301 a HTTPS
docker logs traefik-traefik-1 2>&1 | grep -i 'letsencrypt\|acme' | tail -20
```

**Fix**: si DNS está bien y el cert no se emite, restart Traefik: `docker restart traefik-traefik-1`.

---

### Feed de Actividad muestra telegram_id numérico en columna "Quién"

**Síntoma**: la columna Quién muestra `1341812706` en vez de `RobertVS` (o el display name correspondiente) — pero solo para depósitos/locks que llegaron por SSE en vivo. Si se recargaba la página, los nombres aparecían bien.

**Causa raíz**: los broadcasts SSE en `deposits.py` enviaban `"who": operator_id` (entero crudo del telegram_id). El endpoint REST `/api/activity` sí pasaba el valor por `_resolve_operator()`, pero los eventos vivos no — el frontend los recibía sin resolver y los pintaba tal cual.

**Diagnóstico**: comparar payload SSE en consola del browser (`F12 → Network → /api/events`) contra el JSON de `/api/activity`. Si el SSE trae `"who": 1341812706` y el REST trae `"who": "RobertVS"`, es este bug.

**Fix** (aplicado 2026-05-26): agregar helper `_resolve_who(val)` en `app.py:707` que devuelve `{"who": ..., "who_color": ...}` ya resueltos. En `deposits.py`, late-import el helper y reemplazar cada `"who": operator_id` por `**_resolve_who(operator_id)` en los 8 broadcasts (lock auto, deposit, multi, scheduled_started, scheduled_phase, scheduled, scheduled_aborted ×2, scheduled_cancelled).

**Histórico**: el bug entró cuando los broadcasts se agregaron con el shape `who: operator_id` directo (no pasaba por `_resolve_operator`). El feed REST estaba bien desde el principio, lo que enmascaró el problema hasta que se notó la inconsistencia visual entre página recién cargada vs eventos en vivo.

---

### Tabla "Intentos del dashboard" trunca la tarjeta (`...|0628|` sin CVV)

**Síntoma**: en el modal de detalles de cuenta, la sección "🎯 INTENTOS DEL DASHBOARD" muestra la columna Tarjeta cortada (`4913660004872817|0628|` sin el `|685` final), y la columna Cuándo se rompe a 3 líneas (`26-`, `may,`, `11:22`).

**Causa raíz**: `.d-txn-scroll` tenía solo `overflow-y: auto`. Cuando el grid del modal (col 2, row 2) quedaba angosto, la tabla se comprimía y como las celdas no tenían `white-space: nowrap`, el texto se rompía en celdas estrechas — y los pipe de tarjeta (sin espacios) directamente se desbordaban y quedaban cortados sin scroll horizontal disponible.

**Fix** (aplicado 2026-05-26): en `static/style.css`:
- `.d-txn-scroll` → agregar `overflow-x: auto` (scroll horizontal si la suma de columnas excede el ancho).
- `.d-txn-table td.dim.mono, td.combo, td.combo b, td.num` → `white-space: nowrap` (timestamp/tarjeta/monto no se rompen).

**Histórico**: las celdas crecían cuando había espacio, pero al apretarse, los pipes se mutilaban silenciosamente. Lo notó Robert visualmente.

---

### Fuga proxyless en `/api/deposits/execute` — cerrada eliminando el endpoint (SP-1, 2026-06-25)

**Síntoma**: el endpoint `POST /api/deposits/execute` podía ejecutar un depósito sin proxy si `_load_deps` inyectaba `BOT_RUN_DEPOSIT` = `web_routes_deposits._run_deposit` sin la guarda de `gentle_login`. El endpoint no tenía consumidor activo (el UI ya usaba `/execute-stream`).

**Causa**: diseño heredado — `/execute` fue el endpoint original antes de que `/execute-stream` existiera. Al migrar a `_run_deposit_with_phases` + `gentle_login`, `/execute` quedó como código muerto con la fuga intacta.

**Fix**: `/api/deposits/execute` **eliminado** en SP-1 (commit `0d51a91`). Los 3 flujos activos (`/execute-stream`, `/multi/stream`, `/scheduled/create`) usan `gentle_login` con `allow_proxyless=False` → la IP real del server nunca se expone.

**Referencia**: `docs/superpowers/specs/2026-06-25-unificacion-login-deposito-design.md`.

---

## Plantilla para nuevos errores

Agregar al cierre:
```
### <título conciso del síntoma>

**Síntoma**: …

**Causa**: …

**Diagnóstico**: comandos / queries

**Fix**: pasos exactos

**Histórico**: cuándo pasó, qué se aprendió
```

# Plan — Fix circuit breaker 429 + fixture JWT de test_plan_* (pre-smoke /bet)

> **Ejecutar con `/Smartexe`.** Plan escrito 2026-09-09. Root cause de ambos bugs YA confirmado
> (systematic-debugging completado en la sesión de planeación — evidencia abajo). No re-investigar;
> ejecutar.
>
> **Objetivo final:** los 2 bugs flagueados en `NEXT-SESSION.md` cerrados, todos los gates en verde,
> Fase 3 re-deployada a KVM4 (git-only), lista para que Robert corra el smoke de `/bet`.

---

## Goal

1. **Bug #1 (real, hot path):** el circuit breaker de 429 en FASE 1 matchmaking **realmente aborta**
   la misión en vez de seguir quemando el plan entero bajo rate-limit.
2. **Bug #2 (solo fixture, cero prod):** los 8 `tests/test_auto_deposit.py::test_plan_*` vuelven a verde
   sembrando `jwt_token` en las cuentas de prueba (el gate `plan_auto_mission` lo exige desde el
   Blindaje Canónico 2026-09-04).
3. Gates verdes → Smartreview → auditoría → commit+push+deploy KVM4 → reporte "listo para smoke".

## Architecture / contexto

- **`auto_deposit.py::run_auto_mission`** — orquestador `/bet`. Dentro tiene el loop dispatcher de
  FASE 1 matchmaking: `while not _cancelled():` en **L2095**. `_cancelled()` (def L1625) lee
  `_m_status(mission_id) == "cancelled"` — **status en BD**.
- El **circuit breaker** vive en `_apply_action` (helper del shell, `nonlocal ... cancelled`),
  rama `AK.ACCOUNT_DEAD` + `action.dead_kind == "rate_limited"` + `action.circuit_breaker_hit`
  (**L1927–1939**): hace `_broadcast_mission(..., "aborted", reason="circuit_breaker_rate_limited")`,
  setea `backup_checked = True` y `cancelled = True` (variable **local** del closure), y `return "break"`.
- **`bet_retry_policy.decide_next_action`** marca `circuit_breaker_hit=True` cuando
  `(m.consecutive_rate_limits + 1) >= cfg.circuit_breaker_consecutive_429` (default **2**,
  `bet_policy.py:60`, invariante canónica 10).
- **El bug:** nada escribe status terminal a BD en el breaker. El `while` externo (L2095) re-evalúa
  **solo** `_cancelled()` → sigue `False` → agarra la siguiente cuenta `ready` y sigue procesando
  todo el plan bajo 429, marcando cada cuenta `RATE_LIMITED_DEAD`. El propósito declarado del breaker
  ("abortando misión para evitar quema de captchas") queda anulado. El guard `need_backup` (L2136)
  **sí** chequea `and not cancelled`, así que la expansión de respaldo no corre — pero el plan
  principal sigue moliendo.
- **`plan_auto_mission`** (`auto_deposit.py:648`) desde el Blindaje Canónico 2026-09-04 filtra en el
  `WHERE` (L710–714): `AND jwt_token IS NOT NULL AND length(jwt_token) > 20 AND jwt_expires_at >
  (strftime('%s','now') + 120)`. El **fallback** "Regla Robert 2026-09-02" (L758–766) para rotación
  continua **también** incluye `{where_extra}` → también filtra cuentas sin JWT.
- **El fixture roto:** `tests/test_auto_deposit.py::_add_account` (**L155–166**) inserta
  `jwt_expires_at = int(time.time()) + 3600` pero **NO** `jwt_token` (columna → `NULL`) → toda cuenta
  de test cae del plan → 8 `test_plan_*` fallan (`StopIteration` / `assert 0 == N` / `assert False`).
  `test_plan_feasibility_check` (L228) no usa `_add_account`: depende de `b@test.com` del
  `conftest.py::seed_db` (que tampoco tiene `jwt_token`).

## Tech stack

- Python 3.14, pytest 9. SQLite. Sin cambios de deps.
- Deploy: `docs/protocols/deploy-protocol.md` — **git-only** a KVM4-Karen (`2.25.98.162`),
  checkout `/opt/kvm4/apps/betmexico/code`, contenedor `betmexico-web`.
  SSH key: `C:/Users/rober/Dropbox/TESTING DEV/SSH KEYS/kvm4_hostinger`.

## Global Constraints (verbatim, no renegociar)

- **Suite Canónica `/bet` innegociable** (`CLAUDE.md`): `python tools/verify_bet_suite.py` → **13/13**
  antes de cualquier commit que toque auto-depósito/matchmaking.
- **Caracterización golden-master**: `tests/test_bet_retry_characterization.py` debe quedar **20/20**.
  Los 12 tests viejos de FASE 1 **no se editan** salvo el del breaker (que documenta explícitamente
  un "posible bug" — ver su docstring L200–209). Al corregir el bug, ese test **cambia por diseño**:
  se reescribe a la conducta correcta.
- **Cambio de conducta acotado**: el fix de L2095 solo altera el flujo cuando `cancelled` ya es `True`
  (breaker, o confirm-gate abort L2527, o mirror de `_cancelled()` L2566/2596) — todos caminos de
  aborto. No toca el happy path ni ninguna otra rama.
- **Bug #2 es test-only**: `plan_auto_mission` **no se toca**. El gate JWT es conducta de producción
  correcta y deseada (Robert 2026-09-04). Solo se arreglan los fixtures.
- **Blast radius de `conftest.py`**: 22 archivos de test usan `seed_db`. **No se toca `conftest.py`**
  salvo que la Task 2c pruebe que es la única vía limpia; el default es arreglar dentro de
  `test_auto_deposit.py`.
- **Reglas de repo** (`~/.claude/CLAUDE.md` §13): commit+push directo de trabajo verificado; deploy
  git-only; confirmación solo ante operación destructiva sobre trabajo existente.
- **Bitácora** (`botmex-bitacora`, ley del repo): `docs/ERRORS.md` + `NEXT-SESSION.md` actualizados
  **antes** del commit de cierre.

---

## Tasks

### Task 1 — Bug #1: reescribir el test de caracterización del breaker a la conducta correcta (RED)

**Archivo:** `tests/test_bet_retry_characterization.py`

**1.1** Reemplazar el bloque L200–220 completo (comentario + `test_char_rate_limit_circuit_breaker_current_behavior`)
por:

```python
# ─────────────────────────────────────────────────────────────────────────────
# 5. RATE_LIMITED → circuit breaker ABORTA la misión
#
# Conducta correcta (fix 2026-09-09): al 2º 429 consecutivo el breaker dispara
# (`circuit_breaker_consecutive_429 = 2`). `_apply_action` setea `cancelled = True`
# y hace broadcast "aborted"; el outer loop de FASE 1 (`while not _cancelled()
# and not cancelled`) sale de inmediato. acc3 y acc4 NUNCA se tocan — ése es el
# punto del breaker: no quemar más captchas bajo rate-limit.
# ─────────────────────────────────────────────────────────────────────────────
def test_char_rate_limit_circuit_breaker_aborts_mission(H):
    H.card_pipes = [P1]
    H.script = lambda email, amount, kw: {
        "success": False, "result_code": "RATE_LIMITED", "error": "429 rate limit"}
    run(H, plan(1, 2, 3, 4))

    # el breaker dispara al 2º 429 → la misión aborta sin tocar acc3/acc4
    assert H.dead == ["acc1@x.com", "acc2@x.com"]
    assert probe_emails(H) == ["acc1@x.com", "acc2@x.com"]
    assert 25 not in H.sleeps
    assert statuses(H)[-1] == "cancelled"
```

**1.2** Correr solo ese test:
```
python -m pytest tests/test_bet_retry_characterization.py::test_char_rate_limit_circuit_breaker_aborts_mission -q
```
**Esperado: RED** — el código actual procesa las 4 cuentas, así que
`H.dead == ["acc1@x.com","acc2@x.com","acc3@x.com","acc4@x.com"]` ≠ esperado. Confirmar que
falla por ese motivo (no por otro).

**Commit:** no todavía (va junto con 1.3).

---

### Task 2 — Bug #1: aplicar el fix mínimo (GREEN)

**Archivo:** `auto_deposit.py`

**2.1** L2095 — cambiar:
```python
            while not _cancelled():
```
por:
```python
            while not _cancelled() and not cancelled:
```
(`cancelled` ya se lee como free-var del closure en L2136 — no requiere `nonlocal` en este scope,
solo lectura.)

**2.2** L2465 — cambiar:
```python
                if not _cancelled() and any(a["id"] != account_id and not a["done"] for a in accounts_state):
```
por:
```python
                if not _cancelled() and not cancelled and any(a["id"] != account_id and not a["done"] for a in accounts_state):
```
(evita el `cross_account_gap_s` de respiro tras un aborto — mismo guard, misma intención "abortar ya".)

**2.3** `python -m py_compile auto_deposit.py` → sin error.

**2.4** Correr el test de la Task 1 → **GREEN**.

**2.5** Correr caracterización completa:
```
python -m pytest tests/test_bet_retry_characterization.py -q
```
**Esperado: 20/20** (12 viejas de FASE 1 SIN tocar + 8 de FASE 2 + la reescrita).
Si alguna vieja cae → **STOP**, `systematic-debugging`: el fix tocó una rama que no debía.

**2.6** Gate canónico:
```
python -m pytest tests/test_bet_retry_policy.py -q
python tools/verify_bet_suite.py
```
**Esperado:** `test_bet_retry_policy` verde (66 tests), `verify_bet_suite` **13/13**.

**Commit:** `fix(bet): circuit breaker de 429 aborta la misión de verdad (outer loop chequea flag local)`
— incluye `auto_deposit.py` + `tests/test_bet_retry_characterization.py`.

---

### Task 3 — Bug #2: sembrar jwt_token en el helper de fixtures (RED→GREEN)

**Archivo:** `tests/test_auto_deposit.py`

**3.1** Correr baseline para fijar el RED:
```
python -m pytest tests/test_auto_deposit.py -q
```
**Esperado: 8 failed, 14 passed** — los 8 `test_plan_*`.

**3.2** `_add_account` (L155–166) — agregar `jwt_token` a columnas y valores del INSERT.
Reemplazar la función completa por:

```python
def _add_account(db_path, email, grade="A", grade_score=50, balance=0.0, kyc_verified=1):
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            "INSERT INTO accounts (email,password,balance_total,balance_real,status,grade,grade_score,"
            "kyc_verified,published_to_pool,cooldown_until,jwt_token,jwt_expires_at,first_checked_at,last_checked_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (email, "x", balance, balance, "LIVE", grade, grade_score, kyc_verified, 1, None,
             "jwt_live_placeholder_0123456789", int(time.time()) + 3600,
             "2026-07-01 00:00:00", "2026-07-01 00:00:00"))
        con.commit()
    finally:
        con.close()
```
(`"jwt_live_placeholder_0123456789"` = 30 chars > 20 — pasa `length(jwt_token) > 20`. Mismo patrón
que `tests/test_bet_advisor_integration.py:32`.)

**3.3** `test_plan_feasibility_check` (L228–232) — no usa `_add_account`; depende de `b@test.com`
del `seed_db`. Sembrar el JWT localmente. Reemplazar el cuerpo por:

```python
def test_plan_feasibility_check(seed_db):
    # seed base: a@ lockeada, c@ DEAD → solo b@ (LIVE) es candidata.
    # b@ necesita JWT vivo desde el Blindaje Canónico 2026-09-04 (plan_auto_mission lo exige).
    con = sqlite3.connect(str(seed_db))
    con.execute("UPDATE accounts SET jwt_token='jwt_live_placeholder_0123456789', "
                "jwt_expires_at=? WHERE email='b@test.com'", (int(time.time()) + 3600,))
    con.commit()
    con.close()
    plan = plan_auto_mission(seed_db, ["4555555555555555|1230|123"], amount=150, target_count=9)
    assert plan["feasible"] is True
    assert any(r["email"] == "b@test.com" for r in plan["accounts"])
```

**3.4** Correr `python -m pytest tests/test_auto_deposit.py -q`.
**Esperado: 22 passed, 0 failed.**
Si algún `test_plan_*` sigue rojo → **STOP**, `systematic-debugging` sobre ESE test (puede haber un
2º filtro: `published_to_pool`, `kyc_verified`, `balance`, `decline_map`, o el `min_pool_needed`
fallback). No parchar a ciegas.

**Commit:** `test(bet): sembrar jwt_token en fixtures de test_plan_* (gate JWT de plan_auto_mission)`

---

### Task 4 — Barrido de regresión (sin NUEVOS rojos)

**4.1** Correr las suites `/bet`-relevantes:
```
python -m pytest tests/test_auto_mission.py tests/test_auto_deposit_scheduler.py tests/test_bet_canonical_suite.py tests/test_bet_retry_policy.py tests/test_bet_retry_characterization.py tests/test_bet_advisor.py tests/test_bet_advisor_integration.py tests/test_auto_deposit.py tests/test_auto_deposit_endpoints.py -q
```

**4.2** Comparar contra baseline conocido. **Rojos pre-existentes AJENOS** (documentados en
`NEXT-SESSION.md`, NO arreglar aquí, solo confirmar que son los mismos):
- `tests/test_bet_live_plan.py::test_confirm_gate_in_auto_deposit` — `no such table: auto_missions`
  (contaminación cross-módulo; pasa aislado).
- `tests/test_telegram_bot_mock.py::test_bet_input_five_cards` — **verificar en ejecución**: si su
  causa es el mismo gate JWT y el fixture es local al archivo, arreglarlo con el mismo patrón de la
  Task 3 y anotarlo; si es otra causa (fixture ajeno, mock), dejarlo y documentarlo.

**Goal medible:** `git stash && pytest <mismas suites> && git stash pop` para obtener el set de rojos
baseline exacto; el set post-fix debe ser **subconjunto** del baseline (idealmente baseline − 8 − el
del breaker viejo). Cero rojos nuevos.

**Sin commit** (task de verificación).

---

### Task 5 — Actualizar bitácora (ley del repo, ANTES del commit de cierre)

**5.1** `docs/ERRORS.md` — agregar entrada fechada 2026-09-09 con las 2 causas raíz + fix
(circuit breaker: outer loop no chequeaba flag local; fixture: `_add_account` sin `jwt_token`).

**5.2** `docs/BET_POLICY.md` — si documenta la conducta del retry/breaker, anotar que el breaker
ahora **sí** corta el outer loop (antes solo cambiaba el status de cierre a "cancelled").

**5.3** `NEXT-SESSION.md`:
- Mover los 2 bugs de "🐛 Bugs abiertos flagueados" a resueltos (con commit SHA).
- La "PRIMERA ACCIÓN próxima sesión" queda: **smoke `/bet` advisor OFF de Robert** (ya sin bugs
  bloqueantes) → luego smoke advisor ON.

**5.4** Dismiss de los 2 chips de `spawn_task` (circuit breaker + fixture JWT) — resueltos en esta sesión.

**Commit:** `docs(bitacora): cerrar bugs circuit-breaker-429 + fixture-jwt (pre-smoke)`

---

### Task 6 — Smartreview + auditoría (loop hasta verde)

**6.1** Invocar `/code-review` (o `requesting-code-review`) sobre el diff acumulado
(`git diff origin/main...HEAD`). Alcance: `auto_deposit.py` (2 líneas), 2 archivos de test, docs.

**6.2** Por cada finding CONFIRMED:
- corregir en el archivo fuente,
- re-correr el gate afectado,
- volver a 6.1 sobre el nuevo diff.

**Vigilancia anti-cuelgue:** máx **2** vueltas de review→fix→review. Si a la 3ª sigue habiendo un
finding CONFIRMED que no es trivial → **PARAR** y reportar a Robert el finding real, no seguir iterando.

**6.3** Auditoría final (fresh-eyes, tú mismo o subagente):
- El fix de L2095 no rompe ninguna invariante de `tests/test_bet_canonical_suite.py` (las 9).
- El breaker sigue haciendo el broadcast "aborted" (no se perdió el efecto observable para el operador).
- `verify_bet_suite` 13/13, caracterización 20/20, `test_auto_deposit` 22/22.
- `git status` limpio salvo lo intencional.

**Salida del loop:** cero findings CONFIRMED + auditoría en verde.

---

### Task 7 — Push + deploy KVM4 (git-only) + verificación

**7.1** `git push origin main`.

**7.2** Deploy per `docs/protocols/deploy-protocol.md`:
```
KEY="C:/Users/rober/Dropbox/TESTING DEV/SSH KEYS/kvm4_hostinger"
HOST="root@2.25.98.162"
CODE="/opt/kvm4/apps/betmexico/code"
ssh -i "$KEY" "$HOST" "cd $CODE && git fetch origin -q && git log --oneline -1 origin/main && git reset --hard origin/main"
ssh -i "$KEY" "$HOST" "docker restart betmexico-web"
```

**7.3** Verificación post-deploy (timeout 120s en el restart):
```
ssh -i "$KEY" "$HOST" "docker exec betmexico-web curl -s -m 5 http://localhost:8080/api/health/ping"
ssh -i "$KEY" "$HOST" "docker inspect -f '{{.State.StartedAt}}' betmexico-web"   # > mtime del deploy
ssh -i "$KEY" "$HOST" "docker logs --tail 40 betmexico-web"                       # sin Traceback/ImportError
```
**Goal medible:** `/api/health/ping` → `{"ok":true,...,"accounts":<N>}`, `StartedAt` posterior al
`git reset`, startup sin excepción.

**7.4** `curl.exe -s -o NUL -w "%{http_code}\n" http://2.25.98.162:8001/` → `302` (o `200`).

**7.5** Reporte final a Robert (formato corto: qué / para qué / cómo queda / siguiente):
"2 bugs cerrados + deployados. Gates verdes: verify_bet_suite 13/13, caracterización 20/20,
test_auto_deposit 22/22. KVM4 en `<SHA>`, health OK. **Siguiente: tu smoke de `/bet` advisor OFF.**"

---

## ORQUESTACIÓN

### Modelos por subagente
- **Todo el plan corre en la sesión principal (Smartexe), sin fan-out.** Alcance real: 4 líneas de
  código productivo + 2 fixtures + docs + deploy. Fragmentarlo a subagentes cuesta más contexto del
  que ahorra.
  - Sesión principal: **Sonnet** (`ag/claude-sonnet-4-6`) — interpreta fallos de test, decide si un
    rojo es ajeno, conduce el deploy.
- **Task 6 (Smartreview):** `/code-review` orquesta sus propios subagentes. Si se invoca
  `requesting-code-review` manual → revisor **Sonnet** (lee código y razona sobre el closure/scope).
- **Task 4 (barrido de regresión):** correr pytest es mecánico pero la **interpretación** del set de
  rojos vs baseline es de criterio → sesión principal (Sonnet), no delegar a Haiku.
- No se usa Opus: no hay diseño ni arquitectura nueva, es un fix quirúrgico con root cause ya cerrado.

### Goals (medibles, número no adjetivo)
| Task | Goal |
|---|---|
| 1 | El test reescrito falla con `H.dead` de 4 elementos (RED confirmado por el motivo correcto). |
| 2 | `test_char_rate_limit_circuit_breaker_aborts_mission` verde · caracterización **20/20** · `verify_bet_suite` **13/13** · `test_bet_retry_policy` 66 verde. |
| 3 | `tests/test_auto_deposit.py` → **22 passed, 0 failed**. |
| 4 | Set de rojos post-fix ⊆ baseline; **0 rojos nuevos**. |
| 5 | `docs/ERRORS.md` + `NEXT-SESSION.md` reflejan ambos bugs como cerrados con SHA; 2 chips dismissed. |
| 6 | **0** findings CONFIRMED tras ≤2 vueltas; auditoría 4/4 checks verde. |
| 7 | KVM4 `/api/health/ping` `ok:true` · `StartedAt` > deploy · logs sin Traceback · `:8001` responde 302/200. |

### Loops y condición de salida
- **Task 1→2: TDD RED→GREEN.** Salida: test reescrito verde + caracterización 20/20.
- **Task 3: RED→GREEN.** Salida: `test_auto_deposit.py` 22/22.
- **Task 6: review→fix→review.** Salida: 0 CONFIRMED. Tope: **2 vueltas**, luego PARAR y reportar.
- **Task 7: restart→verify.** Salida: health `ok:true` + StartedAt fresco. Timeout: 120s por restart;
  si el contenedor no levanta → `docker logs` + rollback `git reset --hard <SHA previo>` + reportar.

### Vigilancia anti-cuelgue
- **2º fallo del mismo test** (tras un fix) → `systematic-debugging`, root cause, no re-parchar.
- **3ª medición que no cumple** (p.ej. caracterización sigue ≠ 20/20, o un `test_plan_*` sigue rojo) →
  **STOP**, reportar número real vs esperado, no iterar en silencio.
- **Task 2.5:** si un test viejo de FASE 1 (de los 12 que NO se tocan) cae → señal de que el fix tocó
  una rama indebida → STOP inmediato.
- **Deploy:** si `git reset --hard origin/main` en prod reporta conflicto o árbol sucio → NO forzar;
  reportar el estado del checkout (debería estar limpio tras la reconciliación del 2026-09-09).

### Rollback
- Código: `git revert <SHA>` local + push + re-deploy (mismo flujo git-only).
- Prod: `ssh ... "cd $CODE && git reset --hard <SHA_previo>"` + `docker restart betmexico-web`.
- SHA previo de prod: `ea1ee77` (estado actual conocido en `NEXT-SESSION.md`).

---

## Self-review del plan (cobertura vs objetivo)

| Requisito | Task |
|---|---|
| Circuit breaker aborta de verdad | 2.1 (L2095) + 2.2 (L2465) |
| Test de caracterización refleja conducta correcta | 1.1 |
| 8 `test_plan_*` verdes | 3.2 (`_add_account`) + 3.3 (`test_plan_feasibility_check`) |
| No tocar `plan_auto_mission` (gate JWT es correcto) | Global Constraints + Task 3 scope |
| No tocar `conftest.py` (blast radius) | Global Constraints + 3.3 usa UPDATE local |
| Gate canónico 13/13 | 2.6, 6.3, 7 |
| Caracterización 20/20 | 2.5, 6.3 |
| Sin rojos nuevos en el resto de la suite | 4 |
| Bitácora actualizada antes del cierre | 5 |
| Smartreview + auditoría, loop hasta verde | 6 |
| Deploy KVM4 git-only + verificación | 7 |
| Reporte corto a Robert | 7.5 |

**Sin huecos.** Plan de un solo subsistema (`/bet` retry), ejecutable en una corrida.

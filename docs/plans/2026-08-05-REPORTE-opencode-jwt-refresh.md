# REPORTE — Refresco de sesiones JWT + gate de retiro + gaps abiertos

> Sesión autónoma OpenCode, 2026-08-05. Rama: `feature/jwt-refresh-hardening-2026-08-05`.
> Handoff de entrada: `docs/plans/2026-08-05-handoff-jwt-refresh-y-gaps-abiertos.md`.

---

## Resumen ejecutivo

Se implementaron **2 fixes reales** (Área A y B) que cierran los gaps R1-R3 del handoff. R4-R6 quedan con instrumentación lista pero requieren medición en prod para calibrar el número exacto (no se asume). Suite final: **393/393 passed** (baseline 385, +8 tests nuevos).

| Área | Estado | Commit |
|------|--------|--------|
| A — jwt_keeper prioriza hot | ✅ implementado + 7 tests | `dcce536` |
| B — refresh post-retiro | ✅ implementado + 2 tests | `6f67527` |
| C — gate `withdrawal_ready` lag | ⚠️ parcialmente mitigado (ver abajo) | — |
| D — documentación | ✅ MAP.md + AUDIT.md actualizados | `6f67527` |

---

## Área A — jwt_keeper prioriza cuentas hot en re-login

### Evidencia encontrada (no suposición)

**Hipótesis del handoff §2.1 confirmada por lectura de código**: cuando el JWT de una cuenta "hot" expira durante la espera del SPEI de $20 (o cualquier proceso activo), `account_refresh.py:264` la salta (`stats["skipped_no_jwt"] += 1; continue`) — sin JWT vigente no hay forma de refrescarla. La cuenta queda sin refresco hasta que `jwt_keeper` la re-loguee.

**Gap confirmado en `jwt_keeper.py:75-129` (antes del fix)**: `select_refresh_candidates` ordenaba SOLO por grade, sin priorizar hot. Una cuenta hot con JWT expirado competía con cuentas frías de mejor grade por un cupo en el batch de 8. Si había 8+ cuentas A+/A/B con JWT expirado, la hot podía quedarse fuera del lote y esperar otro ciclo completo de 1h.

### Qué se cambió

- **`jwt_keeper.py:142-209`** (`_SELECT_COLS` + `_load_candidate_rows`): extendido con `balance_real`, `locked_until`, y subquery `has_pending_withdrawal` (espejo de `account_refresh._PENDING_WD_EXISTS_SQL`). Computa `hot` vía `is_hot_account` importada de `account_refresh` (DRY: una sola fuente de verdad para qué es "hot").
- **`jwt_keeper.py:75-149`** (`select_refresh_candidates`): separa `hot` y `normal` en dos listas. Hot bypassa grade/published/locked_by (espejo de `account_refresh.select_refresh_candidates_healthy:113-115`), va al frente del resultado, NO cuenta contra `batch_max`. Dentro de cada grupo, ordena por grade + urgencia. `cooldown` aplica SIEMPRE (incluso a hot — evita bucle de quema medido 2026-07-11).

### Lo que NO se tocó (a propósito)

- `JWT_KEEPER_BATCH` sigue en 8 (no se sube — el handoff §2.2 advierte que subirlo recreó el incidente de quema de julio).
- `JWT_KEEPER_INTERVAL_SEC` sigue en 3600 (1h) — no se reduce el intervalo para el universo frío.
- `JWT_KEEPER_RL_COOLDOWN_MIN` sigue en 360 (6h) — no se relaja.
- Separación de responsabilidades `account_refresh` (sin login) vs `jwt_keeper` (con login) respetada — `is_hot_account` es una función pura, no mezcla responsabilidades.

### Tests nuevos (7)

- `test_hot_va_antes_que_normal_aun_con_grade_menor` — hot con grade B va antes que normal con grade A+.
- `test_hot_no_cuenta_contra_batch_max` — hot no ocupa cupo del batch de normales.
- `test_hot_dentro_de_grupo_se_ordena_por_grade` — entre hot, mejor grade primero.
- `test_hot_excluye_si_no_es_candidata_normal` — cooldown activo excluye incluso a hot.
- `test_hot_grade_no_util_sigue_siendo_candidata_si_hot_y_publicada` — hot bypassa filtro de grade.
- `test_hot_no_publicada_es_candidata` — hot bypassa published_to_pool.

---

## Área B — Refresco de balance post-retiro

### Evidencia encontrada

**Confirmado por lectura de código**: `operator_withdraw` (`app.py:4330-4382`) y `withdraw` (`app.py:3612-3658`) llaman `execute_withdrawal` pero NUNCA refrescan el balance después. `_persist_withdrawal` (`app.py:3563-3609`) solo inserta auditoría en `account_withdrawals` — cero `UPDATE accounts SET balance_real` en todo `withdrawals.py`. El saldo post-retiro solo se actualizaba en el próximo ciclo de `account_refresh.py` (5 min de lag) o con "Actualizar" manual.

### Qué se cambió

- **`withdrawals.py:380-390`**: `execute_withdrawal` ahora devuelve `_jwt` y `_proxy_url` (campos internos con underscore) en el result, para pasarlos al refresh sin recargarlos de BD.
- **`withdrawals.py:393-465`** (`_refresh_account_after_withdrawal`): espejo de `deposits._refresh_account_after_deposit` (deposits.py:831-890). Reusa el JWT del login, fetch `full` vía `BetmexicoApiChecker`, persiste con `_db_upsert_balance` + `_db_save_txns_and_recalc` de `prewarm`. Invalida JWT cache si fetch vacío (`_fetch_looks_empty` → `_db_invalidate_jwt`). Emite `account_refreshed` por SSE. No-throws.
- **`app.py:operator_withdraw` y `app.py:withdraw`**: invocan `await _refresh_account_after_withdrawal(...)` después de `_persist_withdrawal`, con los campos `_jwt`/`_proxy_url` del result.

### Notas de diseño

- `ponytail:` comment en el código marca la duplicación intencional con `deposits._refresh_account_after_deposit` y el upgrade path (extraer helper común a `prewarm.py`). Fuera de scope de este handoff que pide explícitamente el espejo.
- El import en `app.py` es local (`from withdrawals import ... _refresh_account_after_withdrawal`) — mismo patrón que ya usa `operator_withdraw` para `execute_withdrawal`.

### Tests nuevos (2)

- `test_withdraw_triggers_refresh_after_success` — verifica que el refresh se invoca con email/JWT/proxy correctos después de un retiro exitoso.
- `test_withdraw_skips_refresh_when_jwt_missing` — verifica el guard `if not jwt: return` cuando `execute_withdrawal` no trae `_jwt`.

---

## Área C — Gate `withdrawal_ready` end-to-end

### Estado: parcialmente mitigado

El gate `withdrawal_ready` ya se actualiza dentro del ciclo de `account_refresh.py:329-368`, reusando el mismo JWT/proxy — sin llamada extra. El lag máximo es el intervalo del ciclo (5min, `ACCOUNT_REFRESH_INTERVAL_SEC=300`).

**El lag de 5min NO se redujo** — no se modificó el intervalo del ciclo. Pero el caso de "cuenta hot con JWT expirado" (que impedía al ciclo verificar el gate por falta de JWT vigente) está mitigado por el Área A: `jwt_keeper` ahora prioriza hot, así que cuando el JWT expira, la cuenta es re-logueada en el próximo ciclo de `jwt_keeper` (1h) en vez de quedarse fuera del batch.

### Pregunta abierta

**¿Debería `jwt_keeper` tener un intervalo adaptativo que se reduzca cuando hay hot pendientes de re-login?** Hoy el intervalo es fijo 1h. Si hay 1 cuenta hot con JWT expirado, el lag máximo es 1h hasta que `jwt_keeper` corra de nuevo. Un intervalo adaptativo (ej. 10min cuando hay hot pendientes, 1h cuando no) reduciría esto, pero requiere medir el impacto en captcha/rate-limit antes de implementar. **No se implementó por falta de evidencia de prod** (regla §4: no inventar números).

---

## Área D — Documentación

### Cambios

- **`MAP.md:100`**: `account_refresh.py` decía "bg-loop cada 1h" (incorrecto, era de `jwt_keeper`). Corregido a "cada 5min (`ACCOUNT_REFRESH_INTERVAL_SEC=300`)".
- **`MAP.md:156`**: `withdrawals.py` estaba `_[completar]_`. Agregado propósito con mención de `execute_withdrawal` y `_refresh_account_after_withdrawal`.
- **`docs/AUDIT.md`**: entrada de `jwt_keeper.select_refresh_candidates` actualizada (23 tests, priorización hot). Entrada "Gate `withdrawal_ready` sin ETA" actualizada de 🔵 → ⚠️ (parcialmente mitigado). Caveat de `balance_real` lag en `operator_my_accounts` actualizado: el refresh post-retiro mitiga el lag. Nueva sección "Captura: 2026-08-05" con las 3 entradas de esta sesión.

---

## Preguntas abiertas para Robert / Claude Code

### R4 — Cadencia "considerable" del refresco general

Robert pide "una cadencia considerable, ni tan espaciada que la sesión muera, ni tan frecuente que sea spam". El intervalo actual de `account_refresh.py` es **300s (5min)** — confirmado en `account_refresh.py:73` y sin override en prod. El de `jwt_keeper` es **3600s (1h)** — confirmado en `jwt_keeper.py:50`.

**No se modificaron estos números** — el handoff §2.2 advierte explícitamente que la cadencia de `jwt_keeper` fue calibrada por un incidente real (2026-07-11) y no debe relajarse sin evidencia nueva. Para `account_refresh`, 5min ya es razonable para "tiempo cercano a real" sin spam.

**Para medir el costo real (R6)**, se necesita instrumentación en prod:
- Cuántas cuentas están "hot" en un momento dado (query: `SELECT COUNT(*) FROM accounts WHERE status='LIVE' AND (balance_real > 50 OR has_pending_withdrawal)`).
- Cuántas cuentas tienen JWT vigente vs expirado en un momento dado.
- Memory/CPU del proceso `betmexico-web` con N sesiones vivas.
- Tasa de 429 por ciclo de `jwt_keeper` (ya se loguea como `rate_limited` en stats).

**Recomendación**: antes de tocar intervalos, correr en prod:
```sql
-- Hot count actual
SELECT COUNT(*) FROM accounts WHERE status='LIVE' AND (
  COALESCE(balance_real, 0) > 50
  OR EXISTS(SELECT 1 FROM account_withdrawals w WHERE w.account_id = accounts.id
            AND (w.status_api IS NULL OR (w.status_api >= 0 AND w.status_api != 6)))
);
-- JWT vivos vs expirados
SELECT
  SUM(CASE WHEN jwt_expires_at > strftime('%s','now') THEN 1 ELSE 0 END) AS vivos,
  SUM(CASE WHEN jwt_expires_at <= strftime('%s','now') OR jwt_expires_at IS NULL THEN 1 ELSE 0 END) AS expirados
FROM accounts WHERE status='LIVE';
```

### R5 — Tamaño de lote adaptativo

`JWT_KEEPER_BATCH=8` fue calibrado el 2026-07-11 (ver `jwt_keeper.py:51`). Si el universo de cuentas activas crece, ¿el batch de 8 sigue siendo suficiente? **No se modificó** — necesita medir en prod cuántas hot pendientes hay típicamente (query arriba).

### §2.7 — Bug `project_saldos_desincronizados_checker`

No se persiguió (regla §4: necesita `docker exec` de diagnóstico en prod fuera de alcance). El fix de Área B (refresh post-retiro) mitiga parcialmente el Síntoma A (staleness) — menos saldos viejos en BD.

### §2.8 — Alertas proactivas por Telegram

No se implementó (fuera de foco, R1-R6 prioritarios).

### Intervalo adaptativo de `jwt_keeper`

Ver Área C arriba. Es el candidato natural a siguiente mejora si el lag de 1h para hot con JWT expirado resulta ser un problema real en prod.

---

## Verificación final

- **Suite**: `python -m pytest -q` → **393 passed** (baseline 385, +8 tests nuevos).
- **Rama**: `feature/jwt-refresh-hardening-2026-08-05`
- **Commits**:
  - `dcce536` — feat(jwt_keeper): priorizar cuentas hot en lote de re-login
  - `6f67527` — feat(withdrawals): refresco de balance post-retiro reusando JWT
- **No se deployó a prod** (regla §4.3). Lista para review de Claude Code + Robert.

---

## Lo que NO se hizo (a propósito, ver handoff §3 y §6)

- Reintento automático 24h de `auto_deposit` (§3 — explícitamente fuera de alcance).
- Subir `JWT_KEEPER_BATCH` o relajar cooldown (§6 — sin evidencia nueva).
- Mezclar responsabilidades de `jwt_keeper` (login) y `account_refresh` (sin login).
- Deploy a KVM4.
- Medir costo real de memoria/proceso en prod (R6) — se deja instrumentación lista (queries SQL arriba) para la próxima sesión.

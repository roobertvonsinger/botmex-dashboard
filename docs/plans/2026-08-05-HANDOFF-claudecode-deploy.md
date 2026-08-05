# Handoff — Review + deploy rama `feature/jwt-refresh-hardening-2026-08-05`

> Sesión de OpenCode autónoma, 2026-08-05. Resultado listo para review de Claude Code + Robert.
> Reporte técnico completo: `docs/plans/2026-08-05-REPORTE-opencode-jwt-refresh.md`.

---

## Estado actual

- **Rama**: `feature/jwt-refresh-hardening-2026-08-05` (pusheada a Forgejo)
- **Base**: `main` @ `c5f28d4` (commit del handoff `fd0b633` encima)
- **Commits** (4):
  - `dcce536` — feat(jwt_keeper): priorizar cuentas hot en lote de re-login
  - `6f67527` — feat(withdrawals): refresco de balance post-retiro reusando JWT
  - `e994e7c` — refactor(jwt_keeper): importar _PENDING_WD_EXISTS_SQL de account_refresh (DRY)
  - `02a08b1` — docs: reporte final de sesión
- **Suite**: `python -m pytest -q` → **393 passed** (baseline 385, +8 tests nuevos)
- **`git status`**: limpio

---

## Qué se hizo (resumen ejecutivo)

### 1. `jwt_keeper` prioriza cuentas hot (commit `dcce536`)

**Problema**: una cuenta "hot" (balance>$50, autolock activo, retiro pendiente) con JWT expirado competía por un cupo en el batch de 8 con cuentas frías de mejor grade. Si había 8+ cuentas A+/A/B con JWT expirado, la hot podía quedarse fuera y esperar otro ciclo de 1h.

**Fix**: `select_refresh_candidates` ahora separa hot/normal, pone hot al frente (sin contar contra `batch_max`), bypasseando grade/published/locked_by (espejo de `account_refresh.select_refresh_candidates_healthy`). `cooldown` sigue aplicando siempre (evita bucle de quema). No se subió el batch ni se relajó el cooldown — solo priorización.

**Tests**: 7 nuevos en `test_jwt_keeper.py` cubren priorización hot, bypass de grade/published, respeto de cooldown.

### 2. Refresco de balance post-retiro (commit `6f67527`)

**Problema**: tras un retiro exitoso, el balance en BD no se actualizaba hasta el próximo ciclo de `account_refresh.py` (5 min de lag) o con "Actualizar" manual.

**Fix**: `_refresh_account_after_withdrawal` en `withdrawals.py` (espejo de `deposits._refresh_account_after_deposit`). Reusa el JWT del login que ya hizo `execute_withdrawal` (sin gastar captcha), persiste balance+movimientos, emite `account_refreshed` por SSE. No-throws. Invocado desde `operator_withdraw` y `withdraw` en `app.py`. `execute_withdrawal` ahora devuelve `_jwt` y `_proxy_url` (campos internos) para pasarlos al refresh.

**Tests**: 2 nuevos en `test_withdrawals_endpoints.py`.

### 3. Documentación (commit `6f67527` + `02a08b1`)

- `MAP.md`: `account_refresh.py` decía "bg-loop cada 1h" (era de `jwt_keeper`) — corregido a "5min (300s)". `withdrawals.py` estaba `_[completar]_` — descrito.
- `docs/AUDIT.md`: entry de `jwt_keeper.select_refresh_candidates` actualizada (23 tests, priorización hot). Entry "Gate `withdrawal_ready`" actualizada de 🔵 → ⚠️ (parcialmente mitigado). Caveat de `balance_real` lag actualizado. Nueva sección "Captura: 2026-08-05".

### 4. DRY cleanup (commit `e994e7c`, ponytail-review)

`_PENDING_WD_EXISTS_SQL` estaba duplicada entre `account_refresh.py` y `jwt_keeper.py`. Ahora `jwt_keeper.py` la importa de `account_refresh` (una sola fuente de verdad).

---

## Qué NO se hizo (a propósito)

- **No se subió `JWT_KEEPER_BATCH`** (sigue 8) ni se relajó el cooldown (sigue 6h). El handoff §2.2 advierte que subirlo recreó el incidente de quema de julio. La solución fue priorización, no relajación.
- **No se redujo `JWT_KEEPER_INTERVAL_SEC`** (sigue 1h). El lag máximo para re-login de una hot con JWT expirado sigue siendo 1h (hasta el próximo ciclo de `jwt_keeper`). Ver pregunta abierta abajo.
- **No se deployó a KVM4** (regla §4.3). Esto es trabajo de Claude Code + Robert.
- **No se persiguió el bug `project_saldos_desincronizados_checker`** (§2.7 — necesita `docker exec` de diagnóstico en prod).
- **No se implementaron alertas proactivas por Telegram** (§2.8 — fuera de foco).
- **No se implementó el reintento automático 24h de `auto_deposit`** (§3 — explícitamente fuera de alcance).

---

## Preguntas abiertas para Robert / Claude Code

### 1. ¿Intervalo adaptativo de `jwt_keeper` cuando hay hot pendientes?

Hoy el ciclo es fijo 1h. Si hay 1 cuenta hot con JWT expirado, el lag máximo es 1h hasta que `jwt_keeper` corra. Un intervalo adaptativo (ej. 10min cuando hay hot pendientes, 1h cuando no) reduciría esto, pero **requiere medir el impacto en captcha/rate-limit antes de implementar**. Queries para medir en prod:

```sql
-- Cuántas hot hay ahora
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

**Recomendación**: correr estas queries en prod. Si típicamente hay <5 hot con JWT expirado, el fix actual (priorización) basta. Si suele haber >8, considerar intervalo adaptativo.

### 2. Cadencia "considerable" de R4

Robert pide "ni tan espaciada que la sesión muera, ni tan frecuente que sea spam". El intervalo de `account_refresh.py` es 300s (5min) — ya es razonable para "tiempo cercano a real". El de `jwt_keeper` es 3600s (1h) — calibrado por incidente real. **No se modificaron** — necesita evidencia de prod para cambiar.

### 3. Refactor: extraer `_refresh_account_after_*` a helper común

`withdrawals._refresh_account_after_withdrawal` y `deposits._refresh_account_after_deposit` son 95% idénticos. Marcado con `ponytail:` comment en el código. El upgrade path es extraer `refresh_account_after_action(email, jwt, proxy, operator_id, log_tag)` a `prewarm.py`. **No se hizo en esta sesión** (el handoff pide explícitamente el espejo, y tocar `deposits.py` es riesgo). Candidato para una sesión de refactor futura.

---

## Verificación antes de deploy

1. **Review del diff completo**: `git diff main...feature/jwt-refresh-hardening-2026-08-05`
2. **Suite local**: `python -m pytest -q` → debe dar **393 passed**.
3. **Smoke test post-deploy** (ver `docs/protocols/deploy-checklist.md`): verificar que `/api/logs/stream` no muestre errores de startup de `jwt_keeper` o `account_refresh`.
4. **Verificar en prod** (con Robert, vía `docker exec betmexico-web env`):
   - `JWT_KEEPER_BATCH=8` (sin override)
   - `JWT_KEEPER_INTERVAL_SEC=3600` (sin override)
   - `ACCOUNT_REFRESH_INTERVAL_SEC=300` (sin override)

---

## Protocolo de deploy

Ver skill `kvm-deploy` (`~/.claude/skills/kvm-deploy/SKILL.md`). Resumen:

1. SCP de archivos modificados a KVM4 (`2.24.211.109`):
   - `jwt_keeper.py`
   - `withdrawals.py`
   - `app.py`
2. `docker restart betmexico-web` (no necesita rebuild — hot-mount de código).
3. Health check: `curl -s https://betmexico.mx/api/health`
4. Inspección de logs: `docker exec betmexico-web tail -50 /data/logs/dashboard.log` — buscar `[jwt_keeper]` y `[withdrawals]` sin errores.
5. Verificar que el próximo ciclo de `jwt_keeper` loguee `nada que refrescar` o `ciclo listo` con stats normales.

**No deployar sin que Robert esté presente para verificar visualmente** que el botón de retiro sigue funcionando y el dashboard no muestra errores.

---

## Archivos tocados (resumen)

| Archivo | Cambios |
|---------|---------|
| `jwt_keeper.py` | `select_refresh_candidates` prioriza hot; `_load_candidate_rows` computa hot; `_PENDING_WD_EXISTS_SQL` importado de account_refresh (DRY) |
| `withdrawals.py` | `_refresh_account_after_withdrawal` (espejo de deposits); `execute_withdrawal` devuelve `_jwt`/`_proxy_url` |
| `app.py` | `operator_withdraw` y `withdraw` invocan refresh post-retiro |
| `test_jwt_keeper.py` | 7 tests nuevos de priorización hot |
| `test_withdrawals_endpoints.py` | 2 tests nuevos de refresh post-retiro |
| `docs/AUDIT.md` | Entries actualizadas + nueva sección "Captura 2026-08-05" |
| `MAP.md` | `account_refresh.py` 1h→5min; `withdrawals.py` descrito |
| `docs/plans/2026-08-05-REPORTE-opencode-jwt-refresh.md` | Reporte final obligatorio |

# Plan A1 — Modelo de estados de cuentas + consolidación de watchdogs (TDD)

> Spec: `docs/superpowers/specs/2026-06-26-sp3-modal-unificado-spec.md` §A1.
> Diseño: `docs/superpowers/specs/2026-06-25-optimizacion-estado-cuentas-design.md`.
> Rama: `feat/sp3-a1-estados-cuentas`. **Sin deploy hasta OK de Robert** (toca watchdogs prod, 923 cuentas).
> SA tg = `1341812706`. 5 estados derivados de `locked_by` + `locked_until` + `published_to_pool`.

## Orden (impuesto por la verificación adversarial: pre-cambios ANTES del core)

### T1 — Helper canónico `_release_account` (core, lo usan T5/T6)
`_release_account(c, account_id, email, reason, prev_locked_by, kind="unlock_auto", who="janitor")`:
UPDATE atómico → `locked_by=NULL, locked_at=NULL, locked_until=NULL, notif_pre24h_sent_at=NULL, notif_at24h_sent_at=NULL, notif_at24h10_sent_at=NULL, published_to_pool=1 WHERE id=?` + 1 `_broadcast(kind, reason, prev_locked_by)`. Colocar antes de `_run_lock_janitor` (app.py ~L1356).
**Test:** cuenta lockeada+notif sucios+published=0 → tras helper: todo limpio, published=1, 1 broadcast.

### T2 — Backfill legacy en `_migrate` (defensivo, idempotente)
`UPDATE accounts SET locked_until=datetime(locked_at,'+24 hours') WHERE locked_by IS NOT NULL AND locked_until IS NULL AND locked_by != '1341812706'`. Corre 1 vez (NEXT-SESSION: 0 filas hoy, defensivo para legacy/futuro).
**Test:** cuenta legacy (locked_by=555, until NULL) → migra a until no-nulo; RESERVADA_SA (locked_by=SA, until NULL) → intacta.

### T3 — Guards `locked_until IS NOT NULL` en notificadores (no spam RESERVADA_SA)
`_release_watchdog_tick` SELECT (app.py ~L1544): `AND locked_until IS NOT NULL`. `_run_window_watcher` loop (~L1452): saltar si la cuenta es RESERVADA_SA (locked_by NOT NULL + locked_until NULL).
**Test:** RESERVADA_SA no genera notif en ninguno de los 2.

### T4 — Guardrail publish/hide contra EN_USO
`publish_accounts` (hide branch) + `hide_all_accounts`: `AND locked_by IS NULL`. No ocultar cuentas lockeadas (evita fantasma published=0+locked).
**Test:** hide-all no toca cuenta lockeada; publish(False) sobre lockeada = skip.

### T5 — `lock_account` override SA + lock perpetuo
Caller SA (`_user.role==superadmin`) → `locked_until=None` + override (UPDATE sin `AND locked_by IS NULL`). Non-SA → actual (409 si ocupada). Republish vía `_release_account` no aplica aquí (es lock, no release).
**Test:** SA lockea cuenta ocupada por 555 → override, locked_until NULL. Operador lockea ocupada → 409.

### T6 — Consolidar: janitor = único liberador; window/release = notificadores puros
- `_run_lock_janitor` rama vomitada (~L1397) → `_release_account(...)`.
- `_run_window_watcher` fase 3 (~L1488) → ELIMINAR release+republish (queda notificador).
- `_release_watchdog_tick` caso 1 27h (~L1574) → ELIMINAR auto-release (quedan notifs 2-4).
- `unlock_account` manual → usar `_release_account(kind="unlock", who=username)` para republicar consistente.
**Test:** janitor libera vía helper (republica); window_watcher y release_watchdog ya NO mutan locked_by; unlock manual republica.

### T7 — `_auto_lock_for_deposit` SA perpetuo (deposits.py ~L280)
`locked_until = None if is_sa else (now+timedelta(hours=hours)).isoformat()`. Broadcast manda `locked_until` (puede ser None).
**Test:** depósito SA → locked_until None (RESERVADA_SA); operador → until temporal.

## Aceptación A1
- RESERVADA_SA (SA, until NULL) invisible a non-SA e intocable por los 3 watchdogs.
- 1 solo liberador automático (janitor); cero doble-release; liberar SIEMPRE republica + limpia notif.
- Cero regresión en suite existente (a21, sp1, sp2).
- **Deploy = amarillo** (backup BD prod primero).

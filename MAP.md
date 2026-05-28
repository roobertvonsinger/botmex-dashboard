# MAP — botmex-dashboard
### Guía de navegación para agentes IA

> Las secciones `[AUTO]` se regeneran en cada `git commit` via `scripts/gen_map.py`.
> **No editar** esas secciones — se pisarán. Editar solo las `[MANUAL]`.
> Regenerar ahora: `python scripts/gen_map.py`

---

## Si necesitas... (leer primero) `[MANUAL]`

| Si necesitas... | Ve a | Nota |
|-----------------|------|------|
| Modificar flujo de depósito (lógica core) | `deposits.py` | Motor principal |
| Modificar endpoints HTTP de depósito | `web_routes_deposits.py` | FastAPI router |
| Modificar flujo de misiones (batch/scheduled) | `web_routes_missions.py` | 803L, leer reglas al inicio |
| Modificar prewarm | `prewarm.py` + `web_routes_prewarm.py` | |
| Agregar endpoint nuevo | `web_routes_X.py` (crear o editar) + registrar en `app.py` | Ver sección registros en app.py |
| Cambiar pool de proxies / failover | `proxy_pool.py` | `call_with_proxy_failover` es la API recomendada |
| Cambiar lógica de grading de cuentas | `web_grading.py` + `shared/betmexico_payment_analyzer.py` | Algoritmo V10 |
| Cambiar autenticación / sesiones | `auth.py` + `web_auth.py` | |
| Ver logs en vivo (endpoint) | `web_routes_logs.py` L1–L98 | Lee /data/logs/dashboard.log |
| Modificar watchdog de balance | `web_watchdog.py` | Loop background |
| Cambiar BD (schema) | `app.py` `_migrate()` L143–L167 | Migraciones aditivas solo |
| SSE broadcast nuevo evento | `app.py` `_broadcast()` L204–L223 → `docs/SSE_EVENTS.md` | |
| Cambiar caps duros de depósito | `deposits.py` L28–L35 | DEP_MAX_PER_TXN, DEP_MAX_24H, AUTOLOCK_HOURS_* |
| Analizar si una tarjeta está quemada | `shared/betmexico_payment_analyzer.py` | Algoritmo V10 |
| Ver estado funcional de features | `docs/AUDIT.md` | ✅❌⚠️🔵❓ |
| Ver errores conocidos + fix | `docs/ERRORS.md` | |
| Deploy a KVM4 | `DEPLOY.md` + `docs/protocols/deploy-protocol.md` | |
| Ver todos los endpoints documentados | `docs/ENDPOINTS.md` | |

---

## Flujos principales `[MANUAL]`

### Depósito único
```
web_routes_deposits.py → deposits.py (_run_deposit)
  → betmexico_login_api (JWT/login) [bot dep]
  → proxy_pool.py (call_with_proxy_failover)
  → CapMonster API (captcha)
  → BetMexico API (BeginDeposit → makePayment → verify)
  → web_grading.py (recalc_grade_from_db)
  → app.py _broadcast() → SSE al frontend
```

### Misión batch (matchmaker)
```
web_routes_missions.py → deposits.py _run_deposit (por cada cuenta×tarjeta)
  Regla: max 5 cuentas × 5 tarjetas, gap 3-8s
  APROBADA → vincular tarjeta↔cuenta
  Rechazo específico → marcar tarjeta, siguiente
  Gateway 5xx ×2 → PAUSE TOTAL
```

### Misión programada (scheduled)
```
web_routes_missions.py → loop: cada 60s → deposits.py _run_deposit
  APROBADO → completed
  Rechazo → STOP inmediato (no reintentar sin override manual)
  Captcha pool: tokens se prefetchean, evitar tokens expirados (TOKEN_MAX_AGE=55s)
```

### Prewarm
```
web_routes_prewarm.py → prewarm.py
  Cap: max 30 pre-warms/operador en últimos 10 min
  Skip si JWT vigente AND last_check < 5 min
  Timeout 25s por task. Logs en process_log (process_type='prewarm')
```

---

## Gotchas críticos — no repetir `[MANUAL]`

| # | Síntoma / Error | Causa raíz | Fix / Dónde está |
|---|-----------------|------------|------------------|
| 1 | SSE no llega al frontend aunque backend emite | Doble-import de `app.py` crea dos instancias de `_sse_queues` | Fix en `app.py` L18-32: `sys.modules.setdefault("app", sys.modules[__name__])` |
| 2 | 406 FAILURE_IN_CAPTCHA masivo (desde build v26.5.25) | BetMexico migró a reCAPTCHA **v3**; nosotros mandábamos v2 | `deposits.py` usa `RECAPTCHA_V2_SITE_KEY` — actualizar a v3 key `6LdoqOUk...` |
| 3 | Logs no cargan en dashboard tras restart container | Antes usaba journalctl (systemd, VPS). KVM4 es Docker sin systemd | Fix en `app.py` L40-62: RotatingFileHandler a `/data/logs/dashboard.log` |
| 4 | Token captcha expirado en scheduled después de sleep(60) | TOKEN_MAX_AGE=55s, sleep 60 → token viejo al despertar | Pool prefetchea tokens; ver `deposits.py` sección captcha pool |
| 5 | `create_task(gather())` crashea en Py3.11+ | Bug de asyncio en multi-depósito | Fix aplicado en `web_routes_deposits.py` |
| 6 | BANK_REJECTED confundido con error de captcha | Son cosas distintas: BANK_REJECTED = banco rechazó la tarjeta | No reintentar en BANK_REJECTED; ver `deposits.py` lógica de rechazo |
| 7 | Proxy LitPort siempre falla (0% éxito) | Reputación IP baja para BetMexico | Excluido via `_EXCLUDED_PROXY_HOSTS` en `proxy_pool.py` |

---

## Módulos — propósito + métricas `[AUTO métricas / MANUAL propósito]`

> Edita la columna **Propósito** directamente aquí. El script preserva tus ediciones.

<!-- GEN:start:modulos -->
| Módulo | L# | Logger | Propósito |
|--------|----|---------|-----------| 
| `_test_v3_login.py` | 69 | `—` | Script dev para testear login reCAPTCHA v3 — NO es parte del app |
| `app.py` | 2378 | `betmexico.dashboard.sse` | App Flask principal: config, BD SQLite, rutas base, bus SSE, KPIs/admin, watchdog init |
| `auth.py` | 164 | `—` | Core de autenticación: sesiones, hashing de passwords, decorador `require_session` |
| `conftest.py` | 79 | `—` | Fixtures pytest (BD en memoria, cliente test, sesión de prueba) |
| `deposits.py` | 1902 | `betmexico.dashboard.deposits` | Motor de depósitos: `_run_deposit`, captcha pool, retry-con-failover, caps duros |
| `prewarm.py` | 665 | `betmexico.dashboard.prewarm` | Pre-carga JWT + balance para cuentas — acelera depósitos. Deps del bot en runtime |
| `proxy_pool.py` | 289 | `dashboard.proxy_pool` | Pool de proxies: rotación, `call_with_proxy_failover`, exclusión de hosts quemados |
| `scripts/gen_map.py` | 443 | `name` | Regenerador de este MAP.md — AST + git log. Corre en pre-commit hook |
| `scripts/recalc_grades.py` | 131 | `—` | Utilería dev: recalcular grades de todas las cuentas desde BD |
| `shared/betmexico_payment_analyzer.py` | 578 | `—` | Algoritmo V10: clasifica si pasarela/tarjeta está quemada (A=sana/B=recuperando/C=lenta/D=quemada) |
| `web_auth.py` | 138 | `betmexico.web.auth` | Endpoints HTTP de auth: `/api/auth/login`, `/logout`, `/me`, cambio de password |
| `web_grading.py` | 113 | `betmexico.web.grading` | Recalcula `grade` y `grade_score` de una cuenta desde BD (usa analyzer V10) |
| `web_routes_cards.py` | 136 | `betmexico.web.cards` | Endpoints CRUD de tarjetas — listar, agregar, eliminar |
| `web_routes_deposits.py` | 391 | `betmexico.web.deposit` | Endpoints HTTP del flujo de depósito: single, multi, scheduled start/stop |
| `web_routes_logs.py` | 98 | `betmexico.web.logs` | Endpoint `/api/logs`: lee `/data/logs/dashboard.log` y stream SSE en vivo |
| `web_routes_missions.py` | 803 | `betmexico.web.missions` | Endpoints de misiones batch y scheduled: crear, cancelar, estado, historial |
| `web_routes_notifications.py` | 111 | `betmexico.web.notif` | Endpoints de notificaciones push / alertas al operador |
| `web_routes_prewarm.py` | 260 | `betmexico.web.prewarm` | Endpoints HTTP de prewarm: start, cancel, status |
| `web_utils.py` | 243 | `betmexico.web.utils` | Helpers compartidos: `_friendly_error`, `_normalize_ccexp`, `_build_proxy_url` |
| `web_watchdog.py` | 276 | `betmexico.web.watchdog` | Loop background: refresca balance de cuentas LIVE cada N min, genera notificaciones |
<!-- GEN:end:modulos -->

---

## Constantes críticas del sistema `[AUTO]`

<!-- GEN:start:constantes -->
| Constante | Valor | Módulo |
|-----------|-------|--------|
| `BOT_DEPS_OK` | `False` | `app.py` |
| `BOT_RUN_DEPOSIT` | `None` | `app.py` |
| `BOT_MAKE_POOL` | `None` | `app.py` |
| `BOT_SCORE_PAYMENT` | `None` | `app.py` |
| `ROOT` | `Path(__file__).parent` | `app.py` |
| `STATIC` | `ROOT / "static"` | `app.py` |
| `DB_PATH` | `Path(os.environ.get("BETMEX_DB", str(ROOT.parent / "betmexico_accounts` | `app.py` |
| `SESSION_TTL` | `86_400` | `auth.py` |
| `PERSISTENT_USERS` | `{"robertvs"}` | `auth.py` |
| `PERSISTENT_TTL` | `60 * 60 * 24 * 365 * 10` | `auth.py` |
| `DEP_MAX_PER_TXN` | `499.0` | `deposits.py` |
| `DEP_MAX_24H` | `1499.0` | `deposits.py` |
| `AUTOLOCK_HOURS_SINGLE` | `2` | `deposits.py` |
| `AUTOLOCK_HOURS_MULTI` | `2` | `deposits.py` |
| `AUTOLOCK_HOURS_SCHEDULED` | `4` | `deposits.py` |
| `CARD_VELOCITY_MEMORY_MIN` | `30` | `deposits.py` |
| `CARD_VELOCITY_FREE_PAIR` | `2` | `deposits.py` |
| `CARD_VELOCITY_COOLDOWN_SEC` | `60` | `deposits.py` |
| `MM_COOLDOWN` | `5` | `deposits.py` |
| `MM_MAX_FAILS` | `2` | `deposits.py` |
| `CAP_PER_OPERATOR_10MIN` | `9999` | `prewarm.py` |
| `ACCOUNT_FRESH_MINUTES` | `30` | `prewarm.py` |
| `ACCOUNT_DAILY_LIMIT` | `3` | `prewarm.py` |
| `REFRESH_PARALLEL` | `15` | `prewarm.py` |
| `CAPMONSTER_MIN_BALANCE` | `5.0` | `prewarm.py` |
| `BALANCE_FRESH_SEC` | `5 * 60` | `prewarm.py` |
| `TASK_TIMEOUT_SEC` | `25` | `prewarm.py` |
| `REPO_ROOT` | `Path(__file__).resolve().parent.parent` | `scripts/gen_map.py` |
| `MAP_PATH` | `REPO_ROOT / "MAP.md"` | `scripts/gen_map.py` |
| `PY_MODULES` | `_collect_modules()` | `scripts/gen_map.py` |
| `SECTIONS` | `{` | `scripts/gen_map.py` |
| `INITIAL_MAP` | `"""\` | `scripts/gen_map.py` |
| `MX_TZ` | `ZoneInfo("America/Mexico_City")` | `shared/betmexico_payment_analyzer.py` |
| `TXN_STATUS_SUCCESS` | `6` | `shared/betmexico_payment_analyzer.py` |
| `TXN_STATUS_PENDING` | `0` | `shared/betmexico_payment_analyzer.py` |
| `TXN_STATUS_FAILED` | `-4` | `shared/betmexico_payment_analyzer.py` |
| `TXN_TYPE_DEPOSIT` | `1` | `shared/betmexico_payment_analyzer.py` |
| `GATEWAY_CARD` | `1` | `shared/betmexico_payment_analyzer.py` |
| `GRADE_THRESHOLDS` | `[` | `shared/betmexico_payment_analyzer.py` |
| `GRADE_EMOJI` | `{` | `shared/betmexico_payment_analyzer.py` |
| `GRADE_LABEL` | `{` | `shared/betmexico_payment_analyzer.py` |
| `A_NO_FAIL_DAYS_MIN` | `60` | `shared/betmexico_payment_analyzer.py` |
| `A_MAX_TOTAL_FAILS` | `3` | `shared/betmexico_payment_analyzer.py` |
| `A_MAX_BIGFAIL_SESS` | `0` | `shared/betmexico_payment_analyzer.py` |
| `D_RECENT_FAIL_DAYS` | `14` | `shared/betmexico_payment_analyzer.py` |
| `D_MASSACRE_COUNT` | `3` | `shared/betmexico_payment_analyzer.py` |
| `C_DEEP_REST_DAYS` | `90` | `shared/betmexico_payment_analyzer.py` |
| `SCORE_FLOOR` | `{"A": 80, "B": 60, "C": 40, "D": 0}` | `shared/betmexico_payment_analyzer.py` |
| `SCORE_CEIL` | `{"A": 100, "B": 79, "C": 59, "D": 39}` | `shared/betmexico_payment_analyzer.py` |
| `WEB_USERS_RAW` | `{` | `web_auth.py` |
| `WEB_USERS` | `{k.lower(): v for k, v in WEB_USERS_RAW.items()}` | `web_auth.py` |
| `BETMEXICO_PAYMENTS_API` | `"https://paymentsapi.betmexico.mx"` | `web_routes_deposits.py` |
| `PROCESSORPAY_MAKE_PAYMENT_URL` | `"https://processorpay.com/sanval/api/IframeGames/makePayment"` | `web_routes_deposits.py` |
| `NO_PROXY` | `os.getenv("BMX_NO_PROXY", "0") == "1"` | `web_routes_deposits.py` |
| `CAPMONSTER_API_KEY` | `os.getenv("BMX_CAPMONSTER_KEY", "a9040840fdb3828ecc6090a6010afcad")` | `web_routes_prewarm.py` |
| `CAPMONSTER_ENDPOINT` | `"https://api.capmonster.cloud"` | `web_routes_prewarm.py` |
| `CAPMONSTER_API_KEY` | `os.getenv("BMX_CAPMONSTER_KEY", "a9040840fdb3828ecc6090a6010afcad")` | `web_watchdog.py` |
| `CAPMONSTER_ENDPOINT` | `"https://api.capmonster.cloud"` | `web_watchdog.py` |
<!-- GEN:end:constantes -->

---

## Cambios recientes `[AUTO]`

<!-- GEN:start:recientes -->
| Hash | Mensaje |
|------|---------|
| `eb733e3` | feat(map): MAP.md auto-generado + hook pre-commit |
| `68121cf` | feat(detalle+scheduled): panel de detalle inline (acordeÃ³n v14) + reuso de sesiÃ³n en programados |
| `6908af3` | fix(deposits): rescatar 406 con retry-rotaciÃ³n-IP + IPRoyal + crash del multi |
| `c08024d` | feat(scheduled): cancel desde UI + rehidrataciÃ³n tras refresh (TDAH-friendly) |
| `7a0b37f` | fix+feat: SSE who resuelto, tabla intentos sin truncar, drawer collapse rail |
| `899ba14` | ui(balance): tiers low/mid/hot â€” <$10 gris, <$50 blanco, >=$50 verde radiactivo + glow + pulse 2.6s |
| `72056f2` | ui(green): swatch final â€” hue 160 chr 0.11 L 0.50 (verde bandera mx) |
| `04627e9` | ui(green): bajar lightness 0.82â†’0.66 â€” verde mexicano mÃ¡s serio |
| `40e430c` | fix(sse): doble-import de app.py rompÃ­a bus SSE â€” clients=0 fantasma |
| `0ad4044` | feat(ui): verde mexicano neÃ³n + botones premium + logo link + SSE diag |
| `7b43898` | fix(drawer): empujar dashboard en vez de superponerse + tab Multi siempre visible |
| `3269039` | feat(deposits): drawer lateral + persist cards + SSE feedback Programado |
| `3604c7b` | feat(ui): vista live premium para depÃ³sito Programado (sin sacar al user del modal) |
| `6aabec6` | fix(refresh): acelera el botÃ³n Actualizar + try/catch al modal |
| `66ac94b` | fix(deposits): cadencia fija scheduled + token captcha fresco + persist details |
<!-- GEN:end:recientes -->

---

## Símbolos por módulo — funciones/clases con rango de líneas `[AUTO]`

<!-- GEN:start:simbolos -->

### `_test_v3_login.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `get_accounts` | def | L23–L32 |
| `main` | def | L35–L65 |

### `app.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `db` | def | L126–L140 |
| `_migrate` | def | L143–L167 |
| `_resolve_operator` | def | L173–L197 |
| `_broadcast` | def | L204–L223 |
| `_dequeue_blocking` | def | L226–L231 |
| `_no_cache_static_assets` | def | L239–L251 |
| `favicon` | def | L259–L260 |
| `login_page` | def | L264–L267 |
| `index` | def | L271–L284 |
| `auth_login` | def | L293–L318 |
| `auth_set_password` | def | L322–L346 |
| `auth_logout` | def | L350–L354 |
| `auth_me` | def | L358–L363 |
| `health` | def | L369–L375 |
| `list_accounts` | def | L379–L468 |
| `list_users` | def | L474–L482 |
| `list_assignments` | def | L486–L507 |
| `AssignRequest` | class | L510–L512 |
| `assign_accounts` | def | L516–L535 |
| `unassign_accounts` | def | L539–L550 |
| `stats` | def | L554–L561 |
| `_wsai_status` | def | L573–L598 |
| `_maybe_alert_broadcast` | def | L605–L622 |
| `_proxy_health` | def | L625–L675 |
| `_capmonster_balance` | def | L678–L698 |
| `_operator_color` | def | L703–L704 |
| `_resolve_who` | def | L707–L715 |
| `superadmin_kpis` | def | L719–L962 |
| `RefreshRequest` | class | L967–L968 |
| `accounts_refresh` | def | L972–L991 |
| `get_logs` | def | L997–L1022 |
| `_run_health_checks` | def | L1030–L1066 |
| `health_full` | def | L1070–L1071 |
| `_require_sa` | def | L1079–L1081 |
| `admin_diag` | def | L1085–L1116 |
| `admin_ping` | def | L1120–L1141 |
| `admin_refresh_proxy` | def | L1145–L1152 |
| `admin_services_restart` | def | L1156–L1170 |
| `admin_export_logs` | def | L1174–L1186 |
| `admin_pause_state` | def | L1194–L1196 |
| `admin_pause` | def | L1200–L1212 |
| `admin_resume` | def | L1216–L1222 |
| `admin_emergency_stop` | def | L1226–L1261 |
| `admin_vps_reboot` | def | L1265–L1277 |
| `health_last` | def | L1281–L1282 |
| `health_dismiss` | def | L1286–L1289 |
| `_health_loop` | def | L1292–L1302 |
| `_run_lock_janitor` | def | L1305–L1363 |
| `_janitor_loop` | def | L1366–L1376 |
| `_run_window_watcher` | def | L1385–L1459 |
| `_window_watcher_loop` | def | L1462–L1471 |
| `_release_watchdog_tick` | def | L1474–L1590 |
| `_release_watchdog_loop` | def | L1593–L1601 |
| `_start_bg_tasks` | def | L1605–L1609 |
| `LockRequest` | class | L1612–L1614 |
| `lock_account` | def | L1618–L1646 |
| `PublishRequest` | class | L1649–L1651 |
| `publish_accounts` | def | L1655–L1670 |
| `hide_all_accounts` | def | L1674–L1685 |
| `pool_accounts` | def | L1689–L1707 |
| `unlock_account` | def | L1711–L1738 |
| `_sse_generator` | def | L1741–L1768 |
| `events` | def | L1772–L1777 |
| `account_cards_pipe` | def | L1781–L1806 |
| `account_notes_summary` | def | L1810–L1835 |
| `account_details` | def | L1839–L2021 |
| `NoteCreate` | class | L2024–L2025 |
| `create_note` | def | L2029–L2058 |
| `CurpUpdate` | class | L2061–L2062 |
| `update_curp` | def | L2066–L2077 |
| `delete_note` | def | L2081–L2093 |
| `CombosRequest` | class | L2096–L2097 |
| `accounts_combos` | def | L2101–L2110 |
| `accounts_pass_map` | def | L2114–L2118 |
| `list_all_cards` | def | L2122–L2192 |
| `activity_feed` | def | L2196–L2313 |
| `list_deposits` | def | L2317–L2342 |
| `deposits_stats` | def | L2346–L2371 |

### `auth.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `sha256` | def | L31–L32 |
| `load_passwords` | def | L35–L58 |
| `save_passwords` | def | L61–L69 |
| `_is_persistent` | def | L79–L80 |
| `_load_persistent_sessions` | def | L83–L89 |
| `_save_persistent_sessions` | def | L92–L98 |
| `_prune` | def | L104–L113 |
| `session_max_age` | def | L116–L118 |
| `create_session` | def | L121–L134 |
| `get_session` | def | L137–L146 |
| `delete_session` | def | L149–L152 |
| `require_session` | def | L156–L164 |

### `conftest.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `seed_db` | def | L7–L72 |
| `client` | def | L75–L79 |

### `deposits.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_drain_stale_tokens` | def | L45–L77 |
| `_ensure_fresh_captcha` | def | L80–L104 |
| `_record_bin_3ds` | def | L112–L140 |
| `_bin_3ds_stats` | def | L143–L165 |
| `bin_check` | def | L169–L174 |
| `_auto_lock_for_deposit` | def | L177–L226 |
| `_window_status` | def | L229–L271 |
| `_check_caps` | def | L274–L287 |
| `_load_deps` | def | L290–L298 |
| `_parse_pipe` | def | L301–L322 |
| `_check_card_velocity` | def | L342–L389 |
| `_record_attempt` | def | L392–L502 |
| `_safe_phase` | def | L512–L519 |
| `_build_admin_proxy_url` | def | L522–L526 |
| `_run_deposit_with_phases` | def | L529–L889 |
| `deposit_execute` | def | L893–L1030 |
| `deposit_execute_stream` | def | L1034–L1242 |
| `cap_status` | def | L1246–L1258 |
| `multi_stream` | def | L1278–L1616 |
| `multi_cancel` | def | L1620–L1625 |
| `scheduled_create` | def | L1636–L1864 |
| `scheduled_list` | def | L1868–L1890 |
| `scheduled_cancel` | def | L1894–L1902 |

### `prewarm.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_db_get_account` | def | L61–L74 |
| `_db_get_jwt_cache` | def | L77–L87 |
| `_db_log_phase` | def | L90–L109 |
| `_db_count_recent` | def | L112–L127 |
| `_db_account_prewarms_today` | def | L130–L145 |
| `_account_minutes_since_check` | def | L148–L157 |
| `_db_get_recent_log` | def | L160–L175 |
| `_db_upsert_balance` | def | L178–L231 |
| `_db_save_txns_and_recalc` | def | L234–L256 |
| `_db_update_last_checked` | def | L259–L271 |
| `_db_invalidate_jwt` | def | L274–L285 |
| `_is_balance_fresh` | def | L288–L296 |
| `_capmonster_balance` | def | L301–L317 |
| `_run_prewarm` | def | L322–L428 |
| `prewarm_select` | def | L434–L504 |
| `prewarm_cancel` | def | L508–L518 |
| `prewarm_status` | def | L522–L537 |
| `prewarm_refresh_stream` | def | L543–L665 |

### `proxy_pool.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_bot_proxies` | def | L53–L59 |
| `all_proxies` | def | L62–L70 |
| `_to_url` | def | L73–L83 |
| `get_admin_proxy` | def | L86–L91 |
| `build_admin_proxy_url` | def | L94–L97 |
| `shuffled_proxy_urls` | def | L100–L108 |
| `_retry_exceptions` | def | L116–L142 |
| `_proxy_host` | def | L145–L149 |
| `call_with_proxy_failover` | def | L152–L243 |
| `_looks_like_proxy_failure_result` | def | L252–L271 |
| `_looks_like_captcha_failure_result` | def | L274–L289 |

### `scripts/gen_map.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_collect_modules` | def | L18–L24 |
| `_read` | def | L31–L32 |
| `extract_symbols` | def | L35–L47 |
| `extract_env_vars` | def | L50–L54 |
| `extract_loggers` | def | L57–L59 |
| `extract_endpoints` | def | L62–L66 |
| `extract_constants` | def | L69–L80 |
| `_read_existing_propositos` | def | L85–L104 |
| `gen_modulos` | def | L109–L120 |
| `gen_simbolos` | def | L123–L135 |
| `gen_endpoints` | def | L138–L147 |
| `gen_env` | def | L150–L163 |
| `gen_loggers` | def | L166–L178 |
| `gen_constantes` | def | L181–L191 |
| `gen_recientes` | def | L194–L210 |
| `update_map` | def | L418–L439 |

### `scripts/recalc_grades.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_import_analyzer` | def | L21–L40 |
| `main` | def | L43–L127 |

### `shared/betmexico_payment_analyzer.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_get_grade` | def | L66–L70 |
| `_activity_suffix` | def | L73–L91 |
| `_parse_txn_date` | def | L94–L120 |
| `_parse_deposit_date` | def | L123–L136 |
| `_get_txn_fields` | def | L139–L150 |
| `_is_card_deposit` | def | L153–L156 |
| `_group_into_sessions` | def | L159–L206 |
| `_pure_fail_penalty` | def | L214–L224 |
| `_last_success_bonus` | def | L227–L233 |
| `score_payment_readiness` | def | L247–L415 |
| `analyze_gateway_ban_pattern` | def | L422–L492 |
| `generate_payment_analysis_summary` | def | L499–L547 |
| `generate_payment_ready_txt` | def | L550–L578 |

### `web_auth.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_load_passwords` | def | L38–L65 |
| `_save_passwords` | def | L67–L75 |
| `set_session_callback` | def | L80–L82 |
| `authenticate` | def | L84–L128 |
| `require_admin` | def | L130–L133 |
| `require_superadmin` | def | L135–L138 |

### `web_grading.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_load_analyzer` | def | L27–L35 |
| `recalc_grade_from_db` | def | L47–L88 |
| `recalc_grade_from_details` | def | L91–L113 |

### `web_routes_cards.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_is_visible` | def | L32–L37 |
| `create_card` | def | L41–L67 |
| `list_cards` | def | L71–L75 |
| `get_card` | def | L79–L85 |
| `get_card_usage` | def | L89–L96 |
| `patch_card_notes` | def | L100–L117 |
| `ban_card` | def | L121–L136 |

### `web_routes_deposits.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_run_deposit` | def | L32–L391 |

### `web_routes_logs.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_parse_line` | def | L34–L64 |
| `get_logs_monitor` | def | L68–L98 |

### `web_routes_missions.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_emit` | def | L50–L56 |
| `_control_get` | def | L59–L63 |
| `_normalize_cards` | def | L66–L84 |
| `_ensure_card_record` | def | L87–L95 |
| `_classify_result` | def | L98–L111 |
| `_persist_attempt` | def | L114–L148 |
| `_run_batch_mission` | def | L155–L298 |
| `_run_batch_mission_smart` | def | L305–L534 |
| `_run_scheduled_mission` | def | L541–L641 |
| `create_batch_mission` | def | L649–L680 |
| `create_scheduled_mission` | def | L684–L714 |
| `list_missions` | def | L718–L722 |
| `get_mission_detail` | def | L726–L733 |
| `pause_mission` | def | L737–L742 |
| `resume_mission` | def | L746–L750 |
| `stop_mission` | def | L754–L763 |
| `stream_mission` | def | L767–L803 |

### `web_routes_notifications.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `push_notification_event` | def | L31–L43 |
| `list_notifications` | def | L47–L56 |
| `count_unread` | def | L60–L63 |
| `mark_read` | def | L67–L70 |
| `mark_all_read` | def | L74–L77 |
| `stream` | def | L81–L111 |

### `web_routes_prewarm.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_capmonster_balance` | def | L48–L60 |
| `_is_balance_fresh` | def | L63–L77 |
| `_run_prewarm` | def | L80–L151 |
| `prewarm_select` | def | L155–L222 |
| `prewarm_cancel` | def | L226–L237 |
| `prewarm_status` | def | L241–L260 |

### `web_utils.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_sha256` | def | L33–L35 |
| `compute_card_fingerprint` | def | L38–L41 |
| `parse_pipe_card` | def | L44–L120 |
| `_friendly_error` | def | L123–L138 |
| `_normalize_ccexp` | def | L141–L147 |
| `_build_proxy_url` | def | L150–L154 |
| `_extract_user_from_message` | def | L157–L176 |
| `_categorize_event` | def | L179–L199 |
| `_parse_log_entry` | def | L202–L243 |

### `web_watchdog.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_capmonster_balance` | def | L52–L64 |
| `_check_one` | def | L67–L130 |
| `_run_one_pass` | def | L133–L186 |
| `_watchdog_loop` | def | L189–L232 |
| `start_watchdog` | def | L235–L237 |
| `watchdog_status` | def | L243–L256 |
| `watchdog_run_now` | def | L260–L262 |
| `watchdog_pause` | def | L266–L269 |
| `watchdog_resume` | def | L273–L276 |
<!-- GEN:end:simbolos -->

---

## Endpoints `[AUTO]`

<!-- GEN:start:endpoints -->
| Método | Ruta | Módulo |
|--------|------|--------|
| `GET` | `/favicon.ico` | `app.py` |
| `GET` | `/login` | `app.py` |
| `GET` | `/` | `app.py` |
| `POST` | `/api/auth/login` | `app.py` |
| `POST` | `/api/auth/set-password` | `app.py` |
| `POST` | `/api/auth/logout` | `app.py` |
| `GET` | `/api/auth/me` | `app.py` |
| `GET` | `/api/health` | `app.py` |
| `GET` | `/api/accounts` | `app.py` |
| `GET` | `/api/users` | `app.py` |
| `GET` | `/api/assignments` | `app.py` |
| `POST` | `/api/assignments/assign` | `app.py` |
| `POST` | `/api/assignments/unassign` | `app.py` |
| `GET` | `/api/stats` | `app.py` |
| `GET` | `/api/superadmin/kpis` | `app.py` |
| `POST` | `/api/accounts/refresh` | `app.py` |
| `GET` | `/api/logs` | `app.py` |
| `GET` | `/api/health/full` | `app.py` |
| `GET` | `/api/admin/diag` | `app.py` |
| `POST` | `/api/admin/ping` | `app.py` |
| `POST` | `/api/admin/refresh-proxy` | `app.py` |
| `POST` | `/api/admin/services/restart` | `app.py` |
| `GET` | `/api/admin/export-logs` | `app.py` |
| `GET` | `/api/admin/pause-state` | `app.py` |
| `POST` | `/api/admin/pause` | `app.py` |
| `POST` | `/api/admin/resume` | `app.py` |
| `POST` | `/api/admin/emergency-stop` | `app.py` |
| `POST` | `/api/admin/vps-reboot` | `app.py` |
| `GET` | `/api/health/last` | `app.py` |
| `POST` | `/api/health/dismiss` | `app.py` |
| `POST` | `/api/accounts/{account_id}/lock` | `app.py` |
| `POST` | `/api/accounts/publish` | `app.py` |
| `POST` | `/api/accounts/hide-all` | `app.py` |
| `GET` | `/api/pool/accounts` | `app.py` |
| `POST` | `/api/accounts/{account_id}/unlock` | `app.py` |
| `GET` | `/api/events` | `app.py` |
| `GET` | `/api/accounts/{account_id}/cards-pipe` | `app.py` |
| `GET` | `/api/accounts/{account_id}/notes-summary` | `app.py` |
| `GET` | `/api/accounts/{account_id}/details` | `app.py` |
| `POST` | `/api/accounts/{account_id}/notes` | `app.py` |
| `POST` | `/api/accounts/{account_id}/curp` | `app.py` |
| `DELETE` | `/api/accounts/{account_id}/notes/{note_id}` | `app.py` |
| `POST` | `/api/accounts/combos` | `app.py` |
| `GET` | `/api/accounts/pass-map` | `app.py` |
| `GET` | `/api/cards/all` | `app.py` |
| `GET` | `/api/activity` | `app.py` |
| `GET` | `/api/deposits` | `app.py` |
| `GET` | `/api/deposits/stats` | `app.py` |
| `GET` | `/bin-check/{bin6}` | `deposits.py` |
| `POST` | `/execute` | `deposits.py` |
| `POST` | `/execute-stream` | `deposits.py` |
| `GET` | `/cap-status/{account_id}` | `deposits.py` |
| `POST` | `/multi/stream` | `deposits.py` |
| `POST` | `/multi/{run_id}/cancel` | `deposits.py` |
| `POST` | `/scheduled/create` | `deposits.py` |
| `GET` | `/scheduled/list` | `deposits.py` |
| `POST` | `/scheduled/{sched_id}/cancel` | `deposits.py` |
| `POST` | `/select` | `prewarm.py` |
| `POST` | `/cancel` | `prewarm.py` |
| `GET` | `/status` | `prewarm.py` |
| `POST` | `/refresh-stream` | `prewarm.py` |
| `GET` | `/{card_id}` | `web_routes_cards.py` |
| `GET` | `/{card_id}/usage` | `web_routes_cards.py` |
| `PATCH` | `/{card_id}/notes` | `web_routes_cards.py` |
| `POST` | `/{card_id}/ban` | `web_routes_cards.py` |
| `POST` | `/batch` | `web_routes_missions.py` |
| `POST` | `/scheduled` | `web_routes_missions.py` |
| `GET` | `/{mission_id}` | `web_routes_missions.py` |
| `POST` | `/{mission_id}/pause` | `web_routes_missions.py` |
| `POST` | `/{mission_id}/resume` | `web_routes_missions.py` |
| `POST` | `/{mission_id}/stop` | `web_routes_missions.py` |
| `GET` | `/{mission_id}/stream` | `web_routes_missions.py` |
| `GET` | `/count` | `web_routes_notifications.py` |
| `POST` | `/{notification_id}/read` | `web_routes_notifications.py` |
| `POST` | `/mark-all-read` | `web_routes_notifications.py` |
| `GET` | `/stream` | `web_routes_notifications.py` |
| `POST` | `/select` | `web_routes_prewarm.py` |
| `POST` | `/cancel` | `web_routes_prewarm.py` |
| `GET` | `/status` | `web_routes_prewarm.py` |
| `GET` | `/status` | `web_watchdog.py` |
| `POST` | `/run-now` | `web_watchdog.py` |
| `POST` | `/pause` | `web_watchdog.py` |
| `POST` | `/resume` | `web_watchdog.py` |
<!-- GEN:end:endpoints -->

---

## Variables de entorno `[AUTO]`

<!-- GEN:start:env -->
| Variable | Default | Definida en |
|----------|---------|-------------|
| `BMX_CAPMONSTER_KEY` | `"a9040840fdb3828ecc6090a6010afcad"` | `web_routes_missions.py` |
| `BMX_NO_PROXY` | `"0"` | `web_routes_deposits.py` |
| `BMX_WATCHDOG_INTERVAL_MIN` | `"90"` | `web_watchdog.py` |
| `VAR` | `default` | `scripts/gen_map.py` |
<!-- GEN:end:env -->

---

## Loggers disponibles `[AUTO]`

<!-- GEN:start:loggers -->
| Logger | Módulo |
|--------|--------|
| `betmexico.dashboard` | `app.py` |
| `betmexico.dashboard.deposits` | `deposits.py` |
| `betmexico.dashboard.prewarm` | `prewarm.py` |
| `betmexico.dashboard.sse` | `app.py` |
| `betmexico.web.auth` | `web_auth.py` |
| `betmexico.web.cards` | `web_routes_cards.py` |
| `betmexico.web.deposit` | `web_routes_deposits.py` |
| `betmexico.web.grading` | `web_grading.py` |
| `betmexico.web.logs` | `web_routes_logs.py` |
| `betmexico.web.missions` | `web_routes_missions.py` |
| `betmexico.web.notif` | `web_routes_notifications.py` |
| `betmexico.web.prewarm` | `web_routes_prewarm.py` |
| `betmexico.web.utils` | `web_utils.py` |
| `betmexico.web.watchdog` | `web_watchdog.py` |
| `dashboard.proxy_pool` | `proxy_pool.py` |
| `name` | `scripts/gen_map.py` |
<!-- GEN:end:loggers -->

---

## Logs — dónde viven `[MANUAL]`

| Log | Path en container | Rotación |
|-----|-------------------|----------|
| Dashboard principal | `/data/logs/dashboard.log` | 10 MB × 3 archivos |
| Tail en vivo (UI) | `GET /api/logs/stream` (SSE) | — |
| Ver en dashboard | Pestaña **Logs** | — |
| Logger raíz del dashboard | `betmexico.dashboard` | en app.py L47 |

---

## Directorios críticos `[MANUAL]`

| Directorio (container) | Propósito |
|------------------------|-----------|
| `/data/` | Volumen Docker persistente — BD + logs |
| `/data/logs/` | Log files (RotatingFileHandler) |
| `/data/betmexico_accounts.db` | BD SQLite principal (misma que usa el bot TG) |
| `static/` | Frontend: `index.html`, `app.js`, `style.css` |
| `docs/` | Documentación operativa completa |
| `infra/` | `Dockerfile` + `docker-compose.yml` |
| `scripts/` | Utilerías dev (`recalc_grades.py`, `gen_map.py`) |
| `shared/` | Módulos compartidos con bot Telegram |

---

## Docs de referencia `[MANUAL]`

| Doc | Qué tiene |
|-----|-----------|
| `docs/ARCHITECTURE.md` | Esquema BD, flujos, decisiones de diseño |
| `docs/ENDPOINTS.md` | Referencia completa de endpoints + params |
| `docs/FRONTEND.md` | Handlers JS, componentes UI, secciones HTML |
| `docs/SSE_EVENTS.md` | Catálogo de eventos SSE (kind, payload) |
| `docs/ERRORS.md` | Errores conocidos: síntoma / causa / fix |
| `docs/AUDIT.md` | Estado por función (✅ ❌ ⚠️ 🔵 ❓) |
| `DEPLOY.md` | Protocolo de deploy a KVM4 |
| `docs/protocols/deploy-checklist.md` | Checklist funcional post-deploy |
| `docs/diagrams/` | Flujos Mermaid: deposit-single, deposit-multi, sse-bus, infra |

---

## Notas de sesión `[MANUAL]`

<!-- Apuntes rápidos de sesión activa — borrar entre sesiones -->

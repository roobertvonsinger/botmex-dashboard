# MAP_DEEP — botmex-dashboard
### Mapa de funciones por módulo — leer solo cuando navegas código interno

> Generado por `scripts/gen_map.py`. No editar manualmente.
> Regenerar: `python scripts/gen_map.py`
> Para orientación general (flujos, gotchas, módulos): ver `MAP.md`.

---

## Símbolos por módulo `[AUTO]`

Busca el nombre de la función con Ctrl+F y obtén el rango de líneas exacto.

<!-- GEN:start:simbolos -->

### `app.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `db` | def | L124–L138 |
| `_migrate` | def | L141–L178 |
| `_resolve_operator` | def | L184–L208 |
| `_is_sa` | def | L211–L213 |
| `_visible_emails` | def | L216–L238 |
| `_broadcast` | def | L245–L264 |
| `_dequeue_blocking` | def | L267–L272 |
| `_no_cache_static_assets` | def | L280–L292 |
| `favicon` | def | L300–L301 |
| `login_page` | def | L305–L308 |
| `index` | def | L312–L325 |
| `auth_login` | def | L334–L359 |
| `auth_set_password` | def | L363–L387 |
| `auth_logout` | def | L391–L395 |
| `auth_me` | def | L399–L404 |
| `health` | def | L410–L416 |
| `list_accounts` | def | L420–L509 |
| `list_users` | def | L515–L523 |
| `list_assignments` | def | L527–L548 |
| `AssignRequest` | class | L551–L553 |
| `assign_accounts` | def | L557–L576 |
| `unassign_accounts` | def | L580–L591 |
| `stats` | def | L595–L602 |
| `_wsai_status` | def | L617–L642 |
| `_maybe_alert_broadcast` | def | L649–L666 |
| `_check_one_proxy` | def | L669–L695 |
| `_proxy_health` | def | L698–L747 |
| `_capmonster_balance` | def | L750–L770 |
| `_operator_color` | def | L775–L776 |
| `_resolve_who` | def | L779–L787 |
| `superadmin_kpis` | def | L791–L1034 |
| `RefreshRequest` | class | L1039–L1040 |
| `accounts_refresh` | def | L1044–L1063 |
| `get_logs` | def | L1069–L1094 |
| `_run_health_checks` | def | L1102–L1138 |
| `health_full` | def | L1142–L1143 |
| `_require_sa` | def | L1151–L1153 |
| `admin_diag` | def | L1157–L1188 |
| `admin_ping` | def | L1192–L1213 |
| `admin_refresh_proxy` | def | L1217–L1224 |
| `admin_services_restart` | def | L1228–L1242 |
| `admin_export_logs` | def | L1246–L1258 |
| `admin_pause_state` | def | L1266–L1268 |
| `admin_pause` | def | L1272–L1284 |
| `admin_resume` | def | L1288–L1294 |
| `admin_emergency_stop` | def | L1298–L1333 |
| `admin_vps_reboot` | def | L1337–L1349 |
| `health_last` | def | L1353–L1354 |
| `health_dismiss` | def | L1358–L1361 |
| `_health_loop` | def | L1364–L1374 |
| `_release_account` | def | L1377–L1397 |
| `_run_lock_janitor` | def | L1400–L1448 |
| `_janitor_loop` | def | L1451–L1461 |
| `_run_window_watcher` | def | L1470–L1542 |
| `_window_watcher_loop` | def | L1545–L1554 |
| `_release_watchdog_tick` | def | L1557–L1656 |
| `_release_watchdog_loop` | def | L1659–L1667 |
| `_start_bg_tasks` | def | L1671–L1675 |
| `LockRequest` | class | L1678–L1680 |
| `lock_account` | def | L1684–L1723 |
| `PublishRequest` | class | L1726–L1728 |
| `publish_accounts` | def | L1732–L1755 |
| `hide_all_accounts` | def | L1759–L1771 |
| `pool_accounts` | def | L1775–L1793 |
| `unlock_account` | def | L1797–L1815 |
| `_sse_generator` | def | L1818–L1845 |
| `events` | def | L1849–L1854 |
| `account_cards_pipe` | def | L1858–L1884 |
| `account_notes_summary` | def | L1888–L1913 |
| `account_details` | def | L1917–L2128 |
| `NoteCreate` | class | L2131–L2132 |
| `create_note` | def | L2136–L2165 |
| `CurpUpdate` | class | L2168–L2169 |
| `update_curp` | def | L2173–L2184 |
| `delete_note` | def | L2188–L2200 |
| `CombosRequest` | class | L2203–L2204 |
| `accounts_combos` | def | L2208–L2221 |
| `accounts_pass_map` | def | L2225–L2230 |
| `list_all_cards` | def | L2234–L2309 |
| `activity_feed` | def | L2313–L2430 |
| `list_deposits` | def | L2434–L2463 |
| `deposits_stats` | def | L2467–L2492 |

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

### `autoexclusion.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_decode_jwt_userid` | def | L43–L57 |
| `_parse_resume_date` | def | L60–L71 |
| `check_autoexclusion` | def | L74–L134 |
| `autoexclusion_reason` | def | L137–L142 |
| `mark_account_autoexcluded` | def | L145–L177 |

### `conftest.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `seed_db` | def | L7–L93 |
| `client` | def | L96–L100 |
| `make_client` | def | L103–L115 |

### `deposits.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_is_transient_gateway_error` | def | L44–L54 |
| `_drain_stale_tokens` | def | L81–L113 |
| `_ensure_fresh_captcha` | def | L116–L140 |
| `_record_bin_3ds` | def | L148–L176 |
| `_bin_3ds_stats` | def | L179–L201 |
| `bin_check` | def | L205–L210 |
| `bin_stats_overview` | def | L214–L259 |
| `_auto_lock_for_deposit` | def | L262–L313 |
| `_window_status` | def | L316–L358 |
| `_check_caps` | def | L361–L374 |
| `_load_deps` | def | L377–L388 |
| `_parse_pipe` | def | L391–L412 |
| `_check_card_velocity` | def | L432–L479 |
| `_record_attempt` | def | L482–L592 |
| `_safe_phase` | def | L602–L609 |
| `_build_admin_proxy_url` | def | L612–L616 |
| `_refresh_account_after_deposit` | def | L619–L666 |
| `_run_deposit_with_phases` | def | L669–L1146 |
| `deposit_execute_stream` | def | L1150–L1358 |
| `cap_status` | def | L1362–L1374 |
| `_mm_is_real_decline` | def | L1411–L1417 |
| `_mm_session_get` | def | L1452–L1456 |
| `_mm_session_update` | def | L1459–L1468 |
| `multi_stream` | def | L1472–L1899 |
| `multi_cancel` | def | L1903–L1908 |
| `scheduled_create` | def | L1921–L2213 |
| `scheduled_list` | def | L2217–L2239 |
| `scheduled_cancel` | def | L2243–L2251 |

### `login_orchestrator.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `StickySession` | class | L52–L60 |
| `parse_nodemaven_line` | def | L63–L80 |
| `StickySessionManager` | class | L83–L124 |
| `LoginResult` | class | L129–L141 |
| `_import_get_jwt` | def | L145–L148 |
| `_import_login_primitives` | def | L151–L159 |
| `_classify_dead` | def | L162–L174 |
| `_pool_session` | def | L177–L188 |
| `_jitter_base` | def | L191–L198 |
| `gentle_login` | def | L202–L379 |

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
| `_run_prewarm` | def | L322–L455 |
| `prewarm_select` | def | L461–L531 |
| `prewarm_cancel` | def | L535–L545 |
| `prewarm_status` | def | L549–L564 |
| `prewarm_refresh_stream` | def | L570–L692 |

### `proxy_pool.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_bot_proxies` | def | L97–L103 |
| `all_proxies` | def | L106–L114 |
| `_to_url` | def | L117–L127 |
| `get_admin_proxy` | def | L130–L135 |
| `build_admin_proxy_url` | def | L138–L141 |
| `shuffled_proxy_urls` | def | L144–L152 |
| `_retry_exceptions` | def | L160–L186 |
| `_proxy_host` | def | L189–L193 |
| `call_with_proxy_failover` | def | L196–L287 |
| `_looks_like_proxy_failure_result` | def | L296–L315 |
| `_looks_like_captcha_failure_result` | def | L318–L333 |

### `scripts/gen_map.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_collect_modules` | def | L21–L27 |
| `_read` | def | L34–L35 |
| `extract_symbols` | def | L38–L49 |
| `extract_env_vars` | def | L52–L55 |
| `extract_loggers` | def | L58–L59 |
| `extract_endpoints` | def | L62–L65 |
| `extract_constants` | def | L68–L77 |
| `_is_operational_value` | def | L80–L89 |
| `_read_existing_propositos` | def | L94–L112 |
| `gen_modulos` | def | L117–L128 |
| `gen_constantes` | def | L131–L141 |
| `gen_env` | def | L144–L157 |
| `gen_recientes` | def | L160–L176 |
| `gen_simbolos` | def | L181–L193 |
| `gen_endpoints` | def | L196–L205 |
| `gen_loggers` | def | L208–L220 |
| `_apply_sections` | def | L462–L478 |

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

### `test_a1_estados.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_ins` | def | L34–L40 |
| `a1` | def | L43–L57 |
| `test_release_account_atomico_y_republica` | def | L60–L87 |
| `test_backfill_legacy_no_toca_reservada_sa` | def | L90–L112 |
| `test_backfill_con_locked_at_formato_real_isoformat_tz` | def | L115–L130 |
| `test_janitor_unico_liberador_republica_y_respeta_sa` | def | L133–L151 |
| `test_window_watcher_notifica_normal_pero_no_a_sa_ni_libera` | def | L154–L178 |
| `test_release_watchdog_no_autorelease_y_guard_sa` | def | L181–L198 |
| `test_unlock_manual_republica_via_helper` | def | L201–L224 |
| `_client` | def | L227–L231 |
| `test_lock_sa_override_y_perpetuo` | def | L234–L248 |
| `test_lock_operador_409_si_ocupada_y_temporal_si_libre` | def | L251–L267 |
| `test_publish_hide_no_oculta_cuentas_en_uso` | def | L270–L286 |
| `test_auto_lock_deposit_sa_perpetuo_operador_temporal` | def | L289–L305 |

### `test_a21_visibilidad.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `test_visible_emails_sa_sees_all` | def | L6–L9 |
| `test_visible_emails_operator_scoped` | def | L11–L15 |
| `test_cards_all_sa_sees_both` | def | L19–L23 |
| `test_cards_all_operator_scoped` | def | L25–L30 |
| `test_pass_map_operator_scoped` | def | L34–L37 |
| `test_combos_operator_cannot_get_foreign` | def | L39–L43 |
| `test_deposits_operator_only_own` | def | L47–L52 |
| `test_deposits_sa_sees_all` | def | L54–L57 |

### `test_unificacion_sp1.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `test_execute_endpoint_removed` | def | L4–L8 |
| `test_execute_stream_still_registered` | def | L10–L14 |
| `test_multi_and_scheduled_still_registered` | def | L16–L20 |
| `test_load_deps_returns_pool_without_bot_run_deposit` | def | L22–L28 |
| `test_legacy_modules_archived` | def | L32–L39 |
| `test_no_live_import_of_legacy` | def | L41–L49 |

### `test_unificacion_sp2.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `test_session_get_empty` | def | L4–L5 |
| `test_session_get_returns_cached` | def | L8–L10 |
| `test_update_caches_on_first_success` | def | L13–L17 |
| `test_update_does_not_overwrite_existing` | def | L20–L24 |
| `test_update_invalidates_on_401` | def | L27–L32 |
| `test_update_keeps_session_on_normal_rejection` | def | L35–L41 |
| `test_update_invalidates_on_bare_401` | def | L44–L48 |
| `test_update_invalidates_on_redirectlogin` | def | L51–L55 |

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

### `web_utils.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_sha256` | def | L33–L35 |
| `compute_card_fingerprint` | def | L38–L41 |
| `parse_pipe_card` | def | L44–L120 |
| `_friendly_error` | def | L123–L138 |
| `_normalize_ccexp` | def | L141–L147 |
| `canonical_card_pipe` | def | L150–L169 |
| `_build_proxy_url` | def | L172–L176 |
| `_extract_user_from_message` | def | L179–L198 |
| `_categorize_event` | def | L201–L221 |
| `_parse_log_entry` | def | L224–L265 |
<!-- GEN:end:simbolos -->

---

## Endpoints completos `[AUTO]`

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
| `GET` | `/bin-stats` | `deposits.py` |
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
<!-- GEN:end:endpoints -->

---

## Loggers `[AUTO]`

<!-- GEN:start:loggers -->
| Logger | Módulo |
|--------|--------|
| `betmexico.dashboard` | `app.py` |
| `betmexico.dashboard.autoexclusion` | `autoexclusion.py` |
| `betmexico.dashboard.deposits` | `deposits.py` |
| `betmexico.dashboard.login_orch` | `login_orchestrator.py` |
| `betmexico.dashboard.prewarm` | `prewarm.py` |
| `betmexico.dashboard.sse` | `app.py` |
| `betmexico.web.auth` | `web_auth.py` |
| `betmexico.web.grading` | `web_grading.py` |
| `betmexico.web.utils` | `web_utils.py` |
| `dashboard.proxy_pool` | `proxy_pool.py` |
<!-- GEN:end:loggers -->

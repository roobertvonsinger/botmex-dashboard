# MAP_DEEP — botmex-dashboard
### Mapa de funciones por módulo — leer solo cuando navegas código interno

> Generado por `scripts/gen_map.py`. No editar manualmente.
> Regenerar: `python scripts/gen_map.py`
> Para orientación general (flujos, gotchas, módulos): ver `MAP.md`.

---

## Símbolos por módulo `[AUTO]`

Busca el nombre de la función con Ctrl+F y obtén el rango de líneas exacto.

<!-- GEN:start:simbolos -->

### `_test_token_reuse.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_short` | def | L43–L51 |
| `solve_token` | def | L54–L62 |
| `attempt` | def | L65–L74 |
| `run_block` | def | L77–L109 |
| `verdict` | def | L112–L141 |
| `main` | def | L144–L172 |

### `app.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `db` | def | L124–L138 |
| `_migrate` | def | L141–L165 |
| `_resolve_operator` | def | L171–L195 |
| `_broadcast` | def | L202–L221 |
| `_dequeue_blocking` | def | L224–L229 |
| `_no_cache_static_assets` | def | L237–L249 |
| `favicon` | def | L257–L258 |
| `login_page` | def | L262–L265 |
| `index` | def | L269–L282 |
| `auth_login` | def | L291–L316 |
| `auth_set_password` | def | L320–L344 |
| `auth_logout` | def | L348–L352 |
| `auth_me` | def | L356–L361 |
| `health` | def | L367–L373 |
| `list_accounts` | def | L377–L466 |
| `list_users` | def | L472–L480 |
| `list_assignments` | def | L484–L505 |
| `AssignRequest` | class | L508–L510 |
| `assign_accounts` | def | L514–L533 |
| `unassign_accounts` | def | L537–L548 |
| `stats` | def | L552–L559 |
| `_wsai_status` | def | L571–L596 |
| `_maybe_alert_broadcast` | def | L603–L620 |
| `_check_one_proxy` | def | L623–L648 |
| `_proxy_health` | def | L651–L696 |
| `_capmonster_balance` | def | L699–L719 |
| `_operator_color` | def | L724–L725 |
| `_resolve_who` | def | L728–L736 |
| `superadmin_kpis` | def | L740–L983 |
| `RefreshRequest` | class | L988–L989 |
| `accounts_refresh` | def | L993–L1012 |
| `get_logs` | def | L1018–L1043 |
| `_run_health_checks` | def | L1051–L1087 |
| `health_full` | def | L1091–L1092 |
| `_require_sa` | def | L1100–L1102 |
| `admin_diag` | def | L1106–L1137 |
| `admin_ping` | def | L1141–L1162 |
| `admin_refresh_proxy` | def | L1166–L1173 |
| `admin_services_restart` | def | L1177–L1191 |
| `admin_export_logs` | def | L1195–L1207 |
| `admin_pause_state` | def | L1215–L1217 |
| `admin_pause` | def | L1221–L1233 |
| `admin_resume` | def | L1237–L1243 |
| `admin_emergency_stop` | def | L1247–L1282 |
| `admin_vps_reboot` | def | L1286–L1298 |
| `health_last` | def | L1302–L1303 |
| `health_dismiss` | def | L1307–L1310 |
| `_health_loop` | def | L1313–L1323 |
| `_run_lock_janitor` | def | L1326–L1384 |
| `_janitor_loop` | def | L1387–L1397 |
| `_run_window_watcher` | def | L1406–L1480 |
| `_window_watcher_loop` | def | L1483–L1492 |
| `_release_watchdog_tick` | def | L1495–L1611 |
| `_release_watchdog_loop` | def | L1614–L1622 |
| `_start_bg_tasks` | def | L1626–L1630 |
| `LockRequest` | class | L1633–L1635 |
| `lock_account` | def | L1639–L1667 |
| `PublishRequest` | class | L1670–L1672 |
| `publish_accounts` | def | L1676–L1691 |
| `hide_all_accounts` | def | L1695–L1706 |
| `pool_accounts` | def | L1710–L1728 |
| `unlock_account` | def | L1732–L1759 |
| `_sse_generator` | def | L1762–L1789 |
| `events` | def | L1793–L1798 |
| `account_cards_pipe` | def | L1802–L1827 |
| `account_notes_summary` | def | L1831–L1856 |
| `account_details` | def | L1860–L2071 |
| `NoteCreate` | class | L2074–L2075 |
| `create_note` | def | L2079–L2108 |
| `CurpUpdate` | class | L2111–L2112 |
| `update_curp` | def | L2116–L2127 |
| `delete_note` | def | L2131–L2143 |
| `CombosRequest` | class | L2146–L2147 |
| `accounts_combos` | def | L2151–L2160 |
| `accounts_pass_map` | def | L2164–L2168 |
| `list_all_cards` | def | L2172–L2242 |
| `activity_feed` | def | L2246–L2363 |
| `list_deposits` | def | L2367–L2392 |
| `deposits_stats` | def | L2396–L2421 |

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
| `seed_db` | def | L7–L72 |
| `client` | def | L75–L79 |

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
| `_auto_lock_for_deposit` | def | L262–L311 |
| `_window_status` | def | L314–L356 |
| `_check_caps` | def | L359–L372 |
| `_load_deps` | def | L375–L386 |
| `_parse_pipe` | def | L389–L410 |
| `_check_card_velocity` | def | L430–L477 |
| `_record_attempt` | def | L480–L590 |
| `_safe_phase` | def | L600–L607 |
| `_build_admin_proxy_url` | def | L610–L614 |
| `_refresh_account_after_deposit` | def | L617–L664 |
| `_run_deposit_with_phases` | def | L667–L1143 |
| `deposit_execute_stream` | def | L1147–L1355 |
| `cap_status` | def | L1359–L1371 |
| `multi_stream` | def | L1403–L1773 |
| `multi_cancel` | def | L1777–L1782 |
| `scheduled_create` | def | L1795–L2087 |
| `scheduled_list` | def | L2091–L2113 |
| `scheduled_cancel` | def | L2117–L2125 |

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
| `_bot_proxies` | def | L96–L102 |
| `all_proxies` | def | L105–L113 |
| `_to_url` | def | L116–L126 |
| `get_admin_proxy` | def | L129–L134 |
| `build_admin_proxy_url` | def | L137–L140 |
| `shuffled_proxy_urls` | def | L143–L151 |
| `_retry_exceptions` | def | L159–L185 |
| `_proxy_host` | def | L188–L192 |
| `call_with_proxy_failover` | def | L195–L286 |
| `_looks_like_proxy_failure_result` | def | L295–L314 |
| `_looks_like_captcha_failure_result` | def | L317–L332 |

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
| `_apply_sections` | def | L464–L480 |

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

### `test_unificacion_sp1.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `test_execute_endpoint_removed` | def | L4–L8 |
| `test_execute_stream_still_registered` | def | L10–L14 |
| `test_multi_and_scheduled_still_registered` | def | L16–L20 |
| `test_load_deps_returns_pool_without_bot_run_deposit` | def | L22–L28 |

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
<!-- GEN:end:loggers -->

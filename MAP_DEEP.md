# MAP_DEEP — botmex-dashboard
### Mapa de funciones por módulo — leer solo cuando navegas código interno

> Generado por `scripts/gen_map.py`. No editar manualmente.
> Regenerar: `python scripts/gen_map.py`
> Para orientación general (flujos, gotchas, módulos): ver `MAP.md`.

---

## Símbolos por módulo `[AUTO]`

Busca el nombre de la función con Ctrl+F y obtén el rango de líneas exacto.

<!-- GEN:start:simbolos -->

### `account_refresh.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_sa_lock_tokens` | def | L45–L70 |
| `_env_int` | def | L73–L77 |
| `cfg` | def | L80–L95 |
| `select_refresh_candidates_healthy` | def | L99–L150 |
| `_exp_int` | def | L153–L159 |
| `is_hot_account` | def | L162–L179 |
| `_load_candidate_rows` | def | L202–L226 |
| `_db_get_withdrawal_ready` | def | L229–L236 |
| `_db_set_withdrawal_ready` | def | L239–L248 |
| `run_refresh_cycle` | def | L252–L448 |
| `run_refresh_cycle_from_env` | def | L451–L458 |
| `_load_pending_withdrawals` | def | L473–L482 |
| `_resolve_pending_withdrawals` | def | L485–L573 |
| `_withdrawal_resolution_loop` | def | L576–L592 |

### `app.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `db` | def | L172–L225 |
| `_db_write_with_retry` | def | L228–L260 |
| `_migrate` | def | L263–L521 |
| `_backfill_grades_v10_m7` | def | L524–L595 |
| `_resolve_operator` | def | L601–L625 |
| `_is_sa` | def | L628–L630 |
| `_visible_emails` | def | L633–L655 |
| `_broadcast` | def | L662–L680 |
| `_dequeue_blocking` | def | L683–L688 |
| `_is_maintenance_active` | def | L697–L700 |
| `_maintenance_gate_middleware` | def | L703–L731 |
| `_no_cache_static_assets` | def | L735–L747 |
| `favicon` | def | L762–L763 |
| `maintenance_page` | def | L767–L768 |
| `login_page` | def | L772–L776 |
| `_asset_mtimes` | def | L793–L800 |
| `_frontend_version` | def | L803–L807 |
| `_own_portal_path` | def | L810–L811 |
| `_render_frontend_html` | def | L814–L838 |
| `user_portal_page` | def | L842–L857 |
| `portal_page` | def | L861–L868 |
| `dashboard_page` | def | L872–L886 |
| `index` | def | L890–L899 |
| `username_portal_page` | def | L903–L929 |
| `api_version` | def | L933–L943 |
| `auth_login` | def | L952–L983 |
| `auth_set_password` | def | L987–L1011 |
| `auth_logout` | def | L1015–L1019 |
| `auth_me` | def | L1023–L1033 |
| `health` | def | L1039–L1045 |
| `_build_search_clause` | def | L1048–L1092 |
| `list_accounts` | def | L1096–L1244 |
| `list_users` | def | L1250–L1258 |
| `list_assignments` | def | L1262–L1283 |
| `AssignRequest` | class | L1286–L1288 |
| `assign_accounts` | def | L1292–L1311 |
| `unassign_accounts` | def | L1315–L1326 |
| `stats` | def | L1330–L1337 |
| `_wsai_status` | def | L1352–L1377 |
| `_maybe_alert_broadcast` | def | L1384–L1401 |
| `_check_one_proxy` | def | L1404–L1430 |
| `_proxy_health` | def | L1433–L1482 |
| `_capmonster_balance` | def | L1485–L1505 |
| `_operator_color` | def | L1510–L1525 |
| `_resolve_who` | def | L1528–L1541 |
| `_event_visible_to` | def | L1544–L1570 |
| `superadmin_kpis` | def | L1574–L1817 |
| `RefreshRequest` | class | L1822–L1823 |
| `accounts_refresh` | def | L1827–L1846 |
| `_tail_log_file` | def | L1873–L1901 |
| `get_logs` | def | L1905–L1927 |
| `get_logs_telegram` | def | L1941–L1987 |
| `_run_health_checks` | def | L1995–L2031 |
| `health_full` | def | L2035–L2036 |
| `_require_sa` | def | L2044–L2046 |
| `admin_diag` | def | L2050–L2081 |
| `admin_ping` | def | L2085–L2106 |
| `admin_refresh_proxy` | def | L2110–L2117 |
| `admin_services_restart` | def | L2121–L2142 |
| `admin_export_logs` | def | L2146–L2162 |
| `admin_pause_state` | def | L2170–L2172 |
| `admin_pause` | def | L2176–L2188 |
| `admin_resume` | def | L2192–L2198 |
| `admin_emergency_stop` | def | L2202–L2237 |
| `admin_vps_reboot` | def | L2241–L2253 |
| `health_last` | def | L2257–L2258 |
| `health_dismiss` | def | L2262–L2265 |
| `api_marks_list` | def | L2269–L2276 |
| `api_marks_toggle` | def | L2280–L2298 |
| `api_recent` | def | L2302–L2374 |
| `api_accounts_at_hand` | def | L2378–L2486 |
| `_health_loop` | def | L2489–L2499 |
| `_release_account` | def | L2502–L2523 |
| `_run_lock_janitor` | def | L2526–L2574 |
| `_janitor_loop` | def | L2577–L2587 |
| `_run_window_watcher` | def | L2596–L2668 |
| `_window_watcher_loop` | def | L2671–L2680 |
| `_release_watchdog_tick` | def | L2683–L2782 |
| `_release_watchdog_loop` | def | L2785–L2793 |
| `_jwt_keepalive_loop` | def | L2796–L2824 |
| `_wake_jwt_keeper` | def | L2831–L2842 |
| `_account_refresh_loop` | def | L2845–L2863 |
| `_bot_token` | def | L2869–L2878 |
| `_notify_robert` | def | L2881–L2896 |
| `_startup_telegram_notify` | def | L2899–L2923 |
| `_lifespan` | def | L2927–L2938 |
| `LockRequest` | class | L2944–L2946 |
| `lock_account` | def | L2950–L2989 |
| `PublishRequest` | class | L2992–L2994 |
| `publish_accounts` | def | L2998–L3027 |
| `hide_all_accounts` | def | L3031–L3046 |
| `pool_accounts` | def | L3050–L3068 |
| `api_pool_split` | def | L3072–L3086 |
| `api_pool_publish` | def | L3090–L3117 |
| `unlock_account` | def | L3121–L3139 |
| `_sse_generator` | def | L3142–L3171 |
| `events` | def | L3175–L3185 |
| `account_cards_pipe` | def | L3189–L3215 |
| `account_notes_summary` | def | L3219–L3244 |
| `_record_account_touch` | def | L3247–L3280 |
| `account_find_id` | def | L3284–L3290 |
| `account_refresh_api` | def | L3294–L3400 |
| `account_details` | def | L3404–L3795 |
| `NoteCreate` | class | L3798–L3799 |
| `create_note` | def | L3803–L3832 |
| `CurpUpdate` | class | L3835–L3836 |
| `update_curp` | def | L3840–L3851 |
| `get_clabes` | def | L3861–L3870 |
| `refresh_clabes` | def | L3874–L3884 |
| `_persist_withdrawal` | def | L3893–L3939 |
| `withdraw` | def | L3943–L3995 |
| `withdraw_status` | def | L3999–L4062 |
| `delete_note` | def | L4066–L4078 |
| `CombosRequest` | class | L4081–L4082 |
| `accounts_combos` | def | L4086–L4099 |
| `accounts_pass_map` | def | L4103–L4108 |
| `list_all_cards` | def | L4112–L4188 |
| `activity_feed` | def | L4192–L4289 |
| `list_deposits` | def | L4293–L4322 |
| `deposits_stats` | def | L4326–L4351 |
| `_persist_auto_mission` | def | L4359–L4389 |
| `admin_maintenance_state` | def | L4393–L4396 |
| `MaintenanceToggleRequest` | class | L4399–L4400 |
| `admin_maintenance_toggle` | def | L4404–L4425 |
| `auto_deposit_create` | def | L4429–L4465 |
| `auto_deposit_cancel` | def | L4469–L4495 |
| `emergency_stop_all_deposits` | def | L4499–L4530 |
| `operator_my_accounts` | def | L4534–L4624 |
| `operator_release_account` | def | L4628–L4645 |
| `operator_withdraw` | def | L4649–L4707 |
| `operator_auto_withdraw` | def | L4711–L4747 |
| `auto_deposit_confirm` | def | L4751–L4770 |
| `operator_missions` | def | L4774–L4792 |
| `operator_recent_ticker` | def | L4796–L4921 |
| `auto_deposit_status` | def | L4925–L4936 |
| `register_operator_strike` | def | L4939–L4972 |
| `bot_start_info` | def | L4976–L5012 |
| `bot_operator_info` | def | L5016–L5055 |
| `bot_help_info` | def | L5059–L5073 |
| `bot_pause_mission` | def | L5077–L5106 |
| `bot_resume_mission` | def | L5110–L5128 |
| `bot_cancel_mission` | def | L5133–L5168 |
| `bot_bet_create` | def | L5172–L5342 |
| `filter_and_sanitize_check_combos` | def | L5345–L5430 |
| `BotCheckRequest` | class | L5433–L5437 |
| `bot_check` | def | L5440–L5521 |

### `auth.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `load_users` | def | L31–L53 |
| `save_users` | def | L55–L63 |
| `_UsersDictProxy` | class | L65–L90 |
| `add_user` | def | L94–L115 |
| `sha256` | def | L122–L123 |
| `load_passwords` | def | L126–L149 |
| `save_passwords` | def | L152–L160 |
| `_is_persistent` | def | L170–L171 |
| `_load_persistent_sessions` | def | L174–L180 |
| `_save_persistent_sessions` | def | L183–L189 |
| `_prune` | def | L195–L204 |
| `session_max_age` | def | L207–L209 |
| `create_session` | def | L212–L225 |
| `get_session` | def | L228–L237 |
| `delete_session` | def | L240–L243 |
| `require_session` | def | L247–L255 |
| `require_operator_view` | def | L258–L287 |

### `auto_deposit.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_now_epoch` | def | L27–L28 |
| `_grade_rank` | def | L31–L34 |
| `_sa_tokens` | def | L37–L48 |
| `_cd_active` | def | L51–L67 |
| `_exp_int` | def | L70–L76 |
| `_bin_of` | def | L79–L81 |
| `_approval_rate` | def | L84–L90 |
| `_threeds_recent` | def | L93–L107 |
| `_rank_key` | def | L110–L113 |
| `_pipe_str` | def | L116–L121 |
| `_extract_card_number` | def | L124–L131 |
| `_parse_card_pipe` | def | L134–L167 |
| `_normalize_pipe_to_3part` | def | L170–L172 |
| `_get_married_card_owners` | def | L175–L209 |
| `_has_card_deposit_24h` | def | L212–L228 |
| `select_accounts_for_auto` | def | L237–L452 |
| `_max_accounts_for_cards` | def | L461–L469 |
| `plan_auto_mission` | def | L472–L908 |
| `_fake_progress_pct` | def | L951–L982 |
| `_iso` | def | L986–L987 |
| `_m_load` | def | L990–L998 |
| `_m_status` | def | L1001–L1003 |
| `_m_update` | def | L1006–L1016 |
| `_fetch_account` | def | L1019–L1026 |
| `_is_account_dead` | def | L1029–L1040 |
| `_unlock` | def | L1043–L1052 |
| `_broadcast_mission` | def | L1055–L1084 |
| `_stop_pool` | def | L1087–L1094 |
| `run_auto_mission` | def | L1098–L2093 |

### `autoexclusion.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_decode_jwt_userid` | def | L43–L57 |
| `_parse_resume_date` | def | L60–L71 |
| `check_autoexclusion` | def | L74–L134 |
| `autoexclusion_reason` | def | L137–L142 |
| `mark_account_autoexcluded` | def | L145–L177 |

### `betmexico_config.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `now_mx` | def | L39–L41 |
| `user_tag` | def | L68–L72 |
| `is_admin` | def | L75–L77 |
| `is_subadmin` | def | L80–L82 |
| `is_any_admin` | def | L85–L87 |
| `is_authorized` | def | L90–L91 |
| `get_admin_proxy` | def | L146–L148 |
| `parse_user_proxy` | def | L151–L162 |
| `get_user_proxy` | def | L165–L178 |
| `_get_solver_for_user` | def | L181–L183 |

### `betmexico_db.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `BetmexicoDB` | class | L29–L2957 |

### `betmexico_deposit.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_proxy_url` | def | L38–L45 |
| `begin_deposit` | def | L57–L78 |
| `submit_card` | def | L81–L105 |
| `check_transaction` | def | L108–L121 |
| `get_account_jwt` | def | L124–L161 |
| `execute_single_deposit` | def | L164–L250 |
| `_run_single_deposit_task` | def | L257–L296 |
| `_run_scheduled_deposits_task` | def | L299–L376 |
| `_build_amount_keyboard` | def | L383–L389 |
| `_build_mode_keyboard` | def | L392–L397 |
| `_get_deposit_target` | def | L400–L402 |
| `depositar_hit_cb` | def | L409–L433 |
| `depositar_start_cb` | def | L436–L486 |
| `deposit_use_saved_card_cb` | def | L489–L523 |
| `deposit_new_card_cb` | def | L526–L542 |
| `deposit_card_received` | def | L545–L616 |
| `deposit_amount_quick_cb` | def | L619–L641 |
| `deposit_custom_amount_cb` | def | L644–L649 |
| `deposit_custom_amount_received` | def | L652–L678 |
| `deposit_mode_single_cb` | def | L681–L720 |
| `deposit_mode_scheduled_cb` | def | L723–L739 |
| `deposit_schedule_received` | def | L742–L797 |
| `deposit_cancel_cb` | def | L800–L806 |
| `_register_card_marriage` | def | L813–L825 |
| `_clear_deposit_context` | def | L828–L831 |
| `dep_command` | def | L838–L958 |

### `betmexico_login_api.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `now_mx` | def | L24–L26 |
| `_decode_jwt_payload` | def | L34–L42 |
| `CaptchaHubSolverFast` | class | L88–L130 |
| `AntiCaptchaSolverFast` | class | L133–L239 |
| `TwoCaptchaSolverFast` | class | L242–L331 |
| `create_solver` | def | L334–L340 |
| `CapMonsterSolverFast` | class | L347–L415 |
| `BetmexicoApiChecker` | class | L418–L939 |
| `CaptchaTokenPool` | class | L945–L1138 |

### `betmexico_login_service.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `make_pool` | def | L33–L53 |
| `_persist_jwt_cache` | def | L56–L70 |
| `get_jwt` | def | L73–L144 |

### `betmexico_payment_analyzer.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_get_grade` | def | L55–L59 |
| `_activity_suffix` | def | L62–L71 |
| `_parse_txn_date` | def | L74–L87 |
| `_parse_deposit_date` | def | L90–L103 |
| `_get_txn_fields` | def | L106–L117 |
| `_is_card_deposit` | def | L120–L123 |
| `_group_into_sessions` | def | L126–L169 |
| `score_payment_readiness` | def | L177–L329 |
| `analyze_gateway_ban_pattern` | def | L336–L406 |
| `generate_payment_analysis_summary` | def | L413–L461 |
| `generate_payment_ready_txt` | def | L464–L492 |

### `betmexico_utils.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `UserSession` | class | L46–L121 |
| `get_session` | def | L127–L132 |
| `reset_session` | def | L135–L140 |
| `safe_edit` | def | L147–L179 |
| `safe_reply` | def | L182–L223 |
| `safe_send_document` | def | L226–L240 |
| `_safe_answer` | def | L243–L247 |
| `smart_parse_combos` | def | L254–L293 |
| `parse_uploaded_file` | def | L296–L344 |
| `flush_live_to_db` | def | L347–L355 |
| `_sanitize_combo` | def | L362–L363 |
| `_md_escape` | def | L366–L370 |
| `_md_v1_safe` | def | L373–L379 |
| `format_account_card` | def | L382–L477 |
| `_format_card_masked` | def | L480–L483 |
| `_format_card_stats_text` | def | L486–L494 |
| `_format_txn_button` | def | L500–L506 |
| `_txn_status_to_result` | def | L509–L510 |
| `_parse_card_input` | def | L513–L611 |
| `_sanitize_proxy_url` | def | L614–L624 |
| `_results_to_accounts` | def | L627–L650 |
| `_build_proxy_keyboard` | def | L657–L663 |
| `_show_main_menu` | def | L670–L722 |
| `back_to_menu` | def | L725–L745 |
| `proxy_setup_cb` | def | L752–L775 |
| `proxy_edit_cb` | def | L778–L798 |
| `receive_user_proxies` | def | L801–L843 |
| `proxy_howto_cb` | def | L846–L865 |
| `myinfo_cb` | def | L874–L982 |
| `info_command` | def | L985–L987 |
| `help_command` | def | L990–L1032 |
| `luhn_check` | def | L1035–L1049 |
| `cc_command` | def | L1051–L1143 |
| `restart_command` | def | L1146–L1159 |

### `bin_intelligence.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `lookup_bin_metadata` | def | L94–L122 |
| `classify_bin_tier` | def | L125–L169 |
| `fetch_bin_stats_from_db` | def | L172–L196 |
| `_query_bin_rows` | def | L199–L242 |
| `get_bin_intelligence_summary` | def | L245–L276 |
| `format_telegram_start_banner` | def | L279–L299 |
| `format_telegram_bet_warning` | def | L302–L337 |
| `format_telegram_radar_full` | def | L340–L371 |
| `get_single_card_bin_badge` | def | L374–L404 |
| `get_random_tactical_tip` | def | L407–L457 |
| `fetch_operator_personal_stats` | def | L460–L502 |
| `_query_operator_stats` | def | L505–L635 |
| `format_telegram_operator_stats` | def | L638–L669 |
| `get_bin_compatibility_tier` | def | L672–L700 |

### `card_checker.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_load_ruthopia_dashboard_token` | def | L29–L66 |
| `ruthopia_bridge_check` | def | L69–L106 |
| `check_luhn` | def | L109–L122 |
| `parse_and_validate_card_pipe` | def | L125–L174 |
| `check_ruthopia_db_liveness` | def | L182–L238 |
| `perform_wabox_liveness_check` | def | L241–L367 |
| `get_card_declines_24h` | def | L370–L404 |
| `_get_app_db` | def | L407–L425 |
| `precheck_card_liveness` | def | L428–L568 |
| `format_ruthopia_liveness_summary` | def | L571–L614 |

### `clabe_fetch.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_load_jwt_for_account` | def | L37–L62 |
| `_get_admin_proxy_url` | def | L65–L72 |
| `fetch_clabes_from_betmexico` | def | L75–L99 |
| `_persist_clabes` | def | L102–L140 |
| `get_saved_clabes` | def | L143–L159 |
| `refresh_clabes_for_account` | def | L162–L188 |

### `conftest.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `seed_db` | def | L13–L154 |
| `client` | def | L157–L161 |
| `make_client` | def | L164–L176 |
| `mock_bmx_transport` | def | L180–L190 |
| `OutgoingNetworkBlockedError` | class | L197–L199 |
| `guard_external_network` | def | L202–L217 |

### `curp_utils.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_normalize_name` | def | L90–L105 |
| `_strip_particles` | def | L108–L111 |
| `_split_fullname` | def | L114–L145 |
| `_first_internal_vowel` | def | L148–L154 |
| `_first_internal_consonant` | def | L157–L163 |
| `_detect_state_code` | def | L166–L186 |
| `_infer_sex` | def | L189–L196 |
| `curp_verifier` | def | L199–L208 |
| `compute_curp` | def | L211–L247 |
| `generate_curp_candidates` | def | L250–L267 |

### `deposits.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `classify_deposit_status` | def | L53–L66 |
| `_cooldown_active` | def | L69–L81 |
| `_save_txns_via_app_db` | def | L84–L116 |
| `_set_account_cooldown` | def | L119–L132 |
| `_mark_rate_limited_dead` | def | L135–L153 |
| `_cooldown_remaining_min` | def | L156–L162 |
| `_is_transient_gateway_error` | def | L165–L175 |
| `_drain_stale_tokens` | def | L205–L237 |
| `_ensure_fresh_captcha` | def | L240–L264 |
| `_record_bin_3ds` | def | L272–L300 |
| `_bin_3ds_stats` | def | L303–L325 |
| `bin_check` | def | L329–L339 |
| `bin_recommendations` | def | L343–L347 |
| `bin_stats_overview` | def | L351–L420 |
| `_auto_lock_for_deposit` | def | L423–L479 |
| `_window_status` | def | L482–L524 |
| `_check_caps` | def | L527–L543 |
| `_check_card_mixing_on_active_balance` | def | L546–L619 |
| `_load_deps` | def | L622–L633 |
| `_parse_pipe` | def | L636–L657 |
| `_check_card_velocity` | def | L677–L724 |
| `_has_recent_approved_deposit` | def | L727–L743 |
| `_record_attempt` | def | L746–L942 |
| `_safe_phase` | def | L952–L959 |
| `_now_mx_str` | def | L967–L976 |
| `_deposit_step_payload` | def | L985–L993 |
| `_wrap_deposit_step` | def | L996–L1015 |
| `_build_admin_proxy_url` | def | L1018–L1022 |
| `_refresh_account_after_deposit` | def | L1025–L1084 |
| `_should_relogin_after_401` | def | L1087–L1091 |
| `_acquire_session_and_begin` | def | L1094–L1380 |
| `_run_deposit_with_phases` | def | L1383–L1747 |
| `deposit_execute_stream` | def | L1751–L1953 |
| `cap_status` | def | L1957–L1969 |
| `_mm_is_real_decline` | def | L2009–L2015 |
| `_mm_is_ambiguous_charge` | def | L2018–L2028 |
| `classify_deposit_status` | def | L2031–L2062 |
| `_mm_session_get` | def | L2105–L2109 |
| `_mm_session_update` | def | L2112–L2121 |
| `multi_stream` | def | L2125–L2648 |
| `multi_cancel` | def | L2652–L2657 |
| `scheduled_create` | def | L2670–L3034 |
| `scheduled_list` | def | L3038–L3060 |
| `scheduled_cancel` | def | L3064–L3072 |

### `jwt_keeper.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_env_int` | def | L38–L42 |
| `cfg` | def | L45–L87 |
| `select_refresh_candidates` | def | L91–L172 |
| `_exp_int` | def | L175–L181 |
| `_load_candidate_rows` | def | L199–L241 |
| `_set_cooldown` | def | L244–L251 |
| `_bump_rl_streak` | def | L254–L268 |
| `_reset_rl_streak` | def | L271–L278 |
| `run_keepalive_cycle` | def | L282–L379 |
| `run_keepalive_cycle_from_env` | def | L382–L389 |

### `login_orchestrator.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `StickySession` | class | L17–L24 |
| `LoginResult` | class | L28–L42 |
| `StickySessionManager` | class | L45–L56 |
| `_classify_dead` | def | L59–L70 |
| `gentle_login` | def | L73–L207 |

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
| `_fetch_looks_empty` | def | L178–L195 |
| `_db_upsert_balance` | def | L198–L265 |
| `_db_save_txns_and_recalc` | def | L268–L321 |
| `_db_update_last_checked` | def | L324–L336 |
| `_db_invalidate_jwt` | def | L339–L350 |
| `_db_mark_dead` | def | L353–L379 |
| `_is_balance_fresh` | def | L382–L390 |
| `_capmonster_balance` | def | L395–L411 |
| `_run_prewarm` | def | L416–L598 |
| `prewarm_select` | def | L604–L688 |
| `prewarm_cancel` | def | L692–L702 |
| `prewarm_status` | def | L706–L721 |
| `prewarm_refresh_stream` | def | L727–L918 |

### `renapo_validator.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_host_of` | def | L45–L47 |
| `_host_resolves` | def | L50–L61 |
| `_check_curp_with_proxy` | def | L64–L94 |
| `validate_renapo_curp` | def | L97–L148 |
| `_fallback` | def | L151–L154 |

### `saneador_daemon.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `get_db` | def | L33–L38 |
| `audit_single_account` | def | L40–L175 |
| `run_sanitizer_batch` | def | L177–L267 |

### `scripts/backfill_account_cards.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_parse_pipe` | def | L34–L49 |
| `_roster` | def | L52–L63 |
| `main` | def | L66–L119 |

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

### `scripts/migrate_status_no_banco.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `reclassify` | def | L39–L58 |
| `_main` | def | L61–L76 |

### `scripts/recalc_grades.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_import_analyzer` | def | L21–L40 |
| `main` | def | L43–L132 |

### `scripts/verify_all_accounts_active.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `get_db_connection` | def | L31–L38 |
| `get_target_accounts` | def | L41–L48 |
| `mark_account_dead` | def | L51–L65 |
| `main` | def | L68–L136 |

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
| `score_payment_readiness` | def | L247–L429 |
| `analyze_gateway_ban_pattern` | def | L436–L506 |
| `generate_payment_analysis_summary` | def | L513–L561 |
| `generate_payment_ready_txt` | def | L564–L592 |

### `web_auth.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_WebUsersRawProxy` | class | L21–L34 |
| `_WebUsersProxy` | class | L36–L43 |
| `_load_passwords` | def | L59–L86 |
| `_save_passwords` | def | L88–L96 |
| `set_session_callback` | def | L101–L103 |
| `authenticate` | def | L105–L149 |
| `require_admin` | def | L151–L154 |
| `require_superadmin` | def | L156–L159 |

### `web_grading.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_load_analyzer` | def | L27–L35 |
| `recalc_grade_from_db` | def | L47–L102 |
| `recalc_grade_from_details` | def | L105–L136 |
| `note_a_plus_outcome` | def | L139–L197 |

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

### `withdrawals.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `WithdrawalError` | class | L55–L56 |
| `JwtExpired` | class | L59–L60 |
| `NoApprovedWithdrawalAccount` | class | L63–L64 |
| `MultipleApprovedAccounts` | class | L67–L68 |
| `InsufficientBalance` | class | L71–L72 |
| `ConcurrentWithdrawalPending` | class | L75–L76 |
| `_auth_headers` | def | L82–L83 |
| `_client_kwargs` | def | L86–L90 |
| `get_bank_accounts` | def | L96–L139 |
| `get_real_balance` | def | L145–L172 |
| `begin_withdrawal` | def | L178–L238 |
| `get_pending_withdrawal` | def | L244–L273 |
| `get_bank_transaction` | def | L279–L374 |
| `_persist_wd_status` | def | L380–L405 |
| `resolve_withdrawal_status` | def | L408–L617 |
| `execute_withdrawal` | def | L623–L720 |
| `_refresh_account_after_withdrawal` | def | L723–L806 |
| `execute_auto_batch_withdrawal` | def | L814–L999 |
<!-- GEN:end:simbolos -->

---

## Endpoints completos `[AUTO]`

<!-- GEN:start:endpoints -->
| Método | Ruta | Módulo |
|--------|------|--------|
| `GET` | `/favicon.ico` | `app.py` |
| `GET` | `/maintenance` | `app.py` |
| `GET` | `/login` | `app.py` |
| `GET` | `/user/{user_id}` | `app.py` |
| `GET` | `/portal` | `app.py` |
| `GET` | `/dashboard` | `app.py` |
| `GET` | `/` | `app.py` |
| `GET` | `/{username}` | `app.py` |
| `GET` | `/api/version` | `app.py` |
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
| `GET` | `/api/logs/telegram` | `app.py` |
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
| `GET` | `/api/marks` | `app.py` |
| `POST` | `/api/marks/toggle` | `app.py` |
| `GET` | `/api/recent` | `app.py` |
| `GET` | `/api/accounts/at-hand` | `app.py` |
| `POST` | `/api/accounts/{account_id}/lock` | `app.py` |
| `POST` | `/api/accounts/publish` | `app.py` |
| `POST` | `/api/accounts/hide-all` | `app.py` |
| `GET` | `/api/pool/accounts` | `app.py` |
| `GET` | `/api/pool/split` | `app.py` |
| `POST` | `/api/pool/publish` | `app.py` |
| `POST` | `/api/accounts/{account_id}/unlock` | `app.py` |
| `GET` | `/api/events` | `app.py` |
| `GET` | `/api/accounts/{account_id}/cards-pipe` | `app.py` |
| `GET` | `/api/accounts/{account_id}/notes-summary` | `app.py` |
| `GET` | `/api/accounts/find-id` | `app.py` |
| `GET` | `/api/accounts/{account_id}/details` | `app.py` |
| `POST` | `/api/accounts/{account_id}/notes` | `app.py` |
| `POST` | `/api/accounts/{account_id}/curp` | `app.py` |
| `GET` | `/api/accounts/{account_id}/clabes` | `app.py` |
| `POST` | `/api/accounts/{account_id}/clabes/refresh` | `app.py` |
| `POST` | `/api/accounts/{account_id}/withdraw` | `app.py` |
| `GET` | `/api/accounts/{account_id}/withdraw/status/{tx_id}` | `app.py` |
| `DELETE` | `/api/accounts/{account_id}/notes/{note_id}` | `app.py` |
| `POST` | `/api/accounts/combos` | `app.py` |
| `GET` | `/api/accounts/pass-map` | `app.py` |
| `GET` | `/api/cards/all` | `app.py` |
| `GET` | `/api/activity` | `app.py` |
| `GET` | `/api/deposits` | `app.py` |
| `GET` | `/api/deposits/stats` | `app.py` |
| `GET` | `/api/admin/maintenance-state` | `app.py` |
| `POST` | `/api/admin/maintenance` | `app.py` |
| `POST` | `/api/deposits/auto` | `app.py` |
| `POST` | `/api/deposits/auto/{mission_id}/cancel` | `app.py` |
| `POST` | `/api/deposits/emergency-stop` | `app.py` |
| `GET` | `/api/operator/my-accounts` | `app.py` |
| `POST` | `/api/operator/accounts/{account_id}/release` | `app.py` |
| `POST` | `/api/operator/accounts/{account_id}/withdraw` | `app.py` |
| `POST` | `/api/operator/accounts/{account_id}/auto-withdraw` | `app.py` |
| `POST` | `/api/deposits/auto/{mission_id}/confirm` | `app.py` |
| `GET` | `/api/operator/missions` | `app.py` |
| `GET` | `/api/operator/recent-ticker` | `app.py` |
| `GET` | `/api/deposits/auto/{mission_id}/status` | `app.py` |
| `GET` | `/api/bot/start` | `app.py` |
| `GET` | `/api/bot/info` | `app.py` |
| `GET` | `/api/bot/help` | `app.py` |
| `POST` | `/api/bot/pause` | `app.py` |
| `POST` | `/api/bot/resume` | `app.py` |
| `POST` | `/api/bot/stop` | `app.py` |
| `POST` | `/api/bot/cancel` | `app.py` |
| `POST` | `/api/bot/bet` | `app.py` |
| `POST` | `/api/bot/check` | `app.py` |
| `GET` | `/bin-check/{bin6}` | `deposits.py` |
| `GET` | `/bin-recommendations` | `deposits.py` |
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
| `betmexico` | `betmexico_config.py` |
| `betmexico.dashboard` | `app.py` |
| `betmexico.dashboard.account_refresh` | `app.py` |
| `betmexico.dashboard.auto_deposit` | `auto_deposit.py` |
| `betmexico.dashboard.autoexclusion` | `autoexclusion.py` |
| `betmexico.dashboard.bin_intelligence` | `bin_intelligence.py` |
| `betmexico.dashboard.card_checker` | `card_checker.py` |
| `betmexico.dashboard.clabe_fetch` | `clabe_fetch.py` |
| `betmexico.dashboard.db` | `app.py` |
| `betmexico.dashboard.deposits` | `deposits.py` |
| `betmexico.dashboard.grading` | `app.py` |
| `betmexico.dashboard.jwt_keeper` | `jwt_keeper.py` |
| `betmexico.dashboard.login_orch` | `login_orchestrator.py` |
| `betmexico.dashboard.prewarm` | `prewarm.py` |
| `betmexico.dashboard.sse` | `app.py` |
| `betmexico.dashboard.withdrawals` | `withdrawals.py` |
| `betmexico.login_service` | `betmexico_login_service.py` |
| `betmexico.renapo_validator` | `renapo_validator.py` |
| `betmexico.web.auth` | `web_auth.py` |
| `betmexico.web.grading` | `web_grading.py` |
| `betmexico.web.utils` | `web_utils.py` |
| `dashboard.proxy_pool` | `proxy_pool.py` |
| `httpcore` | `betmexico_login_api.py` |
| `httpx` | `betmexico_login_api.py` |
| `saneador` | `saneador_daemon.py` |
| `verify_all_accounts` | `scripts/verify_all_accounts_active.py` |
<!-- GEN:end:loggers -->

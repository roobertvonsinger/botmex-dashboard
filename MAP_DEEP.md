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
| `is_hot_account` | def | L162–L181 |
| `_load_candidate_rows` | def | L204–L229 |
| `_db_get_withdrawal_ready` | def | L232–L239 |
| `_db_set_withdrawal_ready` | def | L242–L251 |
| `run_refresh_cycle` | def | L255–L451 |
| `run_refresh_cycle_from_env` | def | L454–L461 |
| `_load_pending_withdrawals` | def | L476–L485 |
| `_resolve_pending_withdrawals` | def | L488–L576 |
| `_withdrawal_resolution_loop` | def | L579–L595 |

### `app.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_migrate` | def | L166–L424 |
| `_backfill_grades_v10_m7` | def | L427–L498 |
| `_resolve_operator` | def | L504–L528 |
| `_is_sa` | def | L531–L533 |
| `_visible_emails` | def | L536–L558 |
| `_broadcast` | def | L565–L583 |
| `_dequeue_blocking` | def | L586–L591 |
| `_is_maintenance_active` | def | L601–L606 |
| `_maintenance_gate_middleware` | def | L609–L637 |
| `_no_cache_static_assets` | def | L641–L653 |
| `favicon` | def | L668–L669 |
| `maintenance_page` | def | L673–L674 |
| `login_page` | def | L678–L682 |
| `_asset_mtimes` | def | L699–L706 |
| `_frontend_version` | def | L709–L713 |
| `_own_portal_path` | def | L716–L717 |
| `_render_frontend_html` | def | L720–L744 |
| `user_portal_page` | def | L748–L763 |
| `portal_page` | def | L767–L774 |
| `dashboard_page` | def | L778–L792 |
| `index` | def | L796–L805 |
| `username_portal_page` | def | L809–L835 |
| `api_version` | def | L839–L849 |
| `auth_login` | def | L858–L889 |
| `auth_set_password` | def | L893–L917 |
| `auth_logout` | def | L921–L925 |
| `auth_me` | def | L929–L939 |
| `health_ping` | def | L945–L952 |
| `health` | def | L958–L964 |
| `_build_search_clause` | def | L967–L1011 |
| `list_accounts` | def | L1015–L1163 |
| `list_users` | def | L1169–L1177 |
| `list_assignments` | def | L1181–L1202 |
| `AssignRequest` | class | L1205–L1207 |
| `assign_accounts` | def | L1211–L1230 |
| `unassign_accounts` | def | L1234–L1245 |
| `stats` | def | L1249–L1256 |
| `_wsai_status` | def | L1271–L1296 |
| `_maybe_alert_broadcast` | def | L1303–L1320 |
| `_check_one_proxy` | def | L1323–L1349 |
| `_proxy_health` | def | L1352–L1401 |
| `_capmonster_balance` | def | L1404–L1424 |
| `_operator_color` | def | L1429–L1444 |
| `_resolve_who` | def | L1447–L1460 |
| `_event_visible_to` | def | L1463–L1489 |
| `superadmin_kpis` | def | L1493–L1736 |
| `RefreshRequest` | class | L1741–L1742 |
| `accounts_refresh` | def | L1746–L1765 |
| `_tail_log_file` | def | L1792–L1820 |
| `get_logs` | def | L1824–L1846 |
| `get_logs_telegram` | def | L1860–L1906 |
| `_run_health_checks` | def | L1914–L1950 |
| `health_full` | def | L1954–L1955 |
| `_require_sa` | def | L1963–L1965 |
| `admin_diag` | def | L1969–L2000 |
| `admin_ping` | def | L2004–L2025 |
| `admin_refresh_proxy` | def | L2029–L2036 |
| `admin_services_restart` | def | L2040–L2061 |
| `admin_export_logs` | def | L2065–L2081 |
| `admin_pause_state` | def | L2089–L2091 |
| `admin_pause` | def | L2095–L2107 |
| `admin_resume` | def | L2111–L2117 |
| `admin_emergency_stop` | def | L2121–L2156 |
| `admin_vps_reboot` | def | L2160–L2172 |
| `health_last` | def | L2176–L2177 |
| `health_dismiss` | def | L2181–L2184 |
| `api_marks_list` | def | L2188–L2195 |
| `api_marks_toggle` | def | L2199–L2217 |
| `api_recent` | def | L2221–L2293 |
| `api_accounts_at_hand` | def | L2297–L2405 |
| `_health_loop` | def | L2408–L2418 |
| `_release_account` | def | L2421–L2442 |
| `_run_lock_janitor` | def | L2445–L2493 |
| `_janitor_loop` | def | L2496–L2506 |
| `_run_window_watcher` | def | L2515–L2587 |
| `_window_watcher_loop` | def | L2590–L2599 |
| `_release_watchdog_tick` | def | L2602–L2701 |
| `_release_watchdog_loop` | def | L2704–L2712 |
| `_jwt_keepalive_loop` | def | L2715–L2743 |
| `_wake_jwt_keeper` | def | L2750–L2761 |
| `_account_refresh_loop` | def | L2764–L2782 |
| `_bot_token` | def | L2788–L2797 |
| `_notify_robert` | def | L2800–L2815 |
| `_startup_telegram_notify` | def | L2818–L2842 |
| `_lifespan` | def | L2846–L2857 |
| `LockRequest` | class | L2863–L2865 |
| `lock_account` | def | L2869–L2908 |
| `PublishRequest` | class | L2911–L2913 |
| `publish_accounts` | def | L2917–L2946 |
| `hide_all_accounts` | def | L2950–L2965 |
| `pool_accounts` | def | L2969–L2987 |
| `api_pool_split` | def | L2991–L3005 |
| `api_pool_publish` | def | L3009–L3036 |
| `unlock_account` | def | L3040–L3058 |
| `_sse_generator` | def | L3061–L3090 |
| `events` | def | L3094–L3104 |
| `account_cards_pipe` | def | L3108–L3134 |
| `account_notes_summary` | def | L3138–L3163 |
| `_record_account_touch` | def | L3166–L3199 |
| `account_find_id` | def | L3203–L3209 |
| `account_refresh_api` | def | L3213–L3318 |
| `account_details` | def | L3322–L3713 |
| `NoteCreate` | class | L3716–L3717 |
| `create_note` | def | L3721–L3750 |
| `CurpUpdate` | class | L3753–L3754 |
| `update_curp` | def | L3758–L3769 |
| `get_clabes` | def | L3779–L3788 |
| `refresh_clabes` | def | L3792–L3802 |
| `_persist_withdrawal` | def | L3811–L3857 |
| `withdraw` | def | L3861–L3913 |
| `withdraw_status` | def | L3917–L3980 |
| `delete_note` | def | L3984–L3996 |
| `CombosRequest` | class | L3999–L4000 |
| `accounts_combos` | def | L4004–L4017 |
| `accounts_pass_map` | def | L4021–L4026 |
| `list_all_cards` | def | L4030–L4106 |
| `activity_feed` | def | L4110–L4207 |
| `list_deposits` | def | L4211–L4240 |
| `deposits_stats` | def | L4244–L4269 |
| `_persist_auto_mission` | def | L4277–L4307 |
| `admin_maintenance_state` | def | L4311–L4314 |
| `MaintenanceToggleRequest` | class | L4317–L4318 |
| `admin_maintenance_toggle` | def | L4322–L4345 |
| `auto_deposit_create` | def | L4349–L4385 |
| `auto_deposit_cancel` | def | L4389–L4415 |
| `emergency_stop_all_deposits` | def | L4419–L4450 |
| `operator_my_accounts` | def | L4454–L4544 |
| `operator_release_account` | def | L4548–L4565 |
| `operator_withdraw` | def | L4569–L4627 |
| `operator_auto_withdraw` | def | L4631–L4667 |
| `auto_deposit_confirm` | def | L4671–L4690 |
| `operator_missions` | def | L4694–L4712 |
| `operator_recent_ticker` | def | L4716–L4841 |
| `auto_deposit_status` | def | L4845–L4856 |
| `register_operator_strike` | def | L4859–L4892 |
| `bot_start_info` | def | L4896–L4932 |
| `bot_operator_info` | def | L4936–L4975 |
| `bot_help_info` | def | L4979–L4993 |
| `bot_pause_mission` | def | L4997–L5026 |
| `bot_resume_mission` | def | L5030–L5048 |
| `bot_cancel_mission` | def | L5053–L5088 |
| `bot_bet_create` | def | L5092–L5262 |
| `filter_and_sanitize_check_combos` | def | L5265–L5350 |
| `BotCheckRequest` | class | L5353–L5357 |
| `bot_check` | def | L5360–L5441 |

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
| `_now_epoch` | def | L28–L29 |
| `_grade_rank` | def | L32–L35 |
| `_sa_tokens` | def | L38–L49 |
| `_cd_active` | def | L52–L68 |
| `_exp_int` | def | L71–L77 |
| `_bin_of` | def | L80–L82 |
| `_approval_rate` | def | L85–L91 |
| `_threeds_recent` | def | L94–L108 |
| `_rank_key` | def | L111–L114 |
| `_pipe_str` | def | L117–L122 |
| `_extract_card_number` | def | L125–L132 |
| `_parse_card_pipe` | def | L135–L168 |
| `_normalize_pipe_to_3part` | def | L171–L173 |
| `_get_married_card_owners` | def | L176–L210 |
| `_has_card_deposit_24h` | def | L213–L229 |
| `select_accounts_for_auto` | def | L241–L478 |
| `_max_accounts_for_cards` | def | L487–L495 |
| `plan_auto_mission` | def | L498–L988 |
| `_fake_progress_pct` | def | L1031–L1062 |
| `_iso` | def | L1066–L1067 |
| `_m_load` | def | L1070–L1078 |
| `_m_status` | def | L1081–L1083 |
| `_m_update` | def | L1086–L1096 |
| `_fetch_account` | def | L1099–L1106 |
| `_is_account_dead` | def | L1109–L1120 |
| `_unlock` | def | L1123–L1132 |
| `_pull_fresh_live_account` | def | L1135–L1218 |
| `_broadcast_mission` | def | L1221–L1250 |
| `_stop_pool` | def | L1253–L1260 |
| `run_auto_mission` | def | L1264–L2306 |

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
| `precheck_card_liveness` | def | L428–L552 |
| `format_ruthopia_liveness_summary` | def | L555–L598 |

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

### `db_registry.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `db` | def | L41–L89 |
| `_db_write_with_retry` | def | L92–L110 |

### `deposits.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `classify_deposit_status` | def | L54–L67 |
| `_cooldown_active` | def | L70–L82 |
| `_save_txns_via_app_db` | def | L85–L117 |
| `_set_account_cooldown` | def | L120–L133 |
| `_mark_rate_limited_dead` | def | L136–L154 |
| `get_married_card_owner` | def | L157–L198 |
| `_check_account_recent_attempt` | def | L201–L231 |
| `_cooldown_remaining_min` | def | L234–L240 |
| `_is_transient_gateway_error` | def | L243–L253 |
| `_drain_stale_tokens` | def | L283–L315 |
| `_ensure_fresh_captcha` | def | L318–L342 |
| `_record_bin_3ds` | def | L350–L378 |
| `_bin_3ds_stats` | def | L381–L403 |
| `bin_check` | def | L407–L417 |
| `bin_recommendations` | def | L421–L425 |
| `bin_stats_overview` | def | L429–L498 |
| `_auto_lock_for_deposit` | def | L501–L557 |
| `_window_status` | def | L560–L602 |
| `_check_caps` | def | L605–L621 |
| `_check_card_mixing_on_active_balance` | def | L624–L697 |
| `_load_deps` | def | L700–L711 |
| `_parse_pipe` | def | L714–L735 |
| `_check_card_velocity` | def | L755–L802 |
| `_has_recent_approved_deposit` | def | L805–L821 |
| `_record_attempt` | def | L824–L1020 |
| `_safe_phase` | def | L1030–L1037 |
| `_now_mx_str` | def | L1045–L1054 |
| `_deposit_step_payload` | def | L1063–L1071 |
| `_wrap_deposit_step` | def | L1074–L1093 |
| `_build_admin_proxy_url` | def | L1096–L1100 |
| `_refresh_account_after_deposit` | def | L1103–L1162 |
| `_should_relogin_after_401` | def | L1165–L1169 |
| `_acquire_session_and_begin` | def | L1172–L1466 |
| `_run_deposit_with_phases` | def | L1469–L1814 |
| `deposit_execute_stream` | def | L1818–L2035 |
| `cap_status` | def | L2039–L2051 |
| `_mm_is_real_decline` | def | L2091–L2097 |
| `_mm_is_ambiguous_charge` | def | L2100–L2110 |
| `classify_deposit_status` | def | L2113–L2144 |
| `_mm_session_get` | def | L2187–L2191 |
| `_mm_session_update` | def | L2194–L2203 |
| `multi_stream` | def | L2207–L2730 |
| `multi_cancel` | def | L2734–L2739 |
| `scheduled_create` | def | L2752–L3125 |
| `scheduled_list` | def | L3129–L3151 |
| `scheduled_cancel` | def | L3155–L3163 |

### `jwt_keeper.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_env_int` | def | L38–L42 |
| `cfg` | def | L45–L87 |
| `select_refresh_candidates` | def | L91–L172 |
| `_exp_int` | def | L175–L181 |
| `_load_candidate_rows` | def | L199–L243 |
| `_set_cooldown` | def | L246–L253 |
| `_bump_rl_streak` | def | L256–L270 |
| `_reset_rl_streak` | def | L273–L280 |
| `run_keepalive_cycle` | def | L284–L381 |
| `run_keepalive_cycle_from_env` | def | L384–L391 |

### `login_orchestrator.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `StickySession` | class | L17–L24 |
| `LoginResult` | class | L28–L42 |
| `StickySessionManager` | class | L45–L56 |
| `_classify_dead` | def | L59–L70 |
| `gentle_login` | def | L73–L236 |

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
| `prewarm_refresh_stream` | def | L727–L917 |

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

### `scripts/reconcile_macro_fleet.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `get_target_accounts` | def | L34–L57 |
| `process_account` | def | L59–L115 |
| `main` | def | L117–L139 |

### `scripts/refresh_recent_fleet.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `get_target_accounts` | def | L30–L44 |
| `process_account` | def | L46–L97 |
| `main` | def | L99–L121 |

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
| `GET` | `/api/health/ping` | `app.py` |
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
| `betmexico.dashboard.db` | `db_registry.py` |
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
| `fleet_refresh` | `scripts/refresh_recent_fleet.py` |
| `httpcore` | `betmexico_login_api.py` |
| `httpx` | `betmexico_login_api.py` |
| `macro_reconcile` | `scripts/reconcile_macro_fleet.py` |
| `saneador` | `saneador_daemon.py` |
| `verify_all_accounts` | `scripts/verify_all_accounts_active.py` |
<!-- GEN:end:loggers -->

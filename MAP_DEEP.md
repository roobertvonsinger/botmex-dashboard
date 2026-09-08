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
| `_CancelledFilter` | class | L88–L101 |
| `_migrate` | def | L190–L466 |
| `_backfill_grades_v10_m7` | def | L469–L540 |
| `_resolve_operator` | def | L546–L570 |
| `_is_sa` | def | L573–L575 |
| `_visible_emails` | def | L578–L600 |
| `_broadcast` | def | L607–L625 |
| `_dequeue_blocking` | def | L628–L633 |
| `_configure_asyncio_exception_handler` | def | L640–L690 |
| `_is_maintenance_active` | def | L701–L706 |
| `_maintenance_gate_middleware` | def | L709–L737 |
| `_no_cache_static_assets` | def | L741–L753 |
| `favicon` | def | L768–L769 |
| `maintenance_page` | def | L773–L774 |
| `login_page` | def | L778–L782 |
| `_asset_mtimes` | def | L799–L806 |
| `_frontend_version` | def | L809–L813 |
| `_own_portal_path` | def | L816–L817 |
| `_render_frontend_html` | def | L820–L844 |
| `user_portal_page` | def | L848–L863 |
| `portal_page` | def | L867–L874 |
| `dashboard_page` | def | L878–L892 |
| `index` | def | L896–L905 |
| `username_portal_page` | def | L909–L935 |
| `api_version` | def | L939–L949 |
| `auth_login` | def | L958–L989 |
| `auth_set_password` | def | L993–L1017 |
| `auth_logout` | def | L1021–L1025 |
| `auth_me` | def | L1029–L1039 |
| `health_ping` | def | L1045–L1052 |
| `health` | def | L1058–L1066 |
| `_build_search_clause` | def | L1069–L1113 |
| `list_accounts` | def | L1117–L1263 |
| `list_users` | def | L1269–L1277 |
| `list_assignments` | def | L1281–L1302 |
| `AssignRequest` | class | L1305–L1307 |
| `assign_accounts` | def | L1311–L1330 |
| `unassign_accounts` | def | L1334–L1345 |
| `stats` | def | L1349–L1356 |
| `_wsai_status` | def | L1371–L1396 |
| `_maybe_alert_broadcast` | def | L1403–L1420 |
| `_check_one_proxy` | def | L1423–L1449 |
| `_proxy_health` | def | L1452–L1501 |
| `_capmonster_balance` | def | L1504–L1524 |
| `_operator_color` | def | L1529–L1544 |
| `_resolve_who` | def | L1547–L1560 |
| `_event_visible_to` | def | L1563–L1589 |
| `superadmin_kpis` | def | L1593–L1836 |
| `RefreshRequest` | class | L1841–L1842 |
| `accounts_refresh` | def | L1846–L1865 |
| `_tail_log_file` | def | L1895–L1933 |
| `get_logs` | def | L1937–L1959 |
| `get_logs_telegram` | def | L1973–L2019 |
| `_run_health_checks` | def | L2027–L2063 |
| `health_full` | def | L2067–L2068 |
| `_require_sa` | def | L2076–L2078 |
| `admin_diag` | def | L2082–L2113 |
| `admin_ping` | def | L2117–L2138 |
| `admin_refresh_proxy` | def | L2142–L2149 |
| `admin_services_restart` | def | L2153–L2174 |
| `admin_export_logs` | def | L2178–L2194 |
| `admin_pause_state` | def | L2202–L2204 |
| `admin_pause` | def | L2208–L2220 |
| `admin_resume` | def | L2224–L2230 |
| `admin_emergency_stop` | def | L2234–L2269 |
| `admin_vps_reboot` | def | L2273–L2285 |
| `health_last` | def | L2289–L2290 |
| `health_dismiss` | def | L2294–L2297 |
| `api_marks_list` | def | L2301–L2308 |
| `api_marks_toggle` | def | L2312–L2330 |
| `api_recent` | def | L2334–L2406 |
| `api_accounts_at_hand` | def | L2410–L2518 |
| `_health_loop` | def | L2521–L2531 |
| `_release_account` | def | L2534–L2555 |
| `_run_lock_janitor` | def | L2558–L2606 |
| `_janitor_loop` | def | L2609–L2619 |
| `_run_window_watcher` | def | L2628–L2700 |
| `_window_watcher_loop` | def | L2703–L2712 |
| `_release_watchdog_tick` | def | L2715–L2814 |
| `_release_watchdog_loop` | def | L2817–L2825 |
| `_jwt_keepalive_loop` | def | L2828–L2856 |
| `_wake_jwt_keeper` | def | L2863–L2874 |
| `_account_refresh_loop` | def | L2877–L2895 |
| `_bot_token` | def | L2901–L2910 |
| `_notify_robert` | def | L2913–L2928 |
| `_startup_telegram_notify` | def | L2931–L2955 |
| `_lifespan` | def | L2959–L2971 |
| `LockRequest` | class | L2977–L2979 |
| `lock_account` | def | L2983–L3022 |
| `PublishRequest` | class | L3025–L3027 |
| `publish_accounts` | def | L3031–L3060 |
| `hide_all_accounts` | def | L3064–L3079 |
| `pool_accounts` | def | L3083–L3101 |
| `api_pool_split` | def | L3105–L3119 |
| `api_pool_publish` | def | L3123–L3150 |
| `unlock_account` | def | L3154–L3172 |
| `_sse_generator` | def | L3175–L3204 |
| `events` | def | L3208–L3218 |
| `account_cards_pipe` | def | L3222–L3248 |
| `account_notes_summary` | def | L3252–L3277 |
| `_record_account_touch` | def | L3280–L3313 |
| `account_find_id` | def | L3317–L3323 |
| `account_refresh_api` | def | L3327–L3432 |
| `account_details` | def | L3436–L3827 |
| `NoteCreate` | class | L3830–L3831 |
| `create_note` | def | L3835–L3864 |
| `CurpUpdate` | class | L3867–L3868 |
| `update_curp` | def | L3872–L3883 |
| `get_clabes` | def | L3893–L3902 |
| `refresh_clabes` | def | L3906–L3916 |
| `_persist_withdrawal` | def | L3925–L3971 |
| `withdraw` | def | L3975–L4027 |
| `withdraw_status` | def | L4031–L4094 |
| `delete_note` | def | L4098–L4110 |
| `CombosRequest` | class | L4113–L4114 |
| `accounts_combos` | def | L4118–L4131 |
| `accounts_pass_map` | def | L4135–L4140 |
| `list_all_cards` | def | L4144–L4220 |
| `activity_feed` | def | L4224–L4321 |
| `list_deposits` | def | L4325–L4354 |
| `deposits_stats` | def | L4358–L4383 |
| `_persist_auto_mission` | def | L4391–L4421 |
| `admin_maintenance_state` | def | L4425–L4428 |
| `MaintenanceToggleRequest` | class | L4431–L4432 |
| `admin_maintenance_toggle` | def | L4436–L4459 |
| `auto_deposit_create` | def | L4463–L4499 |
| `auto_deposit_cancel` | def | L4503–L4529 |
| `emergency_stop_all_deposits` | def | L4533–L4564 |
| `operator_my_accounts` | def | L4568–L4658 |
| `operator_release_account` | def | L4662–L4679 |
| `operator_withdraw` | def | L4683–L4741 |
| `operator_auto_withdraw` | def | L4745–L4781 |
| `auto_deposit_confirm` | def | L4785–L4804 |
| `operator_missions` | def | L4808–L4826 |
| `operator_recent_ticker` | def | L4830–L4955 |
| `auto_deposit_status` | def | L4959–L4970 |
| `register_operator_strike` | def | L4973–L5006 |
| `bot_start_info` | def | L5010–L5046 |
| `bot_operator_info` | def | L5050–L5089 |
| `bot_help_info` | def | L5093–L5107 |
| `bot_pause_mission` | def | L5111–L5140 |
| `bot_resume_mission` | def | L5144–L5162 |
| `bot_cancel_mission` | def | L5167–L5202 |
| `bot_bet_create` | def | L5206–L5376 |
| `filter_and_sanitize_check_combos` | def | L5379–L5464 |
| `BotCheckRequest` | class | L5467–L5471 |
| `bot_check` | def | L5474–L5555 |

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
| `_get_married_card_owners` | def | L176–L218 |
| `_has_card_deposit_24h` | def | L221–L237 |
| `select_accounts_for_auto` | def | L249–L489 |
| `_max_accounts_for_cards` | def | L498–L506 |
| `plan_auto_mission` | def | L509–L1055 |
| `_fake_progress_pct` | def | L1098–L1129 |
| `_iso` | def | L1133–L1134 |
| `_m_load` | def | L1137–L1145 |
| `_m_status` | def | L1148–L1150 |
| `_m_update` | def | L1153–L1163 |
| `_fetch_account` | def | L1166–L1173 |
| `_is_account_dead` | def | L1176–L1190 |
| `_is_account_rate_limited` | def | L1193–L1199 |
| `_unlock` | def | L1202–L1211 |
| `_pull_fresh_live_account` | def | L1214–L1348 |
| `_broadcast_mission` | def | L1351–L1380 |
| `_stop_pool` | def | L1383–L1390 |
| `run_auto_mission` | def | L1394–L2456 |

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
| `BetmexicoDB` | class | L29–L2956 |

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
| `BetmexicoApiChecker` | class | L418–L961 |
| `CaptchaTokenPool` | class | L967–L1168 |

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
| `check_ruthopia_db_liveness` | def | L182–L240 |
| `perform_wabox_liveness_check` | def | L243–L369 |
| `get_card_declines_24h` | def | L372–L417 |
| `_get_app_db` | def | L420–L438 |
| `precheck_card_liveness` | def | L441–L571 |
| `format_ruthopia_liveness_summary` | def | L574–L617 |

### `clabe_fetch.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_load_jwt_for_account` | def | L37–L62 |
| `_get_admin_proxy_url` | def | L65–L72 |
| `fetch_clabes_from_betmexico` | def | L75–L99 |
| `_persist_clabes` | def | L102–L141 |
| `get_saved_clabes` | def | L144–L160 |
| `refresh_clabes_for_account` | def | L163–L189 |

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
| `db` | def | L42–L91 |
| `_db_write_with_retry` | def | L94–L112 |

### `deposits.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `classify_deposit_status` | def | L54–L67 |
| `_cooldown_active` | def | L70–L82 |
| `_save_txns_via_app_db` | def | L85–L117 |
| `_set_account_cooldown` | def | L120–L133 |
| `_mark_rate_limited_dead` | def | L136–L154 |
| `_liberate_card_in_db` | def | L157–L170 |
| `_is_card_liberated_for_owner` | def | L173–L191 |
| `get_married_card_owner` | def | L194–L246 |
| `_check_account_recent_attempt` | def | L249–L279 |
| `_cooldown_remaining_min` | def | L282–L288 |
| `_is_transient_gateway_error` | def | L291–L301 |
| `_drain_stale_tokens` | def | L331–L363 |
| `_ensure_fresh_captcha` | def | L366–L390 |
| `_record_bin_3ds` | def | L398–L426 |
| `_bin_3ds_stats` | def | L429–L451 |
| `bin_check` | def | L455–L465 |
| `bin_recommendations` | def | L469–L473 |
| `bin_stats_overview` | def | L477–L546 |
| `_auto_lock_for_deposit` | def | L549–L605 |
| `_window_status` | def | L608–L650 |
| `_check_caps` | def | L653–L669 |
| `_check_card_mixing_on_active_balance` | def | L672–L745 |
| `_load_deps` | def | L748–L759 |
| `_parse_pipe` | def | L762–L783 |
| `_check_card_velocity` | def | L803–L850 |
| `_has_recent_approved_deposit` | def | L853–L869 |
| `_record_attempt` | def | L872–L1068 |
| `_safe_phase` | def | L1078–L1085 |
| `_now_mx_str` | def | L1093–L1102 |
| `_deposit_step_payload` | def | L1111–L1119 |
| `_wrap_deposit_step` | def | L1122–L1141 |
| `_build_admin_proxy_url` | def | L1144–L1148 |
| `_refresh_account_after_deposit` | def | L1151–L1210 |
| `_should_relogin_after_401` | def | L1213–L1217 |
| `_acquire_session_and_begin` | def | L1220–L1514 |
| `_run_deposit_with_phases` | def | L1517–L1862 |
| `deposit_execute_stream` | def | L1866–L2083 |
| `cap_status` | def | L2087–L2099 |
| `_mm_is_real_decline` | def | L2139–L2145 |
| `_mm_is_ambiguous_charge` | def | L2148–L2158 |
| `classify_deposit_status` | def | L2161–L2192 |
| `_mm_session_get` | def | L2235–L2257 |
| `_mm_session_update` | def | L2260–L2269 |
| `multi_stream` | def | L2273–L2828 |
| `multi_cancel` | def | L2832–L2837 |
| `scheduled_create` | def | L2850–L3223 |
| `scheduled_list` | def | L3227–L3249 |
| `scheduled_cancel` | def | L3253–L3261 |

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
| `prewarm_refresh_stream` | def | L727–L922 |

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

### `scripts/kvm4_local_backup.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `log` | def | L22–L30 |
| `main` | def | L33–L71 |

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

### `scripts/session_balance_poller.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_signal_handler` | def | L92–L95 |
| `get_prioritized_candidates` | def | L98–L136 |
| `check_single_account` | def | L141–L245 |
| `apply_single_update` | def | L248–L342 |
| `run_organic_cycle` | def | L346–L406 |
| `daemon_loop` | def | L409–L445 |
| `main` | def | L448–L465 |

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
| `recalc_grade_from_db` | def | L47–L93 |
| `recalc_grade_from_details` | def | L96–L118 |
| `note_a_plus_outcome` | def | L121–L173 |

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
| `balance_poller` | `scripts/session_balance_poller.py` |
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

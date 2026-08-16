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
| `_resolve_pending_withdrawals` | def | L485–L558 |
| `_withdrawal_resolution_loop` | def | L561–L577 |

### `app.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `db` | def | L172–L225 |
| `_db_write_with_retry` | def | L228–L260 |
| `_migrate` | def | L263–L497 |
| `_backfill_grades_v10_m7` | def | L500–L571 |
| `_resolve_operator` | def | L577–L601 |
| `_is_sa` | def | L604–L606 |
| `_visible_emails` | def | L609–L631 |
| `_broadcast` | def | L638–L656 |
| `_dequeue_blocking` | def | L659–L664 |
| `_is_maintenance_active` | def | L673–L676 |
| `_maintenance_gate_middleware` | def | L679–L707 |
| `_no_cache_static_assets` | def | L711–L723 |
| `favicon` | def | L738–L739 |
| `maintenance_page` | def | L743–L744 |
| `login_page` | def | L748–L752 |
| `_asset_mtimes` | def | L769–L776 |
| `_frontend_version` | def | L779–L783 |
| `_own_portal_path` | def | L786–L787 |
| `_render_frontend_html` | def | L790–L814 |
| `user_portal_page` | def | L818–L833 |
| `portal_page` | def | L837–L844 |
| `dashboard_page` | def | L848–L862 |
| `index` | def | L866–L875 |
| `username_portal_page` | def | L879–L905 |
| `api_version` | def | L909–L919 |
| `auth_login` | def | L928–L959 |
| `auth_set_password` | def | L963–L987 |
| `auth_logout` | def | L991–L995 |
| `auth_me` | def | L999–L1009 |
| `health` | def | L1015–L1021 |
| `_build_search_clause` | def | L1024–L1068 |
| `list_accounts` | def | L1072–L1202 |
| `list_users` | def | L1208–L1216 |
| `list_assignments` | def | L1220–L1241 |
| `AssignRequest` | class | L1244–L1246 |
| `assign_accounts` | def | L1250–L1269 |
| `unassign_accounts` | def | L1273–L1284 |
| `stats` | def | L1288–L1295 |
| `_wsai_status` | def | L1310–L1335 |
| `_maybe_alert_broadcast` | def | L1342–L1359 |
| `_check_one_proxy` | def | L1362–L1388 |
| `_proxy_health` | def | L1391–L1440 |
| `_capmonster_balance` | def | L1443–L1463 |
| `_operator_color` | def | L1468–L1483 |
| `_resolve_who` | def | L1486–L1499 |
| `_event_visible_to` | def | L1502–L1528 |
| `superadmin_kpis` | def | L1532–L1775 |
| `RefreshRequest` | class | L1780–L1781 |
| `accounts_refresh` | def | L1785–L1804 |
| `_tail_log_file` | def | L1831–L1859 |
| `get_logs` | def | L1863–L1885 |
| `get_logs_telegram` | def | L1895–L1910 |
| `_run_health_checks` | def | L1918–L1954 |
| `health_full` | def | L1958–L1959 |
| `_require_sa` | def | L1967–L1969 |
| `admin_diag` | def | L1973–L2004 |
| `admin_ping` | def | L2008–L2029 |
| `admin_refresh_proxy` | def | L2033–L2040 |
| `admin_services_restart` | def | L2044–L2065 |
| `admin_export_logs` | def | L2069–L2085 |
| `admin_pause_state` | def | L2093–L2095 |
| `admin_pause` | def | L2099–L2111 |
| `admin_resume` | def | L2115–L2121 |
| `admin_emergency_stop` | def | L2125–L2160 |
| `admin_vps_reboot` | def | L2164–L2176 |
| `health_last` | def | L2180–L2181 |
| `health_dismiss` | def | L2185–L2188 |
| `api_marks_list` | def | L2192–L2199 |
| `api_marks_toggle` | def | L2203–L2221 |
| `api_recent` | def | L2225–L2297 |
| `api_accounts_at_hand` | def | L2301–L2409 |
| `_health_loop` | def | L2412–L2422 |
| `_release_account` | def | L2425–L2446 |
| `_run_lock_janitor` | def | L2449–L2497 |
| `_janitor_loop` | def | L2500–L2510 |
| `_run_window_watcher` | def | L2519–L2591 |
| `_window_watcher_loop` | def | L2594–L2603 |
| `_release_watchdog_tick` | def | L2606–L2705 |
| `_release_watchdog_loop` | def | L2708–L2716 |
| `_jwt_keepalive_loop` | def | L2719–L2747 |
| `_wake_jwt_keeper` | def | L2754–L2765 |
| `_account_refresh_loop` | def | L2768–L2786 |
| `_bot_token` | def | L2792–L2801 |
| `_notify_robert` | def | L2804–L2819 |
| `_startup_telegram_notify` | def | L2822–L2846 |
| `_lifespan` | def | L2850–L2861 |
| `LockRequest` | class | L2867–L2869 |
| `lock_account` | def | L2873–L2912 |
| `PublishRequest` | class | L2915–L2917 |
| `publish_accounts` | def | L2921–L2950 |
| `hide_all_accounts` | def | L2954–L2969 |
| `pool_accounts` | def | L2973–L2991 |
| `api_pool_split` | def | L2995–L3009 |
| `api_pool_publish` | def | L3013–L3047 |
| `unlock_account` | def | L3051–L3069 |
| `_sse_generator` | def | L3072–L3098 |
| `events` | def | L3102–L3112 |
| `account_cards_pipe` | def | L3116–L3142 |
| `account_notes_summary` | def | L3146–L3171 |
| `_record_account_touch` | def | L3174–L3207 |
| `account_find_id` | def | L3211–L3217 |
| `account_details` | def | L3221–L3601 |
| `NoteCreate` | class | L3604–L3605 |
| `create_note` | def | L3609–L3638 |
| `CurpUpdate` | class | L3641–L3642 |
| `update_curp` | def | L3646–L3657 |
| `get_clabes` | def | L3667–L3676 |
| `refresh_clabes` | def | L3680–L3690 |
| `_persist_withdrawal` | def | L3699–L3745 |
| `withdraw` | def | L3749–L3801 |
| `withdraw_status` | def | L3805–L3856 |
| `delete_note` | def | L3860–L3872 |
| `CombosRequest` | class | L3875–L3876 |
| `accounts_combos` | def | L3880–L3893 |
| `accounts_pass_map` | def | L3897–L3902 |
| `list_all_cards` | def | L3906–L3982 |
| `activity_feed` | def | L3986–L4083 |
| `list_deposits` | def | L4087–L4116 |
| `deposits_stats` | def | L4120–L4145 |
| `_persist_auto_mission` | def | L4153–L4183 |
| `admin_maintenance_state` | def | L4187–L4190 |
| `MaintenanceToggleRequest` | class | L4193–L4194 |
| `admin_maintenance_toggle` | def | L4198–L4219 |
| `auto_deposit_create` | def | L4223–L4259 |
| `auto_deposit_cancel` | def | L4263–L4289 |
| `operator_my_accounts` | def | L4293–L4383 |
| `operator_release_account` | def | L4387–L4404 |
| `operator_withdraw` | def | L4408–L4466 |
| `operator_auto_withdraw` | def | L4470–L4506 |
| `auto_deposit_confirm` | def | L4510–L4529 |
| `operator_missions` | def | L4533–L4551 |
| `operator_recent_ticker` | def | L4555–L4680 |
| `auto_deposit_status` | def | L4684–L4695 |
| `register_operator_strike` | def | L4698–L4731 |
| `bot_start_info` | def | L4735–L4771 |
| `bot_operator_info` | def | L4775–L4814 |
| `bot_help_info` | def | L4818–L4832 |
| `bot_pause_mission` | def | L4836–L4865 |
| `bot_resume_mission` | def | L4869–L4887 |
| `bot_cancel_mission` | def | L4892–L4927 |
| `bot_bet_create` | def | L4931–L5100 |
| `filter_and_sanitize_check_combos` | def | L5103–L5188 |
| `BotCheckRequest` | class | L5191–L5195 |
| `bot_check` | def | L5198–L5279 |

### `auth.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `load_users` | def | L29–L51 |
| `save_users` | def | L53–L61 |
| `_UsersDictProxy` | class | L63–L88 |
| `add_user` | def | L92–L113 |
| `sha256` | def | L120–L121 |
| `load_passwords` | def | L124–L147 |
| `save_passwords` | def | L150–L158 |
| `_is_persistent` | def | L168–L169 |
| `_load_persistent_sessions` | def | L172–L178 |
| `_save_persistent_sessions` | def | L181–L187 |
| `_prune` | def | L193–L202 |
| `session_max_age` | def | L205–L207 |
| `create_session` | def | L210–L223 |
| `get_session` | def | L226–L235 |
| `delete_session` | def | L238–L241 |
| `require_session` | def | L245–L253 |
| `require_operator_view` | def | L256–L285 |

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
| `_get_married_card_owners` | def | L175–L191 |
| `select_accounts_for_auto` | def | L200–L369 |
| `_max_accounts_for_cards` | def | L378–L386 |
| `plan_auto_mission` | def | L389–L658 |
| `_fake_progress_pct` | def | L699–L730 |
| `_iso` | def | L734–L735 |
| `_m_load` | def | L738–L746 |
| `_m_status` | def | L749–L751 |
| `_m_update` | def | L754–L764 |
| `_fetch_account` | def | L767–L774 |
| `_unlock` | def | L777–L786 |
| `_broadcast_mission` | def | L789–L818 |
| `_stop_pool` | def | L821–L828 |
| `run_auto_mission` | def | L832–L1639 |

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
| `get_admin_proxy` | def | L148–L150 |
| `parse_user_proxy` | def | L153–L164 |
| `get_user_proxy` | def | L167–L180 |
| `_get_solver_for_user` | def | L183–L185 |

### `betmexico_db.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `BetmexicoDB` | class | L29–L2924 |

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
| `AntiCaptchaSolverFast` | class | L88–L194 |
| `TwoCaptchaSolverFast` | class | L197–L286 |
| `create_solver` | def | L289–L295 |
| `CapMonsterSolverFast` | class | L302–L370 |
| `BetmexicoApiChecker` | class | L373–L823 |
| `CaptchaTokenPool` | class | L829–L1050 |

### `betmexico_login_service.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `make_pool` | def | L33–L45 |
| `_persist_jwt_cache` | def | L48–L62 |
| `get_jwt` | def | L65–L136 |

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
| `get_bin_intelligence_summary` | def | L245–L305 |
| `format_telegram_start_banner` | def | L308–L329 |
| `format_telegram_bet_warning` | def | L332–L365 |
| `format_telegram_radar_full` | def | L368–L399 |
| `get_single_card_bin_badge` | def | L402–L430 |

### `card_checker.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_load_ruthopia_dashboard_token` | def | L29–L42 |
| `ruthopia_bridge_check` | def | L45–L82 |
| `check_luhn` | def | L85–L98 |
| `parse_and_validate_card_pipe` | def | L101–L150 |
| `perform_wabox_liveness_check` | def | L158–L284 |
| `precheck_card_liveness` | def | L287–L377 |
| `format_ruthopia_liveness_summary` | def | L380–L398 |

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
| `seed_db` | def | L8–L148 |
| `client` | def | L151–L155 |
| `make_client` | def | L158–L170 |
| `mock_bmx_transport` | def | L174–L184 |

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
| `_cooldown_active` | def | L69–L78 |
| `_save_txns_via_app_db` | def | L81–L113 |
| `_set_account_cooldown` | def | L116–L129 |
| `_mark_rate_limited_dead` | def | L132–L144 |
| `_cooldown_remaining_min` | def | L147–L153 |
| `_is_transient_gateway_error` | def | L156–L166 |
| `_drain_stale_tokens` | def | L196–L228 |
| `_ensure_fresh_captcha` | def | L231–L255 |
| `_record_bin_3ds` | def | L263–L291 |
| `_bin_3ds_stats` | def | L294–L316 |
| `bin_check` | def | L320–L330 |
| `bin_recommendations` | def | L334–L338 |
| `bin_stats_overview` | def | L342–L411 |
| `_auto_lock_for_deposit` | def | L414–L470 |
| `_window_status` | def | L473–L515 |
| `_check_caps` | def | L518–L534 |
| `_load_deps` | def | L537–L548 |
| `_parse_pipe` | def | L551–L572 |
| `_check_card_velocity` | def | L592–L639 |
| `_has_recent_approved_deposit` | def | L642–L658 |
| `_record_attempt` | def | L661–L843 |
| `_safe_phase` | def | L853–L860 |
| `_now_mx_str` | def | L868–L877 |
| `_deposit_step_payload` | def | L886–L894 |
| `_wrap_deposit_step` | def | L897–L916 |
| `_build_admin_proxy_url` | def | L919–L923 |
| `_refresh_account_after_deposit` | def | L926–L985 |
| `_should_relogin_after_401` | def | L988–L992 |
| `_acquire_session_and_begin` | def | L995–L1271 |
| `_run_deposit_with_phases` | def | L1274–L1618 |
| `deposit_execute_stream` | def | L1622–L1821 |
| `cap_status` | def | L1825–L1837 |
| `_mm_is_real_decline` | def | L1874–L1880 |
| `_mm_is_ambiguous_charge` | def | L1883–L1893 |
| `classify_deposit_status` | def | L1896–L1927 |
| `_mm_session_get` | def | L1973–L1977 |
| `_mm_session_update` | def | L1980–L1989 |
| `multi_stream` | def | L1993–L2507 |
| `multi_cancel` | def | L2511–L2516 |
| `scheduled_create` | def | L2529–L2893 |
| `scheduled_list` | def | L2897–L2919 |
| `scheduled_cancel` | def | L2923–L2931 |

### `jwt_keeper.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_env_int` | def | L38–L42 |
| `cfg` | def | L45–L87 |
| `select_refresh_candidates` | def | L91–L163 |
| `_exp_int` | def | L166–L172 |
| `_load_candidate_rows` | def | L190–L232 |
| `_set_cooldown` | def | L235–L242 |
| `_bump_rl_streak` | def | L245–L259 |
| `_reset_rl_streak` | def | L262–L269 |
| `run_keepalive_cycle` | def | L273–L386 |
| `run_keepalive_cycle_from_env` | def | L389–L396 |

### `login_orchestrator.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `StickySession` | class | L68–L76 |
| `parse_nodemaven_line` | def | L79–L96 |
| `StickySessionManager` | class | L99–L140 |
| `LoginResult` | class | L145–L162 |
| `_import_get_jwt` | def | L166–L169 |
| `_import_login_primitives` | def | L172–L180 |
| `_classify_dead` | def | L183–L195 |
| `_pool_session` | def | L198–L209 |
| `_jitter_base` | def | L212–L219 |
| `gentle_login` | def | L223–L448 |

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
| `_fetch_looks_empty` | def | L178–L205 |
| `_db_upsert_balance` | def | L208–L275 |
| `_db_save_txns_and_recalc` | def | L278–L331 |
| `_db_update_last_checked` | def | L334–L346 |
| `_db_invalidate_jwt` | def | L349–L360 |
| `_db_mark_dead` | def | L363–L386 |
| `_is_balance_fresh` | def | L389–L397 |
| `_capmonster_balance` | def | L402–L418 |
| `_run_prewarm` | def | L423–L598 |
| `prewarm_select` | def | L604–L688 |
| `prewarm_cancel` | def | L692–L702 |
| `prewarm_status` | def | L706–L721 |
| `prewarm_refresh_stream` | def | L727–L907 |

### `renapo_validator.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_host_of` | def | L45–L47 |
| `_host_resolves` | def | L50–L61 |
| `_check_curp_with_proxy` | def | L64–L94 |
| `validate_renapo_curp` | def | L97–L148 |
| `_fallback` | def | L151–L154 |

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
| `mark_account_dead` | def | L51–L62 |
| `main` | def | L65–L133 |

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

### `test_account_refresh.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_acc` | def | L36–L56 |
| `_run` | def | L59–L63 |
| `test_jwt_vigente_es_candidata` | def | L66–L68 |
| `test_jwt_expirado_no_es_candidata` | def | L71–L73 |
| `test_jwt_nulo_no_es_candidata` | def | L76–L78 |
| `test_jwt_vence_ahora_mismo_no_es_candidata` | def | L81–L83 |
| `test_lockeada_por_operador_se_excluye` | def | L86–L88 |
| `test_grade_no_util_se_excluye` | def | L91–L98 |
| `test_no_live_se_excluye` | def | L101–L103 |
| `test_no_publicada_se_excluye` | def | L106–L108 |
| `test_orden_por_last_checked_ascendente` | def | L111–L119 |
| `test_batch_max_limita` | def | L122–L125 |
| `test_grades_configurable` | def | L128–L131 |
| `test_reservada_sa_con_jwt_vigente_es_candidata` | def | L134–L141 |
| `test_reservada_sa_locked_by_username_es_candidata` | def | L144–L152 |
| `test_reservada_no_sa_no_es_candidata` | def | L155–L158 |
| `test_no_publicada_no_lockeada_no_es_candidata` | def | L161–L164 |
| `test_hot_lockeada_por_operador_no_sa_es_candidata` | def | L174–L177 |
| `test_hot_grade_no_util_es_candidata` | def | L180–L182 |
| `test_hot_no_publicada_es_candidata` | def | L185–L187 |
| `test_hot_sin_jwt_vigente_no_es_candidata` | def | L190–L193 |
| `test_hot_no_live_no_es_candidata` | def | L196–L198 |
| `test_hot_ignora_batch_max` | def | L201–L211 |
| `test_hot_va_primero_en_el_resultado` | def | L214–L224 |
| `_row` | def | L230–L235 |
| `test_hot_por_balance_alto` | def | L238–L239 |
| `test_no_hot_balance_50_exacto` | def | L242–L243 |
| `test_no_hot_balance_bajo_sin_lock_sin_retiro` | def | L246–L247 |
| `test_hot_por_ventana_de_autolock_activa` | def | L250–L253 |
| `test_no_hot_ventana_de_autolock_vencida` | def | L256–L259 |
| `test_hot_por_retiro_pendiente` | def | L262–L263 |
| `test_no_hot_sin_ninguna_señal` | def | L266–L267 |
| `db_conn` | def | L289–L305 |
| `test_load_candidate_rows_marca_hot_por_balance` | def | L308–L318 |
| `test_load_candidate_rows_marca_hot_por_retiro_pendiente` | def | L321–L338 |
| `test_load_candidate_rows_no_hot_normal` | def | L341–L354 |
| `test_db_set_and_get_withdrawal_ready` | def | L357–L376 |
| `test_withdrawal_poll_interval_is_60_not_1200` | def | L386–L391 |
| `test_resolve_pending_withdrawals_updates_status_api` | def | L394–L462 |
| `test_resolve_pending_withdrawals_no_pending_returns_empty` | def | L465–L470 |

### `test_account_touch.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `test_actor_operator_does_not_see_own_touch` | def | L10–L12 |
| `test_sa_does_not_see_own_touch` | def | L15–L18 |
| `test_sa_sees_others_touch` | def | L21–L23 |
| `test_operator_does_not_see_others_touch` | def | L26–L28 |
| `test_touch_dedup_one_per_day` | def | L31–L51 |

### `test_account_touch_isolated.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_reload_with_seed_db` | def | L13–L17 |
| `test_record_touch_persists_new_touch` | def | L20–L29 |
| `test_record_touch_dedup_same_day_returns_false` | def | L32–L41 |
| `test_record_touch_different_actors_both_persist` | def | L44–L53 |
| `test_record_touch_traps_locked_silently` | def | L56–L78 |
| `test_account_details_dispatches_touch_off_request_path` | def | L81–L138 |

### `test_activity_scoped.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `test_activity_operator_only_own` | def | L2–L8 |
| `test_activity_sa_sees_all` | def | L10–L14 |
| `test_recent_includes_own_interactions_and_marks` | def | L17–L25 |
| `test_recent_stats_scoped_to_user` | def | L27–L30 |

### `test_anti_rate_limit.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `FakeDB` | class | L16–L21 |
| `FakePool` | class | L24–L30 |
| `make_fake_checker` | def | L33–L51 |
| `_patch_primitives` | def | L54–L58 |
| `test_loginresult_from_cache_defaults_false` | def | L62–L63 |
| `test_cache_hit_sets_from_cache_true` | def | L66–L74 |
| `test_fresh_login_not_from_cache` | def | L77–L85 |
| `test_ban_returns_rate_limited_immediately` | def | L89–L99 |
| `test_cooldown_active_future` | def | L103–L104 |
| `test_cooldown_active_past` | def | L107–L108 |
| `test_cooldown_active_none` | def | L111–L112 |
| `test_cooldown_active_zero` | def | L115–L116 |
| `test_cooldown_remaining_min_future` | def | L119–L120 |
| `test_cooldown_remaining_min_inactive` | def | L123–L125 |
| `test_relogin_when_cache_and_not_yet` | def | L129–L130 |
| `test_no_relogin_when_not_from_cache` | def | L133–L134 |
| `test_no_relogin_when_already_relogged` | def | L137–L138 |
| `_LR` | class | L142–L155 |
| `_fake_gentle` | def | L158–L166 |
| `_fake_begin` | def | L169–L177 |
| `_noop_phase` | def | L180–L181 |
| `_run_acquire` | def | L184–L209 |
| `test_acquire_fresh_login_then_begin_ok` | def | L212–L220 |
| `test_acquire_cache_hit_assigns_pool_proxy_not_proxyless` | def | L223–L230 |
| `test_acquire_cache_401_invalidates_and_relogins` | def | L233–L250 |
| `test_acquire_rate_limited_marks_dead_and_fails` | def | L253–L262 |
| `test_set_account_cooldown_persists` | def | L265–L278 |

### `test_at_hand.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `test_shape_has_pinned_and_recent_keys` | def | L7–L14 |
| `test_pinned_account_enriched_with_id_and_combo` | def | L17–L30 |
| `test_recent_account_has_id_and_last_ts` | def | L33–L41 |
| `test_operator_does_not_see_foreign_account` | def | L44–L50 |
| `test_sa_sees_own_recent_and_pinned` | def | L53–L64 |
| `test_every_row_has_id_field_present` | def | L67–L73 |

### `test_auto_deposit_selection.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_make_db` | def | L19–L76 |
| `test_gate_duro_published_to_pool` | def | L79–L92 |
| `test_cooldown_48h_dashboard_approved` | def | L98–L118 |
| `test_spei_external_deposit_relegates_to_low` | def | L121–L137 |
| `test_boost_3ds_recent_to_top` | def | L140–L154 |
| `test_bin_cooldown_30d_on_approval` | def | L157–L188 |
| `test_tol_pipe_only_one_account` | def | L191–L203 |
| `test_dynamic_order_recently_tried_last` | def | L206–L218 |
| `test_cards_heavy_deprioritized` | def | L221–L233 |
| `test_tier_proportion_2_2_1` | def | L236–L251 |

### `test_auto_missions_migrate.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `test_migrate_creates_auto_missions` | def | L28–L43 |
| `test_migrate_mission_id_unique` | def | L46–L61 |
| `test_auto_missions_defaults` | def | L64–L82 |
| `test_reaper_fails_zombie_and_releases_lock` | def | L85–L113 |
| `test_migrate_idempotent` | def | L116–L120 |

### `test_balance_only_real_zero_preserved.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `test_db_upsert_balance_persists_real_zero_when_session_alive` | def | L25–L56 |
| `test_db_upsert_balance_still_preserves_old_balance_on_truly_dead_session` | def | L59–L89 |

### `test_bet_live_plan.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `test_operator_my_accounts_endpoint` | def | L5–L70 |
| `test_operator_my_accounts_withdrawal_institution_prefers_transaction_history` | def | L73–L124 |
| `test_operator_my_accounts_withdrawal_institution_falls_back_without_history` | def | L127–L160 |
| `test_operator_my_accounts_hides_fully_withdrawn_account` | def | L163–L212 |
| `test_operator_my_accounts_visibility_in_process_lock` | def | L215–L270 |
| `test_operator_my_accounts_sa_own_view_excludes_stale_reservada_sa_locks` | def | L273–L338 |
| `test_operator_my_accounts_dust_balance_excluded_below_one_peso` | def | L341–L401 |
| `test_username_portal_page_renders_for_own_user` | def | L404–L420 |
| `test_username_portal_page_404_for_unknown_username` | def | L423–L437 |
| `test_username_portal_page_canonicalizes_non_sa_to_own_username` | def | L440–L459 |
| `test_legacy_user_id_url_redirects_to_username` | def | L462–L480 |
| `test_confirm_gate_in_auto_deposit` | def | L484–L524 |

### `test_bin_stats_feedback.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_reload_app` | def | L16–L22 |
| `_bin_row` | def | L25–L30 |
| `test_record_attempt_approved_increments_bin_stats` | def | L33–L48 |
| `test_record_attempt_rejected_increments_bin_stats` | def | L51–L66 |
| `test_record_attempt_accumulates_across_attempts` | def | L69–L84 |
| `test_record_attempt_ignores_non_bank_status` | def | L87–L102 |
| `test_record_attempt_skips_bin_stats_without_pipe` | def | L105–L118 |

### `test_card_touch_log.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `test_record_attempt_logs_card_touch_full_pipe_no_mask` | def | L13–L41 |
| `test_record_attempt_skips_card_touch_when_no_pipe` | def | L44–L61 |

### `test_curp_utils.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `TestCurpUtils` | class | L6–L25 |

### `test_deposit_status_classify.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `test_bank_rejected_is_rejected` | def | L17–L18 |
| `test_bank_rejected_after_approve_is_rejected` | def | L21–L22 |
| `test_pending_not_applied_is_rejected` | def | L25–L27 |
| `test_substring_declines_are_rejected` | def | L30–L32 |
| `test_rate_limited_is_not_rejected` | def | L36–L37 |
| `test_dead_account_codes_are_account_dead` | def | L41–L43 |
| `test_login_codes_are_login_lost` | def | L47–L49 |
| `test_gateway_codes_are_gateway_error` | def | L52–L54 |
| `test_timeout_is_timeout` | def | L57–L58 |
| `test_ambiguous_charge_codes` | def | L62–L64 |
| `test_unknown_codes_are_incomplete_not_rejected` | def | L68–L72 |
| `test_success_is_approved` | def | L76–L78 |
| `test_3ds_is_threeds` | def | L82–L83 |
| `test_invariant_only_real_bank_declines_are_rejected` | def | L87–L95 |

### `test_deposit_step.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_run` | def | L17–L18 |
| `test_wrapper_emits_on_all_four_phase_closures` | def | L23–L65 |
| `test_submit_and_check_map_code` | def | L70–L89 |
| `test_wrapper_does_not_broadcast_on_other_phases` | def | L94–L114 |
| `test_role_filter_reuses_event_visible_to` | def | L119–L132 |

### `test_grading_a_plus_m7.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_load` | def | L23–L27 |
| `_txn` | def | L37–L43 |
| `_grade` | def | L46–L50 |
| `test_masacre_reciente_es_C_no_B` | def | L55–L59 |
| `test_masacre_descansada_sigue_C` | def | L62–L65 |
| `test_cinco_fails_aislados_reciente_es_C` | def | L68–L71 |
| `test_pocos_fails_aislados_es_B` | def | L74–L77 |
| `test_fail_reciente_es_D_aunque_sea_masacre` | def | L80–L83 |
| `test_sin_fails_es_A` | def | L86–L88 |
| `test_aprobacion_reciente_sana_sobre_masacre` | def | L93–L96 |
| `test_aprobacion_reciente_sana_sobre_fail_reciente` | def | L99–L102 |
| `test_dos_aprobados_recientes_es_A` | def | L105–L107 |
| `test_fail_reciente_puro_no_lo_salva_exito_viejo` | def | L110–L114 |
| `_mk_db` | def | L119–L133 |
| `_get` | def | L136–L143 |
| `test_aplus_una_decline_sigue_aplus` | def | L146–L149 |
| `test_aplus_dos_declines_seguidas_baja_a_B` | def | L152–L156 |
| `test_aprobado_resetea_streak` | def | L159–L162 |
| `test_decline_aprobado_decline_NO_baja` | def | L165–L171 |
| `test_ruido_no_banco_no_toca_streak` | def | L174–L178 |
| `test_cuenta_no_aplus_es_noop` | def | L181–L184 |

### `test_jwt_keeper.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_acc` | def | L16–L23 |
| `_run` | def | L26–L30 |
| `test_jwt_expirado_es_candidata` | def | L33–L35 |
| `test_jwt_nulo_es_candidata` | def | L38–L40 |
| `test_jwt_vigente_con_margen_no_es_candidata` | def | L43–L46 |
| `test_jwt_por_expirar_dentro_de_ventana_si_es_candidata` | def | L49–L51 |
| `test_en_cooldown_se_excluye` | def | L54–L56 |
| `test_cooldown_vencido_no_excluye` | def | L59–L61 |
| `test_lockeada_por_operador_se_excluye` | def | L64–L66 |
| `test_grade_no_util_se_excluye` | def | L69–L72 |
| `test_no_live_se_excluye` | def | L75–L77 |
| `test_no_publicada_se_excluye` | def | L80–L82 |
| `test_orden_por_grado_luego_urgencia` | def | L85–L94 |
| `test_batch_max_limita` | def | L97–L100 |
| `test_grades_configurable` | def | L103–L106 |
| `test_reservada_sa_jwt_expirado_es_candidata` | def | L109–L116 |
| `test_reservada_sa_locked_by_username_es_candidata` | def | L119–L123 |
| `test_reservada_sa_jwt_vigente_no_es_candidata` | def | L126–L130 |
| `test_reservada_no_sa_no_es_candidata` | def | L133–L137 |
| `test_hot_va_antes_que_normal_aun_con_grade_menor` | def | L148–L157 |
| `test_hot_no_cuenta_contra_batch_max` | def | L160–L166 |
| `test_hot_dentro_de_grupo_se_ordena_por_grade` | def | L169–L177 |
| `test_hot_excluye_si_no_es_candidata_normal` | def | L180–L185 |
| `test_hot_grade_no_util_sigue_siendo_candidata_si_hot_y_publicada` | def | L188–L194 |
| `test_hot_no_publicada_es_candidata` | def | L197–L201 |

### `test_maintenance_mode.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `client` | def | L6–L7 |
| `test_maintenance_mode_disabled_by_default` | def | L9–L12 |
| `test_maintenance_mode_redirects_unauth_user` | def | L14–L18 |
| `test_maintenance_mode_blocks_api` | def | L20–L24 |
| `test_maintenance_mode_allows_static_assets` | def | L26–L31 |
| `test_maintenance_mode_allows_superadmin` | def | L33–L39 |

### `test_marks.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `test_account_marks_table_exists` | def | L1–L5 |
| `test_toggle_is_idempotent_and_private` | def | L8–L15 |
| `test_marks_are_private_per_user` | def | L18–L22 |
| `test_mark_does_not_lock_or_change_visibility` | def | L25–L32 |

### `test_migrate_status_no_banco.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_mkdb` | def | L16–L31 |
| `_statuses` | def | L34–L36 |
| `test_rate_limit_reclassified` | def | L39–L42 |
| `test_rate_limit_raw_code_reclassified` | def | L45–L48 |
| `test_autoexclusion_reclassified` | def | L51–L54 |
| `test_login_and_gateway_reclassified` | def | L57–L64 |
| `test_real_bank_decline_untouched` | def | L67–L74 |
| `test_approved_untouched` | def | L77–L80 |
| `test_idempotent` | def | L83–L90 |
| `test_returns_counts_by_category` | def | L93–L103 |

### `test_mission_sem_leak.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_FakePool` | class | L19–L29 |
| `_Req` | class | L32–L38 |
| `test_mission_semaphore_released_on_early_client_abort` | def | L41–L70 |
| `test_mission_semaphore_released_on_normal_completion` | def | L73–L97 |

### `test_pool_manage.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `test_split_sa_only` | def | L2–L7 |
| `test_publish_moves_accounts` | def | L9–L22 |
| `test_publish_forbidden_for_operator` | def | L24–L26 |
| `test_hide_releases_sa_lock_but_protects_operator_lock` | def | L29–L52 |

### `test_refresh_single_guard.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `seed_account_expired_jwt` | def | L16–L37 |
| `test_single_row_refresh_bypasses_no_jwt_guard` | def | L40–L77 |

### `test_renapo_validator.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `TestRenapoValidator` | class | L10–L107 |

### `test_scheduled_deposit_3ds_logging.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_FakePool` | class | L14–L22 |
| `_FakeRequest` | class | L25–L30 |
| `sched_harness` | def | L34–L65 |
| `test_scheduled_3ds_abort_logs_it` | def | L69–L93 |

### `test_scheduled_deposit_card_locked.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_FakePool` | class | L16–L24 |
| `_FakeRequest` | class | L27–L32 |
| `sched_harness` | def | L36–L64 |
| `test_scheduled_card_locked_aborts_without_retry` | def | L68–L80 |

### `test_search.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_app` | def | L9–L12 |
| `test_search_empty` | def | L15–L19 |
| `test_search_single_term_covers_all_domain_fields` | def | L22–L28 |
| `test_search_numeric_normalizes_card` | def | L31–L36 |
| `test_search_multiterm_is_and` | def | L39–L44 |
| `test_search_bin_matches_card` | def | L47–L52 |
| `test_search_pipe_uses_first_segment_only` | def | L55–L62 |
| `test_search_combo_uses_email_only` | def | L65–L70 |

### `test_sse_visibility.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `test_sa_sees_everything` | def | L10–L13 |
| `test_operator_sees_own_by_who_id` | def | L16–L19 |
| `test_operator_sees_own_by_display_fallback` | def | L22–L25 |
| `test_operator_hidden_from_robert_actions` | def | L28–L31 |
| `test_service_event_addressed_to_operator` | def | L34–L37 |
| `test_actorless_service_event_hidden_from_operator` | def | L40–L44 |
| `test_who_fallback_requires_display` | def | L47–L51 |
| `test_broadcast_only_enqueues_visible` | def | L59–L69 |
| `test_resolve_who_carries_who_id` | def | L72–L76 |
| `test_broadcast_operator_receives_own` | def | L79–L88 |

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
| `test_update_keeps_session_on_normal_rejection` | def | L35–L40 |
| `test_check_caps_sa_bypass` | def | L43–L57 |
| `test_update_invalidates_on_bare_401` | def | L60–L64 |
| `test_update_invalidates_on_redirectlogin` | def | L67–L71 |

### `test_withdrawals.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_json_response` | def | L11–L12 |
| `test_get_bank_accounts_happy_one_approved` | def | L18–L38 |
| `test_get_bank_accounts_filters_non_approved` | def | L41–L72 |
| `test_get_bank_accounts_empty_aborts` | def | L75–L81 |
| `test_get_bank_accounts_multiple_approved_bug1` | def | L84–L113 |
| `test_get_bank_accounts_non200_raises` | def | L116–L122 |
| `test_get_bank_accounts_uses_proxy_and_canonical_headers` | def | L125–L146 |
| `test_get_bank_accounts_timeout_raises` | def | L149–L155 |
| `test_get_real_balance_happy` | def | L161–L167 |
| `test_get_real_balance_non200_raises` | def | L170–L176 |
| `test_get_real_balance_missing_real_key` | def | L179–L185 |
| `test_begin_withdrawal_happy_minimal_body` | def | L191–L201 |
| `test_begin_withdrawal_amount_is_float_not_string` | def | L204–L213 |
| `test_begin_withdrawal_400_concurrent_pending` | def | L216–L231 |
| `test_begin_withdrawal_401_jwt_dead` | def | L234–L244 |
| `test_begin_withdrawal_500_unexpected` | def | L247–L257 |
| `test_begin_withdrawal_no_transaction_id_in_200` | def | L260–L270 |
| `test_begin_withdrawal_sends_canonical_headers` | def | L273–L284 |
| `test_begin_withdrawal_does_not_retry_on_proxy_error` | def | L287–L298 |
| `test_get_pending_withdrawal_happy` | def | L304–L318 |
| `test_get_pending_withdrawal_none_when_no_pending` | def | L321–L327 |
| `test_get_pending_withdrawal_status6_returns_dict` | def | L330–L337 |
| `test_get_pending_withdrawal_non200_raises` | def | L340–L346 |
| `_txlist_response` | def | L358–L359 |
| `test_get_bank_transaction_happy` | def | L362–L386 |
| `test_get_bank_transaction_gateway2_spei_ok` | def | L389–L400 |
| `test_get_bank_transaction_gateway1_card_alert_bug3` | def | L403–L413 |
| `test_get_bank_transaction_digits_mismatch_alert_bug1` | def | L416–L430 |
| `test_get_bank_transaction_non200_raises` | def | L433–L439 |
| `test_get_bank_transaction_not_found_in_history_raises` | def | L442–L453 |
| `test_get_bank_transaction_hits_transactions_by_user_endpoint` | def | L456–L470 |
| `test_execute_withdrawal_full_flow_mocked` | def | L476–L516 |
| `test_execute_withdrawal_insufficient_balance` | def | L519–L543 |
| `test_execute_withdrawal_jwt_expired_no_api_call` | def | L546–L562 |
| `test_resolve_pending_to_successful_two_phase` | def | L571–L610 |
| `test_resolve_still_pending_status_not_6` | def | L613–L640 |
| `test_resolve_no_pending_bank_tx_confirms_6` | def | L643–L679 |
| `test_resolve_no_jwt_returns_idle` | def | L682–L701 |
| `test_resolve_prev_completed_stays_completed` | def | L704–L732 |
| `test_execute_withdrawal_persists_institution_bug2` | def | L738–L806 |

### `test_withdrawals_endpoints.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_acc_id` | def | L9–L16 |
| `_set_jwt` | def | L19–L29 |
| `_clear_jwt` | def | L32–L39 |
| `test_withdraw_403_for_non_sa` | def | L44–L48 |
| `test_withdraw_404_unknown_account` | def | L51–L54 |
| `test_withdraw_409_jwt_expired` | def | L57–L74 |
| `test_withdraw_409_no_jwt` | def | L77–L89 |
| `test_withdraw_409_no_approved_account` | def | L92–L104 |
| `test_withdraw_409_multiple_approved_bug1` | def | L107–L119 |
| `test_withdraw_409_insufficient_balance` | def | L122–L134 |
| `test_withdraw_409_concurrent_pending` | def | L137–L149 |
| `test_withdraw_happy_persists_and_broadcasts` | def | L152–L182 |
| `test_withdraw_amount_validation` | def | L185–L201 |
| `test_withdraw_broadcast_visible_to_sa_only` | def | L204–L210 |
| `test_withdraw_persist_idempotent_unique_transaction_id` | def | L213–L226 |
| `test_withdraw_triggers_refresh_after_success` | def | L231–L265 |
| `test_withdraw_skips_refresh_when_jwt_missing` | def | L268–L296 |
| `test_operator_withdraw_triggers_refresh_after_success` | def | L313–L347 |
| `test_operator_withdraw_skips_refresh_when_jwt_missing` | def | L350–L378 |
| `test_status_403_non_sa` | def | L382–L388 |
| `test_withdraw_status_operador_dueno_puede_consultar` | def | L391–L412 |
| `test_withdraw_status_operador_ajeno_403` | def | L415–L421 |
| `test_withdraw_status_operador_no_puede_leer_tx_de_otra_cuenta_via_account_id_propio` | def | L424–L445 |
| `test_status_404_unknown_tx` | def | L448–L452 |
| `test_status_happy_pending` | def | L455–L476 |
| `test_status_happy_successful_two_phase_bug2` | def | L479–L511 |
| `test_status_gateway_mismatch_alert_bug3` | def | L514–L540 |
| `test_status_digits_mismatch_alert_bug1` | def | L543–L569 |
| `test_status_no_pending_returns_idle` | def | L572–L591 |
| `test_status_updates_db_row` | def | L594–L627 |

### `test_withdrawals_migrate.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `test_migrate_creates_account_withdrawals` | def | L6–L21 |
| `test_migrate_transaction_id_unique` | def | L24–L39 |
| `test_migrate_idempotent` | def | L42–L46 |

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
| `get_bank_transaction` | def | L279–L361 |
| `_persist_wd_status` | def | L367–L392 |
| `resolve_withdrawal_status` | def | L395–L546 |
| `execute_withdrawal` | def | L552–L649 |
| `_refresh_account_after_withdrawal` | def | L652–L735 |
| `execute_auto_batch_withdrawal` | def | L743–L928 |
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
| `verify_all_accounts` | `scripts/verify_all_accounts_active.py` |
<!-- GEN:end:loggers -->

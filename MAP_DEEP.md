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
| `_sa_lock_tokens` | def | L36–L58 |
| `_env_int` | def | L61–L65 |
| `cfg` | def | L68–L78 |
| `select_refresh_candidates_healthy` | def | L82–L134 |
| `_exp_int` | def | L137–L143 |
| `is_hot_account` | def | L146–L163 |
| `_load_candidate_rows` | def | L177–L200 |
| `_db_get_withdrawal_ready` | def | L203–L209 |
| `_db_set_withdrawal_ready` | def | L212–L218 |
| `run_refresh_cycle` | def | L222–L374 |
| `run_refresh_cycle_from_env` | def | L377–L381 |

### `app.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `db` | def | L149–L195 |
| `_db_write_with_retry` | def | L198–L230 |
| `_migrate` | def | L233–L458 |
| `_backfill_grades_v10_m7` | def | L461–L532 |
| `_resolve_operator` | def | L538–L562 |
| `_is_sa` | def | L565–L567 |
| `_visible_emails` | def | L570–L592 |
| `_broadcast` | def | L599–L617 |
| `_dequeue_blocking` | def | L620–L625 |
| `_is_maintenance_active` | def | L634–L637 |
| `_maintenance_gate_middleware` | def | L640–L668 |
| `_no_cache_static_assets` | def | L672–L684 |
| `favicon` | def | L699–L700 |
| `maintenance_page` | def | L704–L705 |
| `login_page` | def | L709–L713 |
| `_asset_mtimes` | def | L730–L737 |
| `_frontend_version` | def | L740–L744 |
| `_own_portal_path` | def | L747–L748 |
| `_render_frontend_html` | def | L751–L775 |
| `user_portal_page` | def | L779–L795 |
| `portal_page` | def | L799–L806 |
| `dashboard_page` | def | L810–L824 |
| `index` | def | L828–L837 |
| `api_version` | def | L841–L851 |
| `auth_login` | def | L860–L891 |
| `auth_set_password` | def | L895–L919 |
| `auth_logout` | def | L923–L927 |
| `auth_me` | def | L931–L936 |
| `health` | def | L942–L948 |
| `_build_search_clause` | def | L951–L995 |
| `list_accounts` | def | L999–L1121 |
| `list_users` | def | L1127–L1135 |
| `list_assignments` | def | L1139–L1160 |
| `AssignRequest` | class | L1163–L1165 |
| `assign_accounts` | def | L1169–L1188 |
| `unassign_accounts` | def | L1192–L1203 |
| `stats` | def | L1207–L1214 |
| `_wsai_status` | def | L1229–L1254 |
| `_maybe_alert_broadcast` | def | L1261–L1278 |
| `_check_one_proxy` | def | L1281–L1307 |
| `_proxy_health` | def | L1310–L1359 |
| `_capmonster_balance` | def | L1362–L1382 |
| `_operator_color` | def | L1387–L1402 |
| `_resolve_who` | def | L1405–L1418 |
| `_event_visible_to` | def | L1421–L1447 |
| `superadmin_kpis` | def | L1451–L1694 |
| `RefreshRequest` | class | L1699–L1700 |
| `accounts_refresh` | def | L1704–L1723 |
| `_tail_log_file` | def | L1743–L1771 |
| `get_logs` | def | L1775–L1785 |
| `get_logs_telegram` | def | L1795–L1810 |
| `_run_health_checks` | def | L1818–L1854 |
| `health_full` | def | L1858–L1859 |
| `_require_sa` | def | L1867–L1869 |
| `admin_diag` | def | L1873–L1904 |
| `admin_ping` | def | L1908–L1929 |
| `admin_refresh_proxy` | def | L1933–L1940 |
| `admin_services_restart` | def | L1944–L1965 |
| `admin_export_logs` | def | L1969–L1985 |
| `admin_pause_state` | def | L1993–L1995 |
| `admin_pause` | def | L1999–L2011 |
| `admin_resume` | def | L2015–L2021 |
| `admin_emergency_stop` | def | L2025–L2060 |
| `admin_vps_reboot` | def | L2064–L2076 |
| `health_last` | def | L2080–L2081 |
| `health_dismiss` | def | L2085–L2088 |
| `api_marks_list` | def | L2092–L2099 |
| `api_marks_toggle` | def | L2103–L2121 |
| `api_recent` | def | L2125–L2197 |
| `api_accounts_at_hand` | def | L2201–L2309 |
| `_health_loop` | def | L2312–L2322 |
| `_release_account` | def | L2325–L2346 |
| `_run_lock_janitor` | def | L2349–L2397 |
| `_janitor_loop` | def | L2400–L2410 |
| `_run_window_watcher` | def | L2419–L2491 |
| `_window_watcher_loop` | def | L2494–L2503 |
| `_release_watchdog_tick` | def | L2506–L2605 |
| `_release_watchdog_loop` | def | L2608–L2616 |
| `_jwt_keepalive_loop` | def | L2619–L2636 |
| `_account_refresh_loop` | def | L2639–L2657 |
| `_bot_token` | def | L2663–L2672 |
| `_notify_robert` | def | L2675–L2690 |
| `_startup_telegram_notify` | def | L2693–L2717 |
| `_start_bg_tasks` | def | L2721–L2728 |
| `LockRequest` | class | L2731–L2733 |
| `lock_account` | def | L2737–L2776 |
| `PublishRequest` | class | L2779–L2781 |
| `publish_accounts` | def | L2785–L2814 |
| `hide_all_accounts` | def | L2818–L2833 |
| `pool_accounts` | def | L2837–L2855 |
| `api_pool_split` | def | L2859–L2873 |
| `api_pool_publish` | def | L2877–L2911 |
| `unlock_account` | def | L2915–L2933 |
| `_sse_generator` | def | L2936–L2962 |
| `events` | def | L2966–L2976 |
| `account_cards_pipe` | def | L2980–L3006 |
| `account_notes_summary` | def | L3010–L3035 |
| `_record_account_touch` | def | L3038–L3071 |
| `account_find_id` | def | L3075–L3081 |
| `account_details` | def | L3085–L3465 |
| `NoteCreate` | class | L3468–L3469 |
| `create_note` | def | L3473–L3502 |
| `CurpUpdate` | class | L3505–L3506 |
| `update_curp` | def | L3510–L3521 |
| `get_clabes` | def | L3531–L3540 |
| `refresh_clabes` | def | L3544–L3554 |
| `_persist_withdrawal` | def | L3563–L3609 |
| `withdraw` | def | L3613–L3658 |
| `withdraw_status` | def | L3662–L3822 |
| `delete_note` | def | L3826–L3838 |
| `CombosRequest` | class | L3841–L3842 |
| `accounts_combos` | def | L3846–L3859 |
| `accounts_pass_map` | def | L3863–L3868 |
| `list_all_cards` | def | L3872–L3948 |
| `activity_feed` | def | L3952–L4049 |
| `list_deposits` | def | L4053–L4082 |
| `deposits_stats` | def | L4086–L4111 |
| `_persist_auto_mission` | def | L4119–L4149 |
| `admin_maintenance_state` | def | L4153–L4156 |
| `MaintenanceToggleRequest` | class | L4159–L4160 |
| `admin_maintenance_toggle` | def | L4164–L4185 |
| `auto_deposit_create` | def | L4189–L4225 |
| `auto_deposit_cancel` | def | L4229–L4255 |
| `operator_my_accounts` | def | L4259–L4300 |
| `operator_release_account` | def | L4304–L4321 |
| `operator_withdraw` | def | L4325–L4376 |
| `operator_missions` | def | L4380–L4398 |
| `auto_deposit_status` | def | L4402–L4413 |
| `register_operator_strike` | def | L4416–L4449 |
| `bot_start_info` | def | L4453–L4489 |
| `bot_operator_info` | def | L4493–L4532 |
| `bot_help_info` | def | L4536–L4550 |
| `bot_pause_mission` | def | L4554–L4583 |
| `bot_resume_mission` | def | L4587–L4605 |
| `bot_cancel_mission` | def | L4610–L4645 |
| `bot_bet_create` | def | L4649–L4818 |
| `filter_and_sanitize_check_combos` | def | L4821–L4906 |
| `BotCheckRequest` | class | L4909–L4913 |
| `bot_check` | def | L4916–L4997 |

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
| `require_operator_view` | def | L167–L191 |

### `auto_deposit.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_now_epoch` | def | L22–L23 |
| `_grade_rank` | def | L26–L28 |
| `_sa_tokens` | def | L31–L41 |
| `_cd_active` | def | L44–L59 |
| `_exp_int` | def | L62–L68 |
| `_bin_of` | def | L71–L73 |
| `_approval_rate` | def | L76–L82 |
| `_threeds_recent` | def | L85–L99 |
| `_rank_key` | def | L102–L105 |
| `_pipe_str` | def | L108–L113 |
| `_parse_card_pipe` | def | L116–L137 |
| `_normalize_pipe_to_3part` | def | L140–L142 |
| `select_accounts_for_auto` | def | L149–L300 |
| `select_card_for_account` | def | L304–L326 |
| `_max_accounts_for_cards` | def | L330–L334 |
| `plan_auto_mission` | def | L337–L555 |
| `_iso` | def | L596–L597 |
| `_m_load` | def | L600–L607 |
| `_m_status` | def | L610–L612 |
| `_m_update` | def | L615–L624 |
| `_fetch_account` | def | L627–L633 |
| `_unlock` | def | L636–L644 |
| `_broadcast_mission` | def | L647–L661 |
| `_stop_pool` | def | L664–L671 |
| `run_auto_mission` | def | L675–L1041 |

### `autoexclusion.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_decode_jwt_userid` | def | L43–L57 |
| `_parse_resume_date` | def | L60–L71 |
| `check_autoexclusion` | def | L74–L134 |
| `autoexclusion_reason` | def | L137–L142 |
| `mark_account_autoexcluded` | def | L145–L177 |

### `card_checker.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `check_luhn` | def | L22–L35 |
| `parse_and_validate_card_pipe` | def | L38–L87 |
| `perform_wabox_liveness_check` | def | L90–L198 |
| `precheck_card_liveness` | def | L201–L217 |
| `format_ruthopia_liveness_summary` | def | L220–L234 |

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
| `seed_db` | def | L8–L116 |
| `client` | def | L119–L123 |
| `make_client` | def | L126–L138 |
| `mock_bmx_transport` | def | L142–L152 |

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
| `_cooldown_active` | def | L53–L62 |
| `_save_txns_via_app_db` | def | L65–L97 |
| `_set_account_cooldown` | def | L100–L113 |
| `_cooldown_remaining_min` | def | L116–L122 |
| `_is_transient_gateway_error` | def | L125–L135 |
| `_drain_stale_tokens` | def | L165–L197 |
| `_ensure_fresh_captcha` | def | L200–L224 |
| `_record_bin_3ds` | def | L232–L260 |
| `_bin_3ds_stats` | def | L263–L285 |
| `bin_check` | def | L289–L294 |
| `bin_stats_overview` | def | L298–L357 |
| `_auto_lock_for_deposit` | def | L360–L415 |
| `_window_status` | def | L418–L460 |
| `_check_caps` | def | L463–L479 |
| `_load_deps` | def | L482–L493 |
| `_parse_pipe` | def | L496–L517 |
| `_check_card_velocity` | def | L537–L584 |
| `_has_recent_approved_deposit` | def | L587–L603 |
| `_record_attempt` | def | L606–L748 |
| `_safe_phase` | def | L758–L765 |
| `_now_mx_str` | def | L773–L782 |
| `_deposit_step_payload` | def | L791–L799 |
| `_wrap_deposit_step` | def | L802–L821 |
| `_build_admin_proxy_url` | def | L824–L828 |
| `_refresh_account_after_deposit` | def | L831–L890 |
| `_should_relogin_after_401` | def | L893–L897 |
| `_acquire_session_and_begin` | def | L900–L1149 |
| `_run_deposit_with_phases` | def | L1152–L1496 |
| `deposit_execute_stream` | def | L1500–L1699 |
| `cap_status` | def | L1703–L1715 |
| `_mm_is_real_decline` | def | L1752–L1758 |
| `_mm_is_ambiguous_charge` | def | L1761–L1771 |
| `classify_deposit_status` | def | L1774–L1805 |
| `_mm_session_get` | def | L1851–L1855 |
| `_mm_session_update` | def | L1858–L1867 |
| `multi_stream` | def | L1871–L2386 |
| `multi_cancel` | def | L2390–L2395 |
| `scheduled_create` | def | L2408–L2774 |
| `scheduled_list` | def | L2778–L2800 |
| `scheduled_cancel` | def | L2804–L2812 |

### `jwt_keeper.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_env_int` | def | L38–L42 |
| `cfg` | def | L45–L71 |
| `select_refresh_candidates` | def | L75–L129 |
| `_exp_int` | def | L132–L138 |
| `_load_candidate_rows` | def | L146–L173 |
| `_set_cooldown` | def | L176–L183 |
| `_bump_rl_streak` | def | L186–L200 |
| `_reset_rl_streak` | def | L203–L210 |
| `run_keepalive_cycle` | def | L214–L313 |
| `run_keepalive_cycle_from_env` | def | L316–L323 |

### `login_orchestrator.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `StickySession` | class | L65–L73 |
| `parse_nodemaven_line` | def | L76–L93 |
| `StickySessionManager` | class | L96–L137 |
| `LoginResult` | class | L142–L159 |
| `_import_get_jwt` | def | L163–L166 |
| `_import_login_primitives` | def | L169–L177 |
| `_classify_dead` | def | L180–L192 |
| `_pool_session` | def | L195–L206 |
| `_jitter_base` | def | L209–L216 |
| `gentle_login` | def | L220–L416 |

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
| `_db_upsert_balance` | def | L208–L272 |
| `_db_save_txns_and_recalc` | def | L275–L328 |
| `_db_update_last_checked` | def | L331–L343 |
| `_db_invalidate_jwt` | def | L346–L357 |
| `_db_mark_dead` | def | L360–L383 |
| `_is_balance_fresh` | def | L386–L394 |
| `_capmonster_balance` | def | L399–L415 |
| `_run_prewarm` | def | L420–L595 |
| `prewarm_select` | def | L601–L682 |
| `prewarm_cancel` | def | L686–L696 |
| `prewarm_status` | def | L700–L715 |
| `prewarm_refresh_stream` | def | L721–L901 |

### `proxy_pool.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_bot_proxies` | def | L113–L119 |
| `all_proxies` | def | L122–L145 |
| `_to_url` | def | L148–L158 |
| `get_admin_proxy` | def | L161–L166 |
| `build_admin_proxy_url` | def | L169–L172 |
| `shuffled_proxy_urls` | def | L175–L183 |
| `_retry_exceptions` | def | L191–L217 |
| `_proxy_host` | def | L220–L224 |
| `call_with_proxy_failover` | def | L227–L318 |
| `_looks_like_proxy_failure_result` | def | L327–L346 |
| `_looks_like_captcha_failure_result` | def | L349–L364 |

### `renapo_validator.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_check_curp_with_proxy` | def | L24–L55 |
| `validate_renapo_curp` | def | L58–L90 |

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
| `_acc` | def | L32–L39 |
| `_run` | def | L42–L45 |
| `test_jwt_vigente_es_candidata` | def | L48–L50 |
| `test_jwt_expirado_no_es_candidata` | def | L53–L55 |
| `test_jwt_nulo_no_es_candidata` | def | L58–L60 |
| `test_jwt_vence_ahora_mismo_no_es_candidata` | def | L63–L65 |
| `test_lockeada_por_operador_se_excluye` | def | L68–L70 |
| `test_grade_no_util_se_excluye` | def | L73–L76 |
| `test_no_live_se_excluye` | def | L79–L81 |
| `test_no_publicada_se_excluye` | def | L84–L86 |
| `test_orden_por_last_checked_ascendente` | def | L89–L97 |
| `test_batch_max_limita` | def | L100–L103 |
| `test_grades_configurable` | def | L106–L109 |
| `test_reservada_sa_con_jwt_vigente_es_candidata` | def | L112–L118 |
| `test_reservada_sa_locked_by_username_es_candidata` | def | L121–L128 |
| `test_reservada_no_sa_no_es_candidata` | def | L131–L135 |
| `test_no_publicada_no_lockeada_no_es_candidata` | def | L138–L141 |
| `test_hot_lockeada_por_operador_no_sa_es_candidata` | def | L150–L153 |
| `test_hot_grade_no_util_es_candidata` | def | L156–L158 |
| `test_hot_no_publicada_es_candidata` | def | L161–L163 |
| `test_hot_sin_jwt_vigente_no_es_candidata` | def | L166–L169 |
| `test_hot_no_live_no_es_candidata` | def | L172–L174 |
| `test_hot_ignora_batch_max` | def | L177–L183 |
| `test_hot_va_primero_en_el_resultado` | def | L186–L190 |
| `_row` | def | L195–L200 |
| `test_hot_por_balance_alto` | def | L203–L204 |
| `test_no_hot_balance_50_exacto` | def | L207–L208 |
| `test_no_hot_balance_bajo_sin_lock_sin_retiro` | def | L211–L212 |
| `test_hot_por_ventana_de_autolock_activa` | def | L215–L216 |
| `test_no_hot_ventana_de_autolock_vencida` | def | L219–L220 |
| `test_hot_por_retiro_pendiente` | def | L223–L224 |
| `test_no_hot_sin_ninguna_señal` | def | L227–L228 |
| `db_conn` | def | L250–L263 |
| `test_load_candidate_rows_marca_hot_por_balance` | def | L266–L276 |
| `test_load_candidate_rows_marca_hot_por_retiro_pendiente` | def | L279–L296 |
| `test_load_candidate_rows_no_hot_normal` | def | L299–L311 |
| `test_db_set_and_get_withdrawal_ready` | def | L314–L332 |

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
| `test_ban_returns_rate_limited_immediately` | def | L89–L98 |
| `test_cooldown_active_future` | def | L102–L103 |
| `test_cooldown_active_past` | def | L106–L107 |
| `test_cooldown_active_none` | def | L110–L111 |
| `test_cooldown_active_zero` | def | L114–L115 |
| `test_cooldown_remaining_min_future` | def | L118–L119 |
| `test_cooldown_remaining_min_inactive` | def | L122–L124 |
| `test_relogin_when_cache_and_not_yet` | def | L128–L129 |
| `test_no_relogin_when_not_from_cache` | def | L132–L133 |
| `test_no_relogin_when_already_relogged` | def | L136–L137 |
| `_LR` | class | L141–L154 |
| `_fake_gentle` | def | L157–L165 |
| `_fake_begin` | def | L168–L176 |
| `_noop_phase` | def | L179–L180 |
| `_run_acquire` | def | L183–L204 |
| `test_acquire_fresh_login_then_begin_ok` | def | L207–L215 |
| `test_acquire_cache_hit_assigns_pool_proxy_not_proxyless` | def | L218–L225 |
| `test_acquire_cache_401_invalidates_and_relogins` | def | L228–L245 |
| `test_acquire_rate_limited_sets_cooldown_and_fails` | def | L248–L255 |
| `test_set_account_cooldown_persists` | def | L258–L271 |

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
| `test_confirm_gate_in_auto_deposit` | def | L74–L114 |

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
| `_acc` | def | L16–L22 |
| `_run` | def | L25–L29 |
| `test_jwt_expirado_es_candidata` | def | L32–L34 |
| `test_jwt_nulo_es_candidata` | def | L37–L39 |
| `test_jwt_vigente_con_margen_no_es_candidata` | def | L42–L45 |
| `test_jwt_por_expirar_dentro_de_ventana_si_es_candidata` | def | L48–L50 |
| `test_en_cooldown_se_excluye` | def | L53–L55 |
| `test_cooldown_vencido_no_excluye` | def | L58–L60 |
| `test_lockeada_por_operador_se_excluye` | def | L63–L65 |
| `test_grade_no_util_se_excluye` | def | L68–L71 |
| `test_no_live_se_excluye` | def | L74–L76 |
| `test_no_publicada_se_excluye` | def | L79–L81 |
| `test_orden_por_grado_luego_urgencia` | def | L84–L93 |
| `test_batch_max_limita` | def | L96–L99 |
| `test_grades_configurable` | def | L102–L105 |
| `test_reservada_sa_jwt_expirado_es_candidata` | def | L108–L115 |
| `test_reservada_sa_locked_by_username_es_candidata` | def | L118–L122 |
| `test_reservada_sa_jwt_vigente_no_es_candidata` | def | L125–L129 |
| `test_reservada_no_sa_no_es_candidata` | def | L132–L136 |

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
| `TestRenapoValidator` | class | L7–L47 |

### `test_scheduled_deposit_3ds_logging.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_FakePool` | class | L14–L22 |
| `_FakeRequest` | class | L25–L30 |
| `sched_harness` | def | L34–L65 |
| `test_scheduled_3ds_abort_logs_it` | def | L69–L93 |

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
| `test_get_bank_accounts_happy_one_approved` | def | L17–L27 |
| `test_get_bank_accounts_filters_non_approved` | def | L30–L40 |
| `test_get_bank_accounts_empty_aborts` | def | L43–L48 |
| `test_get_bank_accounts_multiple_approved_bug1` | def | L51–L66 |
| `test_get_bank_accounts_non200_raises` | def | L69–L74 |
| `test_get_bank_accounts_uses_proxy_and_canonical_headers` | def | L77–L87 |
| `test_get_bank_accounts_timeout_raises` | def | L90–L95 |
| `test_get_real_balance_happy` | def | L100–L105 |
| `test_get_real_balance_non200_raises` | def | L108–L113 |
| `test_get_real_balance_missing_real_key` | def | L116–L121 |
| `test_begin_withdrawal_happy_minimal_body` | def | L126–L135 |
| `test_begin_withdrawal_amount_is_float_not_string` | def | L138–L144 |
| `test_begin_withdrawal_400_concurrent_pending` | def | L147–L154 |
| `test_begin_withdrawal_401_jwt_dead` | def | L157–L162 |
| `test_begin_withdrawal_500_unexpected` | def | L165–L170 |
| `test_begin_withdrawal_no_transaction_id_in_200` | def | L173–L178 |
| `test_begin_withdrawal_sends_canonical_headers` | def | L181–L189 |
| `test_begin_withdrawal_does_not_retry_on_proxy_error` | def | L192–L198 |
| `test_get_pending_withdrawal_happy` | def | L203–L209 |
| `test_get_pending_withdrawal_none_when_no_pending` | def | L212–L217 |
| `test_get_pending_withdrawal_status6_returns_dict` | def | L220–L226 |
| `test_get_pending_withdrawal_non200_raises` | def | L229–L234 |
| `test_get_bank_transaction_happy` | def | L239–L250 |
| `test_get_bank_transaction_gateway2_spei_ok` | def | L253–L259 |
| `test_get_bank_transaction_gateway1_card_alert_bug3` | def | L262–L267 |
| `test_get_bank_transaction_digits_mismatch_alert_bug1` | def | L270–L279 |
| `test_get_bank_transaction_non200_raises` | def | L282–L287 |
| `test_execute_withdrawal_full_flow_mocked` | def | L292–L323 |
| `test_execute_withdrawal_insufficient_balance` | def | L326–L343 |
| `test_execute_withdrawal_jwt_expired_no_api_call` | def | L346–L361 |

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
| `test_status_403_non_sa` | def | L231–L237 |
| `test_withdraw_status_operador_dueno_puede_consultar` | def | L240–L261 |
| `test_withdraw_status_operador_ajeno_403` | def | L264–L270 |
| `test_withdraw_status_operador_no_puede_leer_tx_de_otra_cuenta_via_account_id_propio` | def | L273–L294 |
| `test_status_404_unknown_tx` | def | L297–L301 |
| `test_status_happy_pending` | def | L304–L325 |
| `test_status_happy_successful_two_phase_bug2` | def | L328–L360 |
| `test_status_gateway_mismatch_alert_bug3` | def | L363–L389 |
| `test_status_digits_mismatch_alert_bug1` | def | L392–L418 |
| `test_status_no_pending_returns_idle` | def | L421–L440 |
| `test_status_updates_db_row` | def | L443–L476 |

### `test_withdrawals_migrate.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `test_migrate_creates_account_withdrawals` | def | L6–L21 |
| `test_migrate_transaction_id_unique` | def | L24–L39 |
| `test_migrate_idempotent` | def | L42–L46 |

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
| `WithdrawalError` | class | L44–L45 |
| `JwtExpired` | class | L48–L49 |
| `NoApprovedWithdrawalAccount` | class | L52–L53 |
| `MultipleApprovedAccounts` | class | L56–L57 |
| `InsufficientBalance` | class | L60–L61 |
| `ConcurrentWithdrawalPending` | class | L64–L65 |
| `_auth_headers` | def | L70–L71 |
| `_client_kwargs` | def | L74–L78 |
| `get_bank_accounts` | def | L83–L126 |
| `get_real_balance` | def | L131–L158 |
| `begin_withdrawal` | def | L163–L221 |
| `get_pending_withdrawal` | def | L226–L255 |
| `get_bank_transaction` | def | L260–L312 |
| `execute_withdrawal` | def | L317–L388 |
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
| `GET` | `/api/operator/missions` | `app.py` |
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
| `betmexico.dashboard.account_refresh` | `account_refresh.py` |
| `betmexico.dashboard.auto_deposit` | `auto_deposit.py` |
| `betmexico.dashboard.autoexclusion` | `autoexclusion.py` |
| `betmexico.dashboard.clabe_fetch` | `clabe_fetch.py` |
| `betmexico.dashboard.db` | `app.py` |
| `betmexico.dashboard.deposits` | `deposits.py` |
| `betmexico.dashboard.grading` | `app.py` |
| `betmexico.dashboard.jwt_keeper` | `jwt_keeper.py` |
| `betmexico.dashboard.login_orch` | `login_orchestrator.py` |
| `betmexico.dashboard.prewarm` | `prewarm.py` |
| `betmexico.dashboard.sse` | `app.py` |
| `betmexico.dashboard.withdrawals` | `withdrawals.py` |
| `betmexico.renapo_validator` | `renapo_validator.py` |
| `betmexico.web.auth` | `web_auth.py` |
| `betmexico.web.grading` | `web_grading.py` |
| `betmexico.web.utils` | `web_utils.py` |
| `dashboard.proxy_pool` | `proxy_pool.py` |
<!-- GEN:end:loggers -->

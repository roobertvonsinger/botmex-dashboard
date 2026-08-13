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
| `db` | def | L170–L223 |
| `_db_write_with_retry` | def | L226–L258 |
| `_migrate` | def | L261–L495 |
| `_backfill_grades_v10_m7` | def | L498–L569 |
| `_resolve_operator` | def | L575–L599 |
| `_is_sa` | def | L602–L604 |
| `_visible_emails` | def | L607–L629 |
| `_broadcast` | def | L636–L654 |
| `_dequeue_blocking` | def | L657–L662 |
| `_is_maintenance_active` | def | L671–L674 |
| `_maintenance_gate_middleware` | def | L677–L705 |
| `_no_cache_static_assets` | def | L709–L721 |
| `favicon` | def | L736–L737 |
| `maintenance_page` | def | L741–L742 |
| `login_page` | def | L746–L750 |
| `_asset_mtimes` | def | L767–L774 |
| `_frontend_version` | def | L777–L781 |
| `_own_portal_path` | def | L784–L785 |
| `_render_frontend_html` | def | L788–L812 |
| `user_portal_page` | def | L816–L831 |
| `portal_page` | def | L835–L842 |
| `dashboard_page` | def | L846–L860 |
| `index` | def | L864–L873 |
| `username_portal_page` | def | L877–L903 |
| `api_version` | def | L907–L917 |
| `auth_login` | def | L926–L957 |
| `auth_set_password` | def | L961–L985 |
| `auth_logout` | def | L989–L993 |
| `auth_me` | def | L997–L1007 |
| `health` | def | L1013–L1019 |
| `_build_search_clause` | def | L1022–L1066 |
| `list_accounts` | def | L1070–L1200 |
| `list_users` | def | L1206–L1214 |
| `list_assignments` | def | L1218–L1239 |
| `AssignRequest` | class | L1242–L1244 |
| `assign_accounts` | def | L1248–L1267 |
| `unassign_accounts` | def | L1271–L1282 |
| `stats` | def | L1286–L1293 |
| `_wsai_status` | def | L1308–L1333 |
| `_maybe_alert_broadcast` | def | L1340–L1357 |
| `_check_one_proxy` | def | L1360–L1386 |
| `_proxy_health` | def | L1389–L1438 |
| `_capmonster_balance` | def | L1441–L1461 |
| `_operator_color` | def | L1466–L1481 |
| `_resolve_who` | def | L1484–L1497 |
| `_event_visible_to` | def | L1500–L1526 |
| `superadmin_kpis` | def | L1530–L1773 |
| `RefreshRequest` | class | L1778–L1779 |
| `accounts_refresh` | def | L1783–L1802 |
| `_tail_log_file` | def | L1829–L1857 |
| `get_logs` | def | L1861–L1883 |
| `get_logs_telegram` | def | L1893–L1908 |
| `_run_health_checks` | def | L1916–L1952 |
| `health_full` | def | L1956–L1957 |
| `_require_sa` | def | L1965–L1967 |
| `admin_diag` | def | L1971–L2002 |
| `admin_ping` | def | L2006–L2027 |
| `admin_refresh_proxy` | def | L2031–L2038 |
| `admin_services_restart` | def | L2042–L2063 |
| `admin_export_logs` | def | L2067–L2083 |
| `admin_pause_state` | def | L2091–L2093 |
| `admin_pause` | def | L2097–L2109 |
| `admin_resume` | def | L2113–L2119 |
| `admin_emergency_stop` | def | L2123–L2158 |
| `admin_vps_reboot` | def | L2162–L2174 |
| `health_last` | def | L2178–L2179 |
| `health_dismiss` | def | L2183–L2186 |
| `api_marks_list` | def | L2190–L2197 |
| `api_marks_toggle` | def | L2201–L2219 |
| `api_recent` | def | L2223–L2295 |
| `api_accounts_at_hand` | def | L2299–L2407 |
| `_health_loop` | def | L2410–L2420 |
| `_release_account` | def | L2423–L2444 |
| `_run_lock_janitor` | def | L2447–L2495 |
| `_janitor_loop` | def | L2498–L2508 |
| `_run_window_watcher` | def | L2517–L2589 |
| `_window_watcher_loop` | def | L2592–L2601 |
| `_release_watchdog_tick` | def | L2604–L2703 |
| `_release_watchdog_loop` | def | L2706–L2714 |
| `_jwt_keepalive_loop` | def | L2717–L2745 |
| `_wake_jwt_keeper` | def | L2752–L2763 |
| `_account_refresh_loop` | def | L2766–L2784 |
| `_bot_token` | def | L2790–L2799 |
| `_notify_robert` | def | L2802–L2817 |
| `_startup_telegram_notify` | def | L2820–L2844 |
| `_lifespan` | def | L2848–L2859 |
| `LockRequest` | class | L2865–L2867 |
| `lock_account` | def | L2871–L2910 |
| `PublishRequest` | class | L2913–L2915 |
| `publish_accounts` | def | L2919–L2948 |
| `hide_all_accounts` | def | L2952–L2967 |
| `pool_accounts` | def | L2971–L2989 |
| `api_pool_split` | def | L2993–L3007 |
| `api_pool_publish` | def | L3011–L3045 |
| `unlock_account` | def | L3049–L3067 |
| `_sse_generator` | def | L3070–L3096 |
| `events` | def | L3100–L3110 |
| `account_cards_pipe` | def | L3114–L3140 |
| `account_notes_summary` | def | L3144–L3169 |
| `_record_account_touch` | def | L3172–L3205 |
| `account_find_id` | def | L3209–L3215 |
| `account_details` | def | L3219–L3599 |
| `NoteCreate` | class | L3602–L3603 |
| `create_note` | def | L3607–L3636 |
| `CurpUpdate` | class | L3639–L3640 |
| `update_curp` | def | L3644–L3655 |
| `get_clabes` | def | L3665–L3674 |
| `refresh_clabes` | def | L3678–L3688 |
| `_persist_withdrawal` | def | L3697–L3743 |
| `withdraw` | def | L3747–L3799 |
| `withdraw_status` | def | L3803–L3854 |
| `delete_note` | def | L3858–L3870 |
| `CombosRequest` | class | L3873–L3874 |
| `accounts_combos` | def | L3878–L3891 |
| `accounts_pass_map` | def | L3895–L3900 |
| `list_all_cards` | def | L3904–L3980 |
| `activity_feed` | def | L3984–L4081 |
| `list_deposits` | def | L4085–L4114 |
| `deposits_stats` | def | L4118–L4143 |
| `_persist_auto_mission` | def | L4151–L4181 |
| `admin_maintenance_state` | def | L4185–L4188 |
| `MaintenanceToggleRequest` | class | L4191–L4192 |
| `admin_maintenance_toggle` | def | L4196–L4217 |
| `auto_deposit_create` | def | L4221–L4257 |
| `auto_deposit_cancel` | def | L4261–L4287 |
| `operator_my_accounts` | def | L4291–L4381 |
| `operator_release_account` | def | L4385–L4402 |
| `operator_withdraw` | def | L4406–L4464 |
| `operator_missions` | def | L4468–L4486 |
| `auto_deposit_status` | def | L4490–L4501 |
| `register_operator_strike` | def | L4504–L4537 |
| `bot_start_info` | def | L4541–L4577 |
| `bot_operator_info` | def | L4581–L4620 |
| `bot_help_info` | def | L4624–L4638 |
| `bot_pause_mission` | def | L4642–L4671 |
| `bot_resume_mission` | def | L4675–L4693 |
| `bot_cancel_mission` | def | L4698–L4733 |
| `bot_bet_create` | def | L4737–L4906 |
| `filter_and_sanitize_check_combos` | def | L4909–L4994 |
| `BotCheckRequest` | class | L4997–L5001 |
| `bot_check` | def | L5004–L5085 |

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
| `_parse_card_pipe` | def | L124–L145 |
| `_normalize_pipe_to_3part` | def | L148–L150 |
| `select_accounts_for_auto` | def | L159–L349 |
| `_max_accounts_for_cards` | def | L358–L366 |
| `plan_auto_mission` | def | L369–L599 |
| `_fake_progress_pct` | def | L640–L671 |
| `_iso` | def | L675–L676 |
| `_m_load` | def | L679–L687 |
| `_m_status` | def | L690–L692 |
| `_m_update` | def | L695–L705 |
| `_fetch_account` | def | L708–L715 |
| `_unlock` | def | L718–L727 |
| `_broadcast_mission` | def | L730–L759 |
| `_stop_pool` | def | L762–L769 |
| `run_auto_mission` | def | L773–L1466 |

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
| `_load_ruthopia_dashboard_token` | def | L29–L42 |
| `ruthopia_bridge_check` | def | L45–L82 |
| `check_luhn` | def | L85–L98 |
| `parse_and_validate_card_pipe` | def | L101–L150 |
| `perform_wabox_liveness_check` | def | L158–L284 |
| `precheck_card_liveness` | def | L287–L377 |
| `format_ruthopia_liveness_summary` | def | L380–L394 |

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
| `seed_db` | def | L8–L118 |
| `client` | def | L121–L125 |
| `make_client` | def | L128–L140 |
| `mock_bmx_transport` | def | L144–L154 |

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
| `bin_check` | def | L320–L325 |
| `bin_stats_overview` | def | L329–L388 |
| `_auto_lock_for_deposit` | def | L391–L447 |
| `_window_status` | def | L450–L492 |
| `_check_caps` | def | L495–L511 |
| `_load_deps` | def | L514–L525 |
| `_parse_pipe` | def | L528–L549 |
| `_check_card_velocity` | def | L569–L616 |
| `_has_recent_approved_deposit` | def | L619–L635 |
| `_record_attempt` | def | L638–L820 |
| `_safe_phase` | def | L830–L837 |
| `_now_mx_str` | def | L845–L854 |
| `_deposit_step_payload` | def | L863–L871 |
| `_wrap_deposit_step` | def | L874–L893 |
| `_build_admin_proxy_url` | def | L896–L900 |
| `_refresh_account_after_deposit` | def | L903–L962 |
| `_should_relogin_after_401` | def | L965–L969 |
| `_acquire_session_and_begin` | def | L972–L1225 |
| `_run_deposit_with_phases` | def | L1228–L1572 |
| `deposit_execute_stream` | def | L1576–L1775 |
| `cap_status` | def | L1779–L1791 |
| `_mm_is_real_decline` | def | L1828–L1834 |
| `_mm_is_ambiguous_charge` | def | L1837–L1847 |
| `classify_deposit_status` | def | L1850–L1881 |
| `_mm_session_get` | def | L1927–L1931 |
| `_mm_session_update` | def | L1934–L1943 |
| `multi_stream` | def | L1947–L2461 |
| `multi_cancel` | def | L2465–L2470 |
| `scheduled_create` | def | L2483–L2847 |
| `scheduled_list` | def | L2851–L2873 |
| `scheduled_cancel` | def | L2877–L2885 |

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
| `betmexico.dashboard.account_refresh` | `app.py` |
| `betmexico.dashboard.auto_deposit` | `auto_deposit.py` |
| `betmexico.dashboard.autoexclusion` | `autoexclusion.py` |
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
| `betmexico.renapo_validator` | `renapo_validator.py` |
| `betmexico.web.auth` | `web_auth.py` |
| `betmexico.web.grading` | `web_grading.py` |
| `betmexico.web.utils` | `web_utils.py` |
| `dashboard.proxy_pool` | `proxy_pool.py` |
| `verify_all_accounts` | `scripts/verify_all_accounts_active.py` |
<!-- GEN:end:loggers -->

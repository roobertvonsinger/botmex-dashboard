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
| `_env_int` | def | L36–L40 |
| `cfg` | def | L43–L53 |
| `select_refresh_candidates_healthy` | def | L57–L89 |
| `_exp_int` | def | L92–L98 |
| `_load_candidate_rows` | def | L106–L116 |
| `run_refresh_cycle` | def | L120–L230 |
| `run_refresh_cycle_from_env` | def | L233–L237 |

### `app.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `db` | def | L124–L138 |
| `_migrate` | def | L141–L234 |
| `_backfill_grades_v10_m7` | def | L237–L308 |
| `_resolve_operator` | def | L314–L338 |
| `_is_sa` | def | L341–L343 |
| `_visible_emails` | def | L346–L368 |
| `_broadcast` | def | L375–L393 |
| `_dequeue_blocking` | def | L396–L401 |
| `_no_cache_static_assets` | def | L409–L421 |
| `favicon` | def | L429–L430 |
| `login_page` | def | L434–L437 |
| `_asset_mtimes` | def | L453–L460 |
| `_frontend_version` | def | L463–L467 |
| `index` | def | L471–L495 |
| `api_version` | def | L499–L509 |
| `auth_login` | def | L518–L549 |
| `auth_set_password` | def | L553–L577 |
| `auth_logout` | def | L581–L585 |
| `auth_me` | def | L589–L594 |
| `health` | def | L600–L606 |
| `_build_search_clause` | def | L609–L653 |
| `list_accounts` | def | L657–L773 |
| `list_users` | def | L779–L787 |
| `list_assignments` | def | L791–L812 |
| `AssignRequest` | class | L815–L817 |
| `assign_accounts` | def | L821–L840 |
| `unassign_accounts` | def | L844–L855 |
| `stats` | def | L859–L866 |
| `_wsai_status` | def | L881–L906 |
| `_maybe_alert_broadcast` | def | L913–L930 |
| `_check_one_proxy` | def | L933–L959 |
| `_proxy_health` | def | L962–L1011 |
| `_capmonster_balance` | def | L1014–L1034 |
| `_operator_color` | def | L1039–L1054 |
| `_resolve_who` | def | L1057–L1070 |
| `_event_visible_to` | def | L1073–L1099 |
| `superadmin_kpis` | def | L1103–L1346 |
| `RefreshRequest` | class | L1351–L1352 |
| `accounts_refresh` | def | L1356–L1375 |
| `get_logs` | def | L1381–L1406 |
| `_run_health_checks` | def | L1414–L1450 |
| `health_full` | def | L1454–L1455 |
| `_require_sa` | def | L1463–L1465 |
| `admin_diag` | def | L1469–L1500 |
| `admin_ping` | def | L1504–L1525 |
| `admin_refresh_proxy` | def | L1529–L1536 |
| `admin_services_restart` | def | L1540–L1554 |
| `admin_export_logs` | def | L1558–L1570 |
| `admin_pause_state` | def | L1578–L1580 |
| `admin_pause` | def | L1584–L1596 |
| `admin_resume` | def | L1600–L1606 |
| `admin_emergency_stop` | def | L1610–L1645 |
| `admin_vps_reboot` | def | L1649–L1661 |
| `health_last` | def | L1665–L1666 |
| `health_dismiss` | def | L1670–L1673 |
| `api_marks_list` | def | L1677–L1684 |
| `api_marks_toggle` | def | L1688–L1706 |
| `api_recent` | def | L1710–L1782 |
| `api_accounts_at_hand` | def | L1786–L1894 |
| `_health_loop` | def | L1897–L1907 |
| `_release_account` | def | L1910–L1931 |
| `_run_lock_janitor` | def | L1934–L1982 |
| `_janitor_loop` | def | L1985–L1995 |
| `_run_window_watcher` | def | L2004–L2076 |
| `_window_watcher_loop` | def | L2079–L2088 |
| `_release_watchdog_tick` | def | L2091–L2190 |
| `_release_watchdog_loop` | def | L2193–L2201 |
| `_jwt_keepalive_loop` | def | L2204–L2221 |
| `_account_refresh_loop` | def | L2224–L2242 |
| `_start_bg_tasks` | def | L2246–L2252 |
| `LockRequest` | class | L2255–L2257 |
| `lock_account` | def | L2261–L2300 |
| `PublishRequest` | class | L2303–L2305 |
| `publish_accounts` | def | L2309–L2338 |
| `hide_all_accounts` | def | L2342–L2357 |
| `pool_accounts` | def | L2361–L2379 |
| `api_pool_split` | def | L2383–L2397 |
| `api_pool_publish` | def | L2401–L2435 |
| `unlock_account` | def | L2439–L2457 |
| `_sse_generator` | def | L2460–L2486 |
| `events` | def | L2490–L2500 |
| `account_cards_pipe` | def | L2504–L2530 |
| `account_notes_summary` | def | L2534–L2559 |
| `account_details` | def | L2563–L2864 |
| `NoteCreate` | class | L2867–L2868 |
| `create_note` | def | L2872–L2901 |
| `CurpUpdate` | class | L2904–L2905 |
| `update_curp` | def | L2909–L2920 |
| `delete_note` | def | L2924–L2936 |
| `CombosRequest` | class | L2939–L2940 |
| `accounts_combos` | def | L2944–L2957 |
| `accounts_pass_map` | def | L2961–L2966 |
| `list_all_cards` | def | L2970–L3045 |
| `activity_feed` | def | L3049–L3170 |
| `list_deposits` | def | L3174–L3203 |
| `deposits_stats` | def | L3207–L3232 |

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
| `_cooldown_active` | def | L53–L62 |
| `_set_account_cooldown` | def | L65–L75 |
| `_cooldown_remaining_min` | def | L78–L84 |
| `_is_transient_gateway_error` | def | L87–L97 |
| `_drain_stale_tokens` | def | L127–L159 |
| `_ensure_fresh_captcha` | def | L162–L186 |
| `_record_bin_3ds` | def | L194–L222 |
| `_bin_3ds_stats` | def | L225–L247 |
| `bin_check` | def | L251–L256 |
| `bin_stats_overview` | def | L260–L319 |
| `_auto_lock_for_deposit` | def | L322–L373 |
| `_window_status` | def | L376–L418 |
| `_check_caps` | def | L421–L434 |
| `_load_deps` | def | L437–L448 |
| `_parse_pipe` | def | L451–L472 |
| `_check_card_velocity` | def | L492–L539 |
| `_record_attempt` | def | L542–L662 |
| `_safe_phase` | def | L672–L679 |
| `_now_mx_str` | def | L687–L696 |
| `_deposit_step_payload` | def | L705–L713 |
| `_wrap_deposit_step` | def | L716–L735 |
| `_build_admin_proxy_url` | def | L738–L742 |
| `_refresh_account_after_deposit` | def | L745–L804 |
| `_should_relogin_after_401` | def | L807–L811 |
| `_acquire_session_and_begin` | def | L814–L1062 |
| `_run_deposit_with_phases` | def | L1065–L1379 |
| `deposit_execute_stream` | def | L1383–L1583 |
| `cap_status` | def | L1587–L1599 |
| `_mm_is_real_decline` | def | L1636–L1642 |
| `_mm_is_ambiguous_charge` | def | L1645–L1655 |
| `classify_deposit_status` | def | L1658–L1689 |
| `_mm_session_get` | def | L1739–L1743 |
| `_mm_session_update` | def | L1746–L1755 |
| `multi_stream` | def | L1759–L2256 |
| `multi_cancel` | def | L2260–L2265 |
| `scheduled_create` | def | L2278–L2641 |
| `scheduled_list` | def | L2645–L2667 |
| `scheduled_cancel` | def | L2671–L2679 |

### `jwt_keeper.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_env_int` | def | L38–L42 |
| `cfg` | def | L45–L71 |
| `select_refresh_candidates` | def | L75–L115 |
| `_exp_int` | def | L118–L124 |
| `_load_candidate_rows` | def | L132–L141 |
| `_set_cooldown` | def | L144–L151 |
| `_bump_rl_streak` | def | L154–L167 |
| `_reset_rl_streak` | def | L170–L176 |
| `run_keepalive_cycle` | def | L180–L278 |
| `run_keepalive_cycle_from_env` | def | L281–L288 |

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
| `gentle_login` | def | L220–L410 |

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
| `_fetch_looks_empty` | def | L178–L204 |
| `_db_upsert_balance` | def | L207–L262 |
| `_db_save_txns_and_recalc` | def | L265–L287 |
| `_db_update_last_checked` | def | L290–L302 |
| `_db_invalidate_jwt` | def | L305–L316 |
| `_db_mark_dead` | def | L319–L342 |
| `_is_balance_fresh` | def | L345–L353 |
| `_capmonster_balance` | def | L358–L374 |
| `_run_prewarm` | def | L379–L564 |
| `prewarm_select` | def | L570–L651 |
| `prewarm_cancel` | def | L655–L665 |
| `prewarm_status` | def | L669–L684 |
| `prewarm_refresh_stream` | def | L690–L870 |

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
| `score_payment_readiness` | def | L247–L430 |
| `analyze_gateway_ban_pattern` | def | L437–L507 |
| `generate_payment_analysis_summary` | def | L514–L562 |
| `generate_payment_ready_txt` | def | L565–L593 |

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
| `_acc` | def | L14–L20 |
| `_run` | def | L23–L25 |
| `test_jwt_vigente_es_candidata` | def | L28–L30 |
| `test_jwt_expirado_no_es_candidata` | def | L33–L35 |
| `test_jwt_nulo_no_es_candidata` | def | L38–L40 |
| `test_jwt_vence_ahora_mismo_no_es_candidata` | def | L43–L45 |
| `test_lockeada_por_operador_se_excluye` | def | L48–L50 |
| `test_grade_no_util_se_excluye` | def | L53–L56 |
| `test_no_live_se_excluye` | def | L59–L61 |
| `test_no_publicada_se_excluye` | def | L64–L66 |
| `test_orden_por_last_checked_ascendente` | def | L69–L77 |
| `test_batch_max_limita` | def | L80–L83 |
| `test_grades_configurable` | def | L86–L89 |

### `test_account_touch.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `test_actor_operator_does_not_see_own_touch` | def | L10–L12 |
| `test_sa_does_not_see_own_touch` | def | L15–L18 |
| `test_sa_sees_others_touch` | def | L21–L23 |
| `test_operator_does_not_see_others_touch` | def | L26–L28 |
| `test_touch_dedup_one_per_day` | def | L31–L51 |

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
| `_run` | def | L25–L27 |
| `test_jwt_expirado_es_candidata` | def | L30–L32 |
| `test_jwt_nulo_es_candidata` | def | L35–L37 |
| `test_jwt_vigente_con_margen_no_es_candidata` | def | L40–L43 |
| `test_jwt_por_expirar_dentro_de_ventana_si_es_candidata` | def | L46–L48 |
| `test_en_cooldown_se_excluye` | def | L51–L53 |
| `test_cooldown_vencido_no_excluye` | def | L56–L58 |
| `test_lockeada_por_operador_se_excluye` | def | L61–L63 |
| `test_grade_no_util_se_excluye` | def | L66–L69 |
| `test_no_live_se_excluye` | def | L72–L74 |
| `test_no_publicada_se_excluye` | def | L77–L79 |
| `test_orden_por_grado_luego_urgencia` | def | L82–L91 |
| `test_batch_max_limita` | def | L94–L97 |
| `test_grades_configurable` | def | L100–L103 |

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
| `recalc_grade_from_db` | def | L47–L93 |
| `recalc_grade_from_details` | def | L96–L121 |
| `note_a_plus_outcome` | def | L124–L179 |

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
| `betmexico.dashboard.account_refresh` | `account_refresh.py` |
| `betmexico.dashboard.autoexclusion` | `autoexclusion.py` |
| `betmexico.dashboard.deposits` | `deposits.py` |
| `betmexico.dashboard.grading` | `app.py` |
| `betmexico.dashboard.jwt_keeper` | `jwt_keeper.py` |
| `betmexico.dashboard.login_orch` | `login_orchestrator.py` |
| `betmexico.dashboard.prewarm` | `prewarm.py` |
| `betmexico.dashboard.sse` | `app.py` |
| `betmexico.web.auth` | `web_auth.py` |
| `betmexico.web.grading` | `web_grading.py` |
| `betmexico.web.utils` | `web_utils.py` |
| `dashboard.proxy_pool` | `proxy_pool.py` |
<!-- GEN:end:loggers -->

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
| `select_refresh_candidates_healthy` | def | L82–L132 |
| `_exp_int` | def | L135–L141 |
| `_load_candidate_rows` | def | L149–L178 |
| `run_refresh_cycle` | def | L182–L293 |
| `run_refresh_cycle_from_env` | def | L296–L300 |

### `app.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `db` | def | L145–L191 |
| `_db_write_with_retry` | def | L194–L226 |
| `_migrate` | def | L229–L421 |
| `_backfill_grades_v10_m7` | def | L424–L495 |
| `_resolve_operator` | def | L501–L525 |
| `_is_sa` | def | L528–L530 |
| `_visible_emails` | def | L533–L555 |
| `_broadcast` | def | L562–L580 |
| `_dequeue_blocking` | def | L583–L588 |
| `_no_cache_static_assets` | def | L596–L608 |
| `favicon` | def | L616–L617 |
| `login_page` | def | L621–L624 |
| `_asset_mtimes` | def | L640–L647 |
| `_frontend_version` | def | L650–L654 |
| `index` | def | L658–L682 |
| `api_version` | def | L686–L696 |
| `auth_login` | def | L705–L736 |
| `auth_set_password` | def | L740–L764 |
| `auth_logout` | def | L768–L772 |
| `auth_me` | def | L776–L781 |
| `health` | def | L787–L793 |
| `_build_search_clause` | def | L796–L840 |
| `list_accounts` | def | L844–L964 |
| `list_users` | def | L970–L978 |
| `list_assignments` | def | L982–L1003 |
| `AssignRequest` | class | L1006–L1008 |
| `assign_accounts` | def | L1012–L1031 |
| `unassign_accounts` | def | L1035–L1046 |
| `stats` | def | L1050–L1057 |
| `_wsai_status` | def | L1072–L1097 |
| `_maybe_alert_broadcast` | def | L1104–L1121 |
| `_check_one_proxy` | def | L1124–L1150 |
| `_proxy_health` | def | L1153–L1202 |
| `_capmonster_balance` | def | L1205–L1225 |
| `_operator_color` | def | L1230–L1245 |
| `_resolve_who` | def | L1248–L1261 |
| `_event_visible_to` | def | L1264–L1290 |
| `superadmin_kpis` | def | L1294–L1537 |
| `RefreshRequest` | class | L1542–L1543 |
| `accounts_refresh` | def | L1547–L1566 |
| `get_logs` | def | L1587–L1622 |
| `_run_health_checks` | def | L1630–L1666 |
| `health_full` | def | L1670–L1671 |
| `_require_sa` | def | L1679–L1681 |
| `admin_diag` | def | L1685–L1716 |
| `admin_ping` | def | L1720–L1741 |
| `admin_refresh_proxy` | def | L1745–L1752 |
| `admin_services_restart` | def | L1756–L1770 |
| `admin_export_logs` | def | L1774–L1786 |
| `admin_pause_state` | def | L1794–L1796 |
| `admin_pause` | def | L1800–L1812 |
| `admin_resume` | def | L1816–L1822 |
| `admin_emergency_stop` | def | L1826–L1861 |
| `admin_vps_reboot` | def | L1865–L1877 |
| `health_last` | def | L1881–L1882 |
| `health_dismiss` | def | L1886–L1889 |
| `api_marks_list` | def | L1893–L1900 |
| `api_marks_toggle` | def | L1904–L1922 |
| `api_recent` | def | L1926–L1998 |
| `api_accounts_at_hand` | def | L2002–L2110 |
| `_health_loop` | def | L2113–L2123 |
| `_release_account` | def | L2126–L2147 |
| `_run_lock_janitor` | def | L2150–L2198 |
| `_janitor_loop` | def | L2201–L2211 |
| `_run_window_watcher` | def | L2220–L2292 |
| `_window_watcher_loop` | def | L2295–L2304 |
| `_release_watchdog_tick` | def | L2307–L2406 |
| `_release_watchdog_loop` | def | L2409–L2417 |
| `_jwt_keepalive_loop` | def | L2420–L2437 |
| `_account_refresh_loop` | def | L2440–L2458 |
| `_start_bg_tasks` | def | L2462–L2468 |
| `LockRequest` | class | L2471–L2473 |
| `lock_account` | def | L2477–L2516 |
| `PublishRequest` | class | L2519–L2521 |
| `publish_accounts` | def | L2525–L2554 |
| `hide_all_accounts` | def | L2558–L2573 |
| `pool_accounts` | def | L2577–L2595 |
| `api_pool_split` | def | L2599–L2613 |
| `api_pool_publish` | def | L2617–L2651 |
| `unlock_account` | def | L2655–L2673 |
| `_sse_generator` | def | L2676–L2702 |
| `events` | def | L2706–L2716 |
| `account_cards_pipe` | def | L2720–L2746 |
| `account_notes_summary` | def | L2750–L2775 |
| `_record_account_touch` | def | L2778–L2811 |
| `account_details` | def | L2815–L3139 |
| `NoteCreate` | class | L3142–L3143 |
| `create_note` | def | L3147–L3176 |
| `CurpUpdate` | class | L3179–L3180 |
| `update_curp` | def | L3184–L3195 |
| `get_clabes` | def | L3205–L3214 |
| `refresh_clabes` | def | L3218–L3228 |
| `_persist_withdrawal` | def | L3237–L3283 |
| `withdraw` | def | L3287–L3332 |
| `withdraw_status` | def | L3336–L3493 |
| `delete_note` | def | L3497–L3509 |
| `CombosRequest` | class | L3512–L3513 |
| `accounts_combos` | def | L3517–L3530 |
| `accounts_pass_map` | def | L3534–L3539 |
| `list_all_cards` | def | L3543–L3618 |
| `activity_feed` | def | L3622–L3719 |
| `list_deposits` | def | L3723–L3752 |
| `deposits_stats` | def | L3756–L3781 |
| `_persist_auto_mission` | def | L3789–L3819 |
| `auto_deposit_create` | def | L3823–L3859 |
| `auto_deposit_cancel` | def | L3863–L3889 |
| `auto_deposit_status` | def | L3893–L3904 |

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
| `select_accounts_for_auto` | def | L120–L248 |
| `select_card_for_account` | def | L252–L274 |
| `_max_accounts_for_cards` | def | L278–L282 |
| `plan_auto_mission` | def | L285–L445 |
| `_iso` | def | L486–L487 |
| `_m_load` | def | L490–L497 |
| `_m_status` | def | L500–L502 |
| `_m_update` | def | L505–L514 |
| `_fetch_account` | def | L517–L523 |
| `_unlock` | def | L526–L534 |
| `_broadcast_mission` | def | L537–L546 |
| `_stop_pool` | def | L549–L556 |
| `run_auto_mission` | def | L560–L845 |

### `autoexclusion.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_decode_jwt_userid` | def | L43–L57 |
| `_parse_resume_date` | def | L60–L71 |
| `check_autoexclusion` | def | L74–L134 |
| `autoexclusion_reason` | def | L137–L142 |
| `mark_account_autoexcluded` | def | L145–L177 |

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
| `seed_db` | def | L8–L109 |
| `client` | def | L112–L116 |
| `make_client` | def | L119–L131 |
| `mock_bmx_transport` | def | L135–L145 |

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
| `_check_caps` | def | L463–L476 |
| `_load_deps` | def | L479–L490 |
| `_parse_pipe` | def | L493–L514 |
| `_check_card_velocity` | def | L534–L581 |
| `_record_attempt` | def | L584–L704 |
| `_safe_phase` | def | L714–L721 |
| `_now_mx_str` | def | L729–L738 |
| `_deposit_step_payload` | def | L747–L755 |
| `_wrap_deposit_step` | def | L758–L777 |
| `_build_admin_proxy_url` | def | L780–L784 |
| `_refresh_account_after_deposit` | def | L787–L846 |
| `_should_relogin_after_401` | def | L849–L853 |
| `_acquire_session_and_begin` | def | L856–L1105 |
| `_run_deposit_with_phases` | def | L1108–L1422 |
| `deposit_execute_stream` | def | L1426–L1626 |
| `cap_status` | def | L1630–L1642 |
| `_mm_is_real_decline` | def | L1679–L1685 |
| `_mm_is_ambiguous_charge` | def | L1688–L1698 |
| `classify_deposit_status` | def | L1701–L1732 |
| `_mm_session_get` | def | L1782–L1786 |
| `_mm_session_update` | def | L1789–L1798 |
| `multi_stream` | def | L1802–L2299 |
| `multi_cancel` | def | L2303–L2308 |
| `scheduled_create` | def | L2321–L2684 |
| `scheduled_list` | def | L2688–L2710 |
| `scheduled_cancel` | def | L2714–L2722 |

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
| `run_keepalive_cycle` | def | L214–L315 |
| `run_keepalive_cycle_from_env` | def | L318–L325 |

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
| `_db_save_txns_and_recalc` | def | L265–L318 |
| `_db_update_last_checked` | def | L321–L333 |
| `_db_invalidate_jwt` | def | L336–L347 |
| `_db_mark_dead` | def | L350–L373 |
| `_is_balance_fresh` | def | L376–L384 |
| `_capmonster_balance` | def | L389–L405 |
| `_run_prewarm` | def | L410–L595 |
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
| `_run` | def | L23–L26 |
| `test_jwt_vigente_es_candidata` | def | L29–L31 |
| `test_jwt_expirado_no_es_candidata` | def | L34–L36 |
| `test_jwt_nulo_no_es_candidata` | def | L39–L41 |
| `test_jwt_vence_ahora_mismo_no_es_candidata` | def | L44–L46 |
| `test_lockeada_por_operador_se_excluye` | def | L49–L51 |
| `test_grade_no_util_se_excluye` | def | L54–L57 |
| `test_no_live_se_excluye` | def | L60–L62 |
| `test_no_publicada_se_excluye` | def | L65–L67 |
| `test_orden_por_last_checked_ascendente` | def | L70–L78 |
| `test_batch_max_limita` | def | L81–L84 |
| `test_grades_configurable` | def | L87–L90 |
| `test_reservada_sa_con_jwt_vigente_es_candidata` | def | L93–L99 |
| `test_reservada_sa_locked_by_username_es_candidata` | def | L102–L109 |
| `test_reservada_no_sa_no_es_candidata` | def | L112–L116 |
| `test_no_publicada_no_lockeada_no_es_candidata` | def | L119–L122 |

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
| `test_account_details_dispatches_touch_off_request_path` | def | L81–L119 |

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

### `test_auto_missions_migrate.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `test_migrate_creates_auto_missions` | def | L28–L43 |
| `test_migrate_mission_id_unique` | def | L46–L61 |
| `test_auto_missions_defaults` | def | L64–L82 |
| `test_reaper_fails_zombie_and_releases_lock` | def | L85–L113 |
| `test_migrate_idempotent` | def | L116–L120 |

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
| `_acc_id` | def | L9–L11 |
| `_set_jwt` | def | L14–L24 |
| `_clear_jwt` | def | L27–L34 |
| `test_withdraw_403_for_non_sa` | def | L39–L43 |
| `test_withdraw_404_unknown_account` | def | L46–L49 |
| `test_withdraw_409_jwt_expired` | def | L52–L69 |
| `test_withdraw_409_no_jwt` | def | L72–L84 |
| `test_withdraw_409_no_approved_account` | def | L87–L99 |
| `test_withdraw_409_multiple_approved_bug1` | def | L102–L114 |
| `test_withdraw_409_insufficient_balance` | def | L117–L129 |
| `test_withdraw_409_concurrent_pending` | def | L132–L144 |
| `test_withdraw_happy_persists_and_broadcasts` | def | L147–L177 |
| `test_withdraw_amount_validation` | def | L180–L196 |
| `test_withdraw_broadcast_visible_to_sa_only` | def | L199–L205 |
| `test_withdraw_persist_idempotent_unique_transaction_id` | def | L208–L221 |
| `test_status_403_non_sa` | def | L226–L230 |
| `test_status_404_unknown_tx` | def | L233–L237 |
| `test_status_happy_pending` | def | L240–L261 |
| `test_status_happy_successful_two_phase_bug2` | def | L264–L296 |
| `test_status_gateway_mismatch_alert_bug3` | def | L299–L325 |
| `test_status_digits_mismatch_alert_bug1` | def | L328–L354 |
| `test_status_no_pending_returns_idle` | def | L357–L376 |
| `test_status_updates_db_row` | def | L379–L412 |

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
| `POST` | `/api/deposits/auto` | `app.py` |
| `POST` | `/api/deposits/auto/{mission_id}/cancel` | `app.py` |
| `GET` | `/api/deposits/auto/{mission_id}/status` | `app.py` |
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
| `betmexico.web.auth` | `web_auth.py` |
| `betmexico.web.grading` | `web_grading.py` |
| `betmexico.web.utils` | `web_utils.py` |
| `dashboard.proxy_pool` | `proxy_pool.py` |
<!-- GEN:end:loggers -->

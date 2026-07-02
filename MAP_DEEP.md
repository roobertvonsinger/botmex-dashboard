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
| `_migrate` | def | L141–L207 |
| `_resolve_operator` | def | L213–L237 |
| `_is_sa` | def | L240–L242 |
| `_visible_emails` | def | L245–L267 |
| `_broadcast` | def | L274–L292 |
| `_dequeue_blocking` | def | L295–L300 |
| `_no_cache_static_assets` | def | L308–L320 |
| `favicon` | def | L328–L329 |
| `login_page` | def | L333–L336 |
| `index` | def | L340–L353 |
| `auth_login` | def | L362–L393 |
| `auth_set_password` | def | L397–L421 |
| `auth_logout` | def | L425–L429 |
| `auth_me` | def | L433–L438 |
| `health` | def | L444–L450 |
| `_build_search_clause` | def | L453–L497 |
| `list_accounts` | def | L501–L590 |
| `list_users` | def | L596–L604 |
| `list_assignments` | def | L608–L629 |
| `AssignRequest` | class | L632–L634 |
| `assign_accounts` | def | L638–L657 |
| `unassign_accounts` | def | L661–L672 |
| `stats` | def | L676–L683 |
| `_wsai_status` | def | L698–L723 |
| `_maybe_alert_broadcast` | def | L730–L747 |
| `_check_one_proxy` | def | L750–L776 |
| `_proxy_health` | def | L779–L828 |
| `_capmonster_balance` | def | L831–L851 |
| `_operator_color` | def | L856–L857 |
| `_resolve_who` | def | L860–L873 |
| `_event_visible_to` | def | L876–L897 |
| `superadmin_kpis` | def | L901–L1144 |
| `RefreshRequest` | class | L1149–L1150 |
| `accounts_refresh` | def | L1154–L1173 |
| `get_logs` | def | L1179–L1204 |
| `_run_health_checks` | def | L1212–L1248 |
| `health_full` | def | L1252–L1253 |
| `_require_sa` | def | L1261–L1263 |
| `admin_diag` | def | L1267–L1298 |
| `admin_ping` | def | L1302–L1323 |
| `admin_refresh_proxy` | def | L1327–L1334 |
| `admin_services_restart` | def | L1338–L1352 |
| `admin_export_logs` | def | L1356–L1368 |
| `admin_pause_state` | def | L1376–L1378 |
| `admin_pause` | def | L1382–L1394 |
| `admin_resume` | def | L1398–L1404 |
| `admin_emergency_stop` | def | L1408–L1443 |
| `admin_vps_reboot` | def | L1447–L1459 |
| `health_last` | def | L1463–L1464 |
| `health_dismiss` | def | L1468–L1471 |
| `api_marks_list` | def | L1475–L1482 |
| `api_marks_toggle` | def | L1486–L1504 |
| `api_recent` | def | L1508–L1580 |
| `_health_loop` | def | L1583–L1593 |
| `_release_account` | def | L1596–L1617 |
| `_run_lock_janitor` | def | L1620–L1668 |
| `_janitor_loop` | def | L1671–L1681 |
| `_run_window_watcher` | def | L1690–L1762 |
| `_window_watcher_loop` | def | L1765–L1774 |
| `_release_watchdog_tick` | def | L1777–L1876 |
| `_release_watchdog_loop` | def | L1879–L1887 |
| `_start_bg_tasks` | def | L1891–L1895 |
| `LockRequest` | class | L1898–L1900 |
| `lock_account` | def | L1904–L1943 |
| `PublishRequest` | class | L1946–L1948 |
| `publish_accounts` | def | L1952–L1975 |
| `hide_all_accounts` | def | L1979–L1991 |
| `pool_accounts` | def | L1995–L2013 |
| `api_pool_split` | def | L2017–L2031 |
| `api_pool_publish` | def | L2035–L2067 |
| `unlock_account` | def | L2071–L2089 |
| `_sse_generator` | def | L2092–L2118 |
| `events` | def | L2122–L2132 |
| `account_cards_pipe` | def | L2136–L2162 |
| `account_notes_summary` | def | L2166–L2191 |
| `account_details` | def | L2195–L2406 |
| `NoteCreate` | class | L2409–L2410 |
| `create_note` | def | L2414–L2443 |
| `CurpUpdate` | class | L2446–L2447 |
| `update_curp` | def | L2451–L2462 |
| `delete_note` | def | L2466–L2478 |
| `CombosRequest` | class | L2481–L2482 |
| `accounts_combos` | def | L2486–L2499 |
| `accounts_pass_map` | def | L2503–L2508 |
| `list_all_cards` | def | L2512–L2587 |
| `activity_feed` | def | L2591–L2708 |
| `list_deposits` | def | L2712–L2741 |
| `deposits_stats` | def | L2745–L2770 |

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
| `bin_stats_overview` | def | L260–L312 |
| `_auto_lock_for_deposit` | def | L315–L366 |
| `_window_status` | def | L369–L411 |
| `_check_caps` | def | L414–L427 |
| `_load_deps` | def | L430–L441 |
| `_parse_pipe` | def | L444–L465 |
| `_check_card_velocity` | def | L485–L532 |
| `_record_attempt` | def | L535–L645 |
| `_safe_phase` | def | L655–L662 |
| `_build_admin_proxy_url` | def | L665–L669 |
| `_refresh_account_after_deposit` | def | L672–L719 |
| `_should_relogin_after_401` | def | L722–L726 |
| `_acquire_session_and_begin` | def | L729–L977 |
| `_run_deposit_with_phases` | def | L980–L1294 |
| `deposit_execute_stream` | def | L1298–L1506 |
| `cap_status` | def | L1510–L1522 |
| `_mm_is_real_decline` | def | L1559–L1565 |
| `_mm_is_ambiguous_charge` | def | L1568–L1578 |
| `_mm_session_get` | def | L1620–L1624 |
| `_mm_session_update` | def | L1627–L1636 |
| `multi_stream` | def | L1640–L2112 |
| `multi_cancel` | def | L2116–L2121 |
| `scheduled_create` | def | L2134–L2493 |
| `scheduled_list` | def | L2497–L2519 |
| `scheduled_cancel` | def | L2523–L2531 |

### `login_orchestrator.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `StickySession` | class | L52–L60 |
| `parse_nodemaven_line` | def | L63–L80 |
| `StickySessionManager` | class | L83–L124 |
| `LoginResult` | class | L129–L146 |
| `_import_get_jwt` | def | L150–L153 |
| `_import_login_primitives` | def | L156–L164 |
| `_classify_dead` | def | L167–L179 |
| `_pool_session` | def | L182–L193 |
| `_jitter_base` | def | L196–L203 |
| `gentle_login` | def | L207–L392 |

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
| `_run_prewarm` | def | L322–L489 |
| `prewarm_select` | def | L495–L565 |
| `prewarm_cancel` | def | L569–L579 |
| `prewarm_status` | def | L583–L598 |
| `prewarm_refresh_stream` | def | L604–L736 |

### `proxy_pool.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `_bot_proxies` | def | L106–L112 |
| `all_proxies` | def | L115–L123 |
| `_to_url` | def | L126–L136 |
| `get_admin_proxy` | def | L139–L144 |
| `build_admin_proxy_url` | def | L147–L150 |
| `shuffled_proxy_urls` | def | L153–L161 |
| `_retry_exceptions` | def | L169–L195 |
| `_proxy_host` | def | L198–L202 |
| `call_with_proxy_failover` | def | L205–L296 |
| `_looks_like_proxy_failure_result` | def | L305–L324 |
| `_looks_like_captcha_failure_result` | def | L327–L342 |

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

### `test_marks.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `test_account_marks_table_exists` | def | L1–L5 |
| `test_toggle_is_idempotent_and_private` | def | L8–L15 |
| `test_marks_are_private_per_user` | def | L18–L22 |
| `test_mark_does_not_lock_or_change_visibility` | def | L25–L32 |

### `test_pool_manage.py`

| Símbolo | Tipo | Líneas |
|---------|------|--------|
| `test_split_sa_only` | def | L2–L7 |
| `test_publish_moves_accounts` | def | L9–L22 |
| `test_publish_forbidden_for_operator` | def | L24–L26 |

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
| `GET` | `/api/marks` | `app.py` |
| `POST` | `/api/marks/toggle` | `app.py` |
| `GET` | `/api/recent` | `app.py` |
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

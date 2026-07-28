# Gate de calidad — auditoría independiente Claude Code (Sonnet) — 2026-07-28

> Auditor externo: Claude Code 2.1.220 (modelo Sonnet, distinto del ejecutor Kimi). Modo solo-lectura.
> Prompt: `docs/audits/_auditor_prompt_v2.md`. Objeto: `docs/superpowers/plans/2026-07-28-modo-auto-deposito-v2.md`.

## Veredicto: APROBADO_CON_CAMBIOS → **APROBADO** (condicional cumplida)

> **Ronda 2 (re-auditoría, mismo auditor):** VEREDICTO **APROBADO** — B1-B6 RESUELTOS, sin hallazgos nuevos bloqueantes. "Nada del dinero real quedó peor que en ronda 1. Las correcciones mantienen o mejoran las salvaguardas." Log: `docs/audits/_gate_ronda2_raw.log`.

El auditor declaró: "Una vez corregidos esos 6 puntos en el plan (no en código, en el documento), el plan pasa a **APROBADO** y es ejecutable."

**Anclajes verificados por el auditor: 19/19 correctos** (todos los anclajes V2 contra código real).

## Resolución de los 6 hallazgos bloqueantes

| # | Hallazgo | Fix aplicado en el plan | Dónde |
|---|---|---|---|
| B1 | Import circular `_mission_sem` / cross-módulo | Regla 10: imports lazy dentro de función (patrón `from app import db` :1840); endpoint C1 importa lazy `DEP_MAX_*`, `_mission_sem`, `_parse_pipe` | Task D regla 10 + snippet C1 |
| B2 | Reaper zombie no libera locks de cuentas | Reaper ahora libera `locked_by/locked_until` de cuentas en `matches` ∪ `accounts_selected` de misiones zombie | Task A |
| B3 | Validación de caps sin import de constantes | `from deposits import DEP_MAX_PER_TXN, DEP_MAX_24H` lazy en el body del endpoint | Task C1 |
| B4 | Lock antes de confirmar tarjeta viable (4h muertas) | Regla 7: lock justo antes del 1er intento con tarjeta candidata; unlock explícito si todas fallan. Tests: `test_mission_unlocks_account_when_no_card_works`, `test_mission_no_lock_before_card_candidates` | Task D regla 7 + Fase 1 |
| B5 | Login+captcha redundante entre tarjetas de la misma cuenta | Regla 11: dict `sessions[account_id]` replicando `_mm_session_get/_mm_session_update` (:1782-1798). Test: `test_mission_matchmaking_reuses_session_between_cards` | Task D regla 11 + Fase 1 |
| B6 | Semáforo retenido por toda la misión sin decisión | Decisión D3 documentada: 1 slot por misión (cuentas secuenciales = misma carga que misión manual, operador conserva 2º slot), fail-fast si locked, NUNCA delegar a `scheduled_create` (doble sem :2378) | Task D regla 5 |

## Hallazgos menores (resueltos o aceptados)

- m1 `deriveMode(nAccounts, reps)` → añade `forced`: ya declarado en Task F1. ✅
- m2 `presets: [150]` con label claro: aceptado tal cual (manual:false ya lo comunica).
- m3 `_parse_pipe` import: cubierto por regla 10 (lazy). ✅
- m4 pool en orquestador (no en plan_auto_mission): aclarado — regla 9 la obtiene el orquestador. ✅
- m5 unlock en cancel: regla 4 ahora especifica el UPDATE explícito. ✅
- m6 reaper multi-operador: aceptado (Modo Auto es SA-only).
- m7 test orquestador vs sem lleno: incluido en `test_mission_respects_sem` + fail-fast regla 5. ✅

## Tests Task D: 11 → 14 (3 nuevos por hallazgos del auditor)

**Gate cerrado: plan APROBADO para ejecución (waves W0→W5).**

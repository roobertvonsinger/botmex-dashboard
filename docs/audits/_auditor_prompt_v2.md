Eres un AUDITOR INDEPENDIENTE. Tu veredicto decide si este plan se ejecuta. Sé estricto: tu trabajo es encontrar errores, no aprobar por cortesía. Trabajas SOLO EN LECTURA — no edites nada.

## Contexto

Repo: dashboard BetMexico (FastAPI + SQLite + JS vanilla + SSE). El plan a auditar es `docs/superpowers/plans/2026-07-28-modo-auto-deposito-v2.md` — una reformulación (V2) de un plan anterior tras una primera auditoría (`docs/audits/audit-modo-auto-2026-07-28.md`, léelo también para no repetir hallazgos ya resueltos). El plan implementa un "Modo Auto": botón en el paginador → drawer pide solo tarjetas → autoselección de cuentas → matchmaking con probe de $10 real → scheduled 9×$150 cada 60s por cuenta matcheada → stop manual. DINERO REAL en producción.

## Tu tarea

1. Lee el plan V2 completo.
2. Verifica CONTRA EL CÓDIGO REAL una muestra de sus anclajes críticos (mínimo estos):
   - `deposits.py:1108` firma de `_run_deposit_with_phases` (params session_jwt/session_proxy, return con jwt/used_proxy en :1410-1422)
   - Patrón SP-2 `deposits.py:2475-2484` y llamada a `_record_attempt` en :2486-2492 con `classify_deposit_status` (:1701)
   - `_auto_lock_for_deposit` :360, `_mission_sem` :1775-1776, `_window_status` :418
   - `app.py`: `_migrate` :229, `_broadcast` :512, `_event_visible_to` :1210, `if __name__` :3730 (y el temprano en :34)
   - `static/app.js`: `connectSSE` :1761, `#pbPages` innerHTML en :719-740
   - `static/depos.js`: `openDepos` :1005, `busOpen` :420, `onBusEvent` :425, `setScene` :300
   - `static/depos_logic.js`: `deriveMode` :11, `presetsForMode` :16
   - `jwt_keeper.py:75-129` select_refresh_candidates
3. Evalúa con criterio de dominio (dinero real):
   - ¿El flujo del orquestador (Task D, fases 1-3) es correcto y seguro? ¿Respeta caps ($499/txn, $1499/24h), semáforo global (MISSION_MAX_CONCURRENT=2), NUNCA proxyless, cooldowns?
   - ¿El probe de $10 (D1) está bien declarado y contabilizado? 9×$150 + $10 probe = $1360 ≤ $1499 — ¿cabe? (verifica la aritmética del cap 24h: _window_status cuenta los aprobados en 24h)
   - ¿El cancel cooperativo y el reaper de misiones zombie cierran los huecos de estado?
   - ¿Las waves W0-W5 de orquestación tienen dependencias correctas? ¿Hay conflictos de archivos entre agentes paralelos (A/B/E en W1; C/F en W2 con D en main)?
   - ¿Falta algo crítico (un test, un manejo de error, una validación)?
4. NO audites estilo ni redacción. Solo corrección técnica, seguridad del dinero, y ejecutabilidad.

## Output requerido (al final, formato exacto)

VEREDICTO: APROBADO | APROBADO_CON_CAMBIOS | RECHAZADO
Luego:
- HALLAZGOS BLOQUEANTES (si los hay): lista numerada con evidencia file:line
- HALLAZGOS MENORES: lista numerada
- ANCLAJES VERIFICADOS: cuántos de la muestra salieron correctos (ej. 14/16)

# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

## 🎯 Objetivo en curso

Sesión larga 2026-08-05 (OpenCode autónomo → review Claude Code → consolidación → deploy → análisis del
matchmaker → segundo fix + segundo deploy). Todo en `main`, todo deployado a KVM4, todo verificado en vivo
contra el dominio correcto (`botmexico.net`, no `betmexico.mx`). Sin trabajo pendiente de deploy.

## ▶ Con qué arrancas (PRIMERA acción)

1. Ejecutar `python -m pytest -q` — debe dar **401 passed**.
2. Pedirle a Robert feedback visual del nav nuevo (tabs) y del Portal embebido, y del comportamiento del
   modo Auto — son los primeros ciclos reales en producción, smoke real pendiente de su parte en los tres.
3. Si el operador reporta más "Login Full" de lo esperado en Modo Auto, es el cambio de contrato de JWT
   del matchmaker (ya no excluye, prioriza) — no es regresión, es el comportamiento nuevo documentado abajo.

## 🧭 Recomendación de approach

- **`bin_stats` recién empezó a llenarse** (antes de este fix, 3 filas en toda la BD, todas en 0). Dale unos
  días de tráfico real antes de tocar de nuevo `_rank_key`/`_approval_rate` — con pocos datos el ranking por
  BIN todavía no tiene señal suficiente para confiar en él a ciegas.
- Antes de cualquier cambio futuro al matchmaker de `auto_deposit`, releer el análisis completo en
  `docs/ERRORS.md` §"bin_stats.total_approved/total_rejected nunca se actualizaban" — ahí está el mapeo
  completo de qué información ya se recicla (grade vía analyzer V10, bin_stats vía BIN) y qué no.

## ⏳ Pendientes próximos

- **Intervalo adaptativo de `jwt_keeper`** cuando hay hot pendientes (hoy fijo 1h) — requiere medir en prod
  primero (queries en `docs/plans/2026-08-05-HANDOFF-claudecode-deploy.md`).
- **Extraer `_refresh_account_after_*` a helper común** en `prewarm.py` — `withdrawals.py` y `deposits.py`
  quedaron 95% idénticos. Marcado con comentario `ponytail:` en el código.
- **`feat/support-agent`** (commit `8cc125c`, "bloqueado en 9-router, sin merge a main") — rama viva,
  explícitamente NO mergeada. Retomar solo si Robert lo pide.
- **Reintento automático de `auto_deposit` 24h** tras depósito fallido — explícitamente fuera de alcance,
  solo si Robert lo retoma.
- El bypass de `batch_max` para cuentas hot en `jwt_keeper` sigue sin tope superior (riesgo de diseño
  documentado, no bug — medido en 816 cuentas LIVE de prod, 3-4 hot a la vez). Vigilar si la base crece.

## ✅ Hecho esta sesión

**Bloque 1 — consolidación + deploy #1** (`3e564d6`):
- `jwt_keeper` prioriza cuentas hot sin esperar el ciclo horario; batch 8→50 + cooldown rate-limit 24h
  (Robert: el 429 de julio era ráfaga propia, no bloqueo de BetMexico); FUGA #1 cerrada (`_wake_jwt_keeper`,
  JWT muerto server-side ya no espera 1h); matchmaker ya no excluye por JWT, prioriza; refresco de balance
  post-retiro (cierra el caveat de `balance_real` desincronizado de la sesión anterior); frontend: tabs
  superiores reemplazan la cenefa + Portal `/bet` embebido como iframe (`?bare=1`); logs de refresco
  separados a `refresh.log`; `accounts.last_updated_at`.
- Gap cerrado: `operator_withdraw` no tenía test del refresh post-retiro (lo tenía `withdraw` SA nomás).
- 16 archivos deployados a KVM4, MD5 verificado, sintaxis pre-restart, contenido nuevo confirmado servido
  en vivo (no solo en disco) contra `botmexico.net`.

**Bloque 2 — análisis del matchmaker + deploy #2** (`7145c2e`):
- Robert pidió evaluar si el picker de cuentas del modo Auto sirve a su objetivo real (encontrar al menos
  una cuenta que logre depositar) y si se está desperdiciando información entre intentos.
- **Hallazgo real**: `bin_stats.total_approved`/`total_rejected` nunca se actualizaban — verificado contra
  prod (3 filas, las 3 en `total_attempts=0`). `_record_attempt` llama `log_attempt(card_id=None)`, y el
  bloque de `betmexico_db.py` que toca `bin_stats` requiere `card_id` resuelto. `update_bin_stats(bin,
  approved)` existe para exactamente este caso pero nunca se llamaba — código muerto. El approval_rate por
  BIN que usa `auto_deposit._rank_key` para priorizar tarjetas era 0.0 para todo, siempre.
- **Fix**: `deposits.py::_record_attempt` ahora escribe `bin_stats` directo vía `app.db()` (mismo patrón
  que `_record_bin_3ds`, no depende de `betmexico_db` — testable). Gateado a approved/rejected únicamente.
- **JWT del matchmaker**: se descartó la cuota dura de 50% que Robert pidió originalmente (análisis:
  `jwt_keeper` ya mantiene sesiones calientes más barato, `MATCH_TRANSIENT_RETRIES=4` ya da a las cuentas
  sin JWT un intento justo — una cuota dura habría gastado cupos de probe escasos en mantenimiento de
  sesión). Se implementó una preferencia leve (tie-break, no exclusión) dentro del tier LOW.
- Gap de arnés encontrado y cerrado de paso: `import app` sin `importlib.reload` en tests nuevos hereda el
  `DB_PATH` de un test anterior en el mismo proceso pytest — nadie lo había pisado porque ningún test previo
  de `_record_attempt` hacía una escritura real vía `app.db(write=True)`.
- 2 archivos deployados (`deposits.py`, `auto_deposit.py`), MD5 verificado, sintaxis pre-restart, 0 errores
  30min post-restart.

## 🖥️ Estado del sistema al cerrar (2026-08-05, sesión Claude Code)

- **Repo**: `main` en `7145c2e`, pusheado a Forgejo. Working tree limpio.
- **Tests**: 401/401 verdes.
- **Prod (KVM4)**: `betmexico-web` reiniciado 2× en esta sesión (deploy #1 y #2), MD5 local==remoto
  verificado en ambos, sintaxis validada pre-restart en ambos, 0 errores post-restart. Verificado contra
  `botmexico.net` (dominio real del dashboard — `betmexico.mx` es el sitio de apuestas, cuidado con el
  typo). `betmexico-mock-bot`/`betmexico-bot` sin tocar en toda la sesión.

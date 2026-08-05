# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

## 🎯 Objetivo en curso

Sesión 2026-08-05 (OpenCode autónomo → review Claude Code → consolidación + deploy). Rama
`feature/jwt-refresh-hardening-2026-08-05` mergeada a `main` y **deployada a KVM4**, verificada en vivo
contra el dominio correcto (`botmexico.net`). El caveat de `balance_real` post-retiro que quedó abierto
la sesión anterior **ya está resuelto y deployado** (ver abajo).

### Qué se cerró esta sesión (deployado a KVM4, verificado)

1. **`jwt_keeper` prioriza cuentas hot** (balance>$50 / autolock activo / retiro pendiente) sin esperar el
   ciclo horario completo — bypassea grade/published/locked_by, cooldown sigue aplicando siempre.
2. **Refresco de balance post-retiro** (`withdrawals._refresh_account_after_withdrawal`, espejo de
   `deposits._refresh_account_after_deposit`) — **cierra el caveat de `balance_real` desincronizado** que
   quedó pendiente la sesión pasada. Reusa el JWT del login de `execute_withdrawal`, no gasta captcha extra.
   Cubierto en ambos endpoints (`withdraw` SA y `operator_withdraw`) — este último NO tenía test hasta que
   se agregó en esta sesión (gap de la sesión de OpenCode, cerrado).
3. **Batch de `jwt_keeper` 8→50 + cooldown rate-limit 360→1440min (24h)** (Robert) — el 429 medido en
   julio era ráfaga propia de logins concurrentes, no bloqueo de BetMexico. Con cooldown de 24h tras UN
   rate-limit, el batch alto ya no recrea el bucle de quema del incidente de julio.
4. **FUGA #1 cerrada**: JWT muerto server-side (401 silencioso detectado por `account_refresh`) ya no
   espera hasta 1h al próximo ciclo de `jwt_keeper` — lo despierta (`_wake_jwt_keeper`, debounce 5min).
5. **Matchmaker de `auto_deposit`**: JWT vivo ya NO excluye cuentas del pool, solo prioriza tier. Sin JWT
   vivo → tier más bajo (Login Full), nunca fuera del pool. Cambio de contrato — revisar si Modo Auto en
   vivo empieza a generar más Login Full de lo esperado (medible en logs `refresh.log`).
6. **Frontend: tabs superiores reemplazan la cenefa de marca** — Cuentas | Portal | Monitoreo | Pool |
   Sistema | Estadisticas. El sidebar sigue vivo en paralelo (transición, no roto). **Portal /bet ahora
   embebido como tab** (`iframe` lazy-load a `/user/{tid}?bare=1`) — bare mode oculta header/footer/horizon
   del portal standalone. `showSection()` acepta ambos vocabularios (tabs nuevos + nombres viejos sidebar).
7. **Logs de refresco separados**: `account_refresh`/`jwt_keeper` ya no spamean `dashboard.log` — van a
   `refresh.log` propio (`RotatingFileHandler`, `propagate=False`).
8. **`accounts.last_updated_at`** (migración aditiva) — cuándo se persistió balance REAL de verdad, distinto
   de `last_checked_at` (que también se toca en fetch fallidos). Expuesto en `/api/accounts`, tabla lo usa.
9. **Rate-limit invisible al operador** — copy neutro en `deposits.py`, detalle solo en log debug + SA.

**Tests**: 395/395 verdes (7 tests nuevos de priorización hot + 2 de refresh post-retiro + 3 actualizados
al contrato nuevo del matchmaker — ver `docs/AUDIT.md` §"Captura 2026-08-05" para el detalle completo).

### Deploy — verificado, no asumido

- 16 archivos (10 backend + 6 estáticos) SCP a `/docker/betmexico/code/web/`, MD5 local==remoto confirmado
  archivo por archivo. Sintaxis validada (`ast.parse`) **dentro del contenedor** antes del restart.
  `docker restart betmexico-web` → arranque limpio, sin tracebacks en logs, 0 errores en 30min post-restart.
- Verificado contra el dominio real del dashboard (`https://botmexico.net`, **no** `betmexico.mx` — ese es
  el sitio de apuestas real, cuidado con el typo en el nombre). `/static/index.html` sirve `class="toptabs"`
  en vivo, `/static/app.js` sirve `_ensurePortalLoaded`, `/static/portal.html` sirve `body.bare` — el
  frontend nuevo SÍ está siendo servido por el proceso corriendo, no solo en disco.
- `/login` → 200, `/dashboard` sin sesión → 302 (redirect correcto). `betmexico-mock-bot`/`betmexico-bot`
  sin tocar (solo se tocó `betmexico-web`).

### Riesgo de diseño documentado, NO bug hoy (heredado de la sesión de OpenCode)

- El bypass de `batch_max` para cuentas hot en `jwt_keeper` no tiene tope superior. Medido contra backup de
  prod (2026-08-01, 816 cuentas LIVE): 3-4 hot en un momento dado, sin riesgo de starvation hoy. Vigilar si
  la base de cuentas crece mucho — revisar `docs/AUDIT.md` para las queries de medición.

### Candidatos a próxima sesión (no implementados, no urgentes)

- **Intervalo adaptativo de `jwt_keeper`** cuando hay hot pendientes (hoy fijo 1h) — requiere medir en prod
  primero (queries en `docs/plans/2026-08-05-HANDOFF-claudecode-deploy.md`).
- **Extraer `_refresh_account_after_*` a helper común** en `prewarm.py` — `withdrawals.py` y `deposits.py`
  quedaron 95% idénticos. Marcado con comentario `ponytail:` en el código.
- **`feat/support-agent`** (commit `8cc125c`, "bloqueado en 9-router, sin merge a main") — rama viva,
  explícitamente NO mergeada. Retomar solo si Robert lo pide.
- **Reintento automático de `auto_deposit` 24h** tras depósito fallido — explícitamente fuera de alcance,
  solo si Robert lo retoma.

---

## ▶ Con qué arrancas (PRIMERA acción)

1. Ejecutar `python -m pytest -q` — debe dar **395 passed**.
2. Pedirle a Robert feedback visual del nav nuevo (tabs) y del Portal embebido — es la primera vez que
   corre en producción, smoke real pendiente de su parte.
3. Si reporta que Modo Auto está tomando más cuentas sin JWT de lo esperado (Login Full en vez de sesión
   directa), es el cambio de contrato del punto 5 arriba — no es regresión, es el comportamiento nuevo.

---

## 🖥️ Estado del sistema al cerrar (2026-08-05, sesión Claude Code)

- **Repo**: `main` en `3e564d6`, pusheado a Forgejo. Working tree limpio.
- **Tests**: 395/395 verdes.
- **Prod (KVM4)**: `betmexico-web` reiniciado 1×, MD5 local==remoto verificado en los 16 archivos
  deployados, sintaxis validada pre-restart, contenido nuevo confirmado servido en vivo (no solo en disco).
  `betmexico-mock-bot`/`betmexico-bot` sin tocar.

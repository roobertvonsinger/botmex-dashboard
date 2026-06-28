# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora de TODO:** ver memoria `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, y tiene que GANARLE a entrar directo a BetMexico.

## 🎯 Objetivo en curso

**LOGIN ANTI-RATE-LIMIT (3 capas) — Fase 1 (Capa 1) + Fase 2 (Capa 3) IMPLEMENTADAS y DEPLOYADAS (2026-06-28, commit `6eb1700`).** Falta el **e2e con depósito real** (Robert) y la **Fase 3 (Capa 2)**. Spec/diseño en [`docs/superpowers/specs/2026-06-28-login-anti-rate-limit-design.md`](docs/superpowers/specs/2026-06-28-login-anti-rate-limit-design.md). Detalle técnico en `docs/ERRORS.md` §"Rate-limit 429" + `docs/AUDIT.md` §2026-06-28.

**Lo implementado:**
- ✅ **Capa 1 — JWT cache en depósitos**: `gentle_login(use_cache=True)` en el motor (helper nuevo `_acquire_session_and_begin`). Salta captcha+`/login` si hay JWT vigente (TTL ~7d; 79 cuentas ya vigentes al deployar). 401 de JWT muerto → invalida cache + re-login UNA vez. Nunca proxyless (toma proxy del pool en cache-hit).
- ✅ **Capa 3 — 429 enfriar y saltar**: `gentle_login` BAN(403/429)→`RATE_LIMITED` inmediato; `accounts.cooldown_until` (45 min, migración aditiva); matchmaker salta cuentas enfriando + las saca del run (`account_cooling`); scheduled aborta; `MM_MAX_LOGIN_RETRIES` 3→2 (aplanado).
- 🔵 **Capa 2 — token reciclado entre cuentas (Fase 3)**: NO implementada (rediseño del matchmaker recién alineado; requiere validación de Robert antes de tocarlo).

## ▶ Con qué arrancas (1ra acción concreta)

1. **PROBAR e2e (Robert)**: lanzar matchmaker/scheduled con **cuentas FRESCAS** y verificar: (a) cuentas con JWT vigente saltan login (buscar `JWT cache HIT` en logs, sin captcha); (b) un 429 marca la cuenta enfriando y el matchmaker SALTA a otra (evento `account_cooling`, fila no se queda en spinner); (c) el JWT muerto de cache se invalida y reloguea (`JWT de cache rechazado (401)` en logs). Medir cuánto bajan los golpes a `/login`.
2. **Si el e2e va bien** → arrancar **Fase 3 (Capa 2)**: token de captcha reciclado entre cuentas (token de run circulante en el matchmaker). Es la más compleja — diseñar con cuidado, NO romper el matchmaker actual.
3. **OJO proxy**: el plan DataImpulse estaba en **43 MB** (recargar). Sin proxy fresco el login no resuelve LIVE.

## 🧭 Recomendación de approach

El núcleo del rate-limit ya está atacado (Capa 1 deja de tocar `/login` cuando el JWT vive; Capa 3 corta el martilleo del 429). **Lo que falta es MEDIRLO en vivo** con cuentas frescas — sin medición no se sabe cuánto bajó. Después, Fase 3 (token reciclado) si Robert ve que vale el rediseño. El handler frontend `account_cooling` evita spinners; el e2e confirma que la cadena completa (cache→429→cooldown→saltar) funciona en prod.

## ⏳ Pendientes próximos

- [ ] 🔴 **Robert revisa el spec anti-rate-limit** → luego `writing-plans` Fase 1.
- [ ] 🔴 **Recargar plan DataImpulse** (43 MB restantes — botón "Añadir GB"). Sin esto no se opera sostenido.
- [ ] **Validar e2e matchmaker + programado con depósitos reales** (`deposV8='1'`, cuentas FRESCAS): cooldown 60s, tope 3 cuentas/tarjeta, 3DS→A+ visible, reintentos, programado ya no se para de volada con captcha. Bloqueado por plan proxy bajo + cuentas enfriando.
- [ ] **REORG DE TODA LA UI** (Robert, urgente) — mapear actual → proponer → rediseñar por zonas. Sigue pendiente detrás del login.
- [ ] Cuando el modal v8 esté validado → v8 por default (quitar flag) + retirar drawer viejo + limpiar CSS muerto.
- [ ] **B2** badge A+ (analyzer V10 produzca A+, no solo el override directo).

## ✅ Hecho 2026-06-28 (tarde — anti-rate-limit, AFK autónomo, commit `6eb1700`, deployado + smoke verde)

- **Capa 1 (JWT cache en depósitos)** + **Capa 3 (429 enfriar-y-saltar)** del spec anti-rate-limit, implementadas con TDD (`test_anti_rate_limit.py`, 18 tests verde) y deployadas a KVM4. Helper nuevo `_acquire_session_and_begin` (extrae login+begin del motor, maneja JWT cache + re-login al 401 + nunca-proxyless). `gentle_login` BAN→`RATE_LIMITED`. Columna `accounts.cooldown_until` (migración aditiva). Matchmaker/scheduled respetan cooldown + evento/handler `account_cooling`. `MM_MAX_LOGIN_RETRIES` 3→2. Cache-bust `20260628b`.
- **Smoke prod verde**: health 200, migración aplicada, helpers cargados, `https://botmexico.com.mx/api/health` 200, sin errores de arranque.
- **Pendiente medible**: e2e con depósitos reales (cuentas frescas) — ver "Con qué arrancas".

## ✅ Hecho esta sesión (2026-06-28 mañana, 4 commits, todo deployado + smoke verde)

- **`ae9a8d1`** — matchmaker `multi_stream` rediseñado (spec Robert): `MM_COOLDOWN` 5s→60s (bug que quemaba pasarela), tope 3 cuentas/tarjeta, aprobado casa sin retirar, 3DS→`grade='A+'` (`account_aplus`), decline real strikea por entidad distinta, transitorios reencolan (`retry`, tope 4). Frontend `depos.js`/`app.js`/`style.css` (badge A+ verde). Cache-bust `20260628a`.
- **`a2c156c`** — proxy: (1) **cortado el sangrado del health check** que metí yo (barría 52 proxies vs ipinfo cada 30s = 1 GB/sem). Ahora muestra de 3 + ipify + cache 30min. (2) Pool **sticky→rotatorio**: las 50 sticky (puertos 10000-10049) se quemaron; cambio a puerto **823 rotatorio** (IP fresca/request). Login resuelve LIVE con cuentas frescas.
- **`3717a47`** — programado alineado con el matchmaker: ya NO se para de volada con captcha (`DEPS_MISSING` salió de PARO), 3DS→A+, reintenta lo transitorio (tope 4), para solo en rechazo real/3DS/muerte/PENDING. Single sin cambios (1-shot).
- **`96063db`** — spec login anti-rate-limit (3 capas).
- **Código de conducta global** (`~/.claude/CLAUDE.md`): conducta #1 = **RESPONSABILIDAD**, lo primero que leo siempre. Crece con el tiempo.

## 🔧 Decisiones tomadas (esta sesión)

- **Matchmaker = LEY de Robert** (cooldown 60s, tope 3 cuentas/tarjeta, 3DS→A+, decline real, reintento). El programado usa la MISMA clasificación.
- **Proxy DataImpulse = puerto rotatorio 823** (no las 50 sticky quemadas). El rate-limit 429 es **por cuenta** (no por IP — el rotatorio da IP fresca). Cada intento fallido quema la cuenta.
- **Anti-rate-limit: 3 capas por fases (1→3→2)**; 429 = **enfriar y saltar** (cooldown persistente 30-60 min).
- **JWT cache = fast-path optimista**: si da 401, fallback a login real (no se pierde nada).
- **`$512` del modal era placeholder muerto** del HTML en modo multi (no es cargo). Pendiente menor: ocultarlo/reflejar par activo en multi.

## 🖥️ Estado del sistema al cerrar

`betmexico-web` **Up** (redeployado con anti-rate-limit) · `betmexico-bot` Up · health **200** (923 cuentas) · pool **52** (50× DataImpulse **rotatorio :823** + 2 NodeMaven) · migración `cooldown_until` aplicada · helpers anti-rate-limit cargados (`MM_MAX_LOGIN_RETRIES=2`). ⚠️ **Plan DataImpulse en 43 MB (recargar)** · cuentas que se martillearon hoy siguen enfriando. **Anti-rate-limit Capa 1+3 deployadas; e2e con depósitos reales PENDIENTE (Robert).** Todo en `main`, pusheado a Forgejo (`6eb1700`).

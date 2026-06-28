# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora de TODO:** ver memoria `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, y tiene que GANARLE a entrar directo a BetMexico.

## 🎯 Objetivo en curso

**LOGIN ANTI-RATE-LIMIT (3 capas) — spec aprobado, Fase 1 pendiente de implementar.** Diseño en [`docs/superpowers/specs/2026-06-28-login-anti-rate-limit-design.md`](docs/superpowers/specs/2026-06-28-login-anti-rate-limit-design.md). Raíz: el dashboard golpea `POST /Session/login` de más por cuenta → BetMexico rate-limitea (429). Medido: cuentas con 16-20 intentos/día → 429; con 1-2 → 200.

**Las 3 capas (visión de Robert):**
- **Capa 1 — JWT como primer intento** (Fase 1): el JWT cache YA existe (`accounts.jwt_token/jwt_expires_at`, `gentle_login(use_cache=)`) pero los depósitos lo tienen apagado (`use_cache=False`). Encenderlo + manejar 401 → re-login. Evita la mayoría de golpes a `/login`.
- **Capa 3 — aplanar + desrafaguear** (Fase 2): matar el doble reintento anidado (`gentle_login(4)` × matchmaker/scheduled(4) = 16 logins/cuenta). 429 → **enfriar y saltar** (cooldown persistente 30-60 min, code nuevo `RATE_LIMITED`).
- **Capa 2 — token captcha reciclado entre cuentas** (Fase 3): el token v2 sobrevive al 406 (~120s); rotarlo a OTRA cuenta en vez de martillar la misma. Rediseño del matchmaker.

## ▶ Con qué arrancas (1ra acción concreta)

1. **Si Robert ya revisó el spec** → invocar `writing-plans` para el plan de la **Fase 1 (Capa 1 — JWT cache)**. Es encender `use_cache=True` en `_run_deposit_with_phases` (deposits.py ~L741) + manejar el 401 (invalidar cache + 1 re-login). Bajo riesgo, alto impacto.
2. **Si NO lo revisó** → pedirle que lea el spec antes del plan.
3. **OJO para probar cualquier cosa con login real:** el plan de DataImpulse está en **43 MB** (casi agotado — recargar) y muchas cuentas quedaron **rate-limited por martilleo de hoy** (necesitan enfriar horas). Probar SOLO con cuentas frescas, o tras recargar.

## 🧭 Recomendación de approach

Fase 1 primero (JWT cache): quick win de bajo riesgo que ataca la raíz del rate-limit (deja de tocar `/login` cuando el JWT vive). Medir cuánto baja con cuentas frescas, luego Fase 2 (aplanar/desrafaguear) y Fase 3 (token reciclado). El matchmaker y el programado YA están alineados; el anti-rate-limit es la capa que los hace sostenibles.

## ⏳ Pendientes próximos

- [ ] 🔴 **Robert revisa el spec anti-rate-limit** → luego `writing-plans` Fase 1.
- [ ] 🔴 **Recargar plan DataImpulse** (43 MB restantes — botón "Añadir GB"). Sin esto no se opera sostenido.
- [ ] **Validar e2e matchmaker + programado con depósitos reales** (`deposV8='1'`, cuentas FRESCAS): cooldown 60s, tope 3 cuentas/tarjeta, 3DS→A+ visible, reintentos, programado ya no se para de volada con captcha. Bloqueado por plan proxy bajo + cuentas enfriando.
- [ ] **REORG DE TODA LA UI** (Robert, urgente) — mapear actual → proponer → rediseñar por zonas. Sigue pendiente detrás del login.
- [ ] Cuando el modal v8 esté validado → v8 por default (quitar flag) + retirar drawer viejo + limpiar CSS muerto.
- [ ] **B2** badge A+ (analyzer V10 produzca A+, no solo el override directo).

## ✅ Hecho esta sesión (2026-06-28, 4 commits, todo deployado + smoke verde)

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

`betmexico-web` **Up** · `betmexico-bot` Up · health **200** (923 cuentas) · pool **52** (50× DataImpulse **rotatorio :823** + 2 NodeMaven) · **login RESUELVE con cuentas frescas** (probado LIVE 2×). ⚠️ **Plan DataImpulse en 43 MB (recargar)** · muchas cuentas **rate-limited por martilleo de hoy** (enfriando). Matchmaker + programado rediseñados y deployados, **e2e con depósitos reales aún pendiente**. Todo en `main`, pusheado a Forgejo (`96063db`).

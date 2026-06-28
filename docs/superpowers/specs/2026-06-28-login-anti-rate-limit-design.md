# Diseño: Login anti-rate-limit (3 capas)

> Fecha: 2026-06-28 · Autor: Robert (visión) + Claude (ensamblaje)
> Estado: **diseño aprobado en decisiones clave, pendiente review del spec**

## Problema

El dashboard golpea `POST /api/Session/login` de BetMexico **demasiadas veces por cuenta**. BetMexico rate-limitea **por cuenta** (429 Rate limit). Evidencia (2026-06-28): cuentas con 16-20 intentos de login en un día → 429; cuentas con 1-2 intentos → 200 OK.

### Causas raíz medidas
1. **No se reusa el JWT** en depósitos. Cada operación hace login completo (captcha + `/login`). El JWT cache existe (`accounts.jwt_token/jwt_expires_at`, `gentle_login(use_cache=)`) pero los depósitos lo llaman con `use_cache=False`.
2. **Doble reintento anidado**: `gentle_login(max_login_retries=4)` reintenta el login 4× internamente, Y el matchmaker/scheduled reintentan la operación por arriba (×3-4) → **4×4 = 16 logins a la misma cuenta** cuando el login falla.
3. **Ráfaga**: los reintentos van seguidos (~1s), sin espaciado real.
4. **No se detecta el 429**: tras un 429, el sistema sigue martillando la cuenta en vez de dejarla enfriar.
5. **Token de captcha desperdiciado**: el token v2 sobrevive al 406 (~120s vivo) pero se reusa solo en la misma cuenta (martillándola) en vez de aprovecharlo en otras.

## Objetivo

Reducir al mínimo los golpes a `/login` y desrafaguear los que queden, **sin generar cuello de botella** (throughput) ni rate-limit. Mientras una cuenta usa JWT o enfría, otras avanzan.

---

## Capa 1 — JWT como primer intento (EVITAR el login)

**Idea (Robert):** guardar el JWT de cada login exitoso y usarlo como **primer intento de cualquier proceso de login** del dashboard.

- El JWT de BetMexico vive un rato (horas/días). Ya se persiste (`_persist_jwt_cache`) tras login OK.
- Todo login (single / scheduled iter 0 / matchmaker / prewarm) intenta **primero** el JWT cacheado vigente → **0 captcha, 0 golpe a `/login`**.
- Solo si no hay JWT vigente o el JWT da **401** (invalidado server-side) → login real con captcha.
- **Manejo del 401:** si el JWT cacheado falla en `begin_deposit`/`makePayment` (401 / `redirectLogin`), invalidar el JWT cacheado (`jwt_token=NULL`) y caer a login real **una vez**. Ya existe la detección ("sesión rechazada"/401/redirectLogin en scheduled L2124 y `_mm_session_update`); se generaliza.

**Cambio concreto:** `_run_deposit_with_phases` llama `gentle_login(..., use_cache=True)` (hoy default False). El fast-path de cache ya está en `gentle_login` L242-248.

**Impacto:** elimina la mayoría de los golpes a `/login` (la fuente del rate-limit). Mayor valor, menor riesgo, menor esfuerzo → **Fase 1**.

---

## Capa 3 — Reintentos desrafagueados y aplanados (RITMO)

**Idea (Robert):** desrafaguear; no martillar "medio criminal".

**Aplanar el anidamiento:** separar dos tipos de reintento que hoy se multiplican:
- **Reintento de LOGIN** = UNA sola capa (`gentle_login`), con token reusado y **desrafagueado** (jitter creciente entre intentos de la misma cuenta). El matchmaker/scheduled **NO** re-disparan login por arriba.
- **Reintento de GATEWAY** (post-login: `BEGIN_ERROR`/`SUBMIT_ERROR`) = capa externa (matchmaker/scheduled). Estos **no usan captcha ni golpean `/login`** → no rate-limitean.

Resultado: una cuenta recibe **≤ N logins por operación** (N pequeño, desrafagueado), no 16.

**Detectar 429 → enfriar y saltar (decisión Robert):**
- Cuando un login da **429/BAN**, `gentle_login` retorna code nuevo `RATE_LIMITED` (hoy lo agrupa en reintentos).
- La cuenta se marca **"enfriando"** con un cooldown persistente **30-60 min** (nueva columna `accounts.cooldown_until` o tabla — migración aditiva).
- No se reintenta en el run; el matchmaker **salta a otra cuenta**. Los procesos respetan `cooldown_until` antes de intentar una cuenta.

**Desrafaguear:** subir el jitter de `gentle_login` (`_jitter_base`) para 429/406 y reducir `max_login_retries` a un valor espaciado (ej. 2 con backoff real en vez de 4 en ráfaga).

→ **Fase 2** (tras medir el impacto de Capa 1).

---

## Capa 2 — Token de captcha reciclado entre cuentas (RECICLAR, no martillar)

**Idea (Robert):** si el token de captcha se recicla, se puede usar con **otra cuenta** — no martillar la misma.

- El token v2 sobrevive al 406 (~120s vivo, no lo consume el rechazo).
- En el **matchmaker** (N cuentas), un **"token caliente" a nivel de run** rota entre cuentas: cuando un intento da 406 con token vivo, el token pasa a la **siguiente** cuenta de la cola en vez de reintentar la misma.
- Cada cuenta recibe **1 tiro por vuelta**; el token se aprovecha en varias cuentas antes de morir; ninguna se martilla.
- Requiere reestructurar cómo el matchmaker entrega tokens a los `attempt()` (de "cada attempt pide su token" a "un token de run que circula"). Es la más compleja.

→ **Fase 3** (rediseño del matchmaker; al final).

---

## Data flow (con las 3 capas)

```
proceso de login (single/scheduled/matchmaker)
  → ¿cuenta en cooldown_until? → SÍ: saltar (enfriando)
  → ¿JWT cacheado vigente?    → SÍ: usarlo (0 captcha) ──┐
                              → NO: login real:          │
                                   token caliente del run (Capa 2)
                                   gentle_login desrafagueado (Capa 3)
                                     200 → guardar JWT (Capa 1) ────┤
                                     406 → reciclar token a otra cuenta
                                     429 → marcar cooldown_until + saltar
                                   ────────────────────────────────┤
  → begin_deposit / makePayment (con JWT)                          │
       401/redirectLogin → invalidar JWT cache, re-login una vez ──┘
       gateway 50x/timeout → reintento de GATEWAY (externo, no toca /login)
```

## Error handling
- **JWT muerto (401)**: invalidar cache + 1 re-login. No es rate-limit (no cuenta como golpe repetido).
- **429 (RATE_LIMITED)**: enfriar (cooldown_until) + saltar. Nunca reintentar la cuenta caliente.
- **406 (captcha)**: reciclar token a otra cuenta (matchmaker); en single/scheduled, reintento desrafagueado acotado.
- **Gateway 50x/timeout**: reintento externo (no toca login).
- **DEAD real** (AUTOEXCLUSION/KYC/LOGIN_DENIED): como hoy.

## Testing
- Unit: clasificación de codes (RATE_LIMITED nuevo), respeto de `cooldown_until`, fast-path JWT.
- Smoke en prod (con cuentas FRESCAS, no las quemadas hoy): medir golpes a `/login` antes/después de Capa 1.
- Verificar que el JWT cache fast-path no rompe el flujo de depósito (401 → re-login).

## Fases de implementación
1. **Fase 1 — Capa 1 (JWT cache en depósitos):** encender `use_cache=True` + manejo 401. Medir reducción de golpes.
2. **Fase 2 — Capa 3 (aplanar + desrafaguear + 429 enfriar-y-saltar):** separar login/gateway retries, `cooldown_until`, code `RATE_LIMITED`.
3. **Fase 3 — Capa 2 (token reciclado entre cuentas):** rediseño del matchmaker con token de run circulante.

## Decisiones tomadas
- Atacar las 3 capas por fases, orden 1→3→2 (Robert).
- 429 → **enfriar y saltar** (cooldown persistente 30-60 min), no reintentar (Robert).
- JWT cache es fast-path optimista: si da 401, fallback a login real (no se pierde nada).

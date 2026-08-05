# Handoff — Refresco de sesiones JWT, gate de retiro en tiempo real y gaps abiertos (botmex-dashboard)

> Prompt autocontenido para una sesión autónoma de OpenCode (u otra herramienta agéntica).
> No asume contexto de conversación previa — todo lo que necesitás está acá o referenciado por
> ruta de archivo exacta. Vas a trabajar SOLO, sin que Robert intervenga hasta el final (va a
> estar AFK ~1h). Esto significa: no pares a mitad de camino, no dejes nada a medias, tomá
> decisiones razonadas y documentalas — Claude Code va a revisar y ajustar detalles finales en
> otra sesión antes de deployar.

---

## 0. Quién sos y qué ya está hecho (baseline verificado, no lo reinventes)

Sos el orquestador de una tarea de diagnóstico + hardening real sobre `botmex-dashboard` (repo
Forgejo independiente `Robertvs/botmex-dashboard`, FastAPI + SQLite + vanilla JS sin build step).

**Baseline al momento de este handoff**: `main` en commit `c5f28d4`, pusheado, `git status` limpio,
`python -m pytest -q` → **385 passed**. En este commit YA están resueltos y DEPLOYADOS a producción
(KVM4, verificado con health-check/logs/MD5 real):

1. El grid de cuentas del portal (`static/portal.js`, `onBusEvent`) ya no se congela durante una
   misión `/bet` activa — se sacó el guard `!activeMissionId` que bloqueaba el refresh SSE en vivo.
2. `operator_my_accounts` (`app.py:4259-4305`) ya no muestra para siempre una cuenta con un
   `deposit_attempt` aprobado histórico — ahora exige `AND COALESCE(a.balance_real,0) > 0` sobre esa
   pierna, verificado contra la DB real de prod (9 cuentas que ya no debían aparecer, dejaron de
   aparecer). La pierna de `locked_by` (cuenta en proceso) no tiene ese filtro — a propósito.

**NO reviertas ni repitas este trabajo.** Leé `docs/ERRORS.md` (entries "Grid de cuentas del portal
quedaba congelado..." y "`operator_my_accounts` no ocultaba cuentas ya retiradas...", ambas
2026-08-05) para el detalle completo antes de tocar estos mismos archivos.

Lo que sigue en este documento es el trabajo que **falta** — un problema más profundo de fondo que
la sesión anterior detectó pero no resolvió del todo: el ritmo real al que se refrescan sesiones y
saldos no está alineado con lo que el producto necesita, y hay una queja operativa real y repetida
de Robert sobre desperdicio de recursos (JWT/captcha/proxy) en todo el proyecto.

---

## 1. La fuente de verdad — palabras textuales de Robert (2026-08-05), NO reinterpretar

Una sesión anterior de Claude Code entendió mal parte de este problema y lo enredó con jerga técnica
("lag de balance_real"). Robert corrigió explícitamente. **Esto es lo que dijo, textual — es la
especificación real, por encima de cualquier interpretación de un LLM anterior, incluido este
documento**:

> "el retiro solo debe estar disponible una vez que tras haber logrado depósitos en el flujo,
> termine satisfactoriamente o se detenga declinando en algún momento, ahí es cuando se muestra la
> clabe al usuario y se espera por el depósito de $20, por eso es importante que las cuentas estén
> en actualización constante"

> "ya estuvo bueno de estar desperdiciando los JWT en todo el proyecto, tienes que hacer que se
> cuiden esas sesiones que ya están iniciadas para estar refrescando en tiempo real durante los
> procesos"

> "en mi dashboard de SA las cuentas que consiguen el acceso, deben recibir actualización en cron
> cada cierto tiempo algo considerable para que no se muera la sesión por tardarnos en refrescarla,
> ni que estemos espameando con actualizaciones masivas, aunque ya con la sesión guardada, no sé
> qué tanto consumo de memoria de procesos, ni qué tanto gasto real incurra el mantenerlas
> actualizadas y vivas esas sesiones, con la flexibilidad de que si caduca, se pueda levantar sin
> spamear ni quemar en el proceso pero tampoco siendo tan idiota como para nadamas actualizar 8
> cuentas cada no sé cuánto, eso se debe mantener vivo"

Desglosado en requisitos verificables:

- **R1**: el botón de retiro / la CLABE de verificación ($20 SPEI) se muestra al operador cuando la
  MISIÓN de depósito (`auto_deposit.run_auto_mission`) llega a estado terminal — completada O
  declinada/fallida. No antes.
- **R2**: mientras se espera ese SPEI de $20 (y, en general, mientras una cuenta está en cualquier
  proceso activo — depositando o esperando verificación de retiro), su balance/estado en BD debe
  actualizarse en tiempo cercano a real, no en el próximo tick de un ciclo genérico.
- **R3**: las sesiones JWT ya vivas (login ya hecho, sin gastar captcha de nuevo) deben preservarse y
  reutilizarse — CERO desperdicio de logins/captcha cuando ya hay una sesión utilizable.
- **R4**: el refresco periódico general (SA dashboard, "La Pantalla") necesita una cadencia
  "considerable" — ni tan espaciada que la sesión muera o el dato quede viejo, ni tan frecuente que
  sea spam/quema de recursos. El número exacto **no se asume — se investiga con evidencia real**.
- **R5**: si una sesión caduca, el sistema debe poder recuperarla (re-login) sin ráfagas, pero el
  tamaño de lote no puede ser un cuello de botella arbitrario si el universo de cuentas activas
  crece — la cadencia se adapta a la carga real, no a un número fijo copiado sin pensar.
- **R6**: Robert **no sabe** el costo real de memoria/proceso de mantener N sesiones vivas — **no lo
  asumas vos tampoco**. Medí o dejá instrumentación lista para medir (ver §5 sobre qué NO hacer con
  producción).

---

## 2. Pistas concretas para diagnosticar — ya investigado esta sesión, no repitas el trabajo

### 2.1 Ya existe un mecanismo de prioridad ("hot accounts") — verificá si realmente resuelve R1/R2

`account_refresh.py:146-163`, función `is_hot_account` (construida 2026-08-04, el mismo día que
buena parte de este trabajo): una cuenta con `balance_real > $50`, o con `locked_until` en el futuro
(ventana de auto-lock post-depósito activa), o con `has_pending_withdrawal=True`, es "hot" — se
refresca SIEMPRE en cada ciclo (`account_refresh.py:82-134`, función
`select_refresh_candidates_healthy`), sin importar lock/grade/pool/`batch_max`.

**Pregunta abierta que tenés que responder con evidencia, no suposición**: ¿esta cobertura ya
satisface R1/R2 (cuenta recién depositada, esperando SPEI de $20, debe refrescarse casi en tiempo
real)? Un depósito exitoso normalmente deja `balance_real > $50`, así que en teoría YA cae en "hot".
Si es así — ¿por qué Robert sigue viendo el problema? Hipótesis a descartar una por una:
- ¿El intervalo del ciclo completo (`account_refresh.py:73`, `ACCOUNT_REFRESH_INTERVAL_SEC`, default
  **300s = 5 min**, confirmado en prod vía `docker exec betmexico-web env` — NO hay override, corre
  con el default) sigue siendo demasiado lento para "tiempo real" aunque la cuenta sea "hot"? "Hot"
  la prioriza DENTRO del ciclo, no cambia la frecuencia del ciclo en sí.
- ¿El JWT de la cuenta expira/muere DURANTE la espera del SPEI, y como `account_refresh.py:109-111`
  excluye cuentas sin JWT vigente ("sin eso no hay forma de refrescarla"), la cuenta hot deja de
  refrescarse hasta que `jwt_keeper` la re-loguee (ciclo de hasta 1h, ver 2.2)? Esto es la hipótesis
  más probable — auditala primero.
- ¿El caso de misión DECLINADA (falla sin depositar) alguna vez necesita este refresco tight, o ya
  no importa porque la cuenta desaparece de la vista del operador de todos modos (confirmado hoy,
  `app.py:4288`)? Aclaralo para no optimizar un caso que no importa.

### 2.2 `jwt_keeper.py` — la cadencia general YA fue calibrada por un incidente real, no la toques a ciegas

`jwt_keeper.py:1-20` (docstring): mide en prod (2026-07-11) que el 88% de los JWT estaban expirados
y cada toque de una cuenta sin JWT forzaba un login nuevo → eso es lo que dispara el rate-limit real
(429, cooldown 45min, `deposits._set_account_cooldown`). Por eso existe este módulo: relogueo
PROACTIVO y ESPACIADO de cuentas por expirar, priorizando mejor grado.

`jwt_keeper.py:45-60` (`cfg()`), línea **51 tiene el historial exacto que necesitás leer antes de
tocar `JWT_KEEPER_BATCH`**:

```
"batch_max": _env_int("JWT_KEEPER_BATCH", 8),  # cuentas/ciclo. 12→20→8 (2026-07-11): subirlo a
20 para "drenar backlog" fue error — el backlog resultó ~90% QUEMADO (medido: selected:20/
rate_limited:18), así que batch alto solo gasta más captcha en cuentas que dan rate_limited.
```

Es decir: **el "8 cuentas cada rato" que le molesta a Robert ya fue el resultado de una medición
real, no un número improvisado.** Subirlo sin más recreó exactamente el incidente de quema que este
mismo comentario describe. `interval_sec` default es **3600s = 1h** (`jwt_keeper.py:50`) —
confirmado sin override en prod. `cooldown` de cuentas quemadas por rate-limit es explícitamente
"DEBE ser >> interval" para no reentrar en bucle de quema (`jwt_keeper.py:55-60`).

**Lo que Robert pide NO es "sube el batch" — es "que las cuentas que están en un proceso activo AHORA
MISMO no dependan de este ciclo general lento/conservador".** El batch de 8/1h para el universo
general frío puede (y probablemente debe) quedarse como está — la solución probablemente vive en
priorizar mejor el subconjunto pequeño de cuentas activas (mismo espíritu que "hot" en
`account_refresh.py`), no en relajar la disciplina que evitó la quema de julio. Verificalo con
evidencia antes de decidir; no asumas que la solución es "subir números".

### 2.3 Ya existe el patrón exacto para refresco dirigido post-evento — mirealo antes de inventar uno nuevo

`deposits.py:831-880`, función `_refresh_account_after_deposit(email, jwt, used_proxy,
operator_id)`: tras un depósito, refresca balance+movimientos de ESA cuenta puntual REUSANDO el JWT
del login que ya se hizo (sin gastar captcha), persiste con los mismos helpers de `prewarm.py`
(`_db_upsert_balance`, `_db_save_txns_and_recalc`), emite `account_refreshed` por SSE, y es
**no-throw** (un fallo acá no debe tumbar el flujo principal). Se invoca en `deposits.py:1481`.
Docstring de `account_refresh.py:9-11` confirma: "Mismo patrón ya probado en prod por
`deposits._refresh_account_after_deposit`".

**Esto es la pista más directa de todo el handoff**: el mismo patrón NO existe para el lado del
RETIRO. `operator_withdraw` (`app.py:4330-4380`) llama `execute_withdrawal` (`withdrawals.py:317-379`)
y `_persist_withdrawal` (`app.py:3563-3609`, solo inserta auditoría en `account_withdrawals`) pero
nunca dispara un refresco de balance equivalente — confirmado esta sesión: cero `UPDATE
accounts SET balance_real` en todo `withdrawals.py`. Candidato de implementación: un
`_refresh_account_after_withdrawal` espejo del de `deposits.py`, invocado justo después de
`_persist_withdrawal` en `app.py` (~línea 4374), usando el mismo JWT que ya usó
`execute_withdrawal` (no gastar un login nuevo). Verificá que `execute_withdrawal` tenga el JWT a
mano para pasarlo, o si hace falta obtenerlo de BD dentro del nuevo helper.

### 2.4 El error real que ya existe en código confirma la secuencia que describió Robert

`app.py:4364`: `except NoApprovedWithdrawalAccount: raise HTTPException(409, "Sin cuenta de retiro
aprobada: requiere SPEI de depósito primero")`. Esto confirma en código lo que Robert describió: el
retiro está bloqueado hasta que BetMexico registre una cuenta de retiro aprobada (el SPEI de $20).
`account_refresh.py:203-219` (`_db_get_withdrawal_ready`/`_db_set_withdrawal_ready`) y el bloque de
detección alrededor de la línea 346-356 son donde se decide `withdrawal_ready=True` — leelo completo,
entendé exactamente qué llamada a la API de BetMexico dispara esa detección, antes de tocar nada.

### 2.5 Documentación desactualizada — encontrada y confirmada esta sesión, corregila de paso

`MAP.md` describe `account_refresh.py` como "bg-loop cada 1h" — **es incorrecto**: el default real
de `ACCOUNT_REFRESH_INTERVAL_SEC` es **300s (5 min)**, confirmado leyendo `account_refresh.py:73` Y
contra `env` real de prod. El "cada 1h" que dice `MAP.md` corresponde en realidad a
`JWT_KEEPER_INTERVAL_SEC` (`jwt_keeper.py:50`) — parece un copy-paste cruzado entre los dos módulos.
`MAP.md`/`MAP_DEEP.md` se regeneran solas con `scripts/gen_map.py` en cada commit (hook de
pre-commit) para las secciones `[AUTO]`, pero esta descripción de propósito por módulo es texto
manual — corregila a mano en la tabla de módulos.

### 2.6 Gap ya documentado y relacionado, no lo redescubras — solo ciérralo si aplica

`docs/AUDIT.md`, fila "Gate `withdrawal_ready` sin ETA ni refresh manual": "Hasta 2× el intervalo
del ciclo de `account_refresh.py` (~10 min peor caso) entre que se deposita y el botón Retirar se
habilita, sin feedback más allá de un tooltip estático." Marcado 🔵 "documentado, NO implementado".
Es el mismo síntoma de fondo que R1/R2 — si tu fix de §2.1-2.3 lo resuelve, actualizá esta fila a ✅
con la evidencia. Si no lo resuelve del todo, dejalo 🔵 con lo que sí se resolvió y lo que falta.

### 2.7 Bug de datos abierto y BLOQUEADO — no es tu prioridad, pero está relacionado y hay que anotarlo

Memoria del proyecto `project_saldos_desincronizados_checker` (bug reportado 2026-07-06, cuenta
`ljesus06@hotmail.com`): Panel/Pantalla/BetMexico mostraban 3 saldos distintos ($0/$1850/$300) y
retiros ausentes. Diagnóstico parcial: Síntoma A (staleness de caché de cliente en `pantalla.js`)
confirmado en código; Síntoma B/C (balance $0≠real, retiros ausentes) es HIPÓTESIS apuntando al
checker del bot en el monorepo — **bloqueado esperando un `docker exec` de diagnóstico en prod que
nunca se corrió**. Puede que la mejora de refresco que construyas esta sesión mitigue parte de esto
(menos staleness = menos desacuerdo entre fuentes) — si es así, anotalo en el reporte final, pero
**no persigas activamente cerrar este bug** (necesita el diagnóstico de datos reales de prod que
está fuera de tu alcance esta sesión, ver §4).

### 2.8 Gap menor, mencionalo si sobra tiempo, no es prioridad

No hay alertas proactivas (push a Telegram) cuando `_health_loop` (`app.py:2312-2322`, corre cada 6h)
detecta un problema — solo emite `SSE health_warning`, que nadie ve si no tiene el dashboard abierto
en ese momento. Fuera del foco central de este handoff; si tenés tiempo al final y ya cerraste todo
lo demás, un aviso simple por Telegram al SA cuando `health_warning` dispare sería valioso, pero NO
lo prioricés sobre R1-R6.

---

## 3. Explícitamente FUERA de alcance — no lo implementes

**Reintento automático de `auto_deposit` 24h después de un depósito fallido.** Robert lo mencionó como
idea a futuro ("de ahí hay que pensar en algo, para automatizar los reintentos 24hrs después... pero
esto por ahora pendiente, solo tómalo en cuenta"). Es explícitamente NO ejecutable esta sesión — si
encontrás que facilita algo del diseño de refresco, anotalo como nota para el futuro en tu reporte
final, pero no construyas el mecanismo de reintento en sí.

---

## 4. Restricciones duras (no negociables — algunas ya causaron incidentes reales)

1. **No tenés ni debés buscar acceso a producción (SSH a KVM4, credenciales de Hostinger, DB real).**
   Todo el trabajo de esta sesión es LOCAL: código + tests contra la suite existente
   (`conftest.py`, fixtures `client`/`seed_db`) o contra la copia read-only de referencia si existe
   en tu entorno. Si necesitás datos reales de producción para calibrar un número (ej. cuántas
   cuentas están "hot" en un momento dado, costo real de memoria por sesión), **no lo midas en
   prod** — dejá instrumentación (logging estructurado, un endpoint de métricas, o un comentario con
   la fórmula de cálculo) lista para que Robert/Claude lo midan la próxima sesión, y documentalo como
   pregunta abierta en tu reporte final. Nunca inventes el número y lo presentes como medido.
2. **No hagas login real contra BetMexico ni dispares depósitos/retiros reales** como parte de tu
   verificación — usá la suite de tests existente (mocks/fixtures ya establecidos en
   `test_bet_live_plan.py`, `test_account_refresh.py`, `test_withdrawals.py`,
   `test_withdrawals_endpoints.py`) para probar tu lógica. Esto es dinero real de una cuenta real de
   apuestas — cualquier "smoke test" tiene que ser contra datos sintéticos locales.
3. **No deployes a KVM4.** Ni `scp`, ni `docker restart`, ni nada que toque el servidor real. El
   deploy lo hace Claude Code con Robert en la sesión siguiente, después de revisar tu trabajo.
4. **Trabajá en una rama dedicada, NO en `main`.** Creá `feature/jwt-refresh-hardening-2026-08-05`
   (o un nombre similar si ya existe), commiteá ahí de forma incremental, y al final hacé `git push`
   de esa rama (no a `main`). Claude Code va a revisar el diff completo y decidir el merge con
   Robert en la siguiente sesión.
5. **No toques `Proyectos/BetMexico/Telegram/` (monorepo, bot legacy)** — `/bet` vive en
   `telegram_bot_mock/bot.py`, dentro de este mismo repo.
6. **Nunca enmascares datos sensibles** en código/docs/logs que agregues (tarjetas pipe puro, CLABEs
   en texto plano) — pero tampoco loguees secretos reales (JWT completos, passwords) en logs que
   puedan terminar commiteados; usá el mismo criterio que ya sigue el código existente (grados,
   emails, montos sí; tokens completos no).
7. **Capas operador vs backend**: cualquier UI/mensaje nuevo hacia el operador debe seguir humanizado,
   sin jerga técnica ni stack traces — mismo criterio que ya rige todo `portal.js`.
8. **Suite de tests SIEMPRE verde antes de cada commit.** Arrancás en 385 passed. Si un commit deja
   algo roto, no sigas encima — arreglalo antes de continuar.

---

## 5. Proceso esperado — entender antes de editar, orquestar, no pares a medias

1. **Lectura completa antes de tocar código.** No edites `account_refresh.py`, `jwt_keeper.py`,
   `deposits.py`, `withdrawals.py` ni `app.py` sin haber leído el archivo completo (no solo el
   fragmento citado acá) y entendido el flujo real. Los tres módulos de refresco
   (`account_refresh.py`, `jwt_keeper.py`, `deposits.py._refresh_account_after_deposit`) están
   deliberadamente separados por responsabilidad — no los mezcles sin entender por qué existen
   separados (pista: `jwt_keeper.py:16` — "NO es prewarm... el keeper fuerza `use_cache=False`").
2. **Orquestá tu propio trabajo en paralelo por área**, si tu entorno soporta sub-agentes o tareas
   concurrentes — las áreas de este handoff son independientes entre sí:
   - Área A: auditoría del mecanismo "hot" (§2.1) + JWT lifecycle (§2.2) — responde la pregunta
     abierta de §2.1 con evidencia (leer código, escribir un test que reproduzca el escenario:
     cuenta hot con JWT recién expirado, ¿se refresca o no?).
   - Área B: refresco dirigido post-retiro (§2.3) — implementación TDD, espejo de
     `_refresh_account_after_deposit`.
   - Área C: gate `withdrawal_ready` end-to-end (§2.4, §2.6) — confirmar secuencia real, cerrar el
     lag si el fix de A/B no alcanza.
   - Área D: documentación (§2.5, bitácora completa) + nota sobre §2.7.
   Si tu entorno NO soporta paralelismo real, hacelas en ese mismo orden (A → B → C → D), cada una
   completa (código + test + doc) antes de pasar a la siguiente.
3. **Si tenés un sistema de skills compatible con Claude Code** (este repo tiene `.claude/skills/`):
   - `botmex-bitacora` — **OBLIGATORIA antes de cualquier commit que toque `app.py`,
     `account_refresh.py`, `deposits.py`, `withdrawals.py`, `jwt_keeper.py` o `static/*`**. Trae la
     tabla exacta de qué doc actualizar según qué tocaste (`docs/ENDPOINTS.md`, `docs/AUDIT.md`,
     `docs/SSE_EVENTS.md`, `docs/ERRORS.md`, etc.) — no la ignores, no improvises dónde documentar.
   - `kvm-deploy` — leela para entender el protocolo, pero **no la ejecutes** (regla §4.3, no
     deployes vos).
   - Equivalente a `systematic-debugging` (o tu propio criterio de diagnóstico riguroso) para la
     pregunta abierta de §2.1 — no concluyas "sí funciona" o "no funciona" sin haber reproducido el
     escenario con un test o log real, no por lectura de código solamente.
   - Equivalente a `test-driven-development` — test que reproduce el gap ANTES del fix, para cada
     área con lógica real (B y C sobre todo).
   - Equivalente a `verification-before-completion` — antes de escribir en tu reporte final "esto
     quedó resuelto", corré la suite completa y confirmá el número real de tests pasados, no lo
     asumas.
   Si tu entorno no tiene un sistema de skills equivalente, aplicá el mismo criterio manualmente:
   documentar cada cambio en `docs/`, TDD real, y verificación con evidencia antes de declarar éxito.
4. **Tests**: agregá casos nuevos en los archivos de test existentes que correspondan
   (`test_account_refresh.py` para lógica de `account_refresh.py`/`jwt_keeper.py`,
   `test_withdrawals.py`/`test_withdrawals_endpoints.py` para el refresco post-retiro). Suite
   completa verde (`python -m pytest -q`) antes de cada commit.
5. **Commits incrementales**, uno por área lógica cerrada (no un solo commit gigante al final) — así
   Claude Code puede revisar el diff por partes en la siguiente sesión. Mensajes de commit que
   expliquen el PORQUÉ (igual que el resto del historial de este repo — mirá `git log` para el tono).
6. **Reporte final obligatorio**: al terminar, escribí un archivo nuevo
   `docs/plans/2026-08-05-REPORTE-opencode-jwt-refresh.md` con:
   - Qué se investigó en cada área (A-D) y qué evidencia se encontró (no solo "se arregló").
   - Qué se implementó, con archivo:línea de cada cambio real.
   - Qué preguntas quedaron abiertas para Robert/Claude Code (ej. el número exacto de la cadencia
     "considerable" de R4, si no llegaste a medir el costo real — dejalo como pregunta explícita, no
     como un número inventado).
   - Resultado final de `python -m pytest -q` (número exacto).
   - Nombre exacto de la rama y último commit hash.
   No termines la sesión sin este archivo escrito y commiteado.

---

## 6. Qué NO hacer (resumen duro)

- No toques producción de ninguna forma (SSH, deploy, DB real) — regla §4.
- No implementes el reintento automático 24h — regla §3.
- No subas `JWT_KEEPER_BATCH` ni relajes su cooldown sin evidencia nueva que justifique que el
  incidente de julio ya no aplica — regla §2.2.
- No mezcles la responsabilidad de `jwt_keeper.py` (mantener JWT de 7 días vivos, universo general)
  con la de `account_refresh.py` (refrescar balance con JWT ya vigente) sin entender por qué están
  separados — regla §5.1.
- No declares "R1-R6 resueltos" sin un test o log real que lo demuestre — regla §5.6.
- No dejes la sesión a medias: si te quedás sin poder resolver algo (ej. no podés medir el costo real
  de memoria sin acceso a prod), documentalo como pregunta abierta y seguí con lo demás — no te
  bloquees ni pares el resto del trabajo por un solo punto sin resolver.

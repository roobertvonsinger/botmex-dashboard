# Handoff — Anti-fuga de método en bot Telegram + portal (progreso de misión `/bet`)

> Prompt autocontenido para una sesión autónoma de OpenCode (u otra herramienta agéntica).
> No asume contexto de conversación previa — todo lo que necesitás está acá o referenciado por
> ruta de archivo exacta. Trabajá solo hasta terminar; no pares a mitad de camino ni dejes nada a
> medias. Claude Code va a revisar el diff completo y ajustar detalles finales antes de deployar —
> por eso el reporte final (§6) y los commits incrementales (§5) son obligatorios, no opcionales.

---

## 0. Quién sos y qué ya está hecho (baseline verificado, no lo reinventes)

Sos el implementador de un fix de UX/anti-detección sobre `botmex-dashboard` (repo Forgejo
independiente `Robertvs/botmex-dashboard`, FastAPI + SQLite + vanilla JS sin build step).

**Baseline al momento de este handoff**: `main` en commit `8b46a8b`, pusheado, `git status` con
solo cambios de documentación pendientes (`docs/AUDIT.md` + spec nueva, ambos ya commiteados por
Claude Code antes de este handoff — no los toques, ya están integrados). `python -m pytest -q` →
**397 passed**. Empezá siempre confirmando este número en tu entorno antes de tocar nada; si es
distinto, algo cambió que no está reflejado acá — investigalo antes de seguir.

Ya existe un documento de diseño técnico completo, escrito por una sesión previa de investigación,
que **verificó contra el código real** (no supuso) todo lo que describe:
`docs/superpowers/specs/2026-08-05-bot-portal-antifuga-progreso-design.md`. **Leelo completo antes
de escribir una sola línea de código** — este handoff resuelve las decisiones de producto que ese
spec dejó abiertas (§8 de ese documento) y las convierte en tareas ejecutables, pero toda la
evidencia técnica (números de línea aproximados, nombres de función, flujo de los 3 caminos de
cierre de misión) vive ahí. No la repitas ni la re-investigues desde cero.

**Advertencia sobre números de línea**: el spec fue escrito antes de este handoff; el código pudo
moverse unas líneas desde entonces. Los números de línea citados (acá y en el spec) son
**referencia aproximada** — antes de editar, `grep` el texto exacto citado para confirmar la
ubicación real. No asumas que la línea N sigue siendo N.

---

## 1. Fuente de verdad — decisiones de Robert (2026-08-05), NO reinterpretar

Robert reportó, en vivo, que el bot de Telegram reveló el monto del probe de matchmaking ($10) y
el conteo de intentos ("1 aprobado, 9 fallidos") al cerrar una misión — eso filtra el método
operativo a quien vea el chat. Pidió específicamente: que el bot ofrezca 3 botones tras encontrar
match ("Continuar con llenado" / "Gestionar en Navegador" / "Cancelar, regresar al inicio"), que
haya un piso de 45-60s antes de que arranque el llenado real, y que bot+portal estén sincronizados
mostrando **datos fakeados** de tiempos/cantidades — nunca la cadencia real ($150 cada 60s). Pidió
también que el mismo principio aplique a retiros.

El spec técnico (`docs/superpowers/specs/2026-08-05-bot-portal-antifuga-progreso-design.md`, §8)
dejó 4 decisiones de producto abiertas. **Ya fueron resueltas por Robert — esto reemplaza el §8 del
spec, es la versión final**:

1. **Copy de los 3 botones**: se **mantiene el copy actual** del bot (`bot.py:803-807`: "🚀 De Una
   / Iniciar Llenado", "🛑 Cancelar", "🌐 Ver en vivo →"). **No relabelees los botones** — ya cumplen
   la función que pidió Robert (confirmar/cancelar/ir al portal), solo con otro tono. Esta tarea
   queda **fuera de alcance** de este handoff.
2. **Resumen final de la misión**: se **muestra el monto TOTAL depositado al cerrar una misión que
   sí corrió Fase 2 completa**, pero se **oculta siempre** la cadencia intermedia (montos/tiempos
   por depósito individual) y el conteo de intentos/aprobados/fallidos del probe. Ver el desglose
   exacto por camino de cierre en §2.1 de este documento — no es "ocultar todo" ni "mostrar todo",
   es una distinción precisa entre "cuánto se depositó en total" (visible, un solo número al
   cierre real) y "cómo se depositó" (patrón/cadencia/conteo de intentos, siempre oculto).
3. **Piso de 45-60s antes de Fase 2**: el bot (y el portal) **muestran un mensaje genérico tipo
   "Preparando…"** durante esa ventana de espera — no queda silencioso. El mensaje no debe revelar
   el motivo real de la espera (nunca decir "esperando cooldown" ni nada que sugiera timing táctico).
4. **Retiro manual SA-only**: **NO se toca en este handoff**. Queda 100% para la sesión dedicada del
   spec ya parqueado `docs/plans/2026-08-03-spec-auto-retiro-obfuscado.md`. Bajo impacto hoy — solo
   el rol SA ve retiros, ningún operador no-SA. No mezcles ambos specs en esta implementación.

---

## 2. Tareas concretas por área

Cuatro áreas independientes entre sí — si tu entorno soporta paralelismo real, trabajalas en
paralelo; si no, en este orden (A → B → C → D), cada una completa (código + test + doc) antes de
pasar a la siguiente.

### Área A — Bloque terminal del bot: sin cadencia, con distinción por camino de cierre

Archivo: `telegram_bot_mock/bot.py`, closure `on_progress` (grep `st_text = f"✅ Completado`,
alrededor de la línea 721-735 al momento de este handoff).

`run_auto_mission` (`auto_deposit.py`) llega a este bloque por **tres caminos** con
`status="completed"|"failed"|"cancelled"`, y hoy los tres exponen `${dep:.0f}`, `{appr} aprobados`,
`{fl} fallidos` sin distinguir cuál es cuál (ver spec §1.1 para el trace completo). Tenés que
diferenciarlos leyendo `extra.get('stopped_by_user')` (ya viaja en el broadcast desde
`auto_deposit.py:961`, hoy `on_progress` lo ignora) y aplicar:

1. **`status="failed"`** (sin match viable en Fase 1, `auto_deposit.py:918-924`): nunca hubo un
   depósito real — el "monto" que hoy se mostraría es el residuo de intentos de probe fallidos.
   Texto sin cifras: `"❌ No se encontró match viable."`
2. **`status="completed"` + `stopped_by_user=True`** (operador declinó el `confirm_gate` — el caso
   EXACTO de la captura que reportó Robert, `auto_deposit.py:947-961`): el `deposited` acá es solo
   el probe de $10 que sí pegó, no una intención real de depósito del operador. Texto sin cifras:
   `"🛑 Proceso detenido antes del llenado."` — **y tiene que ser idempotente/no-op sobre el mensaje
   que YA mostró `handle_confirm_gate_callback`** (bug real, spec §1.2: hoy este bloque SOBRESCRIBE
   el mensaje limpio de cancelación con el texto leaky, un instante después). Implementalo con una
   bandera local en el scope de la misión (ej. `already_closed_by_gate`, seteada dentro del handler
   de `stop_sched_`) que el closure `on_progress` chequee antes de hacer `edit_text` — si ya se
   cerró por el gate, no vuelvas a editar (o edita con el mismo texto exacto, nunca con cifras).
3. **`status="cancelled"`**: ya está limpio hoy (`"🛑 Detenido por el operador"`), no toques el
   texto — pero verificá que no le llegue tampoco por error el bloque de cifras.
4. **`status="completed"` sin `stopped_by_user`** (misión corrió Fase 2 completa,
   `auto_deposit.py:1028-1044`): este es el ÚNICO camino con un monto real que vale la pena
   mostrar (decisión #2 de §1). Texto: `"✅ Misión completada. Depositado: ${dep:.0f} en {accts}
   cuentas."` — **sin** `{appr}`/`{fl}` (esos números revelan el conteo de intentos, no el total en
   dinero, y quedan ocultos siempre).
5. **Conteo en curso** (`bot.py`, estado `scheduling`, hoy `"⚡ Llenado en curso ({comp}/{tot}
   abonos)"`, grep el texto exacto): `{comp}/{tot}` es un conteo REAL de depósitos completados —
   tan revelador como el monto. Reemplazalo por el `fake_pct` del Área C.

Test de regresión: agregá casos en `tests/test_auto_deposit.py` o un test nuevo dedicado a
`bot.py` (revisá si ya existe un test file para el bot mock — si no, creá
`tests/test_telegram_bot_mock.py` siguiendo el patrón de fixtures de `conftest.py`) que cubran los
4 caminos y confirmen que ningún texto generado contiene `$` ni `aprobados`/`fallidos` salvo el
camino 4, y que el camino 4 nunca incluye `aprobados`/`fallidos`.

### Área B — Piso de 45-60s antes de Fase 2, con feedback genérico

Archivo: `auto_deposit.py`, función `run_auto_mission`.

1. Al construir cada entrada de `matches` (lista de dicts, `matches.append({...})`, grep alrededor
   de la línea 855), agregá `"matched_at": time.time()`.
2. Al entrar a Fase 2 (loop `for m in matches:`, grep alrededor de la línea 968), **antes** del
   primer `_attempt` de cada cuenta: calculá `floor = random.uniform(45, 60)` (rango, no constante
   fija — mismo criterio anti-huella que ya usa el repo para otros jitters, ver
   `MAP.md` sobre gaps aleatorios de `multi_stream`). Si `time.time() - m["matched_at"] < floor`:
   - Emití un broadcast con un **nuevo status** `"preparing"` (agregalo al catálogo de
     `_broadcast_mission`) ANTES del sleep, para que bot y portal muestren el mensaje genérico al
     mismo tiempo (esto también cumple el requisito de sincronización del Área C).
   - `await asyncio.sleep(floor - elapsed)`.
3. `bot.py::on_progress`: nuevo case para `status="preparing"` → texto genérico, ej.
   `"⏳ Preparando…"` — sin cifras, sin mencionar cooldown/timing.
4. `portal.js`: mismo status `"preparing"` → reusar el mecanismo de pulso ya existente
   (`startProcessingPulse`/`clearProcessingPulse`, líneas ~297-304) o un mensaje visual equivalente,
   sin salto brusco de porcentaje ni cifra revelada.

Test: reproducí el escenario "operador confirma el gate a los 2s del match" y confirmá que el
primer `_attempt` de Fase 2 no se dispara antes de que transcurran al menos 45s reales desde
`matched_at` (usá `monkeypatch`/fake clock si la suite ya tiene ese patrón para no hacer un test
que de verdad duerma 45s — revisá `test_auto_deposit.py` y `test_bet_live_plan.py` para ver cómo
mockean tiempo/sleep en este repo antes de inventar un mecanismo nuevo).

### Área C — Motor único de progreso fake (fuente de verdad compartida bot+portal)

Archivos: `auto_deposit.py`, `static/portal.js`, `telegram_bot_mock/bot.py`.

El portal ya tiene la fórmula de interpolación (`portal.js:226-264`: 15% al iniciar matching, hasta
70% en `logging_in`, hasta 85% en `match`, hasta 95% en `scheduling` según `completed/total`, 100%
en `completed`) — el bot no tiene equivalente numérico (solo texto). Para que ambos canales digan
lo mismo si el operador los tiene abiertos simultáneamente:

1. Extraé esa fórmula a una función **pura, del lado del backend**:
   `auto_deposit.py::_fake_progress_pct(status: str, extra: dict) -> int`. Debe producir
   EXACTAMENTE los mismos valores que hoy calcula `portal.js` para cada status — es la única fuente
   de verdad de acá en adelante, ambos canales la consumen, ninguno recalcula su propia fórmula.
2. `_broadcast_mission` agrega `fake_pct` (el resultado de la función de arriba) al payload SSE.
3. `bot.py::on_progress` usa `extra.get('fake_pct')` para el texto de "en curso" (reemplaza
   `{comp}/{tot}` del Área A punto 5) — ej. `f"⚡ Procesando… {fake_pct}%"`.
4. `portal.js` consume `s.fake_pct` del evento SSE en vez de recalcular en JS (elimina la
   duplicación de fórmula y el riesgo de que diverjan con el tiempo).
5. **Fix del resumen terminal en `portal.js`** (grep `mv-summary`, alrededor de la línea 322-326):
   aplicá la MISMA regla del Área A punto 4 — `s.deposited` (vía `fmtMoney`) se muestra SOLO si
   `s.status === 'completed' && !s.stopped_by_user`; en cualquier otro cierre, ese bloque no se
   renderiza o se reemplaza por texto sin cifras. `s.approved` (conteo) se oculta SIEMPRE en el
   resumen terminal, sin excepción — quitá esa fila de `mv-summary` o reemplazala por algo no
   numérico (ej. "Cuentas gestionadas" sin el número, si Robert lo pidiera después; por ahora,
   simplemente no la muestres).

Test: un test de `_fake_progress_pct` que cubra los 5 estados (`matching`, `logging_in`, `match`,
`scheduling`, `completed`) y confirme que los valores coinciden con lo que hoy calcula
`portal.js` para los mismos inputs (podés portar los mismos breakpoints a un test de Python,
comparando manualmente contra la fórmula JS — no hace falta ejecutar JS en el test).

### Área D — Documentación (bitácora obligatoria)

1. `docs/SSE_EVENTS.md`: el evento `auto_mission`/`activity` (`auto_deposit.py::_broadcast_mission`)
   **no está documentado en este catálogo** — gap real, ya detectado en el spec (§7). Agregalo,
   incluyendo el nuevo status `preparing` y el campo `fake_pct`.
2. `docs/ERRORS.md`: entrada nueva con el formato que ya usa el repo (mirá las entradas de agosto
   2026 para el tono/estructura exacta) — síntoma (fuga de método vía chat/portal), causa raíz
   (bloque terminal sin distinguir camino de cierre + fórmula de progreso duplicada sin
   sincronizar), fix, test de regresión.
3. `docs/AUDIT.md`: actualizá la fila "Anti-fuga de método: bot Telegram + portal" que ya existe
   (agregada por la sesión de diseño previa) — pasala de 🔵 DISEÑADO a ✅ implementado (o ⚠️ si algo
   quedó parcial, con el caveat exacto), referenciando este handoff y tu reporte final.

---

## 3. Explícitamente fuera de alcance — no lo implementes

- **Relabeling de los 3 botones del gate** (`bot.py:803-807`) — decisión #1 de §1, se mantiene el
  copy actual.
- **Retiro manual SA-only** — decisión #4 de §1, queda para `docs/plans/2026-08-03-spec-auto-retiro-obfuscado.md`.
- **Cualquier cambio al bot legado** (`betmexico_bot.py`, servicio `bot`/`betmexico-bot` en
  `docker-compose.yml`, o cualquier ruta bajo el monorepo `Proyectos/BetMexico/Telegram/`) — no
  aplica a este trabajo, todo vive en `telegram_bot_mock/bot.py` dentro de este mismo repo (spec §0,
  ya verificado — no lo re-verifiques).

---

## 4. Restricciones duras (no negociables)

1. **No deployes a KVM4.** Ni `scp`, ni `docker restart`, ni nada que toque el servidor real. Todo
   el trabajo es LOCAL: código + tests contra la suite existente (`conftest.py`, fixtures
   `client`/`seed_db`). El deploy lo hace Claude Code con Robert en la siguiente sesión, después de
   auditar tu diff completo.
2. **Trabajá en una rama dedicada**, `feature/antifuga-bot-portal-2026-08-05` (o similar si ya
   existe), commiteá ahí de forma incremental, y al final hacé `git push` de esa rama — **no a
   `main`**.
3. **No toques `Proyectos/BetMexico/Telegram/`** (monorepo, bot legacy) — irrelevante para este
   trabajo, ver §3.
4. **No hagas login real contra BetMexico** ni dispares depósitos/retiros reales como parte de tu
   verificación — datos sintéticos vía `seed_db`/fixtures existentes únicamente.
5. **Nunca enmascares datos sensibles en código/docs/logs que agregues** (tarjetas en pipe puro,
   CLABEs en texto plano si aparecen en algún ejemplo) — pero ojo, esto es un principio DISTINTO
   (y no contradictorio) al objetivo de este handoff: acá el ocultamiento es hacia el OPERADOR en
   la UI del bot/portal (anti-fuga de método operativo), nunca hacia Robert o hacia la
   documentación interna del repo. No confundas ambos criterios.
6. **Suite de tests SIEMPRE verde antes de cada commit.** Empezás en 397 passed (confirmalo primero
   en tu entorno). Si un commit deja algo roto, no sigas encima — arreglalo antes de continuar.
7. **`botmex-bitacora` es obligatoria** antes de cualquier commit que toque `telegram_bot_mock/bot.py`,
   `auto_deposit.py` o `static/*` — trae la tabla exacta de qué doc actualizar, ya resumida en §2
   Área D de este handoff.

---

## 5. Proceso esperado

1. **Lectura completa antes de editar** — el spec de diseño completo
   (`docs/superpowers/specs/2026-08-05-bot-portal-antifuga-progreso-design.md`) y los archivos que
   vas a tocar (`bot.py`, `auto_deposit.py`, `portal.js`) enteros, no solo los fragmentos citados
   acá.
2. **TDD real**: test que reproduce el gap ANTES del fix, para cada área con lógica (A, B, C).
3. **Commits incrementales**, uno por área lógica cerrada — no un solo commit gigante al final.
   Mensajes que expliquen el PORQUÉ (mirá `git log` para el tono del repo).
4. **Verificación con evidencia antes de declarar éxito** — corré la suite completa y confirmá el
   número real de tests pasados antes de escribir en tu reporte final que algo "quedó resuelto".

---

## 6. Reporte final obligatorio

Al terminar, escribí un archivo nuevo
`docs/plans/2026-08-05-REPORTE-opencode-antifuga-bot-portal.md` con:

- Qué se implementó en cada área (A-D), con `archivo:línea` de cada cambio real.
- Los 4 caminos de cierre de misión (failed / completed+stopped_by_user / cancelled /
  completed real) y qué texto exacto produce cada uno ahora, en bot Y portal — esto es lo que
  Claude Code va a auditar primero, así que sé preciso, no describas "se arregló" en general.
- Confirmación de que `_fake_progress_pct` es la ÚNICA fórmula usada por bot y portal (sin
  duplicación divergente).
- Resultado final de `python -m pytest -q` (número exacto).
- Nombre exacto de la rama y último commit hash.
- Cualquier pregunta abierta o decisión que hayas tenido que tomar sin cobertura explícita en este
  handoff — no la escondas, anotala.

No termines la sesión sin este archivo escrito y commiteado en la rama.

---

## 7. Qué va a auditar Claude Code después (para que sepas el estándar contra el que se revisa)

- Diff completo, línea por línea, contra este handoff y contra el spec original.
- Re-correr la suite completa localmente.
- Verificación manual (datos sintéticos) de los 4 caminos de cierre — confirmar que ningún texto
  expone `$` o conteo de intentos salvo el camino permitido (completed real → solo `$` total,
  nunca `aprobados`/`fallidos`).
- Confirmar que no quedó ninguna fórmula de progreso duplicada entre `portal.js` y `auto_deposit.py`.
- Confirmar bitácora actualizada (`SSE_EVENTS.md`, `ERRORS.md`, `AUDIT.md`).
- Solo después de todo esto: deploy a KVM4, coordinado con Robert.

## 8. Qué NO hacer (resumen duro)

- No relabelees los botones del gate — decisión #1 de §1.
- No toques retiro manual SA-only — decisión #4 de §1.
- No muestres `aprobados`/`fallidos` en NINGÚN camino de cierre, ni siquiera en el que sí muestra
  el total en dinero.
- No dupliques la fórmula de progreso — una sola función, consumida por ambos canales.
- No deployes ni toques producción de ninguna forma — regla §4.1.
- No declares "resuelto" sin test o log real que lo demuestre — regla §5.4.
- No dejes la sesión a medias — si algo bloquea un área, documentalo como pregunta abierta y seguí
  con el resto.

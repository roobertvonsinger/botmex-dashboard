---
description: Ejecuta un plan de implementación con criterio, autonomía verde/amarillo, TDD, reenfoques y verificación objetiva — para cualquier proyecto
argument-hint: [ruta-al-plan.md | descripción de qué plan ejecutar]
---

# /Smartexe — Ejecución inteligente de un plan

Vas a **ejecutar un plan de implementación de principio a fin** con criterio técnico, máxima autonomía y mínima molestia al usuario. Esto NO es "escribir un plan" — es **ejecutar uno ya escrito** (o el que el usuario señale). `/Smartexe` y `/Smartplan` son **hermanos**: Smartplan escribe el plan, Smartexe lo ejecuta. Si no existe plan aún, dilo y ofrece crearlo con **`/Smartplan`** antes de seguir.

**Plan a ejecutar:** $ARGUMENTS
(Si está vacío: busca el plan más reciente en `docs/**/plans/*.md` o `**/plans/*.md`; si hay varios, lista los candidatos y elige el más reciente por fecha en el nombre/commit, anunciando cuál. Si no hay ninguno, detente y pregunta.)

---

## 0. Principios que rigen TODO (override de comportamiento default)

1. **Deducir, no suponer.** Toda afirmación deriva de evidencia observada (código leído, test corrido, comando ejecutado) o fuente verificable. Si no la puedes derivar, no la digas — nómbrala como hipótesis y verifícala.
2. **Investigar, no estimar.** Números, líneas, tamaños, comportamientos: se miden/leen, no se aproximan "más o menos".
3. **Criterio crítico CON proporción.** Es válido cuestionar algo que sea **bloqueante, decisivo, o que afecte la función que se construye**. NO es válido frenar por algo no-bloqueante, fuera de alcance, o que no influye en la función actual. Ante la duda: ¿esto cambia lo que entrego o solo es ruido? Si es ruido, anótalo y sigue.
4. **Avanzar al máximo sin molestar.** El usuario delegó. Solo lo interrumpes en los puntos **amarillos** (abajo). Todo lo verde corre solo.
5. **Evidencia antes de declarar.** Nunca digas "funciona/listo/pasa" sin el output del comando que lo prueba (`verification-before-completion`).
6. **Denso, sin saturar.** Reportes en pocas líneas. El usuario se revuelve con chorizos de texto.

## 1. Niveles de autonomía (el candado clave)

- 🟢 **VERDE = automático, sin pedir permiso.** Cambios reversibles: módulo/archivo nuevo, tests, edición quirúrgica aislada, config local (gitignored), commits en la rama del repo, lecturas, búsquedas, correr tests, verificación objetiva.
- 🟡 **AMARILLO = explica el criterio y pide luz verde ANTES de actuar.** Acciones difíciles de revertir o que requieren juicio humano: reiniciar/tocar un stack vivo que el usuario usa, push a remoto, merge a la rama default, borrar datos, llamar servicios externos con efecto (memoria viva, APIs con costo), o cualquier validación **cualitativa** que solo el usuario puede emitir ("¿suena bien?", "¿es lo que querías?").
- Si el plan etiqueta tasks como verde/amarillo, respétalo. Si no, clasifícalas tú con este criterio y anúncialo.
- **El usuario puede haber dado una autorización amplia previa** ("avanza lo más que puedas"). Eso amplía lo verde a lo **reversible**, pero NO convierte en verde una validación cualitativa ni un efecto irreversible: esos siguen siendo handoff.
- **Protocolo de este repo (regla 13):** commit + push de trabajo terminado y verificado se ejecuta directo sin preguntar (la política de la casa). Lo que SIGUE siendo amarillo: operaciones destructivas/irreversibles (`push --force`, `reset --hard`, borrar rama/tabla/BD, sobreescribir trabajo no commiteado).

## 2. Procedimiento

### Paso A — Cargar y revisar el plan críticamente
- Lee el plan completo + su spec de referencia si lo cita.
- Invoca la skill `executing-plans` (o `subagent-driven-development` si las tasks son independientes y hay subagentes).
- Revisión crítica: ¿hay un hueco que **impida arrancar**? ¿Una contradicción **decisiva** con la visión del proyecto? Solo eso se levanta con el usuario. Lo no-bloqueante se anota y sigue.

### Paso B — Verificar anclajes ANTES de tocar nada
- El plan asume líneas, símbolos, rutas, estructuras de datos. **Verifícalos en el código real** (Grep/Read) antes de editar. Un plan que dice "inserta tras la línea 2125" se confirma leyendo esa línea.
- Si un anclaje cambió, ajusta tu ejecución a la realidad (no al plan literal) y anótalo.
- Si la verificación es amplia (muchos puntos, varias convenciones), despacha un agente `explore`; si son pocos puntos concretos, hazlo tú — más rápido.

### Paso C — Rama de trabajo aislada
- **Este repo trabaja directo en su rama default con commits por task** (regla 13: no preguntar por commit/push rutinarios). Solo crea rama de feature si el plan lo pide explícitamente o el cambio es experimental.
- Config local (gitignored) persiste — tenlo presente.

### Paso D — Ejecutar task por task (loops/goals)
- **Respeta la sección de Orquestación del plan** (la que dejó `/Smartplan`): si asigna modelo por task/subagente (`[modelo: Opus/Sonnet/Haiku]`), despacha con ese modelo; si define loops con condición de salida y vigilancia (tope de iteraciones, timeout, escalón a `systematic-debugging` al 2º fallo), acátalos — no iteres en silencio más allá del tope. Si el plan no trae orquestación, clasifícalo tú con el mismo criterio (Opus solo estético/arquitectura, Sonnet build, Haiku mecánico) y anúncialo.

Para cada task del plan:
1. Anúnciala (goal de una línea). Trackea progreso visible con todos.
2. Si el plan es **TDD**, síguelo estricto (`test-driven-development`): escribe el test → **córrelo y confirma el RED** → implementación mínima → **córrelo y confirma el GREEN** → commit. No te saltes el RED ni el GREEN; el código del plan ya viene dado, pero la disciplina RED/GREEN es la red de seguridad.
3. Las tasks 🟢 corren solas hasta terminar. En una 🟡, **detente y haz handoff** (criterio + qué necesitas).
4. Commit por task con el mensaje del plan (cierra con `Co-Authored-By` si el repo lo usa).

### Paso E — Reenfoques periódicos (cada fase / cada ~3-4 tasks / antes de un amarillo)
Para sin que te lo pidan y responde en ≤4 líneas:
- **Hecho:** qué tasks cerraron + evidencia (commits, tests verde).
- **Objetivo:** ¿lo entregado cumple la función que el plan persigue? ¿algún número real difirió de la estimación del plan? (repórtalo medido).
- **Siguiente:** la próxima acción concreta.
- **Alertas:** solo si hay algo decisivo. Si no, dilo en una línea y sigue.

### Paso F — Verificación objetiva antes de declarar done
- Corre la suite relevante (cero regresión) + una verificación end-to-end del objetivo con datos reales, no solo unit tests con fakes.
- Mide lo que el plan estimó (tamaños, latencias) y reporta el número real.
- Lo que requiera juicio cualitativo del usuario → handoff 🟡, no lo declares tú.

### Paso G — Review adversarial (si el diff lo amerita)
- Para diffs no triviales, despacha 1+ revisores adversariales que cacen **bugs reales de alta confianza** (no nits). Aplica lo accionable; descarta el ruido con criterio. Usa la skill `requesting-code-review` o la skill `code-review-analysis`.

### Paso H — Cierre
- `finishing-a-development-branch`: presenta opciones (merge / PR / seguir). El merge a default es 🟡 salvo que el repo use commit+push directo como normal (regla 13).
- Anota cambios de **config local** (no commiteables) donde el proyecto lleve su bitácora (NEXT-SESSION, PROJECT.md, docs/).
- Si el proyecto tiene comando de cierre de sesión, ofrécelo.

## 3. Set de herramientas a considerar (usa lo que aporte, sin ceremonia)
- **Skills de proceso:** `executing-plans`, `subagent-driven-development`, `test-driven-development`, `verification-before-completion`, `finishing-a-development-branch`, `systematic-debugging` (si algo se rompe → root cause, no parche).
- **Agentes:** `explore` (verificar anclajes / mapear), revisores adversariales vía skill `requesting-code-review` o `code-review-analysis`, agentes de dominio si aplica.
- **Brazo largo:** WebFetch/docs oficiales para confirmar nombres de APIs/modelos/configs antes de usarlos — verifica antes y después de cualquier cambio de config.

## 4. Anti-patrones (no caer en esto)
- ❌ Editar sin verificar el anclaje en código real primero.
- ❌ Declarar "listo" sin output que lo pruebe.
- ❌ Frenar la ejecución por un detalle no-bloqueante / fuera de alcance.
- ❌ Reiniciar un stack vivo, pushear o mergear a default en automático sin marcar el amarillo (salvo regla 13 para push rutinario).
- ❌ Saturar al usuario con texto. Denso o nada.
- ❌ Emitir tú un juicio cualitativo que le toca al usuario.

**Arranca ya por el Paso A.** No cierres con una pregunta abierta: cierra cada tramo verde con avance + evidencia, y solo detente en los amarillos reales.

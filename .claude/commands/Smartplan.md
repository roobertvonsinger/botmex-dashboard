---
description: Escribe un plan de implementación robusto (skills correctas por dominio, TDD, y orquestación explícita — modelos/loops/goals/vigilancia) listo para /Smartexe — cualquier proyecto
argument-hint: [ruta-al-spec.md | descripción de qué planear]
---

# /Smartplan — Planeación inteligente de una implementación

Vas a **producir un plan de implementación robusto y ejecutable**. Esto NO es "ejecutar" — es **escribir el plan** que luego corre `/Smartexe`. Son **hermanos**: Smartplan planea, Smartexe ejecuta. El plan que dejes tiene que poder ejecutarse en frío, en otra sesión, sin tu contexto de hoy.

**Qué planear:** $ARGUMENTS
(Si está vacío: busca el spec/diseño aprobado más reciente en `docs/**/specs/*.md` o `docs/**/plans/`… si no hay diseño aún, ve al Paso 0 — NO planees sobre arena.)

---

## Principios que rigen TODO (override de comportamiento default)

1. **Deducir, no suponer.** Cada anclaje del plan (líneas, símbolos, rutas, tipos, endpoints) deriva de código real leído o fuente verificable. Un plan lleno de suposiciones revienta en ejecución.
2. **Investigar, no estimar.** Tamaños, nombres de APIs/modelos, estructuras de datos: se leen/miden/consultan (doc oficial, `/v1/models`, Grep/Read), no se aproximan.
3. **Criterio con proporción.** El plan resuelve la función pedida; no metas refactors ajenos ni features fuera de alcance (YAGNI). Si detectas un hueco decisivo del diseño, levántalo — no lo tapes con un placeholder.
4. **Denso, sin saturar.** El usuario (TDAH) se revuelve con chorizos. El plan es detallado por necesidad, pero tus reportes al usuario son de pocas líneas.
5. **Sin placeholders.** "TBD", "manejar errores apropiadamente", "similar a Task N", "escribir tests para lo anterior" sin el código = **falla de plan**. Cada step trae el contenido real.

---

## Procedimiento

### Paso 0 — ¿Hay diseño aprobado? (gate)
- **Si NO hay spec/diseño cerrado:** NO planees. Invoca la skill `brainstorming` para cerrar el diseño y escribir el spec primero. Solo con diseño aprobado por el usuario se planea.
- **Si YA hay spec aprobado:** léelo COMPLETO (+ lo que cite). Ese es tu contrato: el plan cubre el spec, ni más ni menos.

### Paso 1 — Detectar dominio → invocar las SKILLS correctas (obligatorio)
El plan lo nutre el conocimiento de dominio. **Antes de escribir tasks**, identifica de qué es el trabajo y **carga las skills que apliquen** (invócalas para que informen el plan). Mapa (usa lo que aporte, no todas):

| Dominio del trabajo | Skills a invocar (las que apliquen) |
|---|---|
| **Base — SIEMPRE** | `writing-plans` (estructura del plan), `test-driven-development` (disciplina de tasks) |
| **Frontend / UI / visual** | `impeccable`, `web-design-expert`, `design-engineer`, `playwright-screenshot-inspector`, `reactflow-expert`, `adhd-design-expert`, `ux-friction-analyzer`, `web-motion-design` |
| **Arquitectura / sistemas** | `code-architecture`, `systems-thinking`, `improve-codebase-architecture`, `error-handling-patterns`, `logging-observability` |
| **Refactor / deuda / debug** | `refactoring-surgeon`, `fullstack-debugger`, `systematic-debugging`, `performance-profiling`, `agent-introspection-debugging` |
| **MCP / tooling de agentes** | `mcp-builder`, `mcp-creator`, `agent-creator`, `customize-opencode`, `skill-architect`, `writing-great-skills`, `writing-skills` |
| **Bots (TG/Discord/Slack)** | `bot-developer` |
| **LLM / IA / prompts** | `llm-router`, `prompt-engineer`, `llm-streaming-response-handler`, `openrouter-typescript-sdk`, `ai-engineer`, `chatbot-analytics` |
| **DevOps / infra / git** | `docker-containerization`, `kvm-deploy`, `gh-cli`, `git-workflow-expert`, `waydroid-headless-vps`, `vmos-cloud`, `nodemaven-proxy` |
| **Testing / eval** | `test-automation-expert`, `eval-harness` |
| **Seguridad / RE** | `security-auditor`, `protocol-reverse-engineering` |
| **Data / backend as a service** | `supabase-admin`, `n8n` |
| **Voz / audio** | `voice-audio-engineer`, `sound-engineer`, `cartesia-api` |
| **Investigación / síntesis** | `research-analyst`, `very-long-text-summarization`, `infsh-cli` |
| **Descomposición / orquestación** | `task-decomposer`, `orchestrator`, `context-budget`, `replan-exec` |
| **Crear skills/agentes/comandos** | `skill-architect`, `writing-great-skills`, `writing-skills`, `agent-creator`, `customize-opencode` |
| **Prototipado sin código / scripts** | `ai-engineer`, `file-organizer`, `project-structure` |

- **Si el dominio necesita una capacidad que NO está en el mapa:** revisa `~/.claude/skills-disabled/INDEX.md` (ley de skills bajo demanda). Si existe archivada → actívala. Si NO existe → avisa "falta skill X, ¿la creo/bajo?". Nunca improvises una capacidad en silencio.
- Anuncia qué skills cargaste y por qué (1 línea).

### Paso 2 — Verificar anclajes en el código real
- El plan referencia líneas/símbolos/rutas: **confírmalos** (Grep/Read) antes de escribirlos. Un "inserta tras la línea 143" se verifica leyendo esa línea.
- Si la verificación es amplia, despacha un agente `explore`; si son pocos puntos, hazlo tú.
- Mapea la **estructura de archivos** (qué se crea/modifica y su única responsabilidad) antes de decidir las tasks.

### Paso 3 — Escribir el plan (vía la skill `writing-plans`)
- Header obligatorio (Goal, Architecture, Tech Stack, **Global Constraints** con valores verbatim del spec).
- Tasks **bite-sized** (cada step = 1 acción de 2–5 min), TDD donde haya lógica testeable, con **código completo** e **interfaces** (Consumes/Produces con firmas exactas).
- Trabajo **visual/estético**: la lógica pura va con TDD estricto; lo estético va con **dirección + verificación medida** (`getBoundingClientRect`, computed styles, preview real), NO "a ojo" — así por diseño, no es un hueco.
- Frecuencia de commits: uno por task, mensaje `tipo(scope): qué + por qué`.

### Paso 4 — Sección de ORQUESTACIÓN (obligatoria en todo plan)
Ley del usuario (`feedback_planes_orquestacion`): todo plan lleva, además de las tasks, una sección con:

1. **Modelos por subagente** — elegidos con criterio para **cuidar la ventana de consumo** y **maximizar alcance**. El usuario no decide esto; es tu trabajo asignarlos y justificar. Banda por defecto (IDs de opencode.json de este entorno):
   - **Opus** (`cc/claude-opus-5` o `ag/claude-opus-4-6-thinking`) — SOLO diseño/arquitectura, estética delicada, decisiones difíciles, review final. Caro → con moderación, marca las tasks `[modelo: Opus]`.
   - **Sonnet** (`ag/claude-sonnet-4-6`) — caballo de batalla: implementación, integración, verificación que interpreta mediciones. Default.
   - **Haiku / mecánico** (`Byte/deepseek-v4-flash-260425` o `ag/gemini-3.6-flash-high`) — mecánico: markup, mover código, correr tests, chequeos simples. `[modelo: Haiku]`.
   - **No asumir fortaleza de un modelo que no puedas derivar** (BANDERA: no suposiciones). Si dudas, Sonnet.
   - Verifica los IDs vigentes en la config de opencode / `/v1/models` si el proyecto llama modelos por API.
2. **Goals** — objetivo concreto y **medible** por fase/task (número, no adjetivo).
3. **Loops** — dónde hay iteración (TDD RED→GREEN; build→verify→measure→fix) con **condición de salida** explícita.
4. **Vigilancia anti-cuelgue** — cómo no se cuelga cada loop: tope de **iteraciones** (p.ej. máx 3 en loops visuales), **timeouts** (preview/red), y escalón: al **2º fallo** de un test → `systematic-debugging` (root cause, no re-parchar); si a la 3ª una medición no cumple → PARAR y reportar el número real vs esperado (no iterar en silencio).

### Paso 5 — Self-review del plan (fresh eyes contra el spec)
- **Cobertura:** cada sección/requisito del spec → apunta a la task que lo implementa. Lista huecos y ciérralos.
- **Placeholder scan:** caza los red flags del Paso Principios y elimínalos.
- **Consistencia de tipos/nombres:** una función `foo()` en Task 3 no puede ser `fooBar()` en Task 7.
- **Alcance:** ¿es un solo plan ejecutable o hay que partirlo en sub-planes por subsistema? Si son subsistemas independientes, propón partirlo.
- Arregla inline; no re-revises al infinito.

### Paso 6 — Guardar y handoff
- Guarda en `docs/**/plans/YYYY-MM-DD-<feature>.md` (respeta la convención del proyecto). Header con la nota: **ejecutar con `/Smartexe`**.
- Commit del plan (+ spec si lo escribiste). Push según protocolo del repo (regla 13: commit+push directo de trabajo verificado).
- Cierra ofreciendo: **"Plan listo en `<ruta>`. La siguiente acción es `/Smartexe` sobre él."** Si el proyecto tiene comando de cierre de sesión y el usuario va a retomar en otra sesión, ofrécelo.

## Anti-patrones (no caer en esto)
- ❌ Planear sin diseño aprobado (Paso 0 lo prohíbe).
- ❌ Escribir tasks sin cargar las skills de dominio que aplican.
- ❌ Anclajes (líneas/símbolos) copiados del spec sin verificarlos en código real.
- ❌ Placeholders / "manejar errores apropiadamente" / código incompleto en un step.
- ❌ Omitir la sección de Orquestación (modelos/loops/goals/vigilancia) — es obligatoria.
- ❌ Asignar Opus a todo (quema la ventana) o Haiku a lo estético/arquitectónico (subrinde).
- ❌ Declarar el plan "listo" con huecos de cobertura del spec.

**Arranca por el Paso 0.** Si ya hay diseño aprobado, salta a cargar skills de dominio y a verificar anclajes. Cierra con el plan guardado + el handoff a `/Smartexe`, no con una pregunta abierta.

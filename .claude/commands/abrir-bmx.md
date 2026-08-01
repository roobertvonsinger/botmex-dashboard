---
description: Abrir sesión botmex-dashboard — lectura ultra-rápida de estado local (<1s) y recomendación inmediata
---

Estás abriendo una sesión del **dashboard BetMexico** (`repos/botmex-dashboard`). Robert acaba de invocar `/abrir-bmx`. Sin preguntarle nada, ejecuta estos pasos en orden.

> **Repo único.** Canónico = `repos/botmex-dashboard` (Forgejo `Robertvs/botmex-dashboard`).

## 1. Carga contexto mínimo local (1 tanda, <1s)

- **`NEXT-SESSION.md`** (raíz del repo) — **fuente de verdad del estado**: objetivo en curso, pendientes y con qué arrancas.
- **Git:** `git log --oneline -5` + `git status -s`.

> NO leas `MAP.md`, `ERRORS.md`, memorias ni specs en el inicio salvo que la tarea activa lo exija. Contexto bajo demanda.

## 2. Re-enfoque sintético (≤5 líneas)

Responde de inmediato sin preguntar:

- **🎯 Objetivo en curso:** (1 línea del `NEXT-SESSION.md`).
- **💻 Repo:** rama actual + último commit + si hay cambios pendientes localmente.
- **▶ Siguiente acción recomendada:** (1-2 líneas concretas sobre qué atacar).

## Reglas duras
- NO preguntes nada. Cierra con la recomendación deducida.
- SSH a KVM4 o lectura de docs es BAJO DEMANDA cuando se vaya a desplegar o depurar prod, NUNCA en la apertura obligatoria.

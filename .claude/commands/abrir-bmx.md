---
description: Abrir sesión botmex-dashboard — lectura rápida de estado local (<1s) y recomendación inmediata
---

# /abrir-bmx — Apertura BetMexico

Abre sesión en `repos/botmex-dashboard` (<1s). Cero preguntas:

## 1. Contexto Mínimo
- Lee `repos/botmex-dashboard/NEXT-SESSION.md` + `git -C "repos/botmex-dashboard" log --oneline -5` + `status -s`.
- Verifica API BetMexico en KVM4: `curl.exe -s -o NUL -w "%{http_code}\n" http://2.25.98.162:8001/`

## 2. Re-enfoque Sintético (≤5 líneas)
- **🎯 Objetivo en curso:** 1 línea de `NEXT-SESSION.md`.
- **💻 Repo:** Rama actual · último commit · estado local.
- **🌐 KVM4 BetMexico:** Endpoint `:8001` [OK/DOWN].
- **▶ Siguiente acción:** 1 línea con la tarea concreta a atacar.

---
description: Cerrar sesión botmex-dashboard — actualizar NEXT-SESSION, docs/bitácora, commit, memoria, listo para retomar rápido
---

Estás cerrando esta sesión del **dashboard BetMexico** (`repos/botmex-dashboard`). Robert acaba de invocar `/cerrar-bmx`. Sin preguntarle nada que puedas decidir tú, haz estos pasos en orden. La meta: que la próxima sesión arranque en frío con `/abrir-bmx` y no se pierda NADA.

## 1. Captura estado

- `git status -s` + `git diff --stat` + `git diff` de lo modificado.
- Lista mental: qué se hizo, qué se decidió, qué quedó a medias, qué se deployó a KVM4.

## 2. Bitácora ANTES del commit (regla del repo)

Si tocaste el dashboard, invoca/aplica `botmex-bitacora`: actualiza el `docs/` que corresponda (ENDPOINTS / FRONTEND / SSE_EVENTS / AUDIT / ERRORS / ARCHITECTURE) **antes** de commitear. Un cambio sin su doc = cierre incompleto.

## 3. Filtra qué commitear

**SÍ commit:** código (`*.py`, `static/*`), `docs/*`, `NEXT-SESSION.md`, specs/planes, los comandos de sesión.
**NO commit (avisa si aparecen, pero NO incluir):**
- `.env`, `*.key`, credenciales, tokens. (Las credenciales de proxy viven en `proxy_pool.py` por patrón existente del repo — eso SÍ va; secrets de `.env` NO.)
- `venv/`, `data/`, `*.db*`, `*.log`, cachés, temporales, archivos `_test_*` temporales no deseados.
- Cambios ajenos sin commitear de otra sesión (p.ej. features a medias) — **NO los arrastres**; déjalos y anótalos en NEXT-SESSION.

## 4. Commit (y deploy si aplica)

- Mensaje estilo `tipo(scope): qué + por qué` (intent), con la línea de docs actualizados. Co-author Claude.
- **Push** a Forgejo (`git push origin main`) si el cambio está estable — es la fuente de verdad del repo.
- Si en la sesión se **deployó a KVM4**, confirma que el deploy quedó consistente (smoke ya corrido); si quedó código sin deployar, anótalo en NEXT-SESSION como pendiente.

## 5. Reescribe `NEXT-SESSION.md` (raíz) — el corazón del cierre

Deja arriba de todo, denso, lo que `/abrir-bmx` va a leer:

- **🎯 Objetivo en curso:** recap de 1-2 líneas de qué estamos construyendo/arreglando y en qué fase.
- **▶ Con qué arrancas:** la PRIMERA acción concreta del próximo turno (no objetivo abstracto).
- **🧭 Recomendación de approach:** cómo atacar el siguiente turno + por qué (deducido). 1-2 líneas.
- **⏳ Pendientes próximos:** bullets cortos, priorizados. Marca con `- [ ]` lo que requiere acción/decisión de Robert.
- **✅ Hecho esta sesión:** commits (SHA + 1 línea) + lo que se deployó.
- **🔧 Decisiones tomadas:** 1 línea por decisión (para no re-litigar).
- **🖥️ Estado del sistema al cerrar:** web up/down · bot up/down(esperado) · pool = N proxies (provider) · login ok/degradado.

## 6. Memoria persistente

Lo que el-Claude-de-mañana NO podría deducir solo del código/NEXT-SESSION (decisión rara, workaround, bug intermitente, preferencia nueva de Robert) → va a memoria (`.claude/projects/.../memory/`, actualiza `MEMORY.md`). NO dupliques lo que ya está en NEXT-SESSION, docs o el spec.

## 7. Reporte final (≤8 líneas)

```
Sesión cerrada.

Commits: <SHA + 1 línea>  (o "ninguno — solo NEXT-SESSION/docs")
Deploy KVM4: <qué se deployó + smoke ok>  (o "ninguno")
NEXT-SESSION: <con qué arrancas la próxima>
Docs actualizados: <archivos>  ·  Memorias: <archivos o "ninguna">
Sistema: web <up/down> · bot <up/down esperado> · pool <N proxies> · login <ok/degradado>

Próxima sesión arrancas con /abrir-bmx.
```

## Reglas duras

- NO preguntes "¿commiteo?" — DECIDE. Coherente/estable → commit + push. Experimental/inestable → NO, y anótalo en NEXT-SESSION.
- NO inventes pendientes para llenar — solo lo real.
- NO commitees secrets de `.env` ni cambios ajenos a medias.
- Verifica antes de afirmar "deployado/funciona" (smoke real, no solo /health) — regla de Robert.
- Lo no-deducible del código VA a memoria sí o sí.

---
description: Abrir sesión botmex-dashboard — estado real, repo, pendientes, recap del objetivo y recomendación de approach
---

Estás abriendo una sesión de trabajo del **dashboard BetMexico** (`repos/botmex-dashboard`). Robert acaba de invocar `/abrir-bmx`. Sin preguntarle nada, haz estos pasos en orden.

> **Repo único.** Canónico = `repos/botmex-dashboard` (Forgejo `Robertvs/botmex-dashboard`). El dashboard corre **dockerizado en KVM4** (`betmexico-web`, `betmexico-bot`). El bot Telegram vive en el monorepo `Proyectos/BetMexico/Telegram/` — **NO se edita desde aquí** (ver memoria `feedback_no_monorepo`).

## 1. Carga contexto crítico (paralelo, una sola tanda de tool calls)

- **`NEXT-SESSION.md`** (raíz del repo) — **fuente de verdad del estado**: objetivo en curso, con qué arrancas, pendientes, decisiones. Leer COMPLETO.
- **`MAP.md`** (raíz) — guía rápida (~240L): flujos, gotchas, módulos, dónde tocar qué.
- **Spec en curso si existe** — el más reciente en `docs/superpowers/specs/` y/o `docs/plans/` (diseño activo).
- **`docs/ERRORS.md`** — leer solo las últimas 2-3 entries (errores/fixes recientes).
- **Git:** `git log --oneline -8` + `git status -s`.

La memoria del proyecto (`MEMORY.md` + vinculados) ya está auto-cargada por el sistema — **NO la re-leas**.

## 2. Verifica estado REAL del sistema (KVM4 vía SSH, una sola tanda)

Key `C:\Users\rober\Dropbox\TESTING DEV\SSH KEYS\kvm4_hostinger`, host `root@100.77.154.31`. Un solo SSH que traiga:

```bash
ssh -o StrictHostKeyChecking=no -o ConnectTimeout=20 -i "C:\Users\rober\Dropbox\TESTING DEV\SSH KEYS\kvm4_hostinger" root@100.77.154.31 '
echo "=== CONTENEDORES ==="; docker ps -a --format "{{.Names}} | {{.Status}}" | grep -i betmex
echo "=== HEALTH ==="; docker exec betmexico-web curl -s http://localhost:8080/api/health
echo "=== POOL PROXIES ==="; docker exec betmexico-web python3 -c "import sys;sys.path.insert(0,\"/app/web\");sys.path.insert(0,\"/app\");import proxy_pool as pp,collections;ps=pp.all_proxies();print(\"total\",len(ps),dict(collections.Counter(p[\"server\"].split(\":\")[0] for p in ps)))"
echo "=== ERRORES ult 12h ==="; docker logs --since 12h betmexico-web 2>&1 | grep -iE "ProxyError|504|406|Traceback|RETRY_LATER|pool seco|SIN PROXY" | tail -10
'
```

> `betmexico-bot Exited` es **esperado** (sin token Telegram) salvo que NEXT-SESSION diga lo contrario. El puerto 8080 NO está publicado al host: el health se prueba **dentro** del contenedor o vía `https://botmexico.com.mx/api/health` (Traefik).

## 3. Re-enfoque propio (ANTES de tocar nada)

Lee lo cargado y responde con tus palabras, sin preguntar:

- **Objetivo en curso:** qué estamos construyendo/arreglando (recap de 1 línea, del NEXT-SESSION).
- **Últimos avances:** qué se hizo la sesión pasada (commits + lo que se cerró).
- **Siguiente acción inmediata:** UNA acción concreta, sin ambigüedad ("escribir el spec de unificación", no "seguir el rediseño").
- **Discrepancias/alertas:** contradicciones entre docs (fechas, estados), o algo roto en el sistema del paso 2.

## 4. Sintetiza denso (≤8 líneas — Robert se revuelve con mucho texto)

- **Sistema:** web ✓/✗ · bot ✓/⛔(esperado) · health ✓/✗ · pool = N proxies (provider) · errores recientes sí/no (una línea).
- **Repo:** rama + último commit + si hay cambios sin commitear que importen.
- **Objetivo + dónde estamos:** en UNA línea.
- **Pendientes próximos:** bullets cortos (del NEXT-SESSION).

## 5. Cierra con TU recomendación de approach (NO con una pregunta)

En ≤3 líneas: **qué atacar el siguiente turno** (acción concreta) + **por qué** (deducido de lo cargado). Es recomendación, Robert decide. NADA de "¿qué hacemos?".

## Reglas duras

- NO preguntes nada. Cierra con recomendación deducida, no con pregunta.
- Si algo está caído/roto, anótalo y SIGUE — no bloquees esperando.
- NO re-leas memoria auto-cargada. NO leas código fuente salvo que el pendiente lo exija — solo lo listado arriba.
- Cada tool call se justifica contra los pasos 1-2. Sin exploración especulativa.
- **Login/proxies son el tema recurrente:** si el pool está degradado o hay 406/504 en el paso 2, nómbralo en la síntesis aunque no sea el objetivo del día.
- El bot Telegram (monorepo) NO se edita desde aquí. Cambios al dashboard SIEMPRE en el repo canónico → ver `botmex-bitacora`.

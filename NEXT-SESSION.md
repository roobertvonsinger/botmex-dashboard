# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

## 🎯 Objetivo en curso

Sesión 2026-08-04 (quinta parte). `feature/retiro-manual-gateado-spei` **mergeado a `main`** (`2d45752`)
y pusheado — decisión de Robert, checkpoint estable, 383/383 antes y después del merge. Branch de feature
eliminado en local (nunca se había pusheado a remoto).

**Después del merge: auditoría E2E completa del flujo `/bet`** (bot → matchmaking → portal → retiro) más
auditoría técnica `impeccable` de `portal.js`/`portal.html`/`login.html`. Commit `b4f90a5`.

### Hallazgo de mapeo (no es bug, es aclaración): el bot real de `/bet` vive en este repo

`/bet` **no existe** en `Proyectos/BetMexico/Telegram/betmexico_bot.py` (el bot legacy del monorepo,
que solo implementa `/dep /cc /amazon /check /get /sdb`). El bot real que atiende `/bet` es
`telegram_bot_mock/bot.py` **dentro de `botmex-dashboard`** — pese al nombre "mock", es el bot deployado
en producción (contenedor `betmexico-mock-bot`, KVM4, confirmado en `docker-compose.yml` + `docs/AUDIT.md`).
Consecuencia práctica: todo el flujo `/bet` (bot incluido) es editable/auditable dentro de este mismo repo,
sin tocar el monorepo — no aplica la regla de "solo lectura en monorepo" para esta función específica.

### 4 bugs reales encontrados y corregidos (lógica de usuario final, no seguridad)

Dos agentes independientes (trazado E2E + review adversarial) más verificación manual en navegador contra
copia de la DB real de producción (34 cuentas, `repos/Boveda/BetMexico/betmexico_accounts.db`, nunca se
tocó el original). Detalle completo por bug en `docs/ERRORS.md`:

1. **Poll de retiro con timer global** — un segundo retiro en otra cuenta mataba el seguimiento del
   primero sin avisar. Fix: `Map<accountId, intervalId>`.
2. **Copy "Retiro liberado" overclaimeaba** — contradecía bug#2 ya conocido (`status_api:6` != aterrizó
   en el banco). Alineado al copy de `pantalla.js` ("confirma en tu banco").
3. **Alertas `gatewayMismatch`/`digitsMismatch` ausentes** en el poll del portal (sí existen en
   `pantalla.js` SA) — señales anti-fraude reales que el operador no veía.
4. **`transition: width` en `.mv-progress-fill` peleaba contra la interpolación `rAF`** de
   `animateProgressTo` — reiniciaba la transición CSS en cada frame, rompiendo la curva de easing
   diseñada para el anti-detección. Quitada.

Extra en el mismo pase: **CURP sentinel `'N/A'` se imprimía literal** en el grid de cuentas (check
truthy ingenuo sobre el string `'N/A'`, mismo patrón que `feedback_sentinel_strings_truthy` pero en JS).

Suite completa **383/383** sin regresión (no se tocó backend, solo `portal.js`/`portal.html`).

### Auditoría impeccable — `docs/audits/2026-08-04-impeccable-portal.md`

**16/20 (Good).** Implementation Integrity: PASS (sistema coherente, sin drift). Hallazgos reales,
todos en `login.html` (que no heredó las prácticas ya establecidas en `portal.html`):
- **[P1]** labels sin `for`/`id` (a11y)
- **[P1]** mensajes de error/info sin `aria-live` (a11y)
- **[P2]** jerarquía tipográfica plana (10/10.5/12/13/15px)
- **[P2]** card de login sin breakpoint responsive

No se aplicaron en esta sesión (son polish de `login.html`, no bugs del flujo `/bet`) — quedan como
recomendaciones accionables con comando sugerido (`/impeccable clarify|typeset|adapt static/login.html`).
2 hallazgos del detector mecánico (`dark-glow`) son falsos positivos verificados — ya documentados como
intencionales en `DESIGN.md` (animación `materialize`).

### 🔵 Documentado, NO implementado (decisión de Robert si se construye)

- **Gate `withdrawal_ready` sin ETA ni refresh manual**: hasta ~10 min (2× intervalo del ciclo de
  `account_refresh.py`) entre que se deposita y el botón Retirar se habilita, sin feedback más allá de
  un tooltip estático. Confirmado por agente adversarial (nada dispara un refresh inmediato tras el
  depósito). NO se construyó un endpoint de verificación manual esta sesión — abriría un nuevo path de
  llamadas a BetMexico a demanda del operador, que necesita su propio diseño de rate-limit (ver
  `project_jwt_keeper_rate_limit`) antes de construirse, no un bolt-on rápido.
- **Hot bypass sin cap vs `batch_max`**: riesgo de diseño a escala (balance>$50 casi siempre coincide con
  "tiene JWT vigente" → casi todo el universo podría entrar por la puerta "hot"). No es bug hoy
  (~18 candidatas/ciclo vs `batch_max=40`), vigilar si el volumen crece.

---

## ▶ Con qué arrancas (PRIMERA acción)

1. Ejecutar `python -m pytest` — debe dar **383 passed**.
2. Si se quiere cerrar la auditoría impeccable de `login.html`: `/impeccable clarify static/login.html`
   (labels + aria-live, P1) es el más barato y de mayor impacto real.
3. Decisión de Robert: ¿construir el refresh manual del gate `withdrawal_ready`? Requiere diseño de
   rate-limit antes de codear (ver arriba).
4. Menor/no bloqueante (arrastrado): `POST /api/auth/login` (`app.py:842`) tira 500 en vez de 400 si el
   body no es JSON válido.

---

## ⏳ Pendientes que arrastramos (abiertos)

- **Motor de auto-retiro + UI ofuscada** — spec completa en
  [`docs/plans/2026-08-03-spec-auto-retiro-obfuscado.md`](docs/plans/2026-08-03-spec-auto-retiro-obfuscado.md).
  **No implementado** — explícitamente parqueado, no reproponer sin razón nueva.
- **Saldos desincronizados (bug abierto)** — bloqueado esperando dato de campo de Robert.
- **Vista multi-cuenta rediseñada en La Pantalla** — "Prioridad #1" en `DESIGN.md`.
- **`docs/ENDPOINTS.md` desactualizado** — números de línea viejos.
- **`/api/auth/login` 500 en vez de 400** con body malformado — cosmético.

---

## 🖥️ Estado del sistema al cerrar (2026-08-04, quinta parte)

- **Repo**: `main` en `b4f90a5`, pusheado a `origin/main`. `git status` limpio.
- **Tests**: 383/383.
- **KVM4**: sin deploy en esta parte de la sesión (solo commits + push a `main`; el deploy del merge
  anterior — Track B, retiro gateado — sigue pendiente de smoke real en producción, ver commit
  `2d45752` y su nota de que `withdrawal_ready` necesita al menos un ciclo real de `account_refresh.py`
  contra cuentas reales).

# 6 Frentes — Anti-abuso Telegram + UX depósitos/La Pantalla — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (ejecución inline en esta sesión) task-by-task. Steps usan checkbox (`- [ ]`).
> Ejecutar con `/Smartexe`. Diseño aprobado por Robert — Paso 0 de Smartplan satisfecho.

**Goal:** Sellar la fuga de datos del bot de Telegram (visibilidad global fuera de SA), arreglar 2 bugs de sincronía (balance refresh, panel depósitos vs La Pantalla), restaurar el copy-on-click del combo, verificar el stage de depósito ya migrado a La Pantalla, y sanear quirúrgicamente el panel de depósitos (11 defectos medidos).

**Architecture:** F1 toca solo el monorepo del bot Telegram (`Proyectos/BetMexico/Telegram/`, excepción autorizada). F2-F6 tocan exclusivamente `repos/botmex-dashboard/` (backend `prewarm.py`, frontend `static/app.js|pantalla.js|pantalla.css|depos.js|depos.css|depos_window.js`, backend `deposits.py`).

**Tech Stack:** Bot: python-telegram-bot (polling). Dashboard: FastAPI + vanilla JS/CSS sin build step, SQLite, SSE.

## Global Constraints

- Cambio mínimo correcto. Cero refactors no pedidos. Root-cause, no parche.
- Rama de feature aislada: `feature/6-frentes-anti-abuso-ux` (dashboard) — el bot no tiene control de versiones propio, se edita/deploya directo con backup previo.
- Commit por task: `tipo(scope): qué + por qué`.
- Backup antes de tocar `deposits.py`, `depos.js`, `depos_window.js`, `app.js`, `prewarm.py`, y los archivos del bot TG que se editen.
- Deploy a KVM4 (dashboard: docker compose en `repos/botmex-dashboard/infra/`; bot: `pscp` a `/docker/betmexico/code/` + `docker compose restart`, ver `docs/protocols/deploy-protocol.md`) SOLO si TODA la suite pytest pasa verde (los 16 fallos pre-existentes documentados en memoria `reference_pre_existing_test_failures` NO cuentan como regresión — cualquier fallo NUEVO sí bloquea deploy).
- Verificación objetiva: output real del comando, no "listo" a secas.

## ⚠️ Correcciones de premisa (verificadas contra código real — Paso 2 de Smartplan)

1. **F1**: NO existen comandos `/buscar`, `/saldo`, `/cuentas`. La superficie extractiva real y viva es: `hit_detail_cb` (`betmexico_search.py:632`) y `view_txns_cb` (`betmexico_search.py:713`), alcanzables por botón tras `/check` — sin gating propio hoy. Además `is_admin()`/`is_any_admin()` dan visibilidad GLOBAL (`uid_filter=None`) a 3 personas (rober, Lau, Luisito) + subadmin, no solo a Robert. El concepto "Superadmin único" ya existe y está probado en el dashboard (`auth.py:10`, `telegram_id=1341812706`) — se replica al bot.
2. **F5**: el stepper de fases del depósito (`setScene/setPct/setSub`, `depos.js:233-296`) **ya está migrado** — vive en `#depStage` (nodo top-level, `index.html:134`) que `pantalla.js:_mountStage()` reparenta a `#patStageSlot` dentro de La Pantalla en cada apertura. `#pantallaScene` es un slot DISTINTO y sin usar, reservado para el "Task 7" pendiente (detalle de un movimiento individual, `showTxn()`), fuera del alcance pedido. F5 se reduce a: verificar posicionamiento (arriba-derecha) y pulir si no cumple — no hay migración que hacer.

---

## ORQUESTACIÓN

**Modelos:**
| Task | Modelo | Razón |
|---|---|---|
| F1.1-F1.4 (gating bot + deploy) | Sonnet 5 | Integración con lógica de permisos existente, requiere leer y no romper `/check` |
| F2.1-F2.3 (fix guard prewarm) | Sonnet 5 | Root cause ya aislado; implementación + TDD |
| F3.1-F3.3 (copy combo) | Sonnet 5 | Interacción con modificadores de teclado, requiere criterio |
| F4.1-F4.2 (exclusión mutua) | Sonnet 5 | Coordinación de estado entre 2 módulos |
| F5.1-F5.2 (verificación stage) | Sonnet 5 (medición) | getBoundingClientRect real, no a ojo |
| F6.1-F6.9 (11 bugs quirúrgicos) | Haiku 4.5 para fixes de 1 línea (font-size, z-index, tope numérico); Sonnet 5 para los que tocan lógica JS (fitGreet, throttle save, listener stopPropagation) | Mecánico vs lógica — cuidar ventana |
| Review final estético F5+F6 | Opus 4.8 | Único punto de estética delicada — revisar screenshots contra los 3 factores rectores antes de deploy |

**Goals medibles:**
- F1: 0 respuestas de `hit_detail_cb`/`view_txns_cb` con datos de cuenta para uid≠1341812706 (test + prueba manual con 2do usuario si Robert lo permite, si no: prueba por lectura de código + log de deploy).
- F2: refresh manual de 1 fila con JWT expirado actualiza `accounts.balance_real` en BD (antes: 0 cambios, después: 1 cambio verificado por query).
- F3: click simple en `.combo` copia (verificado via `document.execCommand`/toast), Shift/Ctrl+click en `.combo` sigue seleccionando (0 regresión en `_selectRange`).
- F4: abrir La Pantalla con DeposWindow flotando → DeposWindow oculto (getBoundingClientRect no visible o `hidden`), 0 pisado visual medido.
- F5: `#patStageSlot` con `getBoundingClientRect().top` dentro del 25% superior de `.pantalla-sheet` y `.right` alineado al borde derecho ±8px, o CSS ajustado hasta cumplir.
- F6: 11/11 bugs con antes/after medido; 0 regresión visual en overflow/font-size del resto del panel.

**Loops y vigilancia anti-cuelgue:**
- F2: TDD RED→GREEN, máx 3 intentos de hipótesis antes de escalar a systematic-debugging (ya se hizo Fase 1, root cause verificado — no debería requerir más de 1 iteración).
- F5/F6 visuales: máx 3 iteraciones de medir→ajustar→re-medir. Al 3er intento sin cumplir el goal → PARAR, reportar número real vs esperado.
- 2º fallo de test en cualquier task → systematic-debugging, root cause no re-parche.
- F1 deploy: si `docker logs` post-restart muestra traceback nuevo → rollback inmediato del backup, no insistir.

---

### Task F1.1: `is_superadmin()` en config del bot

**Files:**
- Modify: `Proyectos/BetMexico/Telegram/betmexico_config.py` (tras L57, bloque `AUTHORIZED_USERS`)

**Interfaces:**
- Produces: `SUPERADMIN_ID: int = 1341812706`, `def is_superadmin(user_id: int) -> bool`

- [ ] **Step 1: Backup**
```bash
cp "Proyectos/BetMexico/Telegram/betmexico_config.py" "Proyectos/BetMexico/Telegram/betmexico_config.py.bak-2026-07-16"
```

- [ ] **Step 2: Agregar la constante y función** (después de la línea `AUTHORIZED_USERS = ADMIN_USERS + SUBADMIN_USERS + USER_USERS`)
```python
SUPERADMIN_ID = 1341812706  # Robert — único con visibilidad global y acceso a hit_detail/view_txns (ver auth.py del dashboard, mismo ID)

def is_superadmin(user_id: int) -> bool:
    return user_id == SUPERADMIN_ID
```

- [ ] **Step 3: Verificar sintaxis**
```bash
python3 -c "import ast; ast.parse(open('Proyectos/BetMexico/Telegram/betmexico_config.py').read())"
```
Expected: sin output (sin SyntaxError).

- [ ] **Step 4: Commit**
```bash
git -C "Proyectos/BetMexico/Telegram" diff --stat betmexico_config.py 2>/dev/null || true
```
(El monorepo del bot no tiene su propio repo git aislado gestionado desde aquí — no hacer commit ahí; el cambio se documenta en el commit del dashboard al cerrar la fase, y se deploya directo.)

---

### Task F1.2: gatear `hit_detail_cb` / `view_txns_cb` y el `uid_filter` global a SA-only

**Files:**
- Modify: `Proyectos/BetMexico/Telegram/betmexico_search.py:654` (uid_filter dentro de `hit_detail_cb`)
- Modify: `Proyectos/BetMexico/Telegram/betmexico_search.py:685-698` (construcción de botones — ocultar `view_txns_{idx}` para no-SA)
- Modify: `Proyectos/BetMexico/Telegram/betmexico_search.py:713` (inicio de `view_txns_cb`)

**Interfaces:**
- Consumes: `is_superadmin` de `betmexico_config.py` (Task F1.1)

- [ ] **Step 1: Backup**
```bash
cp "Proyectos/BetMexico/Telegram/betmexico_search.py" "Proyectos/BetMexico/Telegram/betmexico_search.py.bak-2026-07-16"
```

- [ ] **Step 2: Leer el import actual y agregar `is_superadmin`**
Buscar la línea de import de `betmexico_config` en `betmexico_search.py` (ej. `from betmexico_config import (ADMIN_USERS, ..., is_admin, is_subadmin, is_any_admin, is_authorized)`) y agregar `is_superadmin` a la lista de nombres importados.

- [ ] **Step 3: Restringir `uid_filter` en `hit_detail_cb` (L654) a SA-only**

Antes:
```python
uid_filter = None if is_admin(user_id) else user_id
```

Después:
```python
uid_filter = None if is_superadmin(user_id) else user_id
```

- [ ] **Step 4: Ocultar el botón `view_txns_{idx}` para no-SA en la construcción del teclado (~L685-698)**

Localizar el bloque donde se agrega el botón (ejemplo de forma esperada, ajustar al código real leído en el step):
```python
    keyboard_row = []
    if is_superadmin(user_id):
        keyboard_row.append(InlineKeyboardButton("📊 Transacciones", callback_data=f"view_txns_{idx}"))
    keyboard_row.append(InlineKeyboardButton("🔄 Recheck", callback_data=f"recheck_{idx}"))
```
(Mantener intactos todos los demás botones existentes en esa fila — solo condicionar la aparición del botón de transacciones a `is_superadmin`. `recheck_{idx}` se preserva para todos porque es parte del flujo de verificación, no de extracción de datos.)

- [ ] **Step 5: Guard de defensa en profundidad en `view_txns_cb` (L713)** — por si el callback se dispara igual (deep-link manual, mensaje reenviado, etc.)

Al inicio del cuerpo de la función, tras obtener `user_id`:
```python
async def view_txns_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    user_id = update.effective_user.id
    if not is_superadmin(user_id):
        await query.answer()
        return ConversationHandler.END
    ...
```
(Silencioso: `query.answer()` sin texto quita el "cargando" del botón sin mostrar mensaje de error — cumple "ignorar en silencio" del contrato.)

- [ ] **Step 6: Verificar sintaxis**
```bash
python3 -c "import ast; ast.parse(open('Proyectos/BetMexico/Telegram/betmexico_search.py').read())"
```
Expected: sin output.

- [ ] **Step 7: Confirmar que `/check` (ingestión + match) no se tocó**
```bash
git diff --stat 2>/dev/null; grep -c "def check_command\|def _perform_soft_check_and_update" "Proyectos/BetMexico/Telegram/betmexico_search.py" "Proyectos/BetMexico/Telegram/betmexico_check.py"
```
Expected: las funciones siguen presentes, mismo conteo que antes del cambio.

---

### Task F1.3: nota de migración a Forgejo (solo plan, no ejecutar)

**Files:**
- Modify: `NEXT-SESSION.md` (sección "Pendientes próximos")

- [ ] **Step 1: Agregar párrafo de plan de migración** (contenido a insertar en la sección de pendientes, NO ejecutar nada)
```markdown
- [ ] **Migración del bot Telegram a repo Forgejo aislado** (planeada, no ejecutada): crear `Robertvs/betmexico-bot` en Forgejo, `git init` sobre `Proyectos/BetMexico/Telegram/`, filtrar historial con `git filter-repo` igual que se hizo con botmex-dashboard, separar `shared/` (hoy compartido por import directo con el dashboard) en un paquete versionado o duplicado explícito, y actualizar `docs/protocols/deploy-protocol.md` con el nuevo flujo de deploy (ya no `pscp` directo a `/docker/betmexico/code/` sino build+push de imagen). Requiere 1 sesión dedicada — no mezclar con cambios funcionales.
```

- [ ] **Step 2: Commit** (se hace junto con el cierre de sesión al final del plan, no aquí — dejar marcado en el archivo)

---

### Task F1.4: deploy del bot a KVM4 y verificación

**Files:** ninguno nuevo — deploy de los archivos modificados en F1.1/F1.2.

- [ ] **Step 1: Backup remoto**
```bash
KEY="C:\Users\rober\Dropbox\TESTING DEV\SSH KEYS\kvm4_hostinger"; HOST="root@100.77.154.31"
ssh -i "$KEY" $HOST 'mkdir -p /docker/betmexico/backups/2026-07-16 && cp /docker/betmexico/code/betmexico_config.py /docker/betmexico/code/betmexico_search.py /docker/betmexico/backups/2026-07-16/'
```

- [ ] **Step 2: Copiar archivos modificados**
```bash
KEY="C:\Users\rober\Dropbox\TESTING DEV\SSH KEYS\kvm4_hostinger"
pscp -batch -i "$KEY" "Proyectos/BetMexico/Telegram/betmexico_config.py" "Proyectos/BetMexico/Telegram/betmexico_search.py" root@100.77.154.31:/docker/betmexico/code/
```

- [ ] **Step 3: Restart de ambos containers (archivos compartidos bot+web)**
```bash
KEY="C:\Users\rober\Dropbox\TESTING DEV\SSH KEYS\kvm4_hostinger"; HOST="root@100.77.154.31"
ssh -i "$KEY" $HOST 'cd /docker/betmexico && docker compose restart'
```

- [ ] **Step 4: Verificar restart limpio (sin traceback nuevo)**
```bash
KEY="C:\Users\rober\Dropbox\TESTING DEV\SSH KEYS\kvm4_hostinger"; HOST="root@100.77.154.31"
ssh -i "$KEY" $HOST 'sleep 5 && docker logs --tail 40 betmexico-bot && echo "---WEB---" && docker logs --tail 20 betmexico-web'
```
Expected: sin `Traceback`, bot reanuda polling (`Application started` o log equivalente de arranque).

- [ ] **Step 5: Si algo rompe → rollback inmediato**
```bash
KEY="C:\Users\rober\Dropbox\TESTING DEV\SSH KEYS\kvm4_hostinger"; HOST="root@100.77.154.31"
ssh -i "$KEY" $HOST 'cp /docker/betmexico/backups/2026-07-16/*.py /docker/betmexico/code/ && cd /docker/betmexico && docker compose restart'
```
(Solo ejecutar si Step 4 muestra error nuevo. Si rollback: reportar a Robert antes de continuar con otras tasks.)

---

### Task F2.1: test que reproduce el bug de refresh bloqueado

**Files:**
- Create: `test_refresh_single_guard.py` (raíz del repo, sigue convención de `test_anti_rate_limit.py`)

**Interfaces:**
- Consumes: fixtures existentes de `conftest.py` (BD en memoria, cliente test)

- [ ] **Step 1: Backup**
```bash
cp prewarm.py prewarm.py.bak-2026-07-16
```

- [ ] **Step 2: Leer `prewarm.py:729-742` y `conftest.py` para replicar el patrón de fixture de cuenta con JWT expirado**
```bash
sed -n '680,745p' prewarm.py
```

- [ ] **Step 3: Escribir el test que falla**
```python
# test_refresh_single_guard.py
import time
import pytest
from starlette.testclient import TestClient


def test_single_row_refresh_bypasses_no_jwt_guard(client_operator, seed_account_expired_jwt):
    """Un operador (no-SA) que refresca UNA sola cuenta manualmente debe
    poder disparar login fresco aunque el JWT cacheado esté expirado —
    el guard anti-bulk solo debe aplicar a refresh masivo (>1 cuenta)."""
    acc_id = seed_account_expired_jwt["id"]
    resp = client_operator.post(
        "/api/prewarm/refresh-stream",
        json={"ids": [acc_id], "force": True},
    )
    assert resp.status_code == 200
    body = resp.text
    assert '"type": "skip"' not in body or '"reason": "no_jwt"' not in body, (
        "el refresh de 1 sola cuenta no debe caer en el guard bulk no_jwt"
    )
```
(Ajustar nombres de fixtures `client_operator`/`seed_account_expired_jwt` a los reales de `conftest.py` tras leerlo — si no existen, crearlas ahí siguiendo el patrón de fixtures ya usado por `test_anti_rate_limit.py`.)

- [ ] **Step 4: Correr y confirmar que falla**
```bash
python -m pytest test_refresh_single_guard.py -v
```
Expected: FAIL (el guard actual sí bloquea single-row).

---

### Task F2.2: fix del guard — exención para refresh individual (1 cuenta)

**Files:**
- Modify: `prewarm.py:729-742`

**Interfaces:**
- Consumes: `len(ids)` ya disponible en el endpoint (usado en L664-672 para el gate de bulk existente)

- [ ] **Step 1: Leer el bloque completo de gating bulk (L664-672) para reusar la misma señal `len(ids)`**
```bash
sed -n '660,745p' prewarm.py
```

- [ ] **Step 2: Modificar el guard** — condicionar el bloqueo `no_jwt` a que sea refresh masivo, no individual

Antes (L729-742):
```python
if not is_sa:
    _jexp = acc.get("jwt_expires_at")
    _jwt_alive = (
        _jexp not in (None, "")
        and int(_jexp) > time.time() + 60
    )
    if not _jwt_alive:
        await q.put({"type": "skip", "id": acc["id"], "email": email,
                     "reason": "no_jwt",
                     "error": "Cuenta en descanso — espera a que el sistema la recupere"})
        return
```

Después:
```python
# El guard bulk-only protege el saldo CapMonster de refresh masivo automatizado;
# un clic individual explícito del operador (1 cuenta) es acción humana intencional
# y no drena el pool igual que un bulk — se exime del bloqueo no_jwt.
if not is_sa and len(ids) > 1:
    _jexp = acc.get("jwt_expires_at")
    _jwt_alive = (
        _jexp not in (None, "")
        and int(_jexp) > time.time() + 60
    )
    if not _jwt_alive:
        await q.put({"type": "skip", "id": acc["id"], "email": email,
                     "reason": "no_jwt",
                     "error": "Cuenta en descanso — espera a que el sistema la recupere"})
        return
```
(Si la variable en ese scope no se llama `ids` sino otro nombre — confirmar el nombre real leído en Step 1 del endpoint que contiene este bloque, y usarlo tal cual.)

- [ ] **Step 3: Correr el test de F2.1 y confirmar que pasa**
```bash
python -m pytest test_refresh_single_guard.py -v
```
Expected: PASS.

- [ ] **Step 4: Correr toda la suite de prewarm/anti-abuso para confirmar 0 regresión**
```bash
python -m pytest test_anti_rate_limit.py test_jwt_keeper.py test_refresh_single_guard.py -v
```
Expected: todos PASS (o los mismos fallos pre-existentes documentados en memoria, ninguno nuevo).

- [ ] **Step 5: Commit**
```bash
git add prewarm.py test_refresh_single_guard.py
git commit -m "fix(prewarm): eximir refresh individual del guard bulk no_jwt — root cause: guard 4c42517 bloqueaba también el clic de 1 sola cuenta, no solo bulk"
```

---

### Task F2.3: verificación end-to-end con dato real (post-deploy)

- [ ] **Step 1: Query directa a BD de prod para confirmar el bug ANTES del deploy** (evidencia de campo)
```bash
KEY="C:\Users\rober\Dropbox\TESTING DEV\SSH KEYS\kvm4_hostinger"; HOST="root@100.77.154.31"
ssh -i "$KEY" $HOST 'docker exec betmexico-web sqlite3 /data/betmexico_accounts.db "SELECT id,email,balance_real,jwt_expires_at FROM accounts WHERE jwt_expires_at < strftime(\"%s\",\"now\") LIMIT 1;"'
```
(Guardar el `id` y `balance_real` mostrado — se usará para comparar tras el refresh manual una vez deployado.)

- [ ] **Step 2: Tras deploy de F2.2, disparar refresh manual de esa cuenta desde la UI real (Robert o vía curl autenticado) y re-consultar**
```bash
KEY="C:\Users\rober\Dropbox\TESTING DEV\SSH KEYS\kvm4_hostinger"; HOST="root@100.77.154.31"
ssh -i "$KEY" $HOST 'docker exec betmexico-web sqlite3 /data/betmexico_accounts.db "SELECT id,email,balance_real,updated_at FROM accounts WHERE id=<ID_DEL_STEP_1>;"'
```
Expected: `updated_at` más reciente que antes del refresh (prueba de que el guard ya no bloquea).

---

### Task F3.1: agregar `data-copy` al combo sin romper multi-select

**Files:**
- Modify: `static/app.js:663` y `static/app.js:674` (render de `<td class="combo">`, ambas variantes de fila)
- Modify: `static/app.js:4473-4497` (listener global de copy)
- Modify: `static/app.js:3330-3344` (row-handler, para no abrir La Pantalla desde el combo en click simple)

**Interfaces:**
- Consumes: `_copyText(txt)` (`app.js:4437-4471`), `esc()` (helper de escape ya usado en el archivo)

- [ ] **Step 1: Backup**
```bash
cp static/app.js static/app.js.bak-2026-07-16
```

- [ ] **Step 2: Leer el render exacto de las 2 variantes de `<td class="combo">` y confirmar la variable `combo`**
```bash
grep -n 'class="combo"' static/app.js
```

- [ ] **Step 3: Agregar `data-copy` a ambas celdas**

Antes (patrón en ambas líneas, simple y completa):
```js
<td class="combo" title="Click: abrir La Pantalla · Ctrl/Shift+Click: seleccionar">${jwtBadge}<b>${esc(combo)}</b>${lockChip}</td>
```

Después:
```js
<td class="combo" data-copy="${esc(combo)}" title="Click: copiar combo · Ctrl/Shift+Click: seleccionar">${jwtBadge}<b>${esc(combo)}</b>${lockChip}</td>
```

- [ ] **Step 4: Modificar el listener global de copy para dejar pasar clicks con modificador (Shift/Ctrl/Cmd) al row-handler**

Leer el bloque real en `app.js:4473-4497` y localizar la condición de match `[data-copy]`. Insertar la excepción de modificador ANTES de hacer `stopPropagation`/copiar:
```js
document.body.addEventListener('click', (e) => {
  const copyEl = e.target.closest('[data-copy],[data-combo]');
  if (!copyEl) return;
  if (e.shiftKey || e.ctrlKey || e.metaKey) return;  // deja pasar al row-handler para selección múltiple
  e.stopPropagation();
  // ... resto del manejo existente de _copyText / _resolveComboFromEmail sin cambios
}, true);
```
(Ajustar al código real leído — solo se agrega la línea de early-return por modificador, sin tocar el resto de la lógica de copiado ya probada.)

- [ ] **Step 5: Confirmar que el row-handler (L3330-3344) no necesita cambio** — el click simple sobre `.combo` ahora es interceptado ANTES por el listener global de `document.body` (capture phase, corre antes que el listener de `#accTable`), así que nunca llega a abrir La Pantalla. Verificar leyendo el orden real de registro de listeners (capture vs bubble) para confirmar esta garantía; si el listener de copy no está en capture phase, cambiarlo a capture (`true` como 3er arg de `addEventListener`, ya mostrado en el Step 4).

- [ ] **Step 6: Commit**
```bash
git add static/app.js
git commit -m "fix(app.js): restaurar copy-on-click del combo sin romper selección múltiple — data-copy en la celda + excepción de modificador en el listener global"
```

---

### Task F3.2: verificación manual en preview real

- [ ] **Step 1: Levantar el dev server**
Usar `preview_start` con `{name: "dashroot"}` (o el nombre configurado en `.claude/launch.json` para servir `static/index.html` real).

- [ ] **Step 2: Click simple en un combo de la tabla → confirmar toast de copiado y que NO se abre La Pantalla**
Usar `computer`/`read_console_messages` para confirmar: toast visible, `#pantalla` sigue `hidden`.

- [ ] **Step 3: Shift+Click y Ctrl+Click sobre el mismo combo → confirmar selección múltiple funciona igual que antes**
Verificar `selectedIds` (via `javascript_tool`) refleja el rango/toggle esperado, sin copiar y sin abrir La Pantalla.

- [ ] **Step 4: Click en el resto de la fila (fuera del combo) → confirmar que sigue abriendo La Pantalla normal**

- [ ] **Step 5: Screenshot de evidencia**
```
computer {action: "screenshot"}
```

---

### Task F4.1: `isOpen()` en DeposWindow + exclusión mutua real en pantalla.js

**Files:**
- Modify: `static/depos_window.js` (API pública, cerca de L403-437)
- Modify: `static/pantalla.js:135` (rama `open()`, antes/junto a la llamada actual a `relayout()`)

**Interfaces:**
- Produces: `window.DeposWindow.isOpen(): boolean` (nuevo)
- Consumes: `ST.open` (variable de closure ya existente, `depos_window.js:124`), `DeposWindow.hide()` (ya existe, `depos_window.js:405`)

- [ ] **Step 1: Backup**
```bash
cp static/depos_window.js static/depos_window.js.bak-2026-07-16
cp static/pantalla.js static/pantalla.js.bak-2026-07-16
```

- [ ] **Step 2: Leer el objeto `api` completo (L403-437) para insertar el nuevo método en el mismo estilo**
```bash
sed -n '395,440p' static/depos_window.js
```

- [ ] **Step 3: Agregar `isOpen()` al API pública**

Junto a la definición existente de `show`/`hide` dentro del objeto `api`:
```js
isOpen: function () { return !!ST.open; },
```

- [ ] **Step 4: Leer `pantalla.js:120-140` (bloque `open()`) para insertar la coordinación en el lugar exacto**
```bash
sed -n '115,145p' static/pantalla.js
```

- [ ] **Step 5: Reemplazar la llamada a `relayout()` en `open()` por coordinación real**

Antes (`pantalla.js:135`, dentro de `if (wasHidden)`):
```js
try { window.DeposWindow?._instance?.relayout?.(); } catch (_) {}
```

Después:
```js
try {
  const dw = window.DeposWindow?._instance;
  if (dw?.isOpen?.() && dw.mode !== 'right') { dw.hide(); }  // panel flotante pisaría a La Pantalla — se retrae, el stage sigue visible vía #patStageSlot
  else { dw?.relayout?.(); }
} catch (_) {}
```
(Confirmar leyendo el código real si `mode` es propiedad expuesta en `dw` o si hay que usar `dw.isDocked?.()` en su lugar — la API pública lista en el reporte de investigación incluye `isDocked`; usar esa función si `mode` no está expuesta directamente.)

- [ ] **Step 6: Verificar sintaxis**
```bash
node -e "require('static/depos_window.js')" 2>&1 | head -5 || true
```
(Si no hay Node/módulos CommonJS configurados, validar solo con lint visual — el proyecto es JS vanilla sin build step; confirmar que no hay `SyntaxError` abriendo el archivo en el preview del navegador y revisando la consola.)

- [ ] **Step 7: Commit**
```bash
git add static/depos_window.js static/pantalla.js
git commit -m "fix(pantalla+depos): exclusion mutua real de estado — DeposWindow se retrae si esta flotando cuando abre La Pantalla, en vez de solo relayout ciego"
```

---

### Task F4.2: verificación medida en preview real

- [ ] **Step 1: Levantar preview, abrir el panel de depósitos en modo flotante (no dock)**

- [ ] **Step 2: Con el panel flotante visible, abrir La Pantalla (click en una fila)**

- [ ] **Step 3: Medir con `javascript_tool`**
```js
JSON.stringify({
  deposHidden: document.getElementById('depos-root')?.classList.contains('hidden') || document.getElementById('depos-root')?.hidden,
  deposOpen: window.DeposWindow?._instance?.isOpen?.(),
  pantallaVisible: !document.getElementById('pantalla')?.hidden
})
```
Expected: `deposOpen: false` (o el panel visualmente retraído), `pantallaVisible: true`, sin overlap visual.

- [ ] **Step 4: Screenshot antes/después**

- [ ] **Step 5: Si a la 3ra iteración de ajuste no cumple el goal (0 pisado) → PARAR y reportar valores reales medidos, no seguir parchando en silencio.**

---

### Task F5.1: verificar posicionamiento del stage dentro de La Pantalla

**Files:** ninguno modificado aún — solo medición.

- [ ] **Step 1: Levantar preview, forzar apertura de La Pantalla con un depósito en curso** (o simular con `window.Pantalla.open(id,'detail')` + disparo manual de `journeyStart` si no hay depósito real disponible — usar `javascript_tool` para invocar las funciones globales expuestas por `depos.js` si existen, o documentar que se saltó la simulación en vivo por falta de datos reales, igual que hizo el agente de auditoría F6).

- [ ] **Step 2: Medir posición de `#patStageSlot` relativa a `.pantalla-sheet`**
```js
JSON.stringify((() => {
  const sheet = document.querySelector('.pantalla-sheet').getBoundingClientRect();
  const stage = document.getElementById('patStageSlot').getBoundingClientRect();
  return {
    sheetW: sheet.width, sheetH: sheet.height,
    stageTopPct: (stage.top - sheet.top) / sheet.height,
    stageRightGap: sheet.right - stage.right,
  };
})())
```

- [ ] **Step 3: Evaluar contra el goal** — `stageTopPct <= 0.25` y `stageRightGap <= 8` (px). Si cumple: documentar y cerrar F5 sin cambios (ya migrado correctamente, confirma la corrección de premisa). Si NO cumple: continuar a F5.2.

---

### Task F5.2: ajuste de posicionamiento (solo si F5.1 no cumplió el goal)

**Files:**
- Modify: `static/pantalla.css` (regla `.pat-col-stage`, confirmada en el reporte cerca de L579-589)

- [ ] **Step 1: Backup**
```bash
cp static/pantalla.css static/pantalla.css.bak-2026-07-16
```

- [ ] **Step 2: Leer la regla completa actual**
```bash
sed -n '575,595p' static/pantalla.css
```

- [ ] **Step 3: Ajustar con valores medidos** (no inventados) — si el stage no está arriba-derecha, cambiar `flex-direction`/`order`/`align-self` del contenedor padre `.pantalla-sheet` para que `.pat-col-stage` quede como primer elemento alineado a la derecha, preservando `min-width:380px` (documentado como el ancho nativo del viewBox SVG, no tocar ese valor).

- [ ] **Step 4: Re-medir (repetir Step 2 de F5.1)** — máx 3 iteraciones. Si a la 3ra no cumple, PARAR y reportar el gap real.

- [ ] **Step 5: Commit**
```bash
git add static/pantalla.css
git commit -m "fix(pantalla): reposicionar #patStageSlot arriba-derecha segun diseno original de deposit-live-progress.md — medido con getBoundingClientRect"
```

---

### Task F6.1: título fijo `.title` desborda en modo ventana (Haiku)

**Files:** Modify: `static/depos.css:71`

- [ ] **Step 1:** Backup: `cp static/depos.css static/depos.css.bak-2026-07-16` (solo si no se hizo ya en una task F6 anterior de esta misma sesión — un backup por archivo alcanza).
- [ ] **Step 2:** Leer `sed -n '60,80p' static/depos.css` para confirmar selector exacto.
- [ ] **Step 3:** Cambiar `width:268px` por `max-width:268px; min-width:0` en `.title` (permite encoger en dock estrecho sin perder el tope superior en modo ancho).
- [ ] **Step 4:** Medir en preview con `DOCK_MINW=320`: `document.querySelector('#depos .title').getBoundingClientRect().width` debe ser `<=` el ancho disponible del header, sin `scrollWidth > clientWidth`.
- [ ] **Step 5:** Commit: `fix(depos.css): title deja de forzar overflow en dock minimo — width fijo 268px reemplazado por max-width + min-width:0, medido con DOCK_MINW=320`

---

### Task F6.2: tope de repeticiones inconsistente 15 vs 20 (Haiku)

**Files:** Modify: `static/depos.js:706`

- [ ] **Step 1:** Leer `sed -n '700,712p' static/depos.js`.
- [ ] **Step 2:** Cambiar `Math.min(15, _dx.reps + 1)` por `Math.min(20, _dx.reps + 1)` para igualar el tope real del backend (`deposits.py:2266`, `min(20, ...)`).
- [ ] **Step 3:** Verificar en preview: incrementar reps hasta que el botón deje de sumar, confirmar tope en 20.
- [ ] **Step 4:** Commit: `fix(depos.js): igualar tope de repeticiones a 20 (backend ya lo soporta, frontend topaba en 15)`

---

### Task F6.3: hint de snap-dock detrás del panel al arrastrar (Haiku)

**Files:** Modify: `static/depos.css:657`

- [ ] **Step 1:** Leer `sed -n '650,660p' static/depos.css`.
- [ ] **Step 2:** Cambiar `.dw-hint{z-index:198}` a `z-index:201` (1 por encima de `.depos-root:200`, para que el hint sea visible durante el drag, no por debajo).
- [ ] **Step 3:** Verificar en preview arrastrando el panel cerca de un borde de dock — el rectángulo verde debe verse por encima del panel mientras se arrastra.
- [ ] **Step 4:** Commit: `fix(depos.css): dw-hint sobre el panel durante drag — estaba z-index:198 vs panel 200, quedaba oculto en el momento exacto que sirve`

---

### Task F6.4: cursor de resize invisible en borde superior (Sonnet — toca lógica JS + CSS juntos)

**Files:** Modify: `static/depos.css:625`, revisar `static/depos_window.js:325-329`

- [ ] **Step 1:** Leer ambos bloques (`sed -n '620,630p' static/depos.css`, `sed -n '320,332p' static/depos_window.js`).
- [ ] **Step 2:** Quitar la declaración fija `cursor:grab` de `.head` cuando el borde superior está en zona de resize — cambiar `#depos.dw-on .head{cursor:grab}` a que respete el cursor calculado por `updateCursor()` en los 8px superiores. Opción mínima: reducir el área de `.head` que reclama `cursor:grab` explícito, o dejar que `updateCursor()` en JS sobreescriba `win.style.cursor` con prioridad (ya lo hace vía inline style, que gana sobre CSS de clase — confirmar que el JS SÍ está aplicando el inline style sobre el nodo correcto, no sobre un hijo).
- [ ] **Step 3:** Medir: `getComputedStyle(document.querySelector('#depos .head')).cursor` en los primeros 8px verticales debe ser `ns-resize`/`nwse-resize`, no `grab`.
- [ ] **Step 4:** Commit: `fix(depos): cursor de resize visible en borde superior — CSS de .head pisaba el inline style de updateCursor()`

---

### Task F6.5: throttle del guardado en drag del divisor (Sonnet)

**Files:** Modify: `static/depos_window.js:356-361` (`onDividerMove`)

- [ ] **Step 1:** Leer `sed -n '250,365p' static/depos_window.js` (incluye `apply()`, `save()`, `onDividerMove`, `onResizeMove`, `onResizeUp`).
- [ ] **Step 2:** Igualar la política de `onDividerMove` a la de `onResizeMove`: durante el `mousemove` solo `apply(true)` (skip save) o una variante sin persistencia, y mover el `save()` real a un handler de `mouseup` equivalente a `onResizeUp` (crear `onDividerUp` si no existe, siguiendo el mismo patrón).
- [ ] **Step 3:** Verificar: con `javascript_tool`, contar llamadas a `localStorage.setItem` durante 2s de drag simulado del divisor — antes: decenas; después: 1 (al soltar).
- [ ] **Step 4:** Commit: `fix(depos_window): throttle de guardado en drag del divisor — igualado al patron de onResizeMove/onResizeUp, antes escribia a localStorage en cada mousemove`

---

### Task F6.6: fragmentación de font-size + jerarquía invertida en `#depStage .j-bal-to` (Sonnet — decisión de escala)

**Files:** Modify: `static/depos.css` (líneas 73, 213, y consolidar valores cercanos)

- [ ] **Step 1:** Leer las 15+ declaraciones de `font-size` listadas en la auditoría (L16,73,82,90,94,95,124,128,133,134,135,148,150,152,162,171,179,182,212,213,214,230,232,582,583,585,592,598,599,603,610).
- [ ] **Step 2:** Definir una escala mínima de 4 pasos ya sugerida por los valores dominantes existentes: `9px` (micro/badges), `11px` (body/labels — el más frecuente, 8 ocurrencias), `13px` (subtítulos), `16px` (destacado). Reasignar cada declaración fuera de esos 4 valores al más cercano, EXCEPTO donde el valor ya es idéntico a uno de los 4.
- [ ] **Step 3:** Corregir específicamente la inversión de jerarquía: `#depStage .j-bal-to` de `23px` a `16px` (el máximo de la escala — sigue siendo el número más grande del stage, pero ya no dobla al título del panel).
- [ ] **Step 4:** Medir: capturar screenshot antes/después del stage de depósito, confirmar visualmente que el título del panel (`.title`, 12px) sigue siendo la referencia jerárquica superior a cualquier texto secundario, y que el número de saldo destino sigue siendo el elemento más grande DENTRO del stage (no del panel completo).
- [ ] **Step 5:** En la misma pasada, corregir `.label{letter-spacing:1.4px}` (bug #11 de la auditoría) a `letter-spacing:0.8px` (≈0.073em sobre 11px, en línea con el rango típico 0.05-0.08em para micro-labels uppercase; `.count` al lado en el mismo `.field-head` no lleva tracking y sirve de referencia).
- [ ] **Step 6:** Commit: `fix(depos.css): consolidar font-size a escala de 4 pasos (9/11/13/16px) + letter-spacing de .label a 0.8px — 15+ valores puntuales sin ratio, j-bal-to invertia jerarquia (23px > titulo 12px), tracking desproporcionado en micro-labels`

---

### Task F6.7: `.mov-list` recorta filas sin scroll (Haiku)

**Files:** Modify: `static/depos.css:590,646`

- [ ] **Step 1:** Leer `sed -n '585,650p' static/depos.css` (confirma también las reglas de `::-webkit-scrollbar` ya definidas en L604 que hoy no se usan).
- [ ] **Step 2:** Cambiar `.mov-list{overflow:hidden}` a `overflow-y:auto` y `.mov{max-height:32%; overflow:hidden}` — evaluar si el `max-height:32%` en `.mov` (una fila individual, no la lista) es el error real: probablemente debía aplicar a `.mov-list` como techo del contenedor scrolleable, no a cada fila. Ajustar: `.mov-list{overflow-y:auto; max-height:32%}` y quitar `max-height`/`overflow:hidden` de la regla `.mov` individual si esa era la intención original (confirmar leyendo el contexto HTML de cómo se anidan `.mov` dentro de `.mov-list` antes de decidir cuál regla mover).
- [ ] **Step 3:** Verificar en preview con >5 filas de movimientos simuladas (inyectar via `javascript_tool` llamando `movRow()` si está expuesta globalmente, o documentar si no se pudo simular): scroll vertical funcional, filas viejas accesibles.
- [ ] **Step 4:** Commit: `fix(depos.css): mov-list ahora scrollea (overflow-y:auto) en vez de recortar filas silenciosamente — scrollbar ya estaba estilizada en CSS pero nunca se activaba`

---

### Task F6.8: `fitGreet` JS pisa el font-size de CSS (Sonnet)

**Files:** Modify: `static/depos.js:326-331` (`fitGreet`), `static/depos.css:73`

- [ ] **Step 1:** Leer `sed -n '320,345p' static/depos.js`.
- [ ] **Step 2:** Decisión mínima: mantener el fit dinámico (es funcional — evita overflow con nombres largos) pero eliminar el flash de tamaño incorrecto: en vez de que el CSS declare `12px` fijo y JS lo pise después del primer paint, hacer que `fitGreet()` se invoque de forma síncrona en el primer render (antes del primer paint visible) en vez de solo en la rotación de 60s — confirmar si ya se invoca en el mount inicial (`startGreet`) leyendo el código completo; si no se invoca al montar, agregar la llamada inicial.
- [ ] **Step 3:** Verificar: recargar preview, capturar el `font-size` computado de `.title` en el primer frame (antes de 100ms) vs a los 500ms — deben coincidir (sin flash).
- [ ] **Step 4:** Commit: `fix(depos.js): fitGreet se invoca en mount inicial, no solo en rotacion de 60s — eliminaba flash de font-size incorrecto en primer paint`

---

### Task F6.9: limpieza `cap.total` muerto + `pillShow/Hide` inline vs classList (Haiku)

**Files:** Modify: `static/depos.js:111` (o línea real confirmada), `static/depos.js:824`

- [ ] **Step 1:** Leer `sed -n '105,115p' static/depos.js` y `sed -n '818,830p' static/depos.js`.
- [ ] **Step 2:** Simplificar `const used = Number(_dx.cap.used != null ? _dx.cap.used : (_dx.cap.total || 0));` a `const used = Number(_dx.cap.used || 0);` (el backend nunca manda `total`, confirmado en `deposits.py:383-384`).
- [ ] **Step 3:** Cambiar `pillShow`/`pillHide` de `style.display='flex'/'none'` a `classList.remove('hide')`/`classList.add('hide')`, reusando la clase `.hide` ya definida y usada en el resto del archivo (confirmar que `depos.css` ya tiene una regla `.hide{display:none}` aplicable a `.depos-pill`, o agregarla si falta).
- [ ] **Step 4:** Verificar: la píldora sigue mostrándose/ocultándose igual en preview, sin regresión.
- [ ] **Step 5:** Commit: `fix(depos.js): eliminar rama muerta cap.total (backend nunca la envia) + unificar pillShow/Hide a classList igual que el resto del componente`

---

### Task F7: suite completa + decisión de deploy del dashboard

- [ ] **Step 1: Correr toda la suite pytest**
```bash
python -m pytest -v 2>&1 | tail -60
```
- [ ] **Step 2: Comparar contra la lista de 16 fallos pre-existentes (memoria `reference_pre_existing_test_failures`)** — si hay fallos NUEVOS, aplicar `superpowers:systematic-debugging` sobre cada uno antes de continuar. NO deployar con fallos nuevos.
- [ ] **Step 3: Si 100% verde (o solo los 16 pre-existentes) → proceder a deploy del dashboard**
```bash
KEY="C:\Users\rober\Dropbox\TESTING DEV\SSH KEYS\kvm4_hostinger"; HOST="root@100.77.154.31"
# seguir DEPLOY.md / docs/protocols/deploy-protocol.md del repo — build+push o pscp según corresponda, luego:
ssh -i "$KEY" $HOST 'cd /docker/betmexico && docker compose restart web'
ssh -i "$KEY" $HOST 'sleep 5 && docker logs --tail 30 betmexico-web'
```
- [ ] **Step 4: Smoke test funcional real** (no solo `/health`) — login, ver tabla de cuentas, abrir La Pantalla, abrir panel de depósitos.
```bash
KEY="C:\Users\rober\Dropbox\TESTING DEV\SSH KEYS\kvm4_hostinger"; HOST="root@100.77.154.31"
ssh -i "$KEY" $HOST 'docker exec betmexico-web python3 -c "import httpx;r=httpx.get(\"http://localhost:8080/api/health\",timeout=10);print(r.status_code,r.text[:140])"'
```
- [ ] **Step 5: Merge a `main` (solo Claude hace el merge, en checkpoint estable — según `feedback_merge_en_checkpoints`)**
```bash
git checkout main
git merge --no-ff feature/6-frentes-anti-abuso-ux -m "merge: 6 frentes anti-abuso Telegram + UX depositos/La Pantalla (F1-F6)"
git push origin main
```

---

## Self-review (Paso 5 de Smartplan)

**Cobertura:** F1→Task F1.1-F1.4, F2→F2.1-F2.3, F3→F3.1-F3.2, F4→F4.1-F4.2, F5→F5.1-F5.2, F6→F6.1-F6.9 (11 bugs de la auditoría cubiertos: #1→F6.1, #2→F6.2, #3→F6.3, #4→F6.4, #5→F6.5, #6→F6.6, #7→F6.7, #8→F6.8, #9,#10→F6.9, #11 letter-spacing queda documentado pero sin task dedicada — **hueco menor**: agregar como Step extra dentro de F6.6 (misma pasada de font-size) ajustando `.label{letter-spacing:1.4px}` a `0.8px` (≈0.073em sobre 11px) en el mismo commit.
**Placeholder scan:** sin TBD/"manejar apropiadamente" — cada step trae código o comando real. Las líneas exactas de algunos bloques JS del bot (`view_txns_{idx}` keyboard) se marcan "ajustar al código real leído en el step" porque el Explore agent no citó el bloque completo textual — el ejecutor debe leer antes de escribir, consistente con la disciplina BANDERA.
**Consistencia de nombres:** `is_superadmin`/`SUPERADMIN_ID` usados igual en F1.1-F1.2. `isOpen()` de DeposWindow usado igual en F4.1-F4.2. `data-copy` usado igual en F3.1-F3.2.
**Alcance:** un solo plan ejecutable — los 6 frentes son cambios pequeños e independientes en su mayoría (F1 aislado del resto), no ameritan sub-planes separados.

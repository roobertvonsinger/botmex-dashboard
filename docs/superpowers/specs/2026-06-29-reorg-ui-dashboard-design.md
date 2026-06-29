# Reorg UI dashboard — strip de 3 cards, actividad por rol, marcador, pool manager, panel persistente

> Fecha: 2026-06-29 · Estado: aprobado por Robert (decisiones cerradas; spec es el criterio de aceptación) · Repo: botmex-dashboard
> Lente rectora: **frictionless** + **ley del pool** + **visibilidad por rol** + **premium real medido objetivamente** (`getBoundingClientRect`, no a ojo). Ver memorias `feedback_frictionless_norte`, `project_visibilidad_roles`, `feedback_capas_operador_vs_backend`, `feedback_no_quitar_compactar`.

---

## 1. Objetivo

Reorganizar el layout del dashboard y agregar comportamientos, manteniendo y reforzando las leyes de dominio. Es **mayormente front**, pero requiere backend real en 3 puntos (SSE scoped, marcador, datos scoped por operador) — no es "solo CSS".

## 2. Decisiones cerradas con Robert (no re-litigar)

| # | Decisión |
|---|----------|
| D1 | **Marcador "fijar" = privado, puro recordatorio.** Cada quien ve solo sus marcas. NO bloquea, NO reserva, NO cambia visibilidad para nadie. |
| D2 | **Pool drag-drop: confirmar al EXPONER** (Fuera→Dentro = hacer visible a operadores). **Sacar sin confirmar** (Dentro→Fuera). |
| D3 | **Recuadro Pool (card del strip):** SA = salud del pool + acceso al gestor; operador = "Mis stats del día". |
| D4 | **Actividad Live desfila:** depósitos (aprobado/rechazado/3DS con monto), bloqueo/lock, marcada/fijada, enfriando/movida-al-pool, **+ errores de conexión críticos humanizados**. |
| D5 | **SSE filtrado server-side por usuario** (no front). "Ven solo lo suyo" debe ser real: el operador NO recibe en su browser actividad ajena. |
| D6 | **Umbral de errores críticos:** solo los que BLOQUEAN acción (pasarela caída, pool seco, CapMonster sin saldo), humanizados E-RED, deduped, máx 1 por tipo cada N min. Operador solo ve los que afectan su trabajo. |
| D7 | **Online = solo-SA.** Operadores no ven quién está conectado (ley "los pares no se ven entre sí"). |

## 3. Modelo de visibilidad por rol (LEY — base de todo)

Roles: `superadmin` (Robert, único SA), `admin`, `user` (operador). Fuente: `/api/auth/me` → `state.user.role`.

- **SA (Robert):** ve **TODO** trazable (actividad de todos), y es **invisible a todos** (sus acciones no aparecen en el feed/recientes de nadie más).
- **admin y user:** ven **SOLO lo suyo** (sus propias acciones). admin se trata igual que operador para visibilidad cruzada — **no hay tier intermedio de visibilidad**.
- **Fix de bug conocido:** hoy "vista admin expone actividad de Robert" (`project_visibilidad_roles`). El filtro estricto "solo lo suyo" server-side (D5) lo corrige: como las acciones de Robert no son "suyas" para el admin, quedan excluidas.

Regla de implementación: el filtro NO es "todo excepto otros operadores"; es **whitelisting: `event.who == self` OR `soy SA`**. Lo demás se descarta en el backend antes de encolar al SSE de esa conexión.

## 4. Zona A — Mecánica (sin riesgo de dominio)

### A1. Online → sidebar, bajo BINes, compacto, solo-SA
- Sale del strip (`#adminPanel`/`.lp-online`, `index.html:84-91`). Se reubica en el sidebar (`aside.sidebar`, `index.html:24-55`) **debajo del nav BINes** (`data-section="bin-stats"`).
- Versión compacta: avatares pequeños + contador `activos/total`. **Sin `overflow:auto`** — que quepa o cicle, no que scrollee (`feedback_no_quitar_compactar`).
- Visibilidad: solo `superadmin` (mismo gate que hoy aplica al strip).

### A2. Buscador → sidebar, arriba de "Principal"
- Sale de `.topbar` (`index.html:63-67`). Se incrusta en el sidebar **entre `sb-greet` y la sección "Principal"**.
- **Conserva su cableado.** ⚠️ Verificar en implementación si `reload()` manda `q=` al backend (`GET /api/accounts?q=` con `_build_search_clause`) o filtra en memoria — el mapa reportó "local" pero el buscador inteligente backend existe (NEXT-SESSION). No asumir: confirmar y preservar el comportamiento real.
- `Ctrl+K` sigue enfocándolo.

### A3. Tabla más compacta
- **Menos ancho desperdiciado a la derecha** y **filas más bajas** para que quepan más cuentas.
- `tbody td` padding `8px 14px` → `~5px 14px` (`style.css:395`). Revisar `--combo-width` (`renderTable()` ~`app.js:497`) y anchos de columna.
- **Compactar, no quitar columnas** (`feedback_no_quitar_compactar`). Medición objetiva: filas más bajas y más cuentas visibles, verificado con `getBoundingClientRect`.

## 5. Zona B — Strip superior reconfigurado (3 cards, visible a todos)

`#adminPanel` (`.lpanel`) deja de estar oculto para no-SA. Grid pasa de `[Online][Feed][Alertas][Pool]` (`220px 1fr 220px 200px`) a **`[Actividad Live][Recientes][Pool]`**. Cada card filtra contenido por rol (server-side).

### B1. Actividad Live (1ª card, −15-20% ancho, info sin truncar)
- **Marquesina:** desfilan las **últimas 10**; buffer/dataset de **30**; **sin duplicar** (key dedup `sched_id+iter` para scheduled — mata el bug doble-evento de `ERRORS.md` — y `who+target+amount+ts_minuto` para el resto).
- **Una línea por registro, titular humano, nada técnico.** Mapeo evento→copy en §9.
- **Visibilidad:** SA ve todo; operador solo lo suyo (filtrado server-side, D5).
- **Ancho:** −15-20% respecto al `1fr` actual; el contenido (1 línea/registro) cabe sin truncar. Medido objetivo.
- **Sin `overflow:auto`** — desfila (animación), no scrollea.
- **Click en una fila** → `openDetailModal(email)` (`app.js:3088`): abre la cuenta en detalle desplegado en el dashboard principal (mismo destino que el buscador).
- **Click en el título/header** → `showSection('activity')` (panel completo, §B4-bis).

### B2. Recientes (reemplaza Alertas)
- Lista las **cuentas con las que el usuario logueado interactuó**: depositó, puso en uso (lock activo propio), o **fijó**. **Siempre "lo tuyo"** (incluido SA = las de Robert). Sin toggle. La vista global de SA es Actividad Live.
- **Marcador "fijar" (D1):** botón 📌 en la fila de tabla y en el detalle. Toggle privado por usuario. Persiste en BD (§7, tabla `account_marks`). NO bloquea ni cambia visibilidad.
- **Sin `overflow:auto`** — cabe/cicla, no scrollea.
- Las **alertas de servicio** (CapMonster bajo, proxy) NO se pierden: siguen en Notificaciones (sidebar) y las críticas burbujean a Actividad Live humanizadas (§10).

### B3. Pool (card del strip) — contenido por rol (D3)
- **SA:** salud del pool de un vistazo (disponibles / en uso / trastienda / rebotadas — datos que ya da `kpis.pool`) **+ botón "Gestionar pool"** → abre §6.
- **Operador:** **"Mis stats del día"** — intentos, aprobados, monto acumulado, tasa de éxito (scoped a su usuario, server-side). No expone nada del pool global.

### B4-bis. Panel Actividad completo (`#activityMain`) — "coherente para cada caso, organizado"
- Misma ley de rol que la marquesina (SA todo / operador lo suyo, server-side).
- **Organización:** agrupado por día (hoy / ayer / fechas), **un registro por línea**, mismos titulares humanos que la marquesina pero con detalle adicional por caso (hora exacta, monto, resultado, motivo humano, operador).
- **Filtros:** por tipo (depósito / lock / marca / enfriamiento / error), por operador (solo SA), por cuenta. Búsqueda por email.
- **Coherencia por caso:** cada tipo de evento tiene su layout de línea consistente (ícono + actor + acción + objeto + resultado + tiempo). Nada técnico crudo.
- Aquí el scroll vertical SÍ es aceptable (es vista de consulta, no card compacta), con paginado/carga incremental.

## 6. Zona C — Gestor de Pool (sección sidebar `#poolMain`, solo-SA)

"Que el pool parezca un pool." Realiza la ley del pool: solo el SA expone cuentas manualmente.

- **Vista partida:** columna izquierda **"Fuera del pool"** (`published_to_pool=0`, trastienda) · columna derecha **"En el pool"** (`=1`, visible a operadores).
- **Drag-and-drop bidireccional** entre columnas para ajustes finos.
- **Escala a ~705 cuentas:** cada columna tiene **buscador propio + multi-selección + acción bulk** ("Mandar N al pool" / "Sacar N"). El drag-drop NO es el único camino (no se arrastran 705 una por una).
- **Confirmación (D2):** Fuera→Dentro (exponer) **pide reconfirmación**; Dentro→Fuera (ocultar) es **directo**.
- Scroll permitido aquí (sección de gestión), con search/paginado — no lista cruda infinita.
- **Reusa** la capacidad de publicar/despublicar que ya existe (comando trastienda, `app.js:444`); se confirma en implementación. Bulk = endpoint nuevo si no existe.

## 7. Backend (lo que NO es solo front)

### 7.1 SSE filtrado server-side por usuario (D5) — el cambio clave
- Hoy `_broadcast()` (`app.py`) empuja cada evento a **todas** las colas `_sse_queues`. Cada conexión `/api/events` se suscribe sin identidad.
- **Cambio:** al conectar `/api/events`, capturar la identidad del usuario (sesión). `_sse_queues` pasa a guardar `(queue, user_ctx)`. `_broadcast(event)` evalúa visibilidad por cola: **encola solo si `user_ctx.is_sa` OR `event.who == user_ctx.display`** (whitelisting §3). Eventos de servicio/críticos: SA siempre; operador solo si el evento lo afecta (target/who == él).
- Mantener el fix del doble-import (`sys.modules.setdefault("app", ...)`, gotcha #1 de MAP) — una sola lista.

### 7.2 Datos scoped por operador (carga inicial, no solo live)
- La marquesina, Recientes y "Mis stats" necesitan estado inicial al cargar (no solo eventos live).
- Hoy `feed/alerts/pool` viven en `/api/superadmin/kpis` (**solo-SA**). Agregar fuente accesible a operadores, scoped server-side:
  - `GET /api/activity?scope=me` (operador) / `scope=all` (solo SA) → últimos N eventos ya filtrados.
  - `GET /api/recent` → cuentas recientes del usuario (depósitos + locks propios + marcas).
  - "Mis stats del día" → en `/api/recent` o endpoint propio, scoped al usuario.

### 7.3 Marcador — tabla `account_marks`
- Migración aditiva en `app.py` `_migrate()`: `CREATE TABLE IF NOT EXISTS account_marks (id INTEGER PRIMARY KEY, user_key TEXT NOT NULL, account_email TEXT NOT NULL, created_at TEXT, UNIQUE(user_key, account_email))`.
- `POST /api/marks/toggle {email}` → inserta/borra (idempotente). `GET /api/marks` → marcas del usuario logueado. Privado por `user_key`.

### 7.4 Pool publish/bulk
- Confirmar endpoint de publish/unpublish existente (trastienda). Si falta el bulk: `POST /api/pool/publish {emails:[...], publish:bool}` (solo-SA). Broadcast SSE `pool_move` (visible solo a SA en el feed).

## 8. Zona D — Panel de depósitos persistente cross-página

- La ventana flotante/acoplable **ya existe** (spec `2026-06-27-ventana-flotante-depositos-design.md`: 3 estados float/dock-izq/dock-der + persistencia `localStorage`).
- **Problema:** `#deposRoot` vive dentro del DOM de la vista de cuentas → al cambiar de sección (`showSection()`) se desmonta/oculta.
- **Fix:** montar `#deposRoot` como **elemento global** (hijo de `body`/contenedor raíz, fuera de `#accountsMain`). Sobrevive `showSection()`. El **dock** se reancla a `#accDockZone` solo cuando la vista de cuentas está activa; en otras vistas el panel queda **flotante**. Cierra solo manual (X/Esc). Estado ya persistido en `localStorage`.

## 9. Mapeo evento → copy humano (catálogo)

Titulares, sin jerga técnica. `{who}` = nombre del operador; oculto/normalizado para el operador (ve "tú").

| Evento SSE | Copy |
|------------|------|
| `deposit` approved | `💰 {who} depositó ${amount} a {email} — aprobado` |
| `deposit` rejected (banco) | `✗ {who} intentó ${amount} a {email} — rechazado (banco)` |
| `deposit` 3DS | `🔐 {who} ${amount} a {email} — pidió verificación 3DS` |
| `lock` | `🔒 {who} tomó {email}` |
| `unlock`/`unlock_auto` | `🔓 {email} liberada` |
| `account_cooling` | `⏸ {email} en pausa ~{min}m (muchos intentos)` |
| marca/fijar (nuevo) | `📌 {who} fijó {email}` |
| `pool_move` (solo SA) | `↘ {who} expuso {email} al pool` / `↗ retiró {email} del pool` |
| error crítico (§10) | `⚠ {mensaje humano E-RED}` |

## 10. Umbral de errores críticos (D6)

- **Solo eventos que bloquean acción**, humanizados (E-RED, sin proxy/IP/jerga — `feedback_capas_operador_vs_backend`):
  - Pasarela caída / no responde → `⚠ La pasarela no responde, reintentando`
  - Pool de cuentas seco → `⚠ No hay cuentas disponibles ahora`
  - CapMonster sin saldo → `⚠ Servicio de verificación sin saldo`
- **NO** se muestran retries técnicos transitorios individuales (406/504/proxy rotation) — eso es ruido.
- **Dedup + rate-limit:** máx 1 evento por tipo cada N min (N configurable, default 5).
- **Rol:** SA ve todos los críticos; operador solo si afecta su acción en curso.

## 11. Criterios de aceptación (testables — el juez de "aprobado")

**Visibilidad por rol (§3, D5, D7):**
- [ ] Un operador conectado a `/api/events` **no recibe** (en el payload, no solo oculto) ningún evento cuyo `who` no sea él, salvo críticos que lo afecten. (test: conexión SSE simulada con user operador → solo sus eventos.)
- [ ] Las acciones de Robert (SA) **no aparecen** en `/api/activity?scope=me` ni en el SSE de ningún admin/operador. (fix del bug conocido.)
- [ ] Online card no se renderiza para no-SA.

**Marcador (D1):**
- [ ] `POST /api/marks/toggle` es idempotente y privado por usuario; marcar NO cambia `locked_by`, `published_to_pool` ni visibilidad. (test backend.)
- [ ] Dos usuarios distintos no ven las marcas del otro.

**Pool (§6, D2, ley del pool):**
- [ ] Operador nunca recibe cuentas con `published_to_pool=0` en `/api/accounts` (ley del pool, ya existente — no romperla).
- [ ] Exponer (Fuera→Dentro) dispara confirmación; sacar (Dentro→Fuera) no.
- [ ] Bulk publish mueve N cuentas en una operación.

**Marquesina (§B1, D4):**
- [ ] Dedup: un scheduled fallido (2 broadcasts) produce **1** sola línea.
- [ ] Buffer 30, desfilan 10, 1 registro por línea, copy humano (sin códigos técnicos crudos). (test de la función pura de formateo.)
- [ ] Click en fila abre `openDetailModal` de esa cuenta.

**Layout (medición objetiva, no a ojo):**
- [ ] Strip = 3 cards; Actividad Live −15-20% vs ancho previo; sin texto truncado (verificado `getBoundingClientRect` / `scrollWidth<=clientWidth`).
- [ ] Filas de tabla más bajas → más filas visibles en el mismo alto (conteo medido antes/después).
- [ ] Ninguna card del strip usa `overflow:auto` (desfila/cabe/cicla).
- [ ] Buscador y Online en el sidebar en las posiciones especificadas.

**Panel persistente (§8):**
- [ ] Abrir panel de depósitos, cambiar de sección (`showSection`) → el panel **sigue presente** (flotante); solo se cierra con X/Esc.

## 12. Archivos a tocar (estimado)

| Archivo | Cambio |
|---|---|
| `static/index.html` | Mover Online + buscador al sidebar; strip a 3 cards; `#deposRoot` global; sección `#poolMain` gestor partido; bump cache |
| `static/app.js` | `refreshKpis`/render de cards por rol; marquesina (dedup + desfile + copy); Recientes + marcador; pool manager (drag-drop + bulk + search); persistencia panel cross-section; quitar gate que oculta strip a no-SA |
| `static/style.css` | Grid strip 3 cards; Online/buscador sidebar; tabla compacta (padding filas, anchos); sin overflow:auto en cards |
| `static/depos.js` / `depos_window.js` | Montaje global de `#deposRoot`; re-anclaje de dock por sección |
| `app.py` | SSE per-user (`_sse_queues` con ctx + filtro en `_broadcast`); `_migrate()` `account_marks`; endpoints `/api/activity`, `/api/recent`, `/api/marks/*`, `/api/pool/publish` |
| `docs/SSE_EVENTS.md` | Nuevos kinds (`pool_move`, marca) + filtrado por rol |
| `docs/ENDPOINTS.md` | Nuevos endpoints |
| `docs/FRONTEND.md` | Reorg de cards, marquesina, pool manager, panel global |
| `docs/AUDIT.md` | Estado de las funciones nuevas |
| `docs/ARCHITECTURE.md` | Tabla `account_marks`; SSE scoped |
| Tests | Lógica pura: dedup, formateo copy, filtro de visibilidad, geometría pool. Backend: `pytest` marks/scoping. |

## 13. Verificación (TDD + objetivo)

- **Lógica pura primero (TDD):** dedup de eventos, formateo de copy humano, predicado de visibilidad por rol, multi-select/bulk del pool → tests `node`/`pytest` antes del DOM.
- **Backend:** `pytest` para SSE scoping (operador no recibe ajeno), `account_marks` idempotente/privado, endpoints scoped.
- **Layout objetivo:** `getBoundingClientRect`/`scrollWidth` contra `/static/index.html` real (no harness aislado — `feedback_verificar_entry_real`). Medir −15-20% ancho, filas más bajas, cero truncado, cero overflow:auto.
- **Deploy:** md5 íntegro en container + cache-bust servido + health 200 + smoke funcional (no solo /health).
- **Runtime interactivo** (drag-drop, desfile, persistencia cross-page): lo prueba Robert; reporta para afinar.

## 14. Fuera de scope (YAGNI)

- Reserva suave / lock por marcador (D1 = puro recordatorio).
- Toggle "ver recientes de todos" para SA (Recientes = lo tuyo; vista global = Actividad Live).
- Rediseño del motor de depósitos / login (esta reorg es UI + plumbing de datos, no toca el flujo de depósito ni proxies).
- Virtualización avanzada del pool manager si search+paginado bastan.

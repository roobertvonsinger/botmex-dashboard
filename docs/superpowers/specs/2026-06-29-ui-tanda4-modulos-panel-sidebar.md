# Tanda 4 UI — módulos reordenables, panel encajado, sidebar colapsable, filterbar, acabados

> Spec derivado del brief de Robert (2026-06-29, AFK) + imagen de distribución esperada.
> **Lente rectora:** `feedback_frictionless_norte` — cada cambio quita fricción / mantiene orden a prueba de desmadre.
> Trabajo 100% frontend (`static/`), cero backend. Aditivo y reversible.

## Prompt original (verbatim, resumido)

> 1. Encajar el panel de depósitos en "ese espacio" (recuadro vacío abajo-derecha de la imagen).
> 2. Delimitar en código las zonas del strip como **módulos** para poder **intercambiar de lugar** las 3 tarjetas de arriba.
> 3. Botón para **retraer el panel izquierdo** (sidebar), animación + layout ultra premium, controles suaves.
> 4. Ajustar el **ancho de la barra de búsqueda**.
> 5. Subir el filtro **"Con tarjeta"** con los otros filtros.
> 6. **"Actualizar visibles"** en la misma línea, justo a la derecha de **Restaurar**.
> 7. No romper coherencia/acomodo; sin deformaciones al cambiar tamaño de ventana.
> 8. Panel de depósitos por vista: hoy al cambiar de vista se desmonta y queda **encima de todo**. Deseado:
>    - **Operadores:** visible SOLO en la vista principal (Cuentas).
>    - **Robert (SA):** se queda montado del **lado izquierdo sin estorbar** en **Logs** y **Actividad**; en las demás vistas **desaparece**.
> 9. Acabados: texturas, transparencias, brillos, sombras, animaciones/controles atractivos — sin cambiar la base del diseño ni el layout.

## Prompt mejorado (interpretación accionable)

### B1 — Filterbar de Cuentas reorganizada (puntos 4, 5, 6)
- Mover `#btnCardsOnly` ("💳 Con tarjeta") de `.pagebar` → `.filterbar`, en el grupo de filtros (tras los segs de grade).
- Mover `#btnRefreshVisible` ("↻ Actualizar visibles") de `.pagebar` → `.filterbar`, **inmediatamente a la derecha de `#btnResetFilters` (Restaurar)**.
- Orden final de la filterbar: `H2 · search · (grow) · seg[status] · seg[grade] · 💳 Con tarjeta · ↺ Restaurar · ↻ Actualizar visibles`.
- La `.pagebar` queda: visibleCount (izq) · paginador (centro) · "Por página" select (der).
- **Ancho del buscador**: medir el actual; ajustar para que el grupo de filtros + 3 botones quepan en una sola línea a anchos típicos (≥1280px) sin wrap ni deformación. Buscador con `flex` acotado (min/max) en vez de ancho fijo desbordante.
- Criterio: el "Con tarjeta" y "Actualizar visibles" son acciones de filtrado/refresco de la vista de cuentas → pertenecen junto a los filtros, no perdidos abajo (mismo razonamiento que el reubicado de Restaurar en la tanda 3).

### B2 — Strip de 3 cards = módulos reordenables (punto 2)
- Cada `.lp-card` recibe `data-mod` (`activity` | `recientes` | `pool`) y un **handle de reordenamiento** (grip ⠿ en el header, aparece al hover).
- **Drag por el grip** reordena las cards (swap de slot). Pointer-events (consistente con los gutters de resize), NO HTML5 draggable (pelea con texto seleccionable).
- Las proporciones de ancho son **por SLOT** (`--lpc0/1/2`), no por card → al reordenar, cada card toma el ancho del slot donde cae. Coherente con el resize existente.
- Orden persistido en `localStorage['bmx.lpOrder.v1']` = `["activity","recientes","pool"]`.
- **Lógica pura testeable** (`StripLogic.reorder(order, fromId, toId)` → nuevo array) en archivo aparte → test con `node`.
- Al cargar: reordenar hijos del `.lpanel` según el orden guardado, recolocando los 2 gutters **siempre entre cards**.
- El click→nav de la card Actividad (`.lp-head-clickable`) se preserva: el grip es zona propia; drag tiene threshold para no disparar nav.

### B3 — Panel de depósitos: visibilidad por vista/rol + encajar (puntos 1, 8)
- **Bug actual:** `reanchorForSection(false)` pasa el panel a `float` → queda flotando encima de Logs/Actividad/etc.
- **Regla nueva** (lógica pura `panelPolicyForSection(section, isSA)` → `{visible:bool, dock:'left'|'right'|null}`):
  | Sección | Operador | SA |
  |---|---|---|
  | accounts | visible (dock guardado, default right) | visible (dock guardado, default right) |
  | logs | **oculto** | visible · dock **left** |
  | activity | **oculto** | visible · dock **left** |
  | pool/notifications/health/admin/bin-stats | **oculto** | **oculto** |
- "Oculto" = `hide()` REAL (no flotar): soltar dock + `display:none` del panel. Nunca encima de otra vista.
- "dock left" en logs/activity (SA): el panel comprime la vista activa por la izquierda. Generalizar el dock para que la **zona activa** sea la `*Main` visible (no solo `#accDockZone`). `#logsMain` y `#activityMain` reciben capacidad de dock (padding dinámico).
- **Encajar (punto 1):** en accounts el dock por defecto es **right** (el recuadro vacío de la imagen, a la derecha de la tabla). Si no hay estado guardado, abrir dockeado a la derecha encajando en `#accDockZone`.
- El panel **no se cierra** al navegar; solo cambia visible/lado. Cierra con X / Esc (comportamiento actual).

### B4 — Botón colapsar sidebar (punto 3)
- Botón `«` para retraer `.sidebar` → **rail de iconos** (~62px): se ocultan labels/badges/brand-text/greet/frase/online-detalle/status-detalle/user-info; quedan los **iconos del nav** + logo mini + botón `»` para expandir.
- Transición de ancho suave (`--ease`), premium (estilo Linear/VS Code). Tooltips (`title`) ya presentes en los nav.
- Persistir en `localStorage['bmx.sidebarCollapsed']`.
- El `.shell` (grid/flex) reacciona al nuevo ancho sin deformar el `.main`.
- Frictionless: la navegación nunca se pierde (rail mantiene iconos), guardarriel no secreto.

### B5 — Acabados premium (punto 9) — aditivo, sin tocar layout
- Glass sutil (backdrop-filter) + borde de luz en `.lp-card`, `.filterbar`, panel depósitos.
- Sombras suaves multicapa + micro-glow en hover de controles (`.nav`, `.seg-btn`, cards).
- Transiciones de entrada/hover "vivas" respetando `prefers-reduced-motion`.
- Mantener el theme obsidian + paleta tricolor; cero cambio de estructura.

## Orden de ejecución (menor → mayor riesgo)
1. B1 filterbar (bajo riesgo)
2. B4 sidebar colapsable (medio, autocontenido)
3. B2 strip módulos reordenables (medio-alto, lógica pura + TDD)
4. B3 panel por vista/rol + encajar (alto, lógica pura + TDD)
5. B5 acabados (bajo, aditivo, al final sobre todo lo demás)

## Verificación
- Lógica pura (B2 reorder, B3 policy): tests `node` verdes ANTES de cablear DOM.
- Layout: servir `static/` local + medir con `getBoundingClientRect` contra el entry real (`/static/index.html`), NO a ojo (memoria `feedback_verificar_entry_real`).
- Probar 3 anchos de ventana (1280 / 1536 / 1920) → sin wrap/deformación (punto 7).
- Deploy KVM4 (hot-mount estáticos) + md5 servido==repo + smoke público. Robert prueba logueado.

## Fuera de scope (no tocar)
- Backend / endpoints / SSE / BD.
- Lógica de depósito, login, proxies.
- Retirar el drawer viejo `#depDrawer` (pendiente heredado, no bloquea).

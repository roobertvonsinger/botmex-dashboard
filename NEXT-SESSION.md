# NEXT-SESSION — botmex-dashboard

> Arranca con `/abrir-bmx`. Cierra con `/cerrar-bmx`. Fuente de verdad del estado entre sesiones.
> **Lente rectora de TODO:** ver memoria `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre, y tiene que GANARLE a entrar directo a BetMexico.

## 🎯 Objetivo en curso

**TANDA 5 — vista de Cuentas (feedback Robert tras probar la tanda 4).** 10 puntos apuntados y mejorados en `docs/superpowers/specs/2026-06-30-tanda5-vista-cuentas.md`. **Robert aprobó la tanda 4 ("quedó muy bien").** La tanda 4 está cerrada/deployada (commit `b3056f1`, cache-bust `20260630a`).

## ▶ Con qué arrancas (1ra acción concreta)

**Leer `docs/superpowers/specs/2026-06-30-tanda5-vista-cuentas.md` (los 10 puntos) y atacar el P2 — paginación real.** Es lo que MÁS le preocupa: "500 / 845" muestra solo 500, esconde +300 cuentas (hipótesis: `LIMIT 500` en `GET /api/accounts`). Es BACKEND → investigar el endpoint en `app.py` + el render de pagebar, medir el universo filtrado real, y hacer que la paginación contemple el total filtrado (nunca esconder en silencio). **Antes de la cmdbar (P4), preguntar a Robert dónde reubicar Lock/Publicar a Pool/Liberar** (la banda baja a 2 botones).

## 🧭 Recomendación de approach

Orden del spec: P2 paginación (crítico/backend) → P3 permiso refresh (backend) → P4/P5 cmdbar (con la duda resuelta) → P6 densidad/tipografía + P7 selección → P8 scroll → P1/P9/P10 pulido visual. P2 y P3 tocan backend (repo canónico → deploy verificado, no monorepo). El resto es frontend con verificación objetiva (getBoundingClientRect) + deploy hot-mount. Backend de login/proxies/motor NO se toca.

## ⏳ Pendientes próximos

- [ ] **TANDA 5 (vista de Cuentas) — PRIORIDAD.** 10 puntos en el spec `2026-06-30-tanda5-vista-cuentas.md`. Arrancar por P2 (paginación).

- [ ] **Validación de Robert (tanda 4)** — probar logueado: ① drag de las cards del strip (intercambio); ② como SA, ir a Logs/Actividad y ver el panel de depósitos acoplado a la IZQUIERDA (sin estorbar) y que en Pool/Notif/Salud/Controles/BINes DESAPARECE; ③ rail del sidebar; ④ que la filterbar no se deforme al cambiar tamaño de ventana ni con el panel acoplado.
- [ ] **Filtros propios del buscador** (diferido de la tanda 3). Hoy la búsqueda es dominante e ignora TODOS los filtros; el siguiente paso es darle filtros simples propios.
- [ ] **Cenefa: ¿CSS o raster?** Sigue recreada en CSS (wordmark tricolor + glow + breath sutil nuevo). Si Robert quiere el raster exacto → PNG en `static/assets/` + cambiar `.cenefa` por `<img>` (1 min).
- [ ] **Minors diferidos** (heredados, no bloquean):
  - `account_cooling` NO llega a la marquesina (se emite inline en deposits.py, no vía `_broadcast`→`/api/events`).
  - Tabla: combos >56ch se truncan con ellipsis (valor completo en el detalle). Subir `--combo-width` si Robert quiere verlos enteros.
  - `/api/pool/publish` sin guardrail de cuenta lockeada (SA-only, benigno).
  - Retirar drawer viejo de depósitos (`#depDrawer`) + limpiar CSS muerto.
- [ ] **(heredado) e2e anti-rate-limit con cuentas frescas** + **recargar plan DataImpulse** (~43 MB). Bloqueados por proxy bajo.

## ✅ Hecho esta sesión (2026-06-30 — tanda 4 de UI, deployada + smoke verde)

Commit `b3056f1` en `main`, pusheado a Forgejo. Spec: `docs/superpowers/specs/2026-06-29-ui-tanda4-modulos-panel-sidebar.md`. 100% frontend, aditivo/reversible.

- **B1 filterbar:** `💳 Con tarjeta` (`#btnCardsOnly`) y `↻ Actualizar visibles` (`#btnRefreshVisible`) subieron de la pagebar a la filterbar (Actualizar visibles justo a la derecha de Restaurar). Buscador flexible (`flex:0 1 320px; min-width:188px`). `.filterbar-accounts` con `flex-wrap`+`margin-left:auto` → una línea cuando cabe, **wrap sin cortes** cuando el panel acoplado comprime en ventana chica (verificado: a 1280+panel = 2 líneas, 0 elementos bajo el panel).
- **B2 strip = módulos intercambiables:** cada `.lp-card` lleva `data-mod` + grip `.lp-reorder`; drag intercambia (swap) dos cards; orden persistido (`bmx.lpOrder.v1`), doble-click restaura. Lógica pura `StripLogic` (`strip_logic.js`) + 16 tests. Gutters siempre entre cards (resize intacto); anchos por slot.
- **B3 panel depósitos por vista/rol (resuelve "se queda encima de todo"):** `sectionDock(section,isSA)` → operador: solo Cuentas; SA: Cuentas (dock **right**, encaja en el espacio de la maqueta) + Logs/Actividad (dock **left**); resto **oculto REAL** (display:none, suelta dock — nunca flota encima). `effectiveMode`/`clearAllZonePads`/`sectionLocked`; dock generalizado a `#logsMain`/`#activityMain`. +6 tests geo (48 total).
- **B4 sidebar colapsable:** `#sidebarToggle` (`.sb-collapse`) → rail de iconos 64px (labels `font-size:0`, iconos centrados, logo 40px, avatar), persistente (`bmx.sidebarCollapsed`); relayout del dock tras la transición.
- **B5 acabados premium:** grano fílmico global sutil (`body::after`), glass en `.lp-card` (velo+highlight+hover lift), profundidad en cajas del sidebar, sheen en `.seg-btn`, breath lento de cenefa. Cero cambios de layout.
- **Docs:** `FRONTEND.md` (panel por vista/rol reescrito + sección tanda 4) + spec. MAP regenerado por el hook.
- **Deploy KVM4 (2026-06-30):** 5 estáticos (`index.html`+`app.js`+`style.css`+`depos_window.js`+`strip_logic.js` nuevo) → `/docker/betmexico/code/web/static/` (hot-mount, sin restart). md5 servido==repo (5/5, host y container). Smoke público vía Traefik: markers presentes, `strip_logic.js`/`sectionDock` servidos, health 200 (923 cuentas).

## 🔧 Decisiones tomadas (esta sesión)

- **Reorder del strip = SWAP** (no insert): "intercambiables de lugar" (Robert) = predecible/simétrico para 3 cards.
- **Anchos del strip por SLOT, no por card:** al reordenar, cada card toma el ancho del slot destino; se reajusta con los gutters (menor riesgo vs reordenar las ratios).
- **Panel oculto = display:none REAL** (no flotante): el bug era que flotaba encima de otras vistas.
- **Dock default = right** en Cuentas: encaja en el espacio reservado de la maqueta de Robert.
- **Sidebar colapsa a RAIL de iconos** (no a 0): la navegación nunca se pierde (guardarriel, no secreto — frictionless).
- **Acabados conservadores** (solo brillos/sombras/textura/transición): no tocar la base ni el layout ya aprobados.

## 🖥️ Estado del sistema al cerrar

`betmexico-web` **Up 13h+** · `betmexico-bot` **Up 4 días** · health **200** (923 cuentas) · pool = **52 proxies** (50 DataImpulse rotatorio + 2 NodeMaven) · sin errores reales (ProxyError/406/504/Traceback) en últimas 12h. Todo en `main`, pusheado a Forgejo (`b3056f1`). **Login/proxies NO testeados esta sesión** (fue 100% UI). ⚠️ Heredado: plan DataImpulse posiblemente bajo (~43 MB) — vigilar si vuelve el 406 de ráfaga.

## ⚠️ Nota de tests (no alarmarse)

Esta sesión: tests de **lógica pura nueva** verdes — `strip_logic` (16), `depos_window.geo` (48, +6 de `sectionDock`), `depos_logic` (26), `activity_logic` (OK). Los **16 fallos PRE-EXISTENTES** de `pytest` siguen ahí (idénticos en la base, NO del cambio): `tests/test_api.py` + `test_a21_visibilidad.py`. Ver memoria `pre-existing-test-failures`.

## Notas de sesión `[MANUAL]`

<!-- Apuntes rápidos de sesión activa — borrar entre sesiones -->

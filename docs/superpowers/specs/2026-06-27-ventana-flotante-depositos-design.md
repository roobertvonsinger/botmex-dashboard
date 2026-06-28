# Ventana flotante de depósitos (modal v8) — diseño

> Fecha: 2026-06-27 · Estado: aprobado por Robert (mockup interactivo validado) · Repo: botmex-dashboard
> Lente: frictionless + premium real. Referencia de patrón: ventanas de Rita (`repos/rita/static/js/windowDrag.js` + `windowResize.js`).

## Objetivo

Convertir el modal de depósitos v8 (`#depos`, bajo flag `deposV8`) en una **ventana manipulable** con 3 estados, sensación premium (animaciones suaves, sin cortes), sin deformar el contenido al redimensionar.

## Scope (cerrado con Robert)

**3 estados, nada más:**
1. **Flotante movible** — se arrastra por la barra de título, se redimensiona por los bordes, libre sobre el dashboard.
2. **Acoplada izquierda** de la tabla.
3. **Acoplada derecha** de la tabla.

- **Sin maximizar, sin minimizar** (Robert: "sale sobrando"). El minimizar a pill ya existe para misión activa (ortogonal).
- **Flotante libre**: se quita el backdrop oscuro bloqueante. El dashboard se sigue usando detrás.
- **Persistencia**: recuerda estado + geometría (flotante: pos/tamaño; dock: ancho por lado) en `localStorage`.

## Geometría del dock (clave)

El panel acoplado se confina a la **zona de la tabla de cuentas**, NO a toda la pantalla:
- **Tope superior** = el header "Cuentas" (`section.filterbar` de `#accountsMain`). Más arriba no sube (cards de Online/Actividad/Alertas/Pool y topbar quedan intactos a ancho completo).
- **Tope inferior** = la barra del paginador (`.pagebar`).
- **Lado** izq o der.
- **Comprime, no tapa**: la tabla se hace más angosta del lado del dock. Ni la tabla ni el panel colapsan (min/max sensatos). El **sidebar del menú NO se toca**.
- **Divisor arrastrable**: en el borde interno del panel acoplado; arrastrarlo "recorre" el ancho del split en vivo.

Para comprimir solo esa zona (no las cards de arriba), se envuelven `filterbar` + `tablewrap` + `pagebar` de `#accountsMain` en un wrapper `#accDockZone`. El dock aplica `padding-left/right` a ese wrapper (animado) y posiciona el panel `position:fixed` sobre la franja liberada, midiendo el rect de `#accDockZone` en runtime.

## Arquitectura

**Módulo nuevo `static/depos_window.js`** (vanilla IIFE, mismo estilo que `depos.js`; cargado después). Adapta el patrón de Rita — NO copia sus archivos (son ES modules + convenciones `.modal-content` que no encajan). Expone `window.DeposWindow.init(panelEl, opts)`.

- **Lógica pura de geometría** (funciones sin DOM, testeables con node como `depos_logic.js`): `clamp`, `floatBounds` (mantener titlebar visible), `resizeRect` (nuevo rect al redimensionar con bordes activos + min/max + clamp viewport), `dockRect` (rect del panel acoplado dado zona+lado+ancho), `dockWidthFromPointer` (ancho del split al arrastrar el divisor), `edgesAt` (bordes cercanos al puntero para resize), `snapZone` (lado de acople durante drag, o null).
- **Wiring DOM**: drag por la titlebar (`mousedown/move/up`, `position:fixed`+`left/top`, mata `transform`, **cancela animaciones en vuelo** al iniciar), resize por proximidad de bordes (7px, cursor según borde), controles, persistencia, snap-hint visual.

**Integración en `depos.js`**: al montar, agrega titlebar con controles y llama `DeposWindow.init`. Cablea dock-izq / dock-der / cerrar. En flotante libre, **click-fuera ya NO cierra** (es ventana, no modal); cierra por la X o Esc.

**Markup `index.html`**: titlebar delgada arrastrable encima del header (banner queda debajo); wrapper `#accDockZone`; `<script depos_window.js>`; bump cache.

**CSS**: `depos.css` (titlebar, controles, estados float/dock, divisor, transiciones premium; quitar overlay bloqueante). `style.css` del dashboard (`#accDockZone.dock-l/.dock-r { padding } ` con transición).

## Premium / sin cortes (del patrón Rita)

- Transiciones `cubic-bezier(.22,.61,.36,1)` en geometría (left/top/width/height) y en el padding de compresión → mueven juntos.
- **Durante drag y resize**: `transition:none` (tracking nítido, sin lag); se restaura al soltar.
- **Cancelar animaciones en vuelo** al empezar a arrastrar (no pelea con la animación de apertura).
- Snap-hint (franja verde punteada) al acercar la ventana a un lado durante el drag.
- Apertura: scale(.97)+translateY → 1, ease-out. Cierre simétrico.
- Banner del header: `object-fit:cover` para no estirarse al cambiar ancho. Cuerpo `flex` + `overflow:auto` → las zonas se re-fluyen al pixel.

## No deformar el contenido

El cuerpo del panel ya es flex con zonas (controles / journey / movimientos). Al redimensionar se cambia width/height de la ventana (nunca `transform:scale`); el contenido se re-acomoda y, si no cabe, scrollea (`overflow:auto`). Min-size garantiza que las zonas no se aplasten.

## Archivos a tocar

| Archivo | Cambio |
|---|---|
| `static/depos_window.js` | NUEVO — drag + resize + dock + persistencia (lógica pura + wiring) |
| `static/depos.js` | titlebar + init de la ventana + cablear controles + click-fuera no cierra |
| `static/depos.css` | titlebar/controles, estados float/dock, divisor, transiciones; quitar overlay bloqueante |
| `static/index.html` | wrapper `#accDockZone`, titlebar, `<script>`, bump cache |
| `static/style.css` | `#accDockZone` compresión animada por lado |
| `static/depos_window.test.js` | NUEVO — tests node de la geometría pura |
| `docs/FRONTEND.md` | bitácora: sección ventana manipulable |

## Verificación

- **Geometría pura**: tests node (`node depos_window.test.js`) — clamp, resizeRect (min/max, viewport), dockRect, dockWidthFromPointer, snapZone.
- **Sintaxis**: `node --check` de los .js.
- **Deploy**: md5 íntegro en container + cache-bust servido + health 200.
- **Runtime**: lo prueba Robert (drag/resize/dock son interactivos). Reporta detalles para afinar.

## Fuera de scope (YAGNI)

Maximizar, minimizar a chip, dock con split entre múltiples ventanas, sidebar izq redimensionable por su cuenta (Robert lo descartó: solo el divisor del dock).

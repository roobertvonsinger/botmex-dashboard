# Tanda 6 — "La Pantalla": superficie ámbar de proyección premium

> Fecha: 2026-07-02 · Repo: botmex-dashboard · Vista: Cuentas
> Lente rectora: **frictionless** + **premium real** (medido, no a ojo — ver `feedback_verificar_entry_real`).
> Reemplaza el enfoque previo de "detalle dentro del KPI" (`2026-07-02-tanda6-strip-detalle-feed-pool.md`, sección Bloque 1). El feed estructurado + pool/fijadas quedan como fases posteriores; esta tanda entrega **La Pantalla**.

## Visión (palabras de Robert)

Una superficie que se **materializa AL FRENTE de los KPIs**, cubriéndolos casi por completo, como si se desplegara una manta y un **proyector láser ultra-HD** escribiera en ella. El texto y los detalles se **componen de sustancia líquida dorada/ámbar translúcida** que forma patrones — el mismo lenguaje visual de las animaciones del panel de depósitos (blobs de mercurio, `goo` filter, trazos que se dibujan). Se materializa de la forma **más suave y agradable** posible, con microanimaciones detalladas, integrada a la UI.

**La Pantalla es la superficie ÚNICA de feedback de la interacción del usuario con una cuenta.** No es de sólo lectura: ahí el usuario ve los **detalles**, ejecuta y observa **cambios**, y sigue el **proceso de depósito en tiempo real** — todo en el mismo lugar. Debe ser **fácil e intuitivo para un usuario con TDAH**: visualización, control y feedback en vivo unificados, sin saltar entre superficies.

Se llama **"La Pantalla"**. Es una superficie reutilizable:
- **Ahora (fase 1):** visualiza el **detalle completo** de una cuenta al hacer **click derecho** en cualquier registro de la tabla, **conservando todos los controles** que hoy tiene el panel de detalle (no sólo mirar — actuar).
- **Después (fase 2):** las **animaciones del panel de depósitos migran aquí** — el drawer conserva los controles de configuración, pero el "viaje" del depósito se proyecta en La Pantalla en vivo (uso casi universal).
- **Futuro:** el usuario podrá manipularla (mover/anclar/redimensionar). Fuera de alcance de esta tanda.

## Controles preservados (La Pantalla es interactiva)

Inventario del panel de detalle actual (`renderDetail`, `app.js:3930`). **Todos** deben vivir en La Pantalla, re-maquetados premium pero funcionalmente intactos (mismos `data-*` / handlers, para no reescribir la lógica):

| Control | Selector/handler actual | Qué hace |
|---------|------------------------|----------|
| **Depositar** | `.d-deposit-btn[data-acc-id]` | Lanza el flujo de depósito para esa cuenta |
| **En uso / Lock** | `.inuse[data-inuse]` | Toggle lock 2h |
| **📌 Fijar** | `.det-mark[data-mark-email]` | Marcar/desmarcar (bandeja de fijadas) |
| **CURP validar** | `.curp-validate-btn[data-acc-id]` | Abre modal gob.mx para validar/corregir |
| **Copiar** | `.d-copy[data-copy]` | Combo, tarjetas, CURP → portapapeles |
| **Movimientos** | `.mv-pg[data-mv-pg]`, `[data-mv-toggle]` | Paginar (10/pág) + expandir cápsula |
| **Agregar tarjeta** | `.addbtn[data-add-card]` | Form inline para nueva tarjeta |
| **Agregar nota** | `.addbtn[data-add-note]` | Form inline para nueva nota |
| **Borrar nota** (SA) | `.srow-del[data-note-id]` | Elimina nota |

**Feedback en tiempo real:** al pulsar **Depositar** desde La Pantalla, el proceso se muestra en la **misma superficie** (transición a `mode=scene`, las escenas líquidas del viaje), y al terminar vuelve al detalle actualizado (saldo/movimientos refrescados por SSE). El usuario no cambia de superficie: mira → actúa → ve el resultado, en un solo lienzo. Esto es la razón de unificar detalle + escenas en La Pantalla.

## Vocabulario visual existente a heredar

Panel de depósitos v8 (`#depos`, `static/depos.js` + `static/depos.css`), sección `.journey`/`.scene-stage`:
- 5 escenas SVG (`#scene-login`, `-form`, `-processing`, `-retry`, `-done`) conmutadas por `setScene(k)` (`depos.js:229`).
- Filtros `goo` (feGaussianBlur + feColorMatrix) = efecto mercurio/líquido; trazos `stroke-dashoffset` que se "dibujan"; halos que respiran; gradientes radiales.
- Paleta actual: **verde** (`#00bd72`). La Pantalla usa **ámbar/dorado** translúcido (`--gold` ya existe en el tema; ámbar `oklch(~0.8 0.13 75)`).
- Crossfade entre escenas: `.scene.on { opacity:1; filter:blur(0) saturate(1); transform:scale(1) }` con transición suave.

La Pantalla reutiliza este sistema (mismo `setScene`, mismos SVG) pero:
1. Vive en un contenedor propio al frente de los KPIs (no dentro del drawer).
2. Añade un **modo "detalle"** además del modo "escena/depósito".
3. Recolorea a ámbar (variables CSS, no duplicar SVGs si se puede tintar por `filter`/`currentColor`).

---

## Arquitectura

### Contenedor
`#pantalla` — overlay `position:absolute` (o `fixed` acotado) montado sobre la zona del strip `.lpanel`, cubriendo casi los 3 KPIs. `z-index` por encima del strip, por debajo de modales globales (toasts, depósito drawer). Backdrop con `backdrop-filter: blur()` para difuminar los KPIs detrás → sensación de "manta translúcida".

Estados:
- **Oculto** (default): no ocupa, no intercepta clicks.
- **Materializándose** (`.pantalla-in`): animación de despliegue (ver Microanimaciones).
- **Visible** (`.pantalla-on`): interactiva.
- **Replegándose** (`.pantalla-out`): animación inversa, luego oculto.

### Modos de contenido (un solo lienzo, varios contenidos)
- `data-mode="detail"` — detalle completo de una cuenta (fase 1).
- `data-mode="scene"` — proyección del viaje de depósito (fase 2).
- `data-mode="txn"` — sub-vista: detalle de UNA transacción (fase 1, al clickar una transacción del detalle).

### Disparadores
- **Click derecho** (`contextmenu`) sobre cualquier `tr[data-id]` de `#accTable` → `preventDefault()` (no menú nativo) → abre La Pantalla en `mode=detail` con esa cuenta. (Fase 1.)
- Durante un depósito (fase 2) → La Pantalla se materializa en `mode=scene` y `setScene` la maneja; el drawer queda con controles.
- **Cierre:** `Esc`, click en el backdrop fuera del lienzo, o botón `×` discreto. Repliegue suave.

---

## Fase 1 — Modo detalle (entregable de esta tanda)

### Datos
Reutiliza `GET /api/accounts/{id}/details` (ya alimenta `renderDetail`). Sin cambios de backend. `openAccountByEmail`/`openDetailModal` se adaptan para pintar en La Pantalla en vez de la fila inline.

### Layout del detalle (premium, re-maquetado — NO copiar el modal actual)
Compuesto sobre la superficie ámbar, con jerarquía clara:

- **Cabecera:** nombre + combo `email:password` (copiable), saldo grande, grade chip, ubicación (estado). CURP/nacimiento/dirección completa disponibles pero secundarios (tenues, no dominan).
- **Transacciones separadas en DOS CATEGORÍAS** (punto explícito de Robert):
  1. **Directas en BetMexico** — movimientos con `source != 'dashboard'` (depósitos/retiros SPEI que la cuenta hizo por su cuenta en BetMexico).
  2. **Del dashboard Botmexico** — movimientos con `source === 'dashboard'` (los que corrimos nosotros; llevan tarjeta, quién, resultado).
  Dos zonas visualmente divididas (tabs, columnas, o secciones apiladas — ver Decisiones), cada una con su lista de transacciones.
- **Click en una transacción** → `mode=txn`: la misma Pantalla transiciona (no abre otra ventana) a la vista de detalle de esa transacción: monto, fecha, estado, tarjeta (si es nuestra), razón, quién, txn_id. Un "volver" regresa a `mode=detail` con transición suave.

### 3DS deja de ser "algo malo" (punto explícito de Robert)
Hoy el 3DS se pinta como cuasi-rechazo: `mv-threeds` en ámbar-warn, y en la tabla de actividad hay columna "3DS" con connotación de fallo. Robert: el 3DS **próximamente será la señal para migrar el grading a "detección por 3DS"** — es información valiosa, no un fracaso.

Cambios (visuales/semánticos, fase 1):
- En La Pantalla, el 3DS se presenta como **estado informativo dorado/neutro** (no rojo, no tachado, no en la cubeta de "rechazado"). Etiqueta tipo "Verificación 3DS" con ícono de escudo, tono ámbar positivo.
- Separarlo claramente de "rechazado (banco)": una transacción 3DS NO es un rechazo del banco; es un challenge de verificación.
- **Gancho documentado (no implementado):** dejar comentario/estructura para que el grading V10 futuro consuma el 3DS como señal. El analyzer (`shared/betmexico_payment_analyzer.py`) hoy no modela 3DS; se anota en `docs/` que es trabajo futuro. NO se toca el algoritmo en esta tanda.

### Microanimaciones (el corazón premium)
Objetivo: "la forma más suave y agradable", sin brincos ni cortes. Sugerencia de composición (afinar en implementación con `frontend-design`):

1. **Despliegue de la manta:** la superficie ámbar crece desde una línea/semilla (arriba-centro) hacia sus bordes con `clip-path` o `scaleY` + blur→focus. Simultáneo: backdrop-blur de los KPIs sube de 0 a full. ~320–420ms, `cubic-bezier` suave.
2. **Encendido del proyector:** un barrido de luz (scanline sutil) recorre la superficie una vez al materializarse; grano/shimmer ámbar muy tenue de fondo (reutiliza `pecera` keyframe idea).
3. **Escritura líquida del texto:** los bloques de texto/números NO aparecen de golpe — se "escriben" con un reveal por `clip-path`/mask que avanza, acompañado del `goo` para que los caracteres parezcan cuajar de gotas de mercurio dorado. Escalonado (stagger) por sección para que fluya.
4. **Transición entre modos** (detail↔txn): crossfade + slide corto sobre el mismo lienzo, nunca un salto duro.
5. **Repliegue:** inversa del despliegue, un poco más rápido (~240ms).
6. `prefers-reduced-motion` → sin escritura líquida ni scanline; fade simple.

---

## Fase 2 — Migración de las escenas de depósito (siguiente, dentro de esta tanda si alcanza)

**El depósito se sigue LANZANDO desde el panel de depósitos** (drawer `#depos`): ahí se configuran cuentas, tarjetas, monto, reps y se pulsa Depositar. Lo que cambia:

- **Se le QUITA la pantallita al drawer:** eliminar `.journey` + `.scene-stage` (el bloque de animación SVG) de `#depos`. El drawer queda sólo con controles + resultado textual mínimo. Robert: "le quitarás la pantallita al panel de depósitos porque será suplida por esta pantalla".
- **Recompactar y reorganizar el drawer con criterio real:** al quitar la pantallita queda un hueco. Reorganizar visualmente los controles (cuentas, tarjetas, monto, reps, botones) para que el drawer se vea equilibrado y compacto SIN la animación — nada de dejar el vacío. Criterio medido, no a ojo (`getBoundingClientRect`, ver `feedback_verificar_entry_real`): compactar/reacomodar al pixel, no eliminar lo que Robert valora (`feedback_no_quitar_compactar`). Verificar contra `/static/index.html` real, no un harness.
- **Las escenas se proyectan en La Pantalla:** extraer el sistema de escenas (`setScene`, los 5 SVG, `mapPhaseToScene`) a un módulo reutilizable que pinta en La Pantalla (`mode=scene`). Al lanzar un depósito, La Pantalla se materializa y muestra el viaje en vivo.
- La Pantalla abarca **más casos de uso** que la vieja pantallita del drawer: no sólo el viaje de depósito, también el detalle de cuenta (fase 1) y lo que venga.
- Recolorear las 5 escenas a ámbar en La Pantalla (o mantener verde para "éxito/dinero" y ámbar para el marco — decidir en implementación).
- SSE sigue igual; sólo cambia el destino del render (drawer → Pantalla).
- El botón **Depositar** de La Pantalla (fase 1) abre el mismo flujo del drawer para esa cuenta; el viaje se ve en La Pantalla. No se duplica lógica de depósito.

---

## Carril de resultados en vivo (solo SA) — monitoreo sin cambiar de vista

**Problema real:** el SA hoy se va a la vista de Logs a monitorear los depósitos. Descartada la opción de "regresar el render a la pantallita del drawer" (reintroduce lo que quitamos + dos destinos de render frágiles).

**Solución:** La Pantalla queda **integrada a la vista principal (Cuentas)** e incluye, **solo en la vista de superadmin (Robert)**, un **carril de resultados en vivo** — feedback curado que trae el monitoreo a la vista principal, haciendo innecesario irse a la vista de Logs. Como el SA ya no cambia de vista para monitorear, **no se requiere ningún mecanismo de continuidad entre vistas** (nada que "lo siga").

- **Qué muestra:** puros hitos, no el log crudo — `login ✓`, `depósito en proceso ⏳`, `completado ✓`, `rechazado`, `3DS`. Con datos técnicos mínimos (email corto, monto, tarjeta •4 últimos, latencia ms) pero **sin el revolvedero** de la vista grande de logs.
- **Formato:** cada acción destacada por **color** según tipo (verde éxito · rojo rechazo banco · **dorado 3DS** · ámbar en-proceso), con formato tabular limpio.
- **Microanimaciones:** entrada de cada línea con cuajado líquido (slide+fade+goo), fluida, **sin saturar** — señal, no ruido. Efímero (las líneas viejas se atenúan/salen).
- **Rol:** exclusivo SA (`project_visibilidad_roles`: el SA ve todo trazable en tiempo real; invisible a operadores). Los operadores ven La Pantalla con detalle + escenas, sin este carril técnico.
- **Diferencia con la vista Actividad:** Actividad = histórico navegable con todo el texto; este carril = tiempo real, curado, efímero, visual.
- **Integrada a la vista principal:** La Pantalla y su carril viven en la vista Cuentas. No hay seguimiento entre vistas — el monitoreo sucede aquí. El `depMissionPill` existente se conserva tal cual (no se toca), pero no es parte de este diseño.

## Archivos a tocar

- `static/index.html` — markup de `#pantalla` (contenedor + backdrop + lienzo + zonas de modo).
- `static/app.js` — listener `contextmenu` en filas, `openPantalla(id, mode)`, render del detalle premium (2 categorías de txn), sub-vista txn, cierre; adaptar `openDetailModal`.
- `static/pantalla.css` (nuevo) o sección en `style.css` — superficie ámbar, backdrop, microanimaciones, escritura líquida, layout del detalle.
- `static/pantalla.js` (nuevo, opcional) — orquestación de La Pantalla + reutilización de `setScene` para fase 2.
- Reutiliza SVG/filtros de `depos.css`/`index.html` (goo, glow, draw).
- `docs/` — anotar el gancho "3DS como señal de grading" (futuro) y actualizar bitácora.

## Decisiones

- **Disparo = click DERECHO** (no izquierdo). El click izquierdo en fila conserva su comportamiento actual (selección/abrir). `contextmenu` con `preventDefault`. (Confirmar: ¿algún registro donde el menú nativo se necesite? No en la tabla de cuentas.)
- **Dos categorías de txn:** apiladas en dos secciones con encabezado propio ("⚡ Botmexico" / "🌐 BetMexico") por default (más legible que tabs en superficie ancha). Ajustable a tabs si Robert lo prefiere.
- **Cobertura:** La Pantalla cubre "casi todo" el strip pero deja un respiro (margen) para que se sienta superpuesta, no pegada. No cubre la tabla ni la topbar.
- **Reutilización de escenas:** una sola superficie con modos; NO dos componentes separados. El detalle y las escenas comparten el marco ámbar y las microanimaciones de materialización.
- **3DS:** sólo cambio visual/semántico en fase 1 (dejar de tratarlo como rechazo). El grading real por 3DS es trabajo futuro documentado, fuera de alcance.

## Criterios de aceptación (fase 1)

1. Click derecho en cualquier fila de la tabla → La Pantalla se materializa al frente de los KPIs con el detalle de esa cuenta; no aparece menú nativo del navegador.
2. La superficie es ámbar/dorada translúcida, cubre casi los 3 KPIs, con backdrop difuminado detrás.
3. La materialización es suave (despliegue + escritura líquida del texto), sin brincos ni cortes; el repliegue también.
4. El detalle muestra cabecera (nombre/combo/saldo/grade/estado) y las transacciones **separadas en 2 categorías** (Botmexico vs BetMexico directas).
5. Click en una transacción → la misma Pantalla muestra el detalle de esa transacción; "volver" regresa al detalle de cuenta, con transición suave.
6. El 3DS se presenta como estado informativo dorado, **no** como rechazo (ni rojo ni tachado ni agrupado con "rechazado banco").
7. **La Pantalla es interactiva:** los 9 controles del inventario (Depositar, Lock, Fijar, validar CURP, copiar, paginar/expandir movimientos, agregar tarjeta, agregar nota, borrar nota) funcionan desde ahí.
8. Pulsar **Depositar** en La Pantalla muestra el proceso en vivo en la **misma** superficie y al terminar vuelve al detalle actualizado, sin cambiar de superficie.
9. `Esc` / click fuera / `×` repliega La Pantalla suavemente.
10. `prefers-reduced-motion` degrada a fade simple sin efectos de líquido/scanline.
11. **(Fase 2)** El depósito se sigue lanzando desde el drawer `#depos`; a éste se le **elimina** `.journey`/`.scene-stage` y se **recompacta** con criterio medido; el viaje se proyecta en La Pantalla.
12. **(Fase 2, solo SA)** La Pantalla, integrada a la vista principal, muestra un carril de resultados en vivo (hitos curados por color + microanimación, sin saturar) que hace innecesario ir a la vista de Logs. Sin mecanismo de continuidad entre vistas.
13. La fase 1 no rompe el drawer de depósitos ni el panel de detalle inline existentes hasta que se migre (fase 2).

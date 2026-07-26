# Botmexico Design System — Obsidian Refined

> Referencia canónica del sistema de diseño del dashboard.
> Cargado por Claude Desktop para mantener coherencia visual al hacer cambios.
> Fuente de verdad: `static/style.css`, `static/depos.css`, `static/pantalla.css`.

---

## 1. Identidad Visual

**Tema:** Obsidian Refined — superficies oscuras de vidrio esmerilado con acento neon verde.

**Personalidad:**
- Premium sin ser caro. Casino sin ser vulgar.
- Color ESPARSO: verde solo en acento/acción, ámbar en dinero/avisos, rojo solo en peligro.
- Glass morphism en todas las superficies elevadas (backdrop-filter blur).
- Textura de grano sutil (fractal noise SVG, overlay) en paneles grandes.
- Neón multi-capa en CTAs primarios (3 intensidades de glow).
- El dashboard debe GANARLE a BetMexico en fluidez — la UI invita a transaccionar, no a mirar.

---

## 2. Design Tokens

### 2.1 Color — Fondo

| Token | Valor | Uso |
|-------|-------|-----|
| `--bg` | `#08090c` | Fondo base (near-black obsidian) |
| `--bg-accent` | `radial-gradient(...) + #08090c` | Fondo con glow verde sutil (12% -8%) |
| `--surface` | `rgba(18,20,24,0.60)` | Superficies con blur |
| `--surface-solid` | `#101216` | Superficies opacas (thead, pagebar) |
| `--surface-elev` | `rgba(24,27,32,0.78)` | Modales, drawers, toasts |

### 2.2 Color — Texto (WCAG AA verificado sobre #08090c)

| Token | Valor | Ratio | Uso |
|-------|-------|-------|-----|
| `--text` | `#eef0f3` | 15.3:1 | Texto primario |
| `--text-dim` | `rgba(238,240,243,0.72)` | 7.8:1 | Texto secundario |
| `--text-muted` | `rgba(238,240,243,0.52)` | 4.5:1 | Labels, timestamps |
| `--text-faint` | `rgba(238,240,243,0.28)` | 2.4:1 | Decorativo SOLO |
| `--hairline` | `rgba(255,255,255,0.12)` | 3.2:1 | Bordes, separadores |
| `--hairline-h` | `rgba(255,255,255,0.20)` | 4.1:1 | Bordes hover/foco |

### 2.3 Color — Acento (verde teal, hue 160)

```css
--accent:      oklch(0.50 0.11 160);       /* base */
--accent-mid:  oklch(0.40 0.10 160);       /* gradiente botón */
--accent-deep: oklch(0.30 0.09 160);       /* profundidad */
--accent-soft: oklch(0.50 0.11 160 / 0.14);  /* fondo sutil */
--accent-soft-2: oklch(0.50 0.11 160 / 0.26); /* fondo activo */
--accent-glow: oklch(0.60 0.13 160 / 0.40);   /* halo neón */
```

**Neón multi-capa** (3 intensidades, "tubo de gas"):
```css
--neon-sm: 0 0 4px oklch(0.68 0.14 160 / 0.65), 0 0 10px oklch(0.58 0.13 160 / 0.32);
--neon-md: 0 0 6px ..., 0 0 14px ..., 0 0 24px ...;
--neon-lg: 0 0 8px ..., 0 0 18px ..., 0 0 36px ...;
```

### 2.4 Color — Semántico

| Token | Valor | Semántica |
|-------|-------|-----------|
| `--danger` | `oklch(0.66 0.21 24)` | Error, acción destructiva |
| `--danger-soft` | `oklch(0.66 0.21 24 / 0.12)` | Fondo peligro |
| `--warn` | `oklch(0.80 0.16 75)` | Aviso, 3DS, cooldown |
| `--warn-soft` | `oklch(0.80 0.16 75 / 0.12)` | Fondo aviso |
| `--gold` | `oklch(0.82 0.14 85)` | Dinero, saldo, retiros |
| `--gold-soft` | `oklch(0.82 0.14 85 / 0.14)` | Fondo dinero |
| `--purple` | `oklch(0.74 0.17 295)` | Locks, cooldowns, operadores |

### 2.5 Color — Grados (salud de cuenta)

Cada grado tiene: `grade-bar-cell` (barra fila), `grade` (pill badge), `grade-dot` (punto), `r-grade-X` (wash fila), `modal.grade-X` (aura modal), `data-grade` (La Pantalla).

| Grado | Color | Hue | Uso |
|-------|-------|-----|-----|
| A+ | `oklch(0.75 0.20 152)` | 152 | Premium, glow fuerte |
| A | `oklch(0.58 0.13 160)` | 160 | Saludable (base) |
| B | `oklch(0.70 0.16 235)` | 235 | Azul grisáceo, OK |
| C | `oklch(0.80 0.16 75)` | 75 | Ámbar, advertencia |
| D | `oklch(0.66 0.21 24)` | 24 | Rojo, peligro |
| U | `rgba(255,255,255,0.14)` | — | Sin grado, neutro |

### 2.6 Color — Operadores

| Token | Color | Uso |
|-------|-------|-----|
| `--op-warn` | `oklch(0.80 0.16 75)` | Operador ámbar |
| `--op-purple` | `oklch(0.74 0.17 295)` | Operador púrpura |
| `--op-accent` | `oklch(0.58 0.13 160)` | Operador verde |
| `--op-azure` | `oklch(0.62 0.16 250)` | Operador azul |

### 2.7 Tipografía

| Token | Familia | Uso |
|-------|---------|-----|
| `--font` | `'Inter', system-ui, sans-serif` | Body text |
| `--font-display` | `'Space Grotesk', 'Inter', sans-serif` | Headings, labels, nav |
| `--font-mono` | `'JetBrains Mono', ui-monospace, monospace` | Data, codes, timestamps |

**Fuentes contextuales** (cargadas por CDN, uso limitado):
- **Satoshi** (Fontshare): paneles de detalle inline (`.acc-detail`), modal depósitos
- **Clash Display** (Fontshare): CTAs de depósito, balance del journey
- **Ranchers**: greeting folklor del personaje (speech bubble)
- **Phosphor Icons** v2.1.1: duotone/bold/fill — iconografía en La Pantalla y depósitos

**Escala tipográfica:**
```css
--fs-9: 9px    --fs-10: 10px   --fs-11: 11px   --fs-12: 12px
--fs-13: 13px  --fs-14: 14px   --fs-16: 16px   --fs-18: 18px
--fs-22: 22px  --fs-28: 28px
```
Body base: 13px. Rendering: `-webkit-font-smoothing: antialiased`.

### 2.8 Espaciado (base 4px)

```css
--space-1: 4px   --space-2: 8px    --space-3: 12px   --space-4: 16px
--space-5: 20px  --space-6: 24px   --space-8: 32px   --space-10: 40px
```

### 2.9 Radio

```css
--radius-sm: 4px    /* botones pequeños, checkboxes */
--radius-md: 8px    /* cards, inputs, nav items */
--radius-lg: 12px   /* modales, drawers */
--radius-xl: 16px   /* pantallas grandes */
--radius-full: 999px /* pills, badges, chips */
```

### 2.10 Elevación

```css
--shadow-sm: 0 1px 2px rgba(0,0,0,0.3)
--shadow-md: 0 4px 12px rgba(0,0,0,0.4)
--shadow-lg: 0 12px 32px rgba(0,0,0,0.5)
--shadow-xl: 0 24px 64px rgba(0,0,0,0.6)
```

### 2.11 Z-Index

```css
--z-dropdown: 100     /* nav dropdowns, drawer */
--z-sticky: 200       /* sticky headers */
--z-modal-backdrop: 300
--z-modal: 400
--z-toast: 500
--z-coachmark: 10000
```

### 2.12 Easing / Motion

```css
--ease-fast: 0.18s cubic-bezier(0.4, 0, 0.2, 1)       /* micro-interacciones */
--ease: 0.42s cubic-bezier(0.22, 0.61, 0.36, 1)        /* transiciones generales */
--ease-curve: cubic-bezier(0.22, 0.61, 0.36, 1)         /* en keyframes */
--ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1)        /* rebote sutil */
```

**Regla de motion:** TODO interaction usa `--ease-fast` (180ms). Transiciones de estado usan `--ease` (420ms). El spring solo aparece en elementos que "saltan" al agarrar (gutter, sel-dot, coachmarks).

### 2.13 Layout

```css
--sidebar-w: 216px    /* sidebar expanded */
--topbar-h: 56px      /* mobile topbar */
--cenefa-h: 30px      /* brand bar superior */
--blur: 7px           /* backdrop-filter base */
--lp-gw: 7px          /* gutter divisor de strip */
```

---

## 3. Componentes

### 3.1 Estructura de Layout

```
┌─ .cenefa (30px, brand bar) ─────────────────────────────────┐
├─ .shell ────────────────────────────────────────────────────┤
│  ├─ .sidebar (216px / 64px rail)                           │
│  └─ .main                                                  │
│     ├─ .topbar (0px default, 56px mobile)                  │
│     ├─ .lpanel (KPI strip, 212px fixed)                    │
│     │  ├─ .lp-card (logs/actividad)                        │
│     │  ├─ .lp-gutter (divisor arrastrable)                 │
│     │  └─ .lp-card (cuentas a la mano)                     │
│     ├─ .pantalla (La Pantalla overlay, absolute)           │
│     ├─ #patStageSlot (escenario depósito)                  │
│     ├─ .filterbar                                          │
│     ├─ .tablewrap ─── table#accTable                       │
│     └─ .pagebar (paginador + acciones fusionadas)          │
└─ .dep-drawer (420px, slide-in derecho, opcional)           │
```

### 3.2 Sidebar

- **Expandido:** 216px, texto + iconos, grupos colapsables
- **Rail (colapsado):** 64px, solo iconos, tooltips
- **Toggle:** `.sb-collapse` — botón circular flotante en borde derecho
- **Elementos:** brand logo, greeting, tristrip (verde/blanco/rojo), nav items, online block, status block, user block
- **Nav items:** icono + texto + badge; estado `.on` = barra accent izquierda + fondo gradient
- **Grupos:** `.sb-group-header` colapsable con chevron, persiste en localStorage
- **Mobile:** drawer fijo desde izquierda, hamburger visible, backdrop overlay

### 3.3 Tabla de Cuentas

- **Compacta:** filas 30px, headers sticky
- **Columnas:** grade-bar (3px) | selección (dot) | saldo (100px mono) | combo (flex) | último depósito | check | acciones (nota/tarjetas/pin)
- **Grade bar:** color sólido por grade con glow, wash gradient que se desvanece a la derecha
- **Selección:** dot accent (no checkbox), Ctrl/Shift+Click tipo Excel, drag-select con marquee
- **Fila glow:** `.pantalla-source` — la cuenta en vista de detalles brilla con borde accent
- **Filas:** `border-bottom: 1px solid var(--hairline)`, hover `rgba(255,255,255,0.025)`
- **Locked:** borde púrpura + lock-chip del operador

### 3.4 KPI Strip (L Invertida)

- **Grid:** 2 cards + 1 gutter arrastrable
- **Cards:** glass morphism (backdrop blur + hairline border + radius 8px)
- **Módulos:** logs/actividad (feed vertical) | cuentas a la mano (alertas/recientes)
- **Gutter:** barra 3px que se ilumina verde al hover/drag, "engorda" al jalar
- **Reorden:** grip dots, drag para swap de módulos
- **Alto fijo:** 212px, sin collapse/drag vertical

### 3.5 La Pantalla (Detail Overlay)

- **Material:** vidrio oscuro templateado — backdrop blur 34px, grano esmerilado, scanline láser
- **Animación entrada:** clip-path inset expanding (semilla arriba-centro → full) + blur fade, 380ms
- **Escritura líquida:** contenido "cuaja" de gotas borrosas — stagger por bloque (62ms step), blur→nítido
- **Layout 3 columnas:** identidad (max-content) | movimientos (flex:1.35) | escenario (flex:1)
- **Grade-color:** tinte de vidrio rota hue según grade (A+/A/B/C/D/U), NO el fondo. Tokens locales (scoped a `.pantalla-sheet`, reescritos por `[data-grade]`):
  ```css
  --pat-gold:      oklch(0.80 0.085 160);   /* default = A; ver pantalla.css para B/C/D/U */
  --pat-gold-soft: oklch(0.80 0.085 160 / 0.14);
  --pat-edge:      oklch(0.80 0.085 160 / 0.28);
  --pat-edge-h:    oklch(0.80 0.085 160 / 0.45);
  ```
- **Columna identidad:** combo copiable (15px mono nacarado) + saldo (26px display dorado) + guardado (tarjetas/notas/clabes)
- **Columna movimientos:** filas compactas con borde lateral de color por resultado (verde/rojo/ámbar/tenue)
- **Columna escenario (en reposo):** apila 2 paneles compactos dorados uno debajo del otro — retiro (`.pat-wd-stage`, solo SA, gateado por `_withdrawBtnState(d, role)`) arriba, depósito (`.pat-dep-stage`, todos los roles) abajo separado por hairline (`border-top: 1px solid var(--pat-edge)`). Mismo lenguaje visual dorado que el resto de La Pantalla, NO el look verde del panel de depósitos viejo (`depos.css`) — el compacto reusa el motor JS (`Depos.mountCompact`, monta `#deposCompactTpl` en `#patDepSlot`) pero re-skinnea `chip`/`chip-x`/`amt-preset` scoped a `.pat-dep-stage` sin tocar `depos.css`.
- **Columna escenario (misión activa):** deposit.js re-parenta aquí el bloque de escenas (`#depStage`, montado en `#patStageSlot`). Coexistencia por CSS puro: `.pat-col-stage:has(#depStage:not([hidden])) .pat-wd-stage, .pat-col-stage:has(#depStage:not([hidden])) .pat-dep-stage { display: none; }` — depos.js queda intacto, la prioridad visual la resuelve el `:has()`.
- **CTA deshabilitado durante misión:** `.pat-act-dep:disabled` / `.pat-act-wd:disabled` — `opacity:.4`, `cursor:not-allowed`, fondo `var(--pat-edge)`, color `var(--text-dim)`, sin glow ni transform en hover. Evita doble-disparo de depósito/retiro mientras ya corre una misión.
- **Ancho medio "cramped":** cuando las 3 columnas no caben lado a lado (`.pat-col-ident` max-content + `.pat-col-txns` min 340px + `.pat-col-stage` min 380px superan el ancho disponible), `pantalla.js` (`_syncColumnsFit`) mide `scrollWidth` real de `.pat-columns` vs su `clientWidth` — NO un breakpoint px inventado — y marca `.pat-cramped`: las columnas se apilan verticalmente con scroll. A diferencia de mobile (≤767px), el escenario NO se oculta, solo cambia de eje.
- **Responsive:** mobile ≤767px apila a 1 columna, oculta escenario, botones 44px touch target

### 3.6 Panel de Depósitos

- **Dual mode:** panel acoplado (dock right, 420px) O modal flotante
- **Vidrio:** backdrop blur 26px, noise overlay, borde izquierdo accent line
- **Header:** banner personaje + greeting speech bubble (Ranchers font) + "Nuevo depósito"
- **Controles:** cuentas (chips mono) + tarjetas (chips lockeados) + monto (input mono) + repeticiones (7-segment display SVG)
- **CTA:** Clash Display bold, gradiente accent, sheen animation al hover
- **Journey/scenes:** SVG animado (login→form→processing→retry→done), re-parentado a La Pantalla en col 3
- **Bitácora:** movimientos en vivo, filas con dot de color por estado
- **Variante compacta (La Pantalla, col 3):** `.pat-dep-stage` — mismo motor JS (`Depos.mountCompact`/`#deposCompactTpl`), controles reducidos (chips cuenta/tarjetas, presets de monto, repeticiones `.pat-dep-reps`, botón "nuevo proceso" `.pat-dep-newproc`) re-skinneados en dorado (`--pat-gold`) en vez del verde del panel dock/modal. Ver 3.5.

### 3.7 Modal

- **Base:** 460px, backdrop blur, grade-colored aura (box-shadow)
- **Estructura:** head (título + close) | body | footer
- **Grid detalle:** 280px col1 (datos) | 1fr col2 (tarjetas + transacciones) | span full (notas)
- **Grade aura:** sombra lateral del color del grado (A=verde, B=azul, C=ámbar, D=rojo)
- **Mobile:** full-screen sin border-radius

### 3.8 Drawer (Depósitos lateral)

- **Width:** 420px fijo, slide-in desde derecha, 260ms
- **No bloqueante:** el dashboard sigue interactuable detrás
- **Body push:** `body.dep-drawer-pushing { padding-right: 420px }`
- **Collapsable:** rail de 36px con botón expand
- **Tabs:** segmented control con estado `.on` (neon glow)
- **Footer:** botón CTA full-width

### 3.9 Botones

| Clase | Variante | Estilo |
|-------|----------|--------|
| `.seg-btn` | Ghost | Hairline border, mono font, hover lift |
| `.act` | Compacto | 26px, inline-flex, inset highlight |
| `.act-primary` | Primario | Gradiente accent, neón glow, bold |
| `.act-ghost` | Ghost | Transparente, solo texto muted |
| `.dep-exec` | CTA Depósito | Full-width, gradiente, sheen sweep |
| `.ico-btn` | Icono | 24px, round 6px |
| `.nav` | Sidebar | Accent bar on active, translateX hover |
| `.pat-act` | La Pantalla | 26px, borde hairline, accent on hover |
| `.pat-act-dep` | Depósito CTA | Relleno `var(--pat-gold)` (tinte por grado) + glow permanente. `:disabled` durante misión activa |
| `.pat-act-wd` | Retiro CTA (SA) | Relleno `var(--pat-gold)`, mismo lenguaje que `.pat-act-dep`. `:disabled` durante misión o si retiro no procede (`_withdrawBtnState`) |

**Regla:** TODO botón tiene `transition: var(--ease-fast)` en background, color, border-color, box-shadow, transform.
**Estado disabled (misión en curso):** `.pat-act-dep:disabled` / `.pat-act-wd:disabled` — `opacity:.4`, `cursor:not-allowed`, fondo `var(--pat-edge)`, color `var(--text-dim)`, `box-shadow:none`; hover no hace nada (`filter:none`/sin `transform`).

### 3.10 Inputs

- **Base:** fondo `rgba(0,0,0,0.35)`, borde `var(--hairline)`, radius 8px
- **Focus:** borde accent + ring `0 0 0 3px var(--accent-soft)`
- **Mono variant:** `.dep-input` con `font-family: var(--font-mono)`
- **Monto:** display grande mono, $ prefix, presets en grid

### 3.11 Chips / Badges

- **Chip:** pill 999px, borde, mono font, `.copyable` para copiar
- **Grade badge:** 22x22 square, color de grade, glow, font-display bold
- **Lock chip:** inline pill con color de operador, borde `currentColor`
- **JWT chip:** emoji indicator (🟢/🔑/⛔/⏳)
- **Badge count:** pill 999px, fondo accent-soft, mono bold

### 3.12 Toast

- **Posición:** fixed bottom-center, z-index 100
- **Estilo:** surface-elev + backdrop blur + hairline-h border
- **Variantes:** default, `.success` (accent border + glow), `.error` (danger border)
- **Animación:** slide up + fade, 200ms

### 3.13 Coachmarks (admin)

- **Estilo:** glass surface verde-oscuro, borde accent, pulse glow
- **Flecha:** triángulo CSS en 4 direcciones
- **Entrada:** slide + blur + spring bounce, 380ms
- **Target glow:** outline pulsante verde en el elemento referenciado
- **Dismiss:** "no mostrar de nuevo" con checkbox

### 3.14 Log Viewer (vista Logs)

Parseo estructurado de líneas de log crudo (`app.js`, formato `YYYY-MM-DD HH:MM:SS,ms [LEVEL] [logger] mensaje`) en componentes con color por severidad, en vez de texto plano monocromático.

- **`.log-line`:** contenedor por línea, `display:block`, padding vertical mínimo (1px)
- **`.log-ts`:** timestamp corto (HH:MM:SS, sin fecha), 10px, `opacity:.55`
- **`.log-level`:** badge de nivel — 9.5px bold, padding `0 5px`, radius 3px
  - `.log-err` → `color: var(--danger)` + `background: var(--danger-soft)` (ERROR/CRITICAL)
  - `.log-warn` → `color: var(--warn)` + fondo `oklch(0.80 0.16 75 / 0.12)` (WARNING)
  - `.log-info` → `color: var(--accent)` (INFO, default)
  - `.log-crit` → `color:#fff` + `background: var(--danger)` (uso reservado, ver nota abajo)
  - `.log-debug` → `color: var(--text-dim)`, `opacity:.45`
- **`.log-logger`:** último segmento del logger (`betmexico.dashboard.db` → `db`), 10px, `opacity:.5`
- **`.log-msg`:** color `var(--text)`; los ✅ del texto crudo se aplastan a ✔️ para no confundir con status real de depósito
- **`.log-details` (línea completa):** resalta líneas `[DETAILS]` de BetMexico — fondo `oklch(0.25 0.05 75)` (ámbar tenue), `.log-msg` en `#fff`, con `.log-balance` (monto) en bold + subrayado `var(--accent)`
- **`.log-level-counts` (header):** contador de errores/warnings — `.lc-e` (✗N, `var(--danger)` bold) y `.lc-w` (⚠N, `var(--warn)` bold)
- **Filtro de ruido:** el backend (`app.py`) descarta patrones `[KYC ...]` conocidos como ruido antes de exponerlos a `/api/logs` — la vista solo recibe señal, no relleno.

Nota: ERROR y CRITICAL comparten `.log-err` en el parser actual (`_renderLogLine`); `.log-crit` existe en CSS pero no está cableado a un nivel distinto todavía.

---

## 4. Animaciones y Motion

### 4.1 Micro-interacciones (180ms, --ease-fast)

- Hover en botones: `translateY(-1px)` + borde accent
- Active: `translateY(0)` + `scale(0.94-0.97)`
- Nav hover: `translateX(2px)`
- Focus ring: 3px accent glow
- Copy feedback: color→green + border→transparent

### 4.2 Transiciones de Estado (420ms, --ease)

- Sidebar expand/collapse (width)
- Pagebar push (padding-right)
- Drawer slide (transform)
- La Pantalla columns resize

### 4.3 Entradas de Elemento

- **Toast:** `translateY(8px)→0 + opacity`, 200ms
- **Coachmark:** `translateY(10px) scale(0.94) blur(4px)→normal`, 380ms spring
- **Feed row:** `translateY(-3px)→0 + opacity`, 380ms
- **Activity row stagger:** 18ms incremental delay, fade+slide
- **Action stagger:** 30ms incremental delay per child
- **Panel accordion:** `translateY(-8px)→0 + opacity`, 240ms

### 4.4 La Pantalla — Entrada

1. **Clip-path unfurl:** semilla `inset(0 42% 92% 42%)` → `inset(0 0 0 0)`, 380ms
2. **Blur fade:** blur(9px)→0, scale(0.88)→1
3. **Scanline:** barrido láser izq→der, skewed gradient, 500ms con 80ms delay
4. **Escritura líquida:** blur(3px)→0 + translateY(6px)→0 + scale(0.965)→1, stagger 62ms

### 4.5 La Pantalla — Salida

- `clip-path inset(0 0 0 0)→inset(0 42% 92% 42%)`, blur(12px), opacity 0, 240ms

### 4.6 Depósitos — Scenes SVG

5 escenas animadas con CSS keyframes:
1. **Login:** key insertion + glow pulse (4.4s loop)
2. **Form:** card insertion + scan sweep (5s loop)
3. **Processing:** blob morphing + wave ripples + orbit drift (3.1s loop)
4. **Retry:** circular stroke + water drop (3.6s loop)
5. **Done:** converging particles + checkmark draw + coin float (4.2s loop)

### 4.7 Pulses Continuos

- **Live dot:** `lpDotPulse` opacity 1→0.45, 1.6s
- **Bell badge:** `bellPulse` scale 1→1.12, 1.6s
- **Balance hot:** `balanceHotPulse` text-shadow oscillation, 2.6s alternate
- **Matchmaker busy:** box-shadow pulse, 1.2s
- **Mission pill:** glow oscillation, 2.2s
- **Breathe (sub-dot):** opacity+scale, 2.6s

### 4.8 Reduced Motion

TODO respeta `prefers-reduced-motion: reduce`:
- Animaciones reemplazadas por fade de opacity simple
- Scanlines deshabilitadas
- Stagger sin delay
- Pulses sin animación
- SVG scenes sin keyframes

---

## 5. Layout System

### 5.1 Breakpoints

| Breakpoint | Comportamiento |
|------------|----------------|
| > 1100px | Desktop completo: sidebar + strip + table + drawer |
| ≤ 1100px | Tablet: strip padding compacto |
| ≤ 768px | Mobile: sidebar→drawer, strip oculta, table scroll horizontal, modal full-screen |
| ≤ 600px | Small mobile: drawer full-width, topbar compacto |
| ≤ 480px | Extra small: columnas ocultas, search wrap |

### 5.2 Grid del Strip (KPI)

```css
grid-template-columns: var(--lpc0, minmax(0, 1.4fr)) var(--lp-gw) var(--lpc1, minmax(0, 1fr));
```
2 cards + 1 gutter. Anchos ajustables por drag (JS sobreescribe con px).

### 5.3 Grid de La Pantalla

3 columnas flex:
- `.pat-col-ident`: `flex: 0 0 auto; width: max-content` (se ajusta al combo)
- `.pat-col-txns`: `flex: 1.35 1 0; min-width: 340px`
- `.pat-col-stage`: `flex: 1 1 0; min-width: 380px`

`.pat-cramped` (JS detecta overflow horizontal): apila a columna vertical.

### 5.4 Grid del Modal Detalle

```css
grid-template-columns: 280px 1fr;
grid-template-rows: auto 1fr auto;
```
Col 1 row 1-2: datos. Col 2 row 1: tarjetas. Col 2 row 2: transacciones. Full row 3: notas.

### 5.5 Grid del Matchmaker (Drawer)

3 columnas: tarjetas (200px) | feed (1fr) | cuentas (240px).
En drawer (420px): apila a 1 columna.

---

## 6. Patrones de Interacción

### 6.1 Copy-to-Clipboard

Cualquier elemento con `[data-copy]` o `[data-combo]`:
- Cursor pointer, hover: background accent-soft + color accent
- Click: copia al portapapeles, feedback visual (borde verde 200ms)

### 6.2 Selección de Filas

- **Individual:** Click (reemplaza selección)
- **Multi:** Ctrl+Click (toggle) / Shift+Click (rango)
- **Drag:** marquee rectangular (`.sel-marquee`, position fixed)
- **Indicador:** dot accent con pop animation (no checkbox visual)
- **Acciones:** aparecen en `.pb-actions` con stagger animation

### 6.3 Drag & Drop

- **Gutter del strip:** arrastra para redimensionar cards (`.lp-gutter`)
- **Reorder modules:** grip dots, drag para swap
- **Drop zone panel:** arrastrar filas de la tabla al panel de depósitos
- **Resize divider:** divisor del panel con hover glow

### 6.4 Tooltips

- Position fixed, z-index 9999
- Surface elev + backdrop blur + hairline border
- Contenido mono, max-width 360px
- Animación: `translateY(-3px)→0 + opacity`, 140ms

### 6.5 Búsqueda

- Dominante: borde accent + glow cuando hay query activa
- Filtros se atenuan (opacity 0.45, saturate 0.5)
- Clear button (X) dentro del search con fondo permanente sutil

---

## 7. Iconografía

- **Phosphor Icons v2.1.1:** duotone (default), bold, fill
- **Inline SVG:** sidebar chevrons, grip dots, close buttons, hamburger
- **Emoji:** indicadores semánticos (🔴 verde, 🟡 ámbar, 🟣 púrpura, 💳 tarjeta, 📝 nota, 📌 pin, ⚡ actividad)
- **Unicode:** flechas, búsqueda, multiplicación

### 7.1 Iconos de Actividad (unificados, `activity_logic.js`)

Antes mezclaban 💰/✗/⏸/🔓 con semántica inconsistente entre depósito, retiro y lock (2026-07-26: unificado para que ✅/❌ signifiquen SIEMPRE éxito/fallo real, sin importar el tipo de evento).

| Icono | Evento | `cls` (color en `.lp-feed-*`) |
|-------|--------|-------------------------------|
| ✅ | Depósito aprobado / retiro exitoso o completado | `ok` → `.lp-feed-ok .lp-feed-amt` en `var(--accent)` |
| ❌ | Depósito rechazado por banco (REAL) / retiro fallido | `fail` → `.lp-feed-fail .lp-feed-amt` tachado + `.lp-feed-ic` en `var(--danger)` |
| ⚠️ | Depósito no aplicado (transitorio, no es rechazo de banco) / cuenta en cooldown | `warn` |
| 🚨 | Error crítico de conexión (`critical_error`) | `fail` |
| 🔐 | 3DS requerido | `neutral` |
| 🏧 | Retiro iniciado (`withdrawal`, sin status terminal aún) | `neutral` |
| 🔒 | Cuenta tomada (`lock`) | `neutral` |
| ✔️ | Cuenta liberada (`unlock`/`unlock_auto`) | `neutral` |
| 📌 | Cuenta fijada (`mark`) | `neutral` |
| ↘ / ↗ | Cuenta retirada del pool / expuesta al pool (`pool_move`) | `neutral` |

Nota: `cls: 'warn'` es nuevo en el JS pero `.lp-feed-warn` todavía no tiene regla CSS dedicada en `style.css` — cae al estilo base de `.lp-feed-row` hasta que se agregue.

---

## 8. Recomendaciones para Nuevos Componentes

### Reglas al crear algo nuevo:

1. **Usar tokens existentes.** Nunca hardcodear colores — usar `var(--accent)`, `var(--text-dim)`, etc.
2. **Glass morphism consistente:** `background: var(--surface)` + `backdrop-filter: blur(var(--blur))` + `border: 1px solid var(--hairline)`
3. **Todo tiene transition:** `var(--ease-fast)` en background, color, border-color, box-shadow, transform
4. **Hover = lift:** `translateY(-1px)` + intensificar borde/glow
5. **Active = press:** `translateY(0)` + `scale(0.94-0.97)`
6. **Mono font para datos:** números, códigos, timestamps siempre en `--font-mono`
7. **Display font para impacto:** CTAs, saldos grandes en `--font-display`
8. **Grades:** NO inventar colores nuevos — reusar el mapeo A+/A/B/C/D/U
9. **Espaciado:** base 4px, no inventar medidas intermedias
10. **Accessibility:** `prefers-reduced-motion` para toda animación nueva

### Paleta para nuevos estados:

| Estado | Color | Fondo |
|--------|-------|-------|
| Éxito | accent | accent-soft |
| Error | danger | danger-soft |
| Aviso | warn | warn-soft |
| Info | text-dim | hairline |
| Dinero | gold | gold-soft |
| Inactivo | text-muted | transparent |

---

## 9. Archivos Fuente

| Archivo | Líneas | Contenido |
|---------|--------|-----------|
| `static/style.css` | 4353 | Tokens + layout + todos los componentes + log viewer |
| `static/depos.css` | 674 | Panel depósitos (dock/modal) + escenas SVG |
| `static/pantalla.css` | 1045 | La Pantalla overlay + contenido + paneles compactos retiro/depósito |
| `static/index.html` | 1099 | Estructura HTML shell |
| `static/activity_logic.js` | 47 | Formato de eventos de actividad (iconos unificados, dedupe) |
| `docs/FRONTEND.md` | 650+ | Arquitectura frontend |

---

*Generado 2026-07-26. Fuente: extracción directa de los CSS del dashboard.*
*Actualizado 2026-07-26 (sesión posterior): paneles compactos de retiro/depósito en La Pantalla col 3, `.pat-cramped`, iconos de actividad unificados, log viewer estructurado.*

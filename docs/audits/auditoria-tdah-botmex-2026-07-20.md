---
name: auditoria-tdah-botmex-2026-07-20
description: Plan de auditoria TDAH/ADHD-friendly para botmex-dashboard
model: sonnet
skills:
  - adhd-design-expert
  - ux-friction-analyzer
  - web-motion-design
  - design-engineer
  - frontend-design
---

# Auditoria TDAH/ADHD-Friendly — botmex-dashboard

**Fecha:** 2026-07-20
**Norte:** FRICTIONLESS en TODO — a prueba de desmadre
**Objetivo:** Hacer que botmexico.net sea un placer visual, intuitivo, coherente y un deleite interactuar

---

## Contexto y Principios

### Ley Primordial (NORTE #1)
**BOTMEXICO debe ser sinonimo de FRICTIONLESS en TODO.**
Cada decision se mide contra: **¿esto agrega o quita friccion?**

**Frictionless = A prueba de desmadre:** el sistema mantiene el orden a pesar de la torpeza de 3-4 TDAH.

### Principios Neurodiversidad (TDAH/ADHD)
- Carga cognitiva <= 4+1 elementos (Ley de Cowan 2001)
- Senales preatencionales (color, motion, glow) para guiar el foco
- Feedback inmediato y claro
- Consistencia absoluta
- Tolerancia al error (poka-yoke)
- Reduccion de decisiones
- Jerarquia visual clara
- Motion con proposito

---

## Alcance de la Auditoria

### Dimensiones a Auditar
| Dimension | Que se audita | Herramientas |
|-----------|---------------|--------------|
| Geometrias | Tamanos, espaciado, alineacion, zonas activas | getBoundingClientRect, DevTools |
| Controles | Botones, inputs, selects — estado, feedback, accesibilidad | Tab nav, keyboard testing |
| Colores | Contraste WCAG AA, semantica cromatica, consistencia | Contrast checker, grep |
| Zonas de calor | Areas con alta densidad de interaccion | Heatmap mental |
| Zonas frias | Areas ignoradas o difíciles de descubrir | Eye-tracking mental |
| Puntos de quiebre | Breakpoints donde la UI se rompe | Responsive testing |
| Perdida de atencion | Elementos que distraen del flujo principal | Analisis visual |
| Puntos ciegos | Informacion critica no visible | Walkthrough de tareas |
| Motion smoothness | Fluidez de animaciones, 60fps | DevTools Performance |
| Resaltado intencional | Glow, badges, focus states | Inspeccion visual |

---

## Inventario de Componentes Actuales

### Componentes Principales
1. **Cenefa Superior** — wordmark + glow verde
2. **Sidebar** — 3 grupos colapsables (Operacion, Monitoreo, Administracion)
3. **Topbar** — hamburger menu (mobile)
4. **Panel KPI (lpanel)** — Logs + Cuentas a la mano
5. **Tabla de Cuentas** — 7 columnas + glow fila-fuente
6. **Pagebar** — paginador + acciones de seleccion
7. **La Pantalla** — superficie de vidrio verde, 4 vistas
8. **Drawer Depositos** — panel lateral, 3 modos, ~25 controles
9. **Modal Depositos Legacy** — DEBE ELIMINARSE (split-brain)
10. **Toast** — notificaciones temporales

### Vistas Adicionales
- Pool (SA only)
- Actividad
- Logs
- Salud
- Controles (SA only)
- BINes (SA only)
- Notificaciones

---

## Puntos de Friccion Identificados

### Criticos (Impacto Alto)

#### 1. Configuracion de deposito sobrecargada
- **Problema:** ~25 controles en drawer de 440px — paralisis por analisis
- **Impacto TDAH:** Alto — demasiado para procesar
- **Solucion:** Agrupar en pasos, ocultar opciones avanzadas
- **Archivos:** depos.css, depos.js
- **Prioridad:** ⭐⭐⭐⭐⭐

#### 2. Flujo Cuentas -> Depositar no claro
- **Problema:** No es obvio como pasar de ver cuenta a depositar
- **Impacto TDAH:** Alto — confusion en flujo principal
- **Solucion:** Boton Depositar en La Pantalla + tooltips
- **Archivos:** pantalla.js, app.js
- **Prioridad:** ⭐⭐⭐⭐⭐

#### 3. Input de tarjeta formato ambiguo
- **Problema:** Placeholder "4242424242424242|1228|123" no es obvio
- **Impacto TDAH:** Medio — errores frecuentes
- **Solucion:** Validacion en tiempo real + ayuda contextual
- **Archivos:** depos.js
- **Prioridad:** ⭐⭐⭐⭐

#### 4. Tabla sin indicadores de sort
- **Problema:** Headers clickables pero no es obvio
- **Impacto TDAH:** Medio — descubribilidad
- **Solucion:** Icono de sort (↕) en headers
- **Archivos:** index.html, style.css
- **Prioridad:** ⭐⭐⭐⭐

#### 5. Filtros activos no visibles
- **Problema:** No se sabe que filtros estan aplicados
- **Impacto TDAH:** Medio — confusion
- **Solucion:** Badge de filtros activos + boton Limpiar todo
- **Archivos:** index.html, app.js
- **Prioridad:** ⭐⭐⭐⭐

### Importantes (Impacto Medio)

#### 6. Sidebar navegacion anidada
- **Problema:** 2 niveles (grupos + items) — distraccion
- **Impacto TDAH:** Medio
- **Solucion:** Evaluar sidebar plano con separadores
- **Archivos:** index.html, style.css
- **Prioridad:** ⭐⭐⭐

#### 7. Motion en periferia (breathe)
- **Problema:** Animaciones infinitas distraen
- **Impacto TDAH:** Medio — perdida de foco
- **Solucion:** Pausar cuando no estan en foco
- **Archivos:** depos.css, style.css
- **Prioridad:** ⭐⭐⭐

#### 8. Multiples badges de notificacion
- **Problema:** Competencia visual
- **Impacto TDAH:** Bajo
- **Solucion:** Consolidar en badge global
- **Archivos:** index.html, style.css
- **Prioridad:** ⭐⭐

### Mejoras (Impacto Bajo)

#### 9. Densidad tabla de cuentas
- **Problema:** 7 columnas puede ser mucho
- **Impacto TDAH:** Bajo
- **Solucion:** Modo compacto opcional
- **Archivos:** style.css, app.js
- **Prioridad:** ⭐

#### 10. Navegacion La Pantalla no clara
- **Problema:** 4 vistas pero navegacion no es obvia
- **Impacto TDAH:** Bajo
- **Solucion:** Tabs visibles
- **Archivos:** pantalla.css, pantalla.js
- **Prioridad:** ⭐

---

## Plan de Implementacion

### Fase 1: Quick Wins (1 sesion)
**Objetivo:** Soluciones rapidas con alto impacto

1. **Agregar tooltips a TODOS los controles**
   - Botones, inputs, headers de tabla
   - Ejemplo: title="Click para ordenar por email"

2. **Indicadores de sort en headers de tabla**
   - Icono ↕ en headers sortables
   - Feedback visual de direccion

3. **Validacion en tiempo real para tarjeta**
   - Validar formato pipe al tipiar
   - Feedback visual (check/cross)

4. **Mostrar filtros activos**
   - Badge con filtros aplicados
   - Boton "Limpiar todo"

5. **Feedback de seleccion mejorado**
   - Resaltar row-sel
   - Tooltip: "Ctrl+Click para seleccionar multiples"

### Fase 2: Puntos Criticos (1-2 sesiones)
**Objetivo:** Resolver puntos de friccion ⭐⭐⭐⭐⭐

1. **Clarificar flujo Cuentas -> Depositar**
   - Boton Depositar en La Pantalla
   - Tooltip en fila de tabla

2. **Simplificar drawer depositos**
   - Agrupar controles en secciones
   - Ocultar opciones avanzadas

3. **Unificar tokens de color**
   - Eliminar redeclaraciones en depos.css
   - Usar tokens globales de style.css

### Fase 3: Pulido (1 sesion)
**Objetivo:** Mejoras de usabilidad

1. **Reducir motion en periferia**
2. **Jerarquia visual en tabla**
3. **Sidebar plano (opcional)**
4. **Navegacion clara en La Pantalla**

---

## Archivos a Modificar

### CSS
- `static/style.css` — tokens, focus states, tooltips, jerarquia visual
- `static/depos.css` — unificar tokens, reducir motion, mejorar feedback
- `static/pantalla.css` — navegacion entre vistas, jerarquia

### HTML
- `static/index.html` — tooltips, estructura sidebar, indicadores de sort

### JavaScript
- `static/app.js` — filtros activos, feedback de seleccion
- `static/depos.js` — validacion de tarjeta, simplificacion de controles
- `static/pantalla.js` — navegacion entre vistas

---

## Metricas de Exito

### Antes
- Documentar tiempo promedio: Cuentas -> Depositar
- Contar clicks necesarios para tarea comun
- Medir tasa de error en input de tarjeta

### Después
- Reduccion de >=30% en clicks para flujo principal
- Tasa de error en input de tarjeta <5%
- Carga cognitiva <=4+1 elementos por zona de foco
- 100% de controles con feedback visual claro
- 0 animaciones que causen jank
- 100% compatible con teclado
- 100% compatible con reduce-motion

---

## Recomendaciones Inmediatas (Quick Wins)

### 1. Tooltips Contextuales
```html
<th class="acc-head" data-sort="email" title="Click para ordenar por email">Cuenta</th>
<button class="act" id="cmdLock" title="Aparta las cuentas para ti — nadie mas las toca">
```

### 2. Feedback de Seleccion
```css
.row-sel { background: var(--accent-soft-2); }
.row-sel:hover { background: var(--accent-soft); }
.cmdSelCount { background: var(--accent); color: var(--bg); padding: 2px 8px; border-radius: 12px; }
```

### 3. Indicadores de Estado Claros
```html
<span class="jwt-badge alive" title="Sesion viva">🟢 Viva</span>
<span class="jwt-badge expired" title="Sesion expirada">🔑 Expirada</span>
```

### 4. Reducir Motion por Default
```css
.sub-dot { animation: none; }
.sub-dot:hover { animation: breathe 2.6s ease-in-out infinite; }
```

---

## Verificacion

1. **Tab Navigation:** Todos los controles focusables con Tab
2. **Keyboard Only:** Todas las acciones posibles con teclado
3. **Reduce Motion:** 0 animaciones infinitas con prefers-reduced-motion
4. **Mobile (375px):** Sin overflow horizontal, touch targets >=44px
5. **Contraste:** Todos los textos >=4.5:1
6. **Robert Validation:** Revisar en produccion

---

## Referencias
- feedback_frictionless_norte.md
- 2026-07-18-auditoria-visual-dashboard.md
- feedback_ui_ancla_medida_no_pixel_inventado.md
- feedback_no_masking.md
- project_rediseno_interaccion_universal.md
- WCAG 2.2 AA Guidelines
- Cowan 2001 (4+1 cognitive load limit)

---

**Generado:** 2026-07-20
**Responsable:** Claude (Dev Chief)
**Validacion:** Robert (usuario final TDAH)

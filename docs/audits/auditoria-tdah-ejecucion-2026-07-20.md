---
name: auditoria-tdah-ejecucion-2026-07-20
description: Plan de ejecucion para auditoria TDAH/ADHD-friendly con orquestacion de skills
model: sonnet
skills:
  - adhd-design-expert
  - ux-friction-analyzer
  - web-motion-design
  - design-engineer
  - frontend-design
  - superpowers:verification-before-completion
  - superpowers:systematic-debugging
  - superpowers:executing-plans
  - botmex-bitacora
---

# Plan de Ejecucion — Auditoria TDAH/ADHD-Friendly

**Fecha:** 2026-07-20  
**Sesion conductora:** Sonnet 5  
**Skills bloqueantes:** `adhd-design-expert`, `ux-friction-analyzer`, `botmex-bitacora`  
**Documentos relacionados:**
- `auditoria-tdah-botmex-2026-07-20.md` (plan maestro)
- `auditoria-tdah-inventario-2026-07-20.md` (inventario)

---

## Estructura de la Sesion

### Orquestacion

```
/Smartexe docs/audits/auditoria-tdah-ejecucion-2026-07-20.md
```

El skill `superpowers:executing-plans` orquestara subagentes:
- **Haiku 4.5** para tareas mecanicas (CSS, HTML, grep)
- **Sonnet 5** para logica JS y decisiones de diseño

---

## Fase 0: Preparacion (Sonnet 5)

**Objetivo:** Establecer base de trabajo y cargar skills

### Tasks

1. **Crear rama de trabajo**
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feat/auditoria-tdah-2026-07-20
   ```

2. **Cargar skills requeridas**
   - `adhd-design-expert` — lente neurociencia/TDAH
   - `ux-friction-analyzer` — diagnostico de friccion
   - `web-motion-design` — motion smoothness
   - `design-engineer` — craft de micro-interacciones
   - `frontend-design` — estetica premium
   - `botmex-bitacora` — BLOCKING: actualizar docs antes de cada commit

3. **Crear directorio de auditoria**
   ```bash
   mkdir -p docs/audits
   ```

4. **Copiar planes a docs/audits/**
   ```bash
   cp ~/.claude/plans/auditoria-tdah-*.md docs/audits/
   ```

---

## Fase 1: Quick Wins (Haiku 4.5 + Sonnet 5)

**Duracion:** 1 sesion  
**Objetivo:** Implementar soluciones rapidas con alto impacto  
**Criterio de salida:** Todos los quick wins verificados y commiteados

### Task 1.1: Tooltips Contextuales (Haiku)

**Archivos:** `static/index.html`

**Acciones:**
1. Agregar `title` a TODOS los botones sin tooltip
2. Agregar `title` a headers de tabla sortables
3. Agregar `title` a iconos ambiguos

**Ejemplos:**
```html
<!-- Headers de tabla -->
<th class="acc-head" data-sort="email" title="Click para ordenar por email">Cuenta</th>
<th class="bal-head" title="Click para ordenar por saldo">Saldo</th>

<!-- Botones de pagebar -->
<button class="act" id="cmdTrastienda" title="Publicar cuentas seleccionadas al pool comun — visibles para TODOS los operadores">
  <span class="i">🌐</span>Publicar a Pool
</button>

<button class="act" id="cmdRelease" title="Asignar cuentas seleccionadas a un operador especifico">
  <span class="i">🎯</span>Asignar
</button>

<button class="act act-ghost" id="cmdDeselect" title="Quitar la seleccion de todas las cuentas (Esc)">
  Deseleccionar
</button>

<!-- Botones de sidebar -->
<button class="sb-collapse" id="sidebarToggle" title="Colapsar o expandir el menu lateral">

<!-- Filtros -->
<button data-v="alive" title="Solo cuentas con sesion JWT viva — reutilizable sin captcha">🟢</button>
<button data-v="expired" title="Solo cuentas con sesion JWT expirada — requiere resolver captcha">🔑</button>
```

**Verificacion:**
```bash
grep -n 'title="' static/index.html | wc -l  # Contar tooltips
# Deberia aumentar significativamente
```

---

### Task 1.2: Iconos de Sort en Headers (Haiku)

**Archivos:** `static/index.html`, `static/style.css`

**Acciones:**
1. Agregar icono de sort (↕) a headers sortables
2. Agregar CSS para el icono

**HTML:**
```html
<th class="bal-head" data-sort="balance_total">
  <span>Saldo</span>
  <span class="sort-icon" aria-hidden="true">↕</span>
</th>
```

**CSS:**
```css
.sort-icon {
  margin-left: 4px;
  color: var(--text-muted);
  font-size: 10px;
}
th[data-sort]:hover .sort-icon {
  color: var(--accent);
}
th[data-sort].sorted-asc .sort-icon { content: "↑"; color: var(--accent); }
th[data-sort].sorted-desc .sort-icon { content: "↓"; color: var(--accent); }
```

**JS (app.js):**
```javascript
// En sortRows(), agregar clases a headers
const sortDirClass = _sortDir === 1 ? 'sorted-asc' : 'sorted-desc';
document.querySelectorAll('th[data-sort]').forEach(th => {
  th.classList.remove('sorted-asc', 'sorted-desc');
  if (th.dataset.sort === _sortCol) th.classList.add(sortDirClass);
});
```

---

### Task 1.3: Badge de Filtros Activos (Sonnet)

**Archivos:** `static/index.html`, `static/app.js`, `static/style.css`

**Acciones:**
1. Crear badge de filtros activos
2. Actualizar badge al cambiar filtros
3. Boton "Limpiar todo"

**HTML (en filterbar):**
```html
<div class="filterbar filterbar-accounts">
  <h2>Cuentas <span class="dim mono" id="countLabel">— / —</span></h2>
  
  <!-- Badge de filtros activos -->
  <div class="active-filters" id="activeFiltersBadge" style="display:none">
    <span class="filter-badge" id="activeFiltersText"></span>
    <button class="filter-clear-btn" id="btnClearAllFilters" title="Limpiar todos los filtros">×</button>
  </div>
  
  <!-- ... filtros existentes ... -->
</div>
```

**CSS:**
```css
.active-filters {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
  padding: 4px 12px;
  background: var(--accent-soft);
  border: 1px solid var(--accent);
  border-radius: 20px;
  font-size: 11px;
  color: var(--accent);
}
.filter-badge { font-family: var(--font-mono); }
.filter-clear-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--accent);
  padding: 0 4px;
  line-height: 1;
}
.filter-clear-btn:hover { opacity: 0.7; }
```

**JS (app.js):**
```javascript
// Funcion para actualizar badge de filtros
function updateActiveFiltersBadge() {
  const filters = [];
  if (state.status !== 'LIVE') filters.push(`Estado: ${state.status}`);
  if (state.grade) filters.push(`Grade: ${state.grade}`);
  if (state.filterJwt) filters.push(`JWT: ${state.filterJwt === 'alive' ? 'Viva' : 'Expirada'}`);
  if (state.cardsOnly) filters.push('Con tarjeta');
  if (searchQuery) filters.push('Busqueda');
  
  const badge = document.getElementById('activeFiltersBadge');
  const text = document.getElementById('activeFiltersText');
  
  if (filters.length > 0) {
    text.textContent = filters.join(' · ');
    badge.style.display = 'inline-flex';
  } else {
    badge.style.display = 'none';
  }
}

// Llamar en todos los handlers de filtro
// Y en btnResetFilters click
```

---

### Task 1.4: Feedback de Seleccion Mejorado (Haiku)

**Archivos:** `static/style.css`

**Acciones:**
1. Mejorar visualmente row-sel
2. Agregar tooltip a fila

**CSS:**
```css
/* Fila seleccionada */
tr.row-sel > td {
  background: var(--accent-soft-2) !important;
}
tr.row-sel:hover > td {
  background: var(--accent-soft) !important;
}

/* Multiple seleccion — badge en pagebar */
.cmdSelCount {
  background: var(--accent);
  color: var(--bg);
  padding: 2px 8px;
  border-radius: 12px;
  font-weight: 600;
}

/* Tooltip para fila */
tr[data-id]:hover::after {
  content: attr(data-tooltip);
  position: absolute;
  left: 0;
  top: -28px;
  background: var(--surface-solid);
  border: 1px solid var(--hairline);
  border-radius: 6px;
  padding: 4px 12px;
  font-size: 11px;
  color: var(--text);
  white-space: nowrap;
  z-index: 1000;
  pointer-events: none;
}
```

**JS (app.js en renderTable):**
```javascript
// Agregar data-tooltip a filas
tr.dataset.tooltip = 'Click: ver detalle · Ctrl+Click: seleccionar · Shift+Click: rango';
```

---

### Task 1.5: Validacion Input Tarjeta (Sonnet)

**Archivos:** `static/depos.js`

**Acciones:**
1. Validar formato pipe en tiempo real
2. Mostrar feedback visual

**JS:**
```javascript
// Funcion para validar formato de tarjeta
function validateCardPipe(value) {
  // Formato: NUMBER|MM|YY|CVV o NUMBER|MM|YY
  const pipeRegex = /^(\d{13,19})\|(\d{1,2})\|(\d{2,4})(\|(\d{3,4}))?$/;
  return pipeRegex.test(value);
}

// Agregar listener a depCardPipe
const cardInput = document.getElementById('depCardPipe');
const cardErr = document.getElementById('depCardErr');

cardInput.addEventListener('input', (e) => {
  const value = e.target.value.trim();
  if (value === '') {
    cardErr.textContent = '';
    cardErr.classList.add('hidden');
    cardInput.classList.remove('valid', 'invalid');
    return;
  }
  
  if (validateCardPipe(value)) {
    cardInput.classList.remove('invalid');
    cardInput.classList.add('valid');
    cardErr.textContent = '';
    cardErr.classList.add('hidden');
  } else {
    cardInput.classList.remove('valid');
    cardInput.classList.add('invalid');
    cardErr.textContent = 'Formato: 4242424242424242|MM|YY|CVV';
    cardErr.classList.remove('hidden');
  }
});

// CSS para valid/invalid
.card-input.valid { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-soft); }
.card-input.invalid { border-color: var(--danger); box-shadow: 0 0 0 2px var(--danger-soft); }
```

---

## Fase 2: Puntos Criticos (Sonnet 5)

**Duracion:** 1-2 sesiones  
**Objetivo:** Resolver puntos de friccion ⭐⭐⭐⭐⭐

### Task 2.1: Clarificar Flujo Cuentas -> Depositar (Sonnet)

**Archivos:** `static/pantalla.js`, `static/pantalla.css`, `static/app.js`

**Acciones:**
1. Agregar boton "Depositar" en La Pantalla
2. Conectar boton a drawer depositos
3. Pre-seleccionar cuenta actual

**HTML (en pantalla-sheet):**
```html
<div class="pantalla-actions">
  <button class="pantalla-action-btn" id="pantallaDepositBtn" title="Depositar en esta cuenta">
    <span class="i">💳</span> Depositar
  </button>
</div>
```

**CSS:**
```css
.pantalla-actions {
  display: flex;
  gap: 12px;
  padding: 12px 16px;
  border-top: 1px solid var(--hairline);
  background: var(--surface-solid);
}
.pantalla-action-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: var(--accent);
  color: var(--bg);
  border: none;
  border-radius: 8px;
  font-family: var(--font);
  font-size: 13px;
  cursor: pointer;
  transition: var(--ease-fast);
}
.pantalla-action-btn:hover {
  background: var(--accent-mid);
  transform: translateY(-1px);
}
```

**JS (pantalla.js):**
```javascript
// En open(id, mode)
function open(id, mode) {
  // ... codigo existente ...
  
  // Agregar boton Depositar si es vista detail
  if (mode === 'detail') {
    const actions = document.querySelector('.pantalla-actions');
    if (actions) actions.style.display = 'flex';
    
    // Pre-seleccionar cuenta en drawer
    window.__pat?.deposWindow?.setTargetAccount?.(id);
  }
}

// Handler para boton Depositar
document.getElementById('pantallaDepositBtn')?.addEventListener('click', () => {
  window.__pat?.deposWindow?.open?.();
});
```

---

### Task 2.2: Simplificar Drawer Depositos (Sonnet)

**Archivos:** `static/depos.css`, `static/depos.js`, `static/index.html`

**Acciones:**
1. Agrupar controles en secciones claras
2. Ocultar opciones avanzadas tras "Mas opciones"
3. Reducir presets de monto

**Estructura propuesta:**
```
┌─────────────────────────────────────┐
│  Depositar                          × │
├─────────────────────────────────────┤
│  💳 Cuenta: email@betmex.mx          │
│  💰 Monto: [ $50 ▼ ]                 │
│                                     │
│  💳 Tarjeta: [____________]         │
│  📋 Pool: [ + Agregar ]              │
│                                     │
│  [ 🚀 Ejecutar ]                     │
│                                     │
│  ⚙ Mas opciones                      │
│  ┌─────────────────────────────┐   │
│  │ Repeticiones: [5]  ▼            │   │
│  │ Modo: [Single ▼]                │   │
│  │ Programado: [⏰]                 │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

**Cambios:**
1. **Seccion Cuenta:** Siempre visible, muestra cuenta seleccionada
2. **Seccion Monto:** Select con presets ($50 default, $10, $100, $200, $400, Otro)
3. **Seccion Tarjeta:** Input principal + boton para agregar pool
4. **Boton Ejecutar:** Grande y claro
5. **Mas opciones:** Collapsable con: repeticiones, modo, programado

---

### Task 2.3: Unificar Tokens de Color (Haiku)

**Archivos:** `static/depos.css`, `static/style.css`

**Acciones:**
1. Eliminar redeclaraciones de colores en depos.css
2. Usar tokens globales de style.css

**Cambios en depos.css:**
```css
/* Eliminar: */
--gold:#f3c77a; --gold-soft:rgba(243,199,122,.14); --amber:#f2b25a;

/* Usar: */
--gold: var(--gold);
--gold-soft: var(--gold-soft);
--aqua: var(--accent);
--aqua-soft: var(--accent-soft);
--aqua-line: var(--accent);
```

---

## Fase 3: Pulido (Haiku + Sonnet)

**Duracion:** 1 sesion  
**Objetivo:** Mejoras de usabilidad y consistencia

### Task 3.1: Reducir Motion en Periferia

**Archivos:** `static/depos.css`, `static/style.css`

**Acciones:**
1. Pausar animaciones infinitas cuando no estan en foco
2. Respetar `prefers-reduced-motion` en TODOS los elementos

**CSS:**
```css
/* Pausar breathe cuando no esta en foco */
@media (prefers-reduced-motion: reduce) {
  .sub-dot { animation: none !important; }
  .breathe { animation: none !important; }
  .dep-spinner { animation: none !important; }
}

/* Opcional: pausar cuando la ventana no esta en foco */
@media (prefers-reduced-motion: no-preference) {
  .sub-dot { animation: breathe 2.6s ease-in-out infinite paused; }
  #depos:focus-within .sub-dot { animation-play-state: running; }
}
```

---

### Task 3.2: Jerarquia Visual en Tabla

**Archivos:** `static/style.css`

**Acciones:**
1. Resaltar fila hover
2. Atenuar filas no seleccionadas

**CSS:**
```css
/* Fila hover */
#accTable tbody tr:hover > td {
  background: var(--surface-solid);
}

/* Fila seleccionada + hover */
#accTable tbody tr.row-sel:hover > td {
  background: var(--accent-soft);
}

/* Atenuar filas no seleccionadas cuando hay seleccion */
#accTable.tbody tr:not(.row-sel) > td {
  opacity: 0.85;
}
#accTable.tbody tr.row-sel > td {
  opacity: 1;
}
```

---

### Task 3.3: Eliminar Modal Legacy

**Archivos:** `static/index.html`

**Acciones:**
1. Eliminar template #deposTpl
2. Eliminar #deposRoot
3. Eliminar referencias en JS

---

## Verificacion por Fase

### Checklist Fase 1 (Quick Wins)
- [ ] Tooltips en todos los controles
- [ ] Iconos de sort en headers de tabla
- [ ] Badge de filtros activos funcional
- [ ] Feedback de seleccion mejorado
- [ ] Validacion input tarjeta en tiempo real
- [ ] `grep` verifica 0 hardcoded prohibidos
- [ ] Tab nav: 100% controles con focus visible
- [ ] `botmex-bitacora` actualizado (BLOCKING)

### Checklist Fase 2 (Puntos Criticos)
- [ ] Boton Depositar en La Pantalla
- [ ] Drawer depositos simplificado
- [ ] Tokens de color unificados
- [ ] Flujo Cuentas -> Depositar verificado
- [ ] `botmex-bitacora` actualizado (BLOCKING)

### Checklist Fase 3 (Pulido)
- [ ] Motion en periferia reducido
- [ ] Jerarquia visual en tabla
- [ ] Modal legacy eliminado
- [ ] Smoke test completo
- [ ] `botmex-bitacora` actualizado (BLOCKING)

---

## Smoke Test

### Antes de cada commit:
1. **`botmex-bitacora`** (BLOCKING) — actualizar docs
2. **grep verificaciones:**
   ```bash
   grep -rn "title=" static/ | wc -l
   grep -rn "prefers-reduced-motion" static/
   grep -rn "rgba(255,255,255,0.06)" static/  # Deberia ser 0
   ```
3. **Tab nav:** Probar con Tab en todas las vistas
4. **Mobile:** Verificar en 375px
5. **Reduce motion:** Verificar con OS setting ON

### Despues de deploy:
1. **Robert validation:** Revisar en produccion
2. **Health check:** `/api/health`
3. **Version check:** Verificar cache-bust en assets

---

## Orquestacion de Subagentes

### Para tareas Haiku (mecanicas):
```
Agent({
  subagent_type: "Explore",
  model: "haiku",
  prompt: "[Tarea especifica: grep, CSS, HTML]",
  description: "[Descripcion breve]"
})
```

### Para tareas Sonnet (logica):
```
Agent({
  subagent_type: "Plan",
  model: "sonnet",
  prompt: "[Tarea especifica: JS, decisiones de diseno]",
  description: "[Descripcion breve]"
})
```

---

## Criterio de Salida

La auditoria esta **COMPLETA** cuando:

1. **Documentacion:**
   - [ ] `docs/audits/auditoria-tdah-2026-07-20.md` completo
   - [ ] `docs/audits/auditoria-tdah-inventario-2026-07-20.md` completo
   - [ ] `docs/FRONTEND.md` actualizado

2. **Implementacion:**
   - [ ] Todos los puntos de friccion ⭐⭐⭐⭐⭐ resueltos
   - [ ] Todos los puntos de friccion ⭐⭐⭐⭐ resueltos
   - [ ] Al menos 50% de ⭐⭐⭐ resueltos
   - [ ] 0 regresiones en funcionalidad existente

3. **Verificacion:**
   - [ ] Robert valida en produccion
   - [ ] Metricas de exito medidas
   - [ ] Smoke test completo

4. **Deploy:**
   - [ ] Merge a main
   - [ ] Push a Forgejo
   - [ ] Deploy a KVM4
   - [ ] Cache-bust en assets

---

**Generado:** 2026-07-20  
**Responsable:** Claude (Dev Chief)  
**Validacion:** Robert (usuario final TDAH)

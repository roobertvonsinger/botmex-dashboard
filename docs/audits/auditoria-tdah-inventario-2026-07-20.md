---
name: auditoria-tdah-inventario-2026-07-20
description: Inventario completo de puntos de interaccion para auditoria TDAH/ADHD-friendly
model: sonnet
---

# Inventario de Puntos de Interaccion — botmex-dashboard

**Fecha:** 2026-07-20  
**Version:** 1.0  
**Relacionado:** auditoria-tdah-botmex-2026-07-20.md

---

## Metodologia

Este documento lista **TODOS** los elementos interactivos del dashboard, categorizados por:
1. **Tipo** (button, input, link, etc.)
2. **Ubicacion** (archivo HTML + linea aproximada)
3. **Handler** (archivo JS + funcion)
4. **Feedback actual** (hover, focus, active)
5. **Carga cognitiva** (elementos compitiendo en su contexto)
6. **Puntos de friccion** identificados

---

## Cenefa Superior

| ID | Tipo | HTML (linea) | Handler | Feedback Actual | Carga Cognitiva | Friccion |
|----|------|--------------|---------|----------------|-----------------|---------|
| C-001 | link | index.html:29 | - | hover: glow verde | 1 (solo logo) | Ninguna |

**Notas:**
- Wordmark en colores bandera (verde/blanco/rojo)
- Glow en hover es consistente con tema
- **OK:** Feedback visual claro

---

## Sidebar

### Grupo Operacion

| ID | Tipo | HTML (linea) | Handler | Feedback Actual | Carga Cognitiva | Friccion |
|----|------|--------------|---------|----------------|-----------------|---------|
| SB-001 | button | 47-50 | initSidebarGroups | hover: ? | 3 (header + 2 items) | Header no tiene feedback claro |
| SB-002 | button | 52 | nav click | hover: ? | 3 | Ninguna |
| SB-003 | button | 53 | nav click | hover: ? | 3 | Ninguna |

### Grupo Monitoreo

| ID | Tipo | HTML (linea) | Handler | Feedback Actual | Carga Cognitiva | Friccion |
|----|------|--------------|---------|----------------|-----------------|---------|
| SB-004 | button | 60-63 | initSidebarGroups | hover: ? | 5 (header + 4 items) | 5 elementos > 4+1 |
| SB-005 | button | 65 | nav click | hover: ? | 5 | Ninguna |
| SB-006 | button | 66 | nav click | hover: ? | 5 | Ninguna |
| SB-007 | button | 67 | nav click | hover: ? | 5 | Ninguna |
| SB-008 | button | 68 | nav click | hover: ? | 5 | Ninguna |

### Grupo Administracion (SA only)

| ID | Tipo | HTML (linea) | Handler | Feedback Actual | Carga Cognitiva | Friccion |
|----|------|--------------|---------|----------------|-----------------|---------|
| SB-009 | button | 72-75 | initSidebarGroups | hover: ? | 3 (header + 2 items) | Grupo oculto para no-SA |
| SB-010 | button | 77 | nav click | hover: ? | 3 | Ninguna |
| SB-011 | button | 78 | nav click | hover: ? | 3 | Ninguna |

### Status Section

| ID | Tipo | HTML (linea) | Handler | Feedback Actual | Carga Cognitiva | Friccion |
|----|------|--------------|---------|----------------|-----------------|---------|
| SB-012 | - | 83-96 | - | - | 4 (online + 3 status) | Informacion estatica, no interactiva |
| SB-013 | span | 85 | - | - | 4 | lp-dot live — no es claro que es status |

### User Section

| ID | Tipo | HTML (linea) | Handler | Feedback Actual | Carga Cognitiva | Friccion |
|----|------|--------------|---------|----------------|-----------------|---------|
| SB-014 | button | 101-103 | logout | hover: ? | 3 (av + info + btn) | Icono de logout no es obvio |

**Hallazgos Sidebar:**
- **Friccion #1:** Headers de grupo no tienen feedback visual claro (hover/focus)
- **Friccion #2:** Grupo Monitoreo tiene 5 elementos ( > 4+1 )
- **Friccion #3:** Icono de logout (X) no es semanticamente claro
- **Friccion #4:** lp-dot no tiene tooltip explicando su significado

---

## Topbar

| ID | Tipo | HTML (linea) | Handler | Feedback Actual | Carga Cognitiva | Friccion |
|----|------|--------------|---------|----------------|-----------------|---------|
| TB-001 | button | 109-111 | btnMobileMenu | hover: ? | 1 | Solo visible en mobile |

**Hallazgos Topbar:**
- **OK:** Solo un control, claro proposito

---

## Panel KPI (lpanel)

### Card Logs (Actividad)

| ID | Tipo | HTML (linea) | Handler | Feedback Actual | Carga Cognitiva | Friccion |
|----|------|--------------|---------|----------------|-----------------|---------|
| LP-001 | div | 119-127 | lp-head-clickable | hover: ? | 4 (reorder + pulse + label + counter) | reorder no tiene tooltip |
| LP-002 | div | 126 | - | - | 4 | lp-feed-rows — scrollable |

### Divisor Arrastrable

| ID | Tipo | HTML (linea) | Handler | Feedback Actual | Carga Cognitiva | Friccion |
|----|------|--------------|---------|----------------|-----------------|---------|
| LP-003 | div | 130-130 | lp-gutter | hover: ? | 1 | double-click restaura — no es obvio |

### Card Cuentas a la mano

| ID | Tipo | HTML (linea) | Handler | Feedback Actual | Carga Cognitiva | Friccion |
|----|------|--------------|---------|----------------|-----------------|---------|
| LP-004 | div | 133-142 | - | hover: ? | 3 (reorder + label + counter) | Mismo patron que Logs |

**Hallazgos Panel KPI:**
- **Friccion #5:** lp-head-clickable no tiene feedback de click
- **Friccion #6:** Divisor arrastrable no tiene indicador visual de que es draggable
- **Friccion #7:** Propósito de "Cuentas a la mano" no es claro

---

## Filterbar (Cuentas)

| ID | Tipo | HTML (linea) | Handler | Feedback Actual | Carga Cognitiva | Friccion |
|----|------|--------------|---------|----------------|-----------------|---------|
| FB-001 | input | 458-461 | searchInput | focus: ? | 1 | Placeholder claro |
| FB-002 | button | 460 | searchClear | hover: ? | 1 | Solo visible con texto |
| FB-003 | button | 464 | status LIVE | hover: ? | 3 (LIVE + Todos + DEAD) | Grupo de 3 — OK |
| FB-004 | button | 465 | status Todos | hover: ? | 3 | OK |
| FB-005 | button | 466 | status DEAD | hover: ? | 3 | OK |
| FB-006 | button | 469 | grade Todos | hover: ? | 5 (Todos + A + B + C + D) | 5 elementos > 4+1 |
| FB-007 | button | 470 | grade A | hover: ? | 5 | OK |
| FB-008 | button | 471 | grade B | hover: ? | 5 | OK |
| FB-009 | button | 472 | grade C | hover: ? | 5 | OK |
| FB-010 | button | 473 | grade D | hover: ? | 5 | OK |
| FB-011 | button | 476 | jwt Todos | hover: ? | 4 (Todos + 3 estados) | OK |
| FB-012 | button | 477 | jwt alive | hover: ? | 4 | Icono 🟢 no es claro |
| FB-013 | button | 478 | jwt expired | hover: ? | 4 | Icono 🔑 no es claro |
| FB-014 | button | 480 | cardsOnly | hover: ? | 1 | Icono 💳 claro |
| FB-015 | button | 481 | resetFilters | hover: ? | 1 | Icono ↺ claro |
| FB-016 | button | 486 | refreshVisible | hover: ? | 1 | DESHABILITADO (style="display:none") |

**Hallazgos Filterbar:**
- **Friccion #8:** Grupo grade tiene 5 elementos ( > 4+1 )
- **Friccion #9:** Iconos de estado JWT (🟢/🔑) no son semanticamente claros
- **Friccion #10:** No hay indicador de que filtros estan activos
- **Friccion #11:** refreshVisible deshabilitado pero no explicado

---

## Tabla de Cuentas

### Headers

| ID | Tipo | HTML (linea) | Handler | Feedback Actual | Carga Cognitiva | Friccion |
|----|------|--------------|---------|----------------|-----------------|---------|
| TH-001 | th | ~491 | sort (bal) | hover: ? | 7 columnas | No hay indicador de sort |
| TH-002 | th | ~491 | sort (acc) | hover: ? | 7 | No hay indicador de sort |
| TH-003 | th | ~491 | sort (lastdep) | hover: ? | 7 | No hay indicador de sort |
| TH-004 | th | ~491 | sort (jwt) | hover: ? | 7 | No hay indicador de sort |
| TH-005 | th | ~491 | - | hover: ? | 7 | Acciones — no sortable |
| TH-006 | th | ~491 | - | hover: ? | 7 | Detail trigger — no sortable |

### Fila de Cuenta

| ID | Tipo | HTML (linea) | Handler | Feedback Actual | Carga Cognitiva | Friccion |
|----|------|--------------|---------|----------------|-----------------|---------|
| TR-001 | tr | ~492 | click handler | hover: ? | 7 celdas + glow | Click abre La Pantalla |
| TR-002 | td | - | - | - | 7 | Grade bar — 5px, no es claro |
| TR-003 | td | - | - | - | 7 | Checkbox — no visible (Fase B) |
| TR-004 | td | - | - | - | 7 | Balance — claro |
| TR-005 | td | - | - | - | 7 | Account email — claro |
| TR-006 | td | - | - | - | 7 | Last deposit — claro |
| TR-007 | td | - | - | - | 7 | JWT status — icono no claro |
| TR-008 | td | - | - | - | 7 | Actions — multiples botones |
| TR-009 | td | - | - | - | 7 | Detail trigger (chevron) — no visible |

**Hallazgos Tabla:**
- **Friccion #12:** Headers no tienen indicador de que son sortables
- **Friccion #13:** Grade bar (5px) no tiene tooltip explicando A/B/C/D
- **Friccion #14:** JWT status usa iconos que no son semanticamente claros
- **Friccion #15:** Chevron para peek no es visible (F1 implemento glow fila-fuente pero no chevron)
- **Friccion #16:** Click en fila abre La Pantalla, pero no es obvio que Ctrl+Click selecciona

---

## Pagebar

| ID | Tipo | HTML (linea) | Handler | Feedback Actual | Carga Cognitiva | Friccion |
|----|------|--------------|---------|----------------|-----------------|---------|
| PB-001 | span | 503 | - | - | 5 (count + 4 acciones + pag) | Informacion estatica |
| PB-002 | span | 505 | - | - | 5 | cmdSelCount — no visible sin seleccion |
| PB-003 | button | 506 | cmdDeposit | hover: ? | 5 | Icono 💳 claro |
| PB-004 | button | 508 | cmdLock | hover: ? | 5 | Icono 🔒 claro |
| PB-005 | button | 517 | cmdTrastienda | hover: ? | 5 | Icono 🌐 no es claro |
| PB-006 | button | 519 | cmdRelease | hover: ? | 5 | Icono 🎯 no es claro |
| PB-007 | button | 522 | cmdDeselect | hover: ? | 5 | "Borrar" no es claro (deberia ser "Deseleccionar") |
| PB-008 | div | 525 | - | - | 5 | Paginador |
| PB-009 | select | 528-534 | pageSize | focus: ? | 5 | Por pagina — claro |

**Hallazgos Pagebar:**
- **Friccion #17:** Acciones aparecen/sedesvanecen segun seleccion — no es claro por que
- **Friccion #18:** Iconos de cmdTrastienda (🌐) y cmdRelease (🎯) no son semanticamente claros
- **Friccion #19:** cmdDeselect dice "Borrar" en lugar de "Deseleccionar"
- **Friccion #20:** cmdSelCount no es visible sin seleccion — no hay feedback de estado

---

## La Pantalla

| ID | Tipo | HTML (linea) | Handler | Feedback Actual | Carga Cognitiva | Friccion |
|----|------|--------------|---------|----------------|-----------------|---------|
| PT-001 | button | 149 | data-close | hover: ? | 1 (close) | OK |
| PT-002 | div | 151 | - | - | Varia por vista | Contenido |
| PT-003 | button | 150 | data-close | hover: ? | 1 | Icono X claro |

**Vistas de La Pantalla:**
- **Detail:** ~20 elementos de informacion
- **Txn:** Tabla de transacciones
- **Scene:** Animacion de deposito
- **Log:** Log de la cuenta

**Hallazgos La Pantalla:**
- **Friccion #21:** No hay forma obvia de cambiar entre vistas (detail/txn/scene/log)
- **Friccion #22:** Vista Detail tiene ~20 elementos — carga cognitiva alta
- **Friccion #23:** No hay boton "Depositar" en La Pantalla para flujo rapido

---

## Drawer Depositos

### Header

| ID | Tipo | HTML (linea) | Handler | Feedback Actual | Carga Cognitiva | Friccion |
|----|------|--------------|---------|----------------|-----------------|---------|
| DP-001 | button | 897 | - | hover: ? | 4 (title + tabs + collapse + close) | Tabs no son obvios |
| DP-002 | button | 898 | tab single | hover: ? | 4 | Icono ⚡ claro |
| DP-003 | button | 899 | tab multi | hover: ? | 4 | Icono 👥 claro |
| DP-004 | button | 900 | tab schedule | hover: ? | 4 | Icono ⏰ claro |
| DP-005 | button | 901 | collapse | hover: ? | 4 | Icono » no es claro |
| DP-006 | button | 902 | close | hover: ? | 4 | Icono × claro |

### Body

| ID | Tipo | HTML (linea) | Handler | Feedback Actual | Carga Cognitiva | Friccion |
|----|------|--------------|---------|----------------|-----------------|---------|
| DP-007 | div | 905 | - | - | 10+ | Help banner — texto largo |
| DP-008 | div | 909-918 | - | - | 10+ | Target (cuenta) |
| DP-009 | input | 935 | depCardPipe | focus: ? | 10+ | Placeholder formato no claro |
| DP-010 | div | 936 | depCardErr | - | 10+ | Error message |
| DP-011 | div | 940-943 | - | - | 10+ | Saved cards (chips) |
| DP-012 | div | 933-937 | - | - | 10+ | Card section |
| DP-013 | div | 957-968 | - | - | 10+ | Amount section |
| DP-014 | button | 959-964 | dep-amt | hover: ? | 10+ | 6 presets de monto |
| DP-015 | input | 967 | depCustomAmount | focus: ? | 10+ | Custom amount |
| DP-016 | div | 971-977 | - | - | 10+ | Schedule reps |
| DP-017 | button | 981-986 | dep-step-btn | hover: ? | 10+ | Stepper buttons |
| DP-018 | div | 981-1002 | - | - | 10+ | Phase stepper |
| DP-019 | div | 1005-1023 | - | - | 10+ | Scheduled run info |
| DP-020 | div | 1026 | - | - | 10+ | Result/feed |
| DP-021 | div | 1029-1054 | - | - | 10+ | Matchmaker view |

### Footer

| ID | Tipo | HTML (linea) | Handler | Feedback Actual | Carga Cognitiva | Friccion |
|----|------|--------------|---------|----------------|-----------------|---------|
| DP-022 | button | 1059 | depExec | hover: ? | 3 | "🚀 Ejecutar" — no es claro que hace |
| DP-023 | button | 1060 | depCancel | hover: ? | 3 | "⏹ Detener" — claro |
| DP-024 | button | 1061 | depSchedCancel | hover: ? | 3 | "⏹ Cancelar mision" — claro |

**Hallazgos Drawer Depositos:**
- **Friccion #24:** ~25 controles en un panel de 440px — SOBRECARGA COGNITIVA
- **Friccion #25:** Input de tarjeta no valida formato en tiempo real
- **Friccion #26:** Placeholder "4242424242424242|1228|123" no explica el formato
- **Friccion #27:** 6 presets de monto + custom — demasiado opciones
- **Friccion #28:** Boton Ejecutar no explica que pasara al clickear
- **Friccion #29:** Diferencia entre modos (single/multi/schedule) no es clara
- **Friccion #30:** Collapse button (») no es semanticamente claro

---

## Modal Depositos Legacy

| ID | Tipo | HTML (linea) | Handler | Feedback Actual | Carga Cognitiva | Friccion |
|----|------|--------------|---------|----------------|-----------------|---------|
| DM-001 | template | 974-1044 | - | - | - | **DEBE ELIMINARSE** — split-brain con drawer |

**Hallazgos:**
- **Friccion #31:** Código muerto que aumenta complejidad
- **Accion:** Eliminar template y referencias

---

## Resumen de Fricciones

### Criticas (⭐⭐⭐⭐⭐) — Impacto Alto + Urgencia Alta

| # | Descripcion | Componentes Afectados | Solucion Propuesta |
|---|-------------|---------------------|-------------------|
| 1 | Drawer depositos con ~25 controles | DP-001 a DP-024 | Agrupar en pasos, ocultar avanzadas |
| 2 | Flujo Cuentas -> Depositar no claro | TR-001, PT-001, DP-001 | Boton Depositar en La Pantalla |
| 3 | Input tarjeta formato ambiguo | DP-009 | Validacion en tiempo real + ayuda |
| 4 | No hay indicador de filtros activos | FB-001 a FB-016 | Badge de filtros + Limpiar todo |
| 5 | Headers de tabla no indican sort | TH-001 a TH-006 | Icono de sort (↕) |

### Importantes (⭐⭐⭐⭐) — Impacto Medio/Alto

| # | Descripcion | Componentes Afectados | Solucion Propuesta |
|---|-------------|---------------------|-------------------|
| 6 | Sidebar grupo Monitoreo: 5 elementos | SB-004 a SB-008 | Reducir a 4 o agrupar |
| 7 | Iconos JWT no claros | FB-012, FB-013, TR-007 | Tooltip + texto |
| 8 | Grade bar sin explicacion | TR-002 | Tooltip A/B/C/D |
| 9 | Acciones pagebar no claras | PB-005, PB-006, PB-007 | Tooltips + iconos mejores |
| 10 | Motion en periferia distrae | SB-013, DP-? | Pausar cuando no en foco |

### Menores (⭐⭐⭐) — Impacto Bajo

| # | Descripcion | Componentes Afectados | Solucion Propuesta |
|---|-------------|---------------------|-------------------|
| 11 | Multiples badges notificacion | SB-006, SB-007, SB-008 | Consolidar en uno |
| 12 | Divisor arrastrable no obvio | LP-003 | Tooltip + cursor:grab |
| 13 | Navegacion La Pantalla no clara | PT-001, PT-002 | Tabs visibles |
| 14 | CmdDeselect dice "Borrar" | PB-007 | Cambiar a "Deseleccionar" |
| 15 | Modal legacy existe | DM-001 | Eliminar |

---

## Metricas del Inventario

- **Total elementos interactivos:** 80+
- **Botones:** ~50
- **Inputs/Selects:** ~10
- **Links:** ~5
- **Elementos con friccion identificada:** 31
- **Fricciones criticas:** 5
- **Fricciones importantes:** 5
- **Fricciones menores:** 5

---

## Recomendaciones de Priorizacion

### Fase 1: Eliminar Fricciones Criticas (5)
1. Simplificar drawer depositos (⭐⭐⭐⭐⭐)
2. Clarificar flujo Cuentas -> Depositar (⭐⭐⭐⭐⭐)
3. Validacion input tarjeta (⭐⭐⭐⭐)
4. Badge de filtros activos (⭐⭐⭐⭐)
5. Iconos de sort en tabla (⭐⭐⭐⭐)

### Fase 2: Resolver Fricciones Importantes (5)
1. Sidebar grupo Monitoreo (⭐⭐⭐⭐)
2. Iconos JWT claros (⭐⭐⭐⭐)
3. Grade bar tooltip (⭐⭐⭐⭐)
4. Pagebar acciones claras (⭐⭐⭐⭐)
5. Motion en periferia (⭐⭐⭐⭐)

### Fase 3: Pulir (5+)
- Consolidar badges
- Divisor arrastrable
- Navegacion La Pantalla
- Eliminar modal legacy
- etc.

---

**Documento generado:** 2026-07-20  
**Version:** 1.0  
**Proximo paso:** Validar con Robert y priorizar

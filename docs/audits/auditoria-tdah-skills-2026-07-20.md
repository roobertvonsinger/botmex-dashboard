---
name: auditoria-tdah-skills-2026-07-20
description: Skills especializadas para auditoria TDAH/ADHD-friendly
---

# Skills para Auditoria TDAH/ADHD-Friendly

**Fecha:** 2026-07-20
**Proposito:** Definir habilidades especializadas para la auditoria

---

## Skills Core (Cargar al inicio)

### 1. adhd-design-expert
**Rol:** Lente de neurociencia y TDAH

**Responsabilidades:**
- Validar que cada decision de diseno considera TDAH
- Asegurar carga cognitiva <= 4+1 elementos
- Verificar senales preatencionales (color, motion, glow)
- Garantizar tolerancia al error (poka-yoke)
- Reducir decisiones para evitar paralisis por analisis

**Criterios de aceptacion:**
- [ ] Cada vista tiene <= 4+1 elementos compitiendo por atencion
- [ ] Informacion critica siempre es visible y resaltada
- [ ] Flujo principal (Cuentas -> Depositar) tiene <= 3 pasos
- [ ] No hay controles que puedan usarse mal por accidente

**Herramientas:**
- Ley de Cowan 2001 (4+1)
- Principios poka-yoke
- Heuristicas de Nielsen para TDAH

---

### 2. ux-friction-analyzer
**Rol:** Diagnostico de friccion por interaccion

**Responsabilidades:**
- Identificar puntos de friccion en cada interaccion
- Validar que cada cambio QUITA friccion (no la mueve)
- Medir impacto de cambios en usabilidad
- Asegurar consistencia en patrones de interaccion

**Criterios de aceptacion:**
- [ ] Cada control tiene feedback visual claro
- [ ] Cada accion es descubrible sin leer docs
- [ ] Cada flujo es <= 3 clicks para tarea comun
- [ ] No hay "puntos ciegos" (info critica oculta)

**Herramientas:**
- Analisis de task completion time
- Heatmap mental de interacciones
- Walkthrough de tareas comunes

---

### 3. web-motion-design
**Rol:** Motion smoothness y accesibilidad

**Responsabilidades:**
- Asegurar 60fps en todas las animaciones
- Respetar `prefers-reduced-motion` en TODOS los elementos
- Verificar que animaciones guian (no distraen)
- Optimizar performance de animaciones

**Criterios de aceptacion:**
- [ ] 0 frame drops en DevTools Performance
- [ ] Todas las animaciones infinitas respetan reduce-motion
- [ ] Animaciones funcionales (feedback) siempre activas
- [ ] Animaciones decorativas pausables

**Herramientas:**
- Chrome DevTools Performance
- `prefers-reduced-motion` media query
- requestAnimationFrame optimization

---

### 4. design-engineer
**Rol:** Craft de micro-interacciones

**Responsabilidades:**
- Implementar focus rings consistentes
- Crear glow states para info critica
- Asegurar transiciones suaves
- Mantener consistencia visual

**Criterios de aceptacion:**
- [ ] Todos los controles tienen :focus-visible
- [ ] Focus ring = 2px solid var(--accent)
- [ ] Transiciones usan easing consistente
- [ ] Glow states no compiten entre si

**Herramientas:**
- CSS custom properties (tokens)
- cubic-bezier easing functions
- box-shadow/outline para focus

---

### 5. frontend-design
**Rol:** Estetica premium bespoke

**Responsabilidades:**
- Mantener tema obsidian-glass
- Asegurar jerarquia visual clara
- Usar tokens de diseno consistentes
- Evitar "templated look"

**Criterios de aceptacion:**
- [ ] Paleta de colores consistente
- [ ] Tipografia jerarquizada
- [ ] Espaciado basado en grid de 4px
- [ ] No hay colores hardcoded

**Herramientas:**
- OKLCH color space
- CSS Grid/Flexbox
- Design tokens en :root

---

## Skills de Soporte

### 6. superpowers:verification-before-completion
**Rol:** Validacion objetiva antes de declarar "done"

**Responsabilidades:**
- Verificar con grep (no a ojo)
- Usar DevTools para mediciones
- Capturar screenshots antes/despues
- Documentar evidencia

**Metodos:**
```bash
# Contraste
grep -rn "rgba(255,255,255,0.06)" static/

# Focus visible
grep -rn ":focus-visible" static/

# Reduced motion
grep -rn "prefers-reduced-motion" static/

# Touch targets
document.querySelectorAll('button, [role="button"]').forEach(el => {
  const rect = el.getBoundingClientRect();
  if (rect.width < 44 || rect.height < 44) console.warn(el);
});
```

---

### 7. superpowers:systematic-debugging
**Rol:** Debugging estructurado

**Responsabilidades:**
- Identificar root cause (no parches)
- Usar metodo cientifico
- Documentar soluciones
- Prevenir regresiones

**Metodo:**
1. Reproducir el issue
2. Aislar variables
3. Testear hipotesis
4. Implementar fix
5. Verificar solucion

---

### 8. superpowers:executing-plans (BLOCKING)
**Rol:** Orquestacion de la sesion

**Responsabilidades:**
- Despachar subagentes
- Monitorear progreso
- Asegurar checkpoints
- Manejar loops y vigilancia

**Configuracion:**
```
Sesion conductora: Sonnet 5
Subagentes Haiku: tareas mecanicas (CSS, HTML, grep)
Subagentes Sonnet: tareas logicas (JS, decisiones)
```

---

### 9. botmex-bitacora (BLOCKING)
**Rol:** Documentacion obligatoria

**Responsabilidades:**
- Actualizar `docs/FRONTEND.md` ANTES de cada commit
- Documentar decisiones de diseno
- Mantener historial de cambios
- Asegurar que docs refleja codigo real

**BLOCKING:** No se aceptan commits sin docs actualizado

---

## Matriz de Skills por Task

| Task | Skill Principal | Skills de Soporte | Modelo |
|------|-----------------|------------------|--------|
| Tooltips contextuales | frontend-design | ux-friction-analyzer | Haiku |
| Iconos de sort | design-engineer | ux-friction-analyzer | Haiku |
| Badge filtros activos | frontend-design | adhd-design-expert | Haiku |
| Feedback seleccion | design-engineer | adhd-design-expert | Haiku |
| Validacion tarjeta | ux-friction-analyzer | design-engineer | Sonnet |
| Flujo Cuentas->Depositar | adhd-design-expert | ux-friction-analyzer | Sonnet |
| Simplificar drawer | adhd-design-expert | frontend-design | Sonnet |
| Unificar tokens | frontend-design | design-engineer | Haiku |
| Reducir motion | web-motion-design | adhd-design-expert | Haiku |
| Jerarquia visual | frontend-design | adhd-design-expert | Haiku |
| Eliminar modal legacy | - | - | Haiku |

---

## Checklist de Skills por Fase

### Fase 0: Preparacion
- [ ] adhd-design-expert cargada
- [ ] ux-friction-analyzer cargada
- [ ] web-motion-design cargada
- [ ] design-engineer cargada
- [ ] frontend-design cargada
- [ ] superpowers:executing-plans cargada
- [ ] botmex-bitacora cargada (BLOCKING)

### Fase 1: Quick Wins
- [ ] frontend-design aplicada
- [ ] design-engineer aplicada
- [ ] ux-friction-analyzer aplicada
- [ ] adhd-design-expert consultada
- [ ] botmex-bitacora actualizada (BLOCKING)

### Fase 2: Puntos Criticos
- [ ] adhd-design-expert aplicada
- [ ] ux-friction-analyzer aplicada
- [ ] design-engineer aplicada
- [ ] botmex-bitacora actualizada (BLOCKING)

### Fase 3: Pulido
- [ ] web-motion-design aplicada
- [ ] frontend-design aplicada
- [ ] adhd-design-expert consultada
- [ ] botmex-bitacora actualizada (BLOCKING)

---

## Validacion de Skills

Al final de cada fase, verificar:

1. **adhd-design-expert:**
   - [ ] Carga cognitiva <= 4+1 en vistas principales
   - [ ] Senales preatencionales presentes
   - [ ] Tolerancia al error implementada

2. **ux-friction-analyzer:**
   - [ ] Puntos de friccion identificados y resueltos
   - [ ] Cada cambio quita friccion (no la mueve)
   - [ ] Flujo principal optimizado

3. **web-motion-design:**
   - [ ] 60fps en todas las animaciones
   - [ ] prefers-reduced-motion respetado
   - [ ] 0 frame drops

4. **design-engineer:**
   - [ ] Focus visible en todos los controles
   - [ ] Transiciones suaves
   - [ ] Feedback visual claro

5. **frontend-design:**
   - [ ] Tema consistente
   - [ ] Jerarquia visual clara
   - [ ] Tokens usados (no hardcoded)

---

**Documento generado:** 2026-07-20
**Uso:** Cargar al inicio de la sesion de auditoria

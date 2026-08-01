# Design Spec: Integración de Graphify MCP en Workflow Dev Chief

**Fecha:** 2026-08-01  
**Estado:** Aprobado por Dev Chief  
**Objetivo:** Integrar `Graphify` como servidor MCP global para permitir a Claude Code y subagentes realizar consultas de arquitectura y dependencias en tiempo real sin inflar el contexto con índices estáticos.

---

## 1. Visión General
Sustituir la lectura/mantenimiento manual de mapas estáticos por un Grafo de Dependencias dinámico y ejecutable vía MCP.

## 2. Componentes

### 2.1 Instalación Global
- Instalación de paquete `graphifyy` en el sistema local.
- Disponibilidad del CLI `graphify` en el PATH de Windows.

### 2.2 Servidor MCP Global (`~/.claude/settings.json`)
- Registro de `graphify mcp` en la configuración global de Claude.
- Disponible automáticamente para la sesión principal y cualquier subagente generado.

### 2.3 Generación del Grafo (`.graphify/`)
- Construcción local con `graphify .` en la raíz del repositorio (`repos/botmex-dashboard`).
- Generación de `.graphify/`, `graph.json`, y `GRAPH_REPORT.md`.
- Exclusión de `.graphify/` en `.gitignore` para mantener el repo limpio.

## 3. Flujo de Trabajo del Agente

1. **Escaneo inicial:** `graphify .` genera o actualiza la topología AST del proyecto.
2. **Consultas MCP bajo demanda:** Cuando el agente necesite analizar impacto de un cambio o entender dependencias, invoca la tool MCP de Graphify (`query`, `path`, `explain`).
3. **Cero contexto inflado:** No se cargan archivos grandes de mapa al inicio de la sesión (`/abrir-bmx`).

## 4. Plan de Despliegue Global
- **Fase 1 (Prueba de concepto):** `botmex-dashboard`.
- **Fase 2 (Escalamiento):** Aplicar patrón en repositorios `ruthopia`, `rita` y monorepo general.

---
*Fin del spec.*

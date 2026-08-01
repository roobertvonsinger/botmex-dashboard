# Graphify MCP Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install `graphifyy`, register its MCP server globally in `~/.claude/settings.json`, and build the initial codebase graph for `botmex-dashboard`.

**Architecture:** Global Python CLI installation (`graphifyy`) connected via Claude Code MCP server configuration. Local graph stored in `.graphify/`.

**Tech Stack:** Python, Tree-sitter (via Graphify), JSON (settings.json), PowerShell.

## 🤖 Orquestación de Agentes y Modelos

| Tarea | Agente / Modelo Recomendado | Justificación |
|---|---|---|
| **Task 1: Install Graphify CLI** | Haiku 4.5 (`claude-haiku-4-5-20251001`) | Tarea 100% mecánica (ejecutar pip / verificación de comandos). |
| **Task 2: Configure Global MCP** | Haiku 4.5 (`claude-haiku-4-5-20251001`) | Edición y fusión de JSON simple en `settings.json`. |
| **Task 3: Build Graph & Gitignore** | Haiku 4.5 (`claude-haiku-4-5-20251001`) | Ejecución de `graphify .` y commit en git. |

### 🔁 Loops y Vigilancia Anti-Cuelgue
- **Loop de Instalación (Task 1):** `pip install` → verificación `graphify --help`. Exit condition: comando disponible en PATH. Max retries: 2.
- **Loop de Grafo (Task 3):** `graphify .` → exit condition: presencia de `.graphify/` y `graph.json`. Timeout: 60s.

## Global Constraints
- Must not bloat session startup context.
- `.graphify/` build folder must be git-ignored.
- Settings update must be non-destructive to existing `settings.json` keys.

---

### Task 1: Install Graphify CLI Globally

**Model:** Haiku 4.5 (`claude-haiku-4-5-20251001`)

**Files:**
- System Environment: Python environment / PATH

**Interfaces:**
- Consumes: `pip` / `uv`
- Produces: Global executable `graphify`

- [ ] **Step 1: Check if graphify is installed**

Run: `Get-Command graphify -ErrorAction SilentlyContinue`
Expected: Empty output if not installed.

- [ ] **Step 2: Install graphifyy via pip**

Run: `pip install graphifyy`
Expected: Successfully installed graphifyy.

- [ ] **Step 3: Verify binary execution**

Run: `graphify --help`
Expected: Help output showing commands (`build`, `query`, `mcp`, etc.).

---

### Task 2: Configure Global MCP Server in `~/.claude/settings.json`

**Model:** Haiku 4.5 (`claude-haiku-4-5-20251001`)

**Files:**
- Modify: `C:\Users\rober\.claude\settings.json`

**Interfaces:**
- Consumes: `graphify mcp` CLI
- Produces: MCP server block `graphify` in Claude settings

- [ ] **Step 1: Read existing settings.json**

Read `C:\Users\rober\.claude\settings.json` to verify current structure.

- [ ] **Step 2: Add graphify entry under `mcpServers`**

Merge:
```json
"mcpServers": {
  "graphify": {
    "command": "graphify",
    "args": ["mcp"]
  }
}
```

- [ ] **Step 3: Save and verify JSON validity**

Verify `settings.json` parses cleanly without syntax errors.

---

### Task 3: Build Initial Graph & Update `.gitignore`

**Model:** Haiku 4.5 (`claude-haiku-4-5-20251001`)

**Files:**
- Create/Generate: `.graphify/`, `graph.json`, `GRAPH_REPORT.md`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: Local codebase AST
- Produces: `.graphify/` local cache

- [ ] **Step 1: Update `.gitignore`**

Append `.graphify/` to `.gitignore` if not present.

- [ ] **Step 2: Run graphify build**

Run: `graphify .`
Expected: AST scanning completes and generates `.graphify/` and `graph.json`.

- [ ] **Step 3: Commit .gitignore update**

```bash
git add .gitignore
git commit -m "chore: add .graphify/ to gitignore"
```

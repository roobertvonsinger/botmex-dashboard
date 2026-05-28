#!/usr/bin/env python3
"""
Regenera las secciones [AUTO] de MAP.md escaneando el repo con AST.
Bloques entre <!-- GEN:start:X --> y <!-- GEN:end:X --> se reemplazan.
El resto de MAP.md queda intacto (secciones [MANUAL]).

Uso: python scripts/gen_map.py
     (el pre-commit hook lo corre automáticamente)
"""
import ast
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MAP_PATH = REPO_ROOT / "MAP.md"

def _collect_modules():
    mods = list(REPO_ROOT.glob("*.py"))
    for subdir in ("shared", "scripts"):
        d = REPO_ROOT / subdir
        if d.exists():
            mods.extend(d.glob("*.py"))
    return sorted(mods)

PY_MODULES = _collect_modules()


# ── Extractores ──────────────────────────────────────────────────────────────

def _read(path):
    return path.read_text(encoding="utf-8", errors="replace")


def extract_symbols(path):
    """Funciones/clases top-level con su rango de líneas."""
    try:
        tree = ast.parse(_read(path))
    except SyntaxError:
        return []
    results = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            results.append((node.name, "def", node.lineno, node.end_lineno))
        elif isinstance(node, ast.ClassDef):
            results.append((node.name, "class", node.lineno, node.end_lineno))
    return results


def extract_env_vars(path):
    """os.getenv('VAR', default) → (VAR, default)."""
    src = _read(path)
    pattern = r'os\.getenv\(\s*["\'](\w+)["\'](?:\s*,\s*([^)\n]+))?\s*\)'
    return [(m[0], m[1].strip() if m[1] else "—") for m in re.findall(pattern, src)]


def extract_loggers(path):
    """getLogger('name') → name."""
    return re.findall(r'getLogger\(\s*["\']([^"\']+)["\']\s*\)', _read(path))


def extract_endpoints(path):
    """@app.METHOD('/route') → (method, route)."""
    src = _read(path)
    pattern = r'@(?:app|router)\.(get|post|put|delete|patch|websocket)\(\s*["\']([^"\']+)["\']'
    return re.findall(pattern, src)


# ── Generadores de sección ────────────────────────────────────────────────────

def gen_modulos():
    rows = ["| Módulo | L# | Logger | Propósito |",
            "|--------|----|---------|-----------| "]
    for p in PY_MODULES:
        rel = p.relative_to(REPO_ROOT).as_posix()
        lcount = len(_read(p).splitlines())
        loggers = extract_loggers(p)
        logger_str = loggers[0] if loggers else "—"
        rows.append(f"| `{rel}` | {lcount} | `{logger_str}` | _[completar]_ |")
    return "\n".join(rows)


def gen_simbolos():
    blocks = []
    for p in PY_MODULES:
        syms = extract_symbols(p)
        if not syms:
            continue
        rel = p.relative_to(REPO_ROOT).as_posix()
        blocks.append(f"\n### `{rel}`\n")
        blocks.append("| Símbolo | Tipo | Líneas |")
        blocks.append("|---------|------|--------|")
        for name, kind, start, end in syms:
            blocks.append(f"| `{name}` | {kind} | L{start}–L{end} |")
    return "\n".join(blocks)


def gen_endpoints():
    rows = ["| Método | Ruta | Módulo |",
            "|--------|------|--------|"]
    for p in PY_MODULES:
        for method, route in extract_endpoints(p):
            rel = p.relative_to(REPO_ROOT).as_posix()
            rows.append(f"| `{method.upper()}` | `{route}` | `{rel}` |")
    if len(rows) == 2:
        rows.append("| — | — | — |")
    return "\n".join(rows)


def gen_env():
    seen: dict[str, tuple[str, str]] = {}
    for p in PY_MODULES:
        rel = p.relative_to(REPO_ROOT).as_posix()
        for var, default in extract_env_vars(p):
            if var not in seen:
                seen[var] = (default, rel)
    rows = ["| Variable | Default | Definida en |",
            "|----------|---------|-------------|"]
    for var, (default, src) in sorted(seen.items()):
        rows.append(f"| `{var}` | `{default}` | `{src}` |")
    if len(rows) == 2:
        rows.append("| — | — | — |")
    return "\n".join(rows)


def gen_loggers():
    seen: dict[str, str] = {}
    for p in PY_MODULES:
        rel = p.relative_to(REPO_ROOT).as_posix()
        for lg in extract_loggers(p):
            seen[lg] = rel
    rows = ["| Logger | Módulo |",
            "|--------|--------|"]
    for lg, src in sorted(seen.items()):
        rows.append(f"| `{lg}` | `{src}` |")
    if len(rows) == 2:
        rows.append("| — | — |")
    return "\n".join(rows)


# ── Secciones registradas ─────────────────────────────────────────────────────

SECTIONS = {
    "modulos":   gen_modulos,
    "simbolos":  gen_simbolos,
    "endpoints": gen_endpoints,
    "env":       gen_env,
    "loggers":   gen_loggers,
}


# ── MAP.md inicial (solo se escribe si no existe) ─────────────────────────────

INITIAL_MAP = """\
# MAP — botmex-dashboard

> `scripts/gen_map.py` regenera las secciones `[AUTO]` en cada commit.
> Editar manualmente **solo** las secciones marcadas `[MANUAL]`.
> Para regenerar ahora: `python scripts/gen_map.py`

---

## Módulos del repo `[AUTO]`

<!-- GEN:start:modulos -->
<!-- GEN:end:modulos -->

---

## Símbolos por módulo — funciones/clases con rango de líneas `[AUTO]`

<!-- GEN:start:simbolos -->
<!-- GEN:end:simbolos -->

---

## Endpoints `[AUTO]`

<!-- GEN:start:endpoints -->
<!-- GEN:end:endpoints -->

---

## Variables de entorno `[AUTO]`

<!-- GEN:start:env -->
<!-- GEN:end:env -->

---

## Loggers disponibles `[AUTO]`

<!-- GEN:start:loggers -->
<!-- GEN:end:loggers -->

---

## Logs — dónde viven `[MANUAL]`

| Log | Path en container | Rotación |
|-----|-------------------|----------|
| Dashboard principal | `/data/logs/dashboard.log` | 10 MB × 3 archivos |
| Tail en vivo (UI) | `GET /api/logs/stream` (SSE) | — |
| Ver en dashboard | Pestaña **Logs** | — |

---

## Directorios críticos `[MANUAL]`

| Directorio | Propósito |
|------------|-----------|
| `/data/` | Volumen Docker — BD SQLite + logs |
| `/data/logs/` | Log files (RotatingFileHandler) |
| `static/` | Frontend (HTML/CSS/JS) |
| `docs/` | Documentación operativa completa |
| `infra/` | Dockerfile + docker-compose.yml |
| `scripts/` | Utilerías dev (recalc_grades, gen_map) |
| `shared/` | Módulos compartidos con bot Telegram |
| `templates/` | Plantilla replicable para otros repos |

---

## Documentación de referencia `[MANUAL]`

| Doc | Qué tiene |
|-----|-----------|
| `docs/ARCHITECTURE.md` | Esquema BD, flujos, decisiones de diseño |
| `docs/ENDPOINTS.md` | Referencia completa de endpoints + params |
| `docs/FRONTEND.md` | Handlers JS, componentes UI, secciones HTML |
| `docs/SSE_EVENTS.md` | Catálogo de eventos SSE (kind, payload) |
| `docs/ERRORS.md` | Errores conocidos: síntoma / causa / fix |
| `docs/AUDIT.md` | Estado por función (✅ ❌ ⚠️ 🔵 ❓) |
| `DEPLOY.md` | Protocolo de deploy a KVM4 |
| `docs/protocols/deploy-checklist.md` | Checklist funcional post-deploy |

---

## Notas de sesión `[MANUAL]`

<!-- Espacio libre para apuntes rápidos de sesión — borrar entre sesiones -->
"""


# ── Core: actualizar MAP.md ───────────────────────────────────────────────────

def update_map():
    if not MAP_PATH.exists():
        MAP_PATH.write_text(INITIAL_MAP, encoding="utf-8")
        print("[gen_map] MAP.md creado (estructura inicial)")

    content = MAP_PATH.read_text(encoding="utf-8")

    for section_id, gen_fn in SECTIONS.items():
        start_tag = f"<!-- GEN:start:{section_id} -->"
        end_tag   = f"<!-- GEN:end:{section_id} -->"
        pattern = re.compile(
            re.escape(start_tag) + r".*?" + re.escape(end_tag),
            re.DOTALL,
        )
        new_block = f"{start_tag}\n{gen_fn()}\n{end_tag}"
        if pattern.search(content):
            content = pattern.sub(new_block, content)
        else:
            print(f"[gen_map] WARN seccion '{section_id}' no encontrada en MAP.md - ignorada")

    MAP_PATH.write_text(content, encoding="utf-8")
    print(f"[gen_map] OK MAP.md actualizado ({MAP_PATH})")


if __name__ == "__main__":
    update_map()

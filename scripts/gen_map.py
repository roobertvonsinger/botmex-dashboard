#!/usr/bin/env python3
"""
Regenera las secciones [AUTO] de MAP.md escaneando el repo con AST + git.
Bloques entre <!-- GEN:start:X --> y <!-- GEN:end:X --> se reemplazan.
El resto de MAP.md queda intacto (secciones [MANUAL] como propósito, gotchas, flujos).

Uso directo: python scripts/gen_map.py
Pre-commit hook lo corre automáticamente en cada commit.
"""
import ast
import re
import subprocess
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


# ── Extractores ───────────────────────────────────────────────────────────────

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
    """getLogger('name') → name (solo string literals, no __name__)."""
    return re.findall(r'getLogger\(\s*["\']([^"\']+)["\']\s*\)', _read(path))


def extract_endpoints(path):
    """@app.METHOD('/route') o @router.METHOD('/route') → (method, route)."""
    src = _read(path)
    pattern = r'@(?:app|router)\.(get|post|put|delete|patch|websocket)\(\s*["\']([^"\']+)["\']'
    return re.findall(pattern, src)


def extract_constants(path):
    """Constantes UPPERCASE a nivel módulo (no dentro de funciones/clases)."""
    src = _read(path)
    skip = {'__all__', '__version__', '__author__'}
    results = []
    # Solo líneas que empiezan al inicio (no indentadas = nivel módulo)
    for m in re.finditer(r'^([A-Z][A-Z_0-9]{2,})\s*=\s*([^\n#]{1,70})', src, re.MULTILINE):
        name = m.group(1)
        val  = m.group(2).strip().rstrip(',')
        if name not in skip:
            results.append((name, val))
    return results


# ── Leer propósito existente (preservar ediciones manuales) ───────────────────

def _read_existing_propositos():
    """Extrae columna Propósito del bloque GEN:modulos existente para no pisarla."""
    if not MAP_PATH.exists():
        return {}
    content = MAP_PATH.read_text(encoding="utf-8")
    m = re.search(r'<!-- GEN:start:modulos -->(.*?)<!-- GEN:end:modulos -->', content, re.DOTALL)
    if not m:
        return {}
    props = {}
    for line in m.group(1).splitlines():
        if not line.startswith('| `'):
            continue
        parts = [p.strip() for p in line.split('|')]
        # | `mod` | L# | `logger` | propósito |
        if len(parts) >= 5:
            mod  = parts[1].strip('`')
            prop = parts[4]
            if prop and prop != '_[completar]_' and prop != 'Propósito':
                props[mod] = prop
    return props


# ── Generadores de sección ────────────────────────────────────────────────────

def gen_modulos():
    props = _read_existing_propositos()
    rows = ["| Módulo | L# | Logger | Propósito |",
            "|--------|----|---------|-----------| "]
    for p in PY_MODULES:
        rel     = p.relative_to(REPO_ROOT).as_posix()
        lcount  = len(_read(p).splitlines())
        loggers = extract_loggers(p)
        logger_str = loggers[0] if loggers else "—"
        prop    = props.get(rel, '_[completar]_')
        rows.append(f"| `{rel}` | {lcount} | `{logger_str}` | {prop} |")
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


def gen_constantes():
    """Constantes UPPERCASE a nivel módulo en todos los .py."""
    rows = ["| Constante | Valor | Módulo |",
            "|-----------|-------|--------|"]
    for p in PY_MODULES:
        rel = p.relative_to(REPO_ROOT).as_posix()
        for name, val in extract_constants(p):
            rows.append(f"| `{name}` | `{val}` | `{rel}` |")
    if len(rows) == 2:
        rows.append("| — | — | — |")
    return "\n".join(rows)


def gen_recientes():
    """Últimos 15 commits (sin merges)."""
    try:
        result = subprocess.run(
            ['git', 'log', '--oneline', '-15', '--no-merges'],
            capture_output=True, text=True, cwd=str(REPO_ROOT)
        )
        lines = result.stdout.strip().splitlines()
        rows = ["| Hash | Mensaje |", "|------|---------|"]
        for line in lines:
            parts = line.split(' ', 1)
            if len(parts) == 2:
                h, msg = parts
                rows.append(f"| `{h}` | {msg} |")
        return "\n".join(rows)
    except Exception as e:
        return f"_(error git log: {e})_"


# ── Secciones registradas ─────────────────────────────────────────────────────

SECTIONS = {
    "modulos":    gen_modulos,
    "simbolos":   gen_simbolos,
    "endpoints":  gen_endpoints,
    "env":        gen_env,
    "loggers":    gen_loggers,
    "constantes": gen_constantes,
    "recientes":  gen_recientes,
}


# ── MAP.md inicial (solo se escribe si no existe) ─────────────────────────────

INITIAL_MAP = """\
# MAP — botmex-dashboard
### Guía de navegación para agentes IA

> Las secciones `[AUTO]` se regeneran en cada `git commit` via `scripts/gen_map.py`.
> **No editar** esas secciones — se pisarán. Editar solo las `[MANUAL]`.
> Regenerar ahora: `python scripts/gen_map.py`

---

## Si necesitas... (leer primero) `[MANUAL]`

| Si necesitas... | Ve a | Nota |
|-----------------|------|------|
| Modificar flujo de depósito (lógica core) | `deposits.py` | Motor principal |
| Modificar endpoints HTTP de depósito | `web_routes_deposits.py` | FastAPI router |
| Modificar flujo de misiones (batch/scheduled) | `web_routes_missions.py` | 803L, leer reglas al inicio |
| Modificar prewarm | `prewarm.py` + `web_routes_prewarm.py` | |
| Agregar endpoint nuevo | `web_routes_X.py` (crear o editar) + registrar en `app.py` | Ver sección registros en app.py |
| Cambiar pool de proxies / failover | `proxy_pool.py` | `call_with_proxy_failover` es la API recomendada |
| Cambiar lógica de grading de cuentas | `web_grading.py` + `shared/betmexico_payment_analyzer.py` | Algoritmo V10 |
| Cambiar autenticación / sesiones | `auth.py` + `web_auth.py` | |
| Ver logs en vivo (endpoint) | `web_routes_logs.py` L1–L98 | Lee /data/logs/dashboard.log |
| Modificar watchdog de balance | `web_watchdog.py` | Loop background |
| Cambiar BD (schema) | `app.py` `_migrate()` L143–L167 | Migraciones aditivas solo |
| SSE broadcast nuevo evento | `app.py` `_broadcast()` L204–L223 → `docs/SSE_EVENTS.md` | |
| Cambiar caps duros de depósito | `deposits.py` L28–L35 | DEP_MAX_PER_TXN, DEP_MAX_24H, AUTOLOCK_HOURS_* |
| Analizar si una tarjeta está quemada | `shared/betmexico_payment_analyzer.py` | Algoritmo V10 |
| Ver estado funcional de features | `docs/AUDIT.md` | ✅❌⚠️🔵❓ |
| Ver errores conocidos + fix | `docs/ERRORS.md` | |
| Deploy a KVM4 | `DEPLOY.md` + `docs/protocols/deploy-protocol.md` | |
| Ver todos los endpoints documentados | `docs/ENDPOINTS.md` | |

---

## Flujos principales `[MANUAL]`

### Depósito único
```
web_routes_deposits.py → deposits.py (_run_deposit)
  → betmexico_login_api (JWT/login) [bot dep]
  → proxy_pool.py (call_with_proxy_failover)
  → CapMonster API (captcha)
  → BetMexico API (BeginDeposit → makePayment → verify)
  → web_grading.py (recalc_grade_from_db)
  → app.py _broadcast() → SSE al frontend
```

### Misión batch (matchmaker)
```
web_routes_missions.py → deposits.py _run_deposit (por cada cuenta×tarjeta)
  Regla: max 5 cuentas × 5 tarjetas, gap 3-8s
  APROBADA → vincular tarjeta↔cuenta
  Rechazo específico → marcar tarjeta, siguiente
  Gateway 5xx ×2 → PAUSE TOTAL
```

### Misión programada (scheduled)
```
web_routes_missions.py → loop: cada 60s → deposits.py _run_deposit
  APROBADO → completed
  Rechazo → STOP inmediato (no reintentar sin override manual)
  Captcha pool: tokens se prefetchean, evitar tokens expirados (TOKEN_MAX_AGE=55s)
```

### Prewarm
```
web_routes_prewarm.py → prewarm.py
  Cap: max 30 pre-warms/operador en últimos 10 min
  Skip si JWT vigente AND last_check < 5 min
  Timeout 25s por task. Logs en process_log (process_type='prewarm')
```

---

## Gotchas críticos — no repetir `[MANUAL]`

| # | Síntoma / Error | Causa raíz | Fix / Dónde está |
|---|-----------------|------------|------------------|
| 1 | SSE no llega al frontend aunque backend emite | Doble-import de `app.py` crea dos instancias de `_sse_queues` | Fix en `app.py` L18-32: `sys.modules.setdefault("app", sys.modules[__name__])` |
| 2 | 406 FAILURE_IN_CAPTCHA masivo (desde build v26.5.25) | BetMexico migró a reCAPTCHA **v3**; nosotros mandábamos v2 | `deposits.py` usa `RECAPTCHA_V2_SITE_KEY` — actualizar a v3 key `6LdoqOUk...` |
| 3 | Logs no cargan en dashboard tras restart container | Antes usaba journalctl (systemd, VPS). KVM4 es Docker sin systemd | Fix en `app.py` L40-62: RotatingFileHandler a `/data/logs/dashboard.log` |
| 4 | Token captcha expirado en scheduled después de sleep(60) | TOKEN_MAX_AGE=55s, sleep 60 → token viejo al despertar | Pool prefetchea tokens; ver `deposits.py` sección captcha pool |
| 5 | `create_task(gather())` crashea en Py3.11+ | Bug de asyncio en multi-depósito | Fix aplicado en `web_routes_deposits.py` |
| 6 | BANK_REJECTED confundido con error de captcha | Son cosas distintas: BANK_REJECTED = banco rechazó la tarjeta | No reintentar en BANK_REJECTED; ver `deposits.py` lógica de rechazo |
| 7 | Proxy LitPort siempre falla (0% éxito) | Reputación IP baja para BetMexico | Excluido via `_EXCLUDED_PROXY_HOSTS` en `proxy_pool.py` |

---

## Módulos — propósito + métricas `[AUTO métricas / MANUAL propósito]`

> Edita la columna **Propósito** directamente aquí. El script preserva tus ediciones.

<!-- GEN:start:modulos -->
<!-- GEN:end:modulos -->

---

## Constantes críticas del sistema `[AUTO]`

<!-- GEN:start:constantes -->
<!-- GEN:end:constantes -->

---

## Cambios recientes `[AUTO]`

<!-- GEN:start:recientes -->
<!-- GEN:end:recientes -->

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
| Logger raíz del dashboard | `betmexico.dashboard` | en app.py L47 |

---

## Directorios críticos `[MANUAL]`

| Directorio (container) | Propósito |
|------------------------|-----------|
| `/data/` | Volumen Docker persistente — BD + logs |
| `/data/logs/` | Log files (RotatingFileHandler) |
| `/data/betmexico_accounts.db` | BD SQLite principal (misma que usa el bot TG) |
| `static/` | Frontend: `index.html`, `app.js`, `style.css` |
| `docs/` | Documentación operativa completa |
| `infra/` | `Dockerfile` + `docker-compose.yml` |
| `scripts/` | Utilerías dev (`recalc_grades.py`, `gen_map.py`) |
| `shared/` | Módulos compartidos con bot Telegram |

---

## Docs de referencia `[MANUAL]`

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
| `docs/diagrams/` | Flujos Mermaid: deposit-single, deposit-multi, sse-bus, infra |

---

## Notas de sesión `[MANUAL]`

<!-- Apuntes rápidos de sesión activa — borrar entre sesiones -->
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

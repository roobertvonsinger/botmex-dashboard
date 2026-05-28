#!/usr/bin/env python3
"""
Genera/actualiza dos archivos de navegación para agentes IA:

  MAP.md       — guía rápida (leer siempre al iniciar sesión, ~200 líneas)
  MAP_DEEP.md  — mapa de funciones/endpoints (leer solo al navegar un módulo)

Uso: python scripts/gen_map.py
Pre-commit hook lo corre automáticamente y agrega ambos al commit.
"""
import ast
import re
import subprocess
from pathlib import Path

REPO_ROOT  = Path(__file__).resolve().parent.parent
MAP_PATH   = REPO_ROOT / "MAP.md"
DEEP_PATH  = REPO_ROOT / "MAP_DEEP.md"


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
    src = _read(path)
    pattern = r'os\.getenv\(\s*["\'](\w+)["\'](?:\s*,\s*([^)\n]+))?\s*\)'
    return [(m[0], m[1].strip() if m[1] else "—") for m in re.findall(pattern, src)]


def extract_loggers(path):
    return re.findall(r'getLogger\(\s*["\']([^"\']+)["\']\s*\)', _read(path))


def extract_endpoints(path):
    src = _read(path)
    pattern = r'@(?:app|router)\.(get|post|put|delete|patch|websocket)\(\s*["\']([^"\']+)["\']'
    return re.findall(pattern, src)


def extract_constants(path):
    """Solo constantes con valores primitivos operacionales (números, strings, sets)."""
    src = _read(path)
    results = []
    for m in re.finditer(r'^([A-Z][A-Z_0-9]{2,})\s*=\s*([^\n#]{1,70})', src, re.MULTILINE):
        name = m.group(1)
        val  = m.group(2).strip().rstrip(',')
        if _is_operational_value(val):
            results.append((name, val))
    return results


def _is_operational_value(val):
    """True si el valor es un número, string literal, set de strings, o aritmética simple."""
    v = val.strip()
    if re.match(r'^-?\d', v):        # número / aritmética
        return True
    if v.startswith(('"', "'")):     # string literal
        return True
    if v.startswith('{') and '}' in v:  # set literal
        return True
    return False


# ── Preservar propósito manual en la tabla de módulos ────────────────────────

def _read_existing_propositos():
    """Lee la columna Propósito del bloque GEN:modulos de MAP.md para preservarla."""
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
        if len(parts) >= 5:
            mod  = parts[1].strip('`')
            prop = parts[4]
            if prop and prop not in ('_[completar]_', 'Propósito'):
                props[mod] = prop
    return props


# ── Generadores para MAP.md ───────────────────────────────────────────────────

def gen_modulos():
    props = _read_existing_propositos()
    rows = ["| Módulo | L# | Logger | Propósito |",
            "|--------|----|---------|-----------| "]
    for p in PY_MODULES:
        rel        = p.relative_to(REPO_ROOT).as_posix()
        lcount     = len(_read(p).splitlines())
        loggers    = extract_loggers(p)
        logger_str = loggers[0] if loggers else "—"
        prop       = props.get(rel, '_[completar]_')
        rows.append(f"| `{rel}` | {lcount} | `{logger_str}` | {prop} |")
    return "\n".join(rows)


def gen_constantes():
    """Solo constantes con valores operacionales (números, strings, sets)."""
    rows = ["| Constante | Valor | Módulo |",
            "|-----------|-------|--------|"]
    for p in PY_MODULES:
        rel = p.relative_to(REPO_ROOT).as_posix()
        for name, val in extract_constants(p):
            rows.append(f"| `{name}` | `{val}` | `{rel}` |")
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


def gen_recientes():
    """Últimos 12 commits sin merges."""
    try:
        result = subprocess.run(
            ['git', 'log', '--oneline', '-12', '--no-merges'],
            capture_output=True, text=True, encoding="utf-8", cwd=str(REPO_ROOT)
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


# ── Generadores para MAP_DEEP.md ──────────────────────────────────────────────

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


# ── Registros de secciones ────────────────────────────────────────────────────

MAP_SECTIONS = {
    "modulos":    gen_modulos,
    "constantes": gen_constantes,
    "env":        gen_env,
    "recientes":  gen_recientes,
}

DEEP_SECTIONS = {
    "simbolos":  gen_simbolos,
    "endpoints": gen_endpoints,
    "loggers":   gen_loggers,
}


# ── Contenido inicial (solo si el archivo no existe) ─────────────────────────

INITIAL_MAP = """\
# MAP — botmex-dashboard
### Guía de navegación para agentes IA · lectura obligatoria al iniciar sesión

> Secciones `[AUTO]` se regeneran en cada commit. No editar — se sobreescriben.
> Para navegar funciones específicas dentro de un módulo: leer `MAP_DEEP.md`.
> Regenerar manualmente: `python scripts/gen_map.py`

---

## Si necesitas... `[MANUAL]`

| Si necesitas... | Ve a | Nota |
|-----------------|------|------|
| Modificar flujo de depósito (lógica core) | `deposits.py` | Motor principal |
| Modificar endpoints HTTP de depósito | `web_routes_deposits.py` | FastAPI router |
| Modificar flujo de misiones (batch/scheduled) | `web_routes_missions.py` | 803L, leer reglas al inicio del archivo |
| Modificar prewarm | `prewarm.py` + `web_routes_prewarm.py` | |
| Agregar endpoint nuevo | `web_routes_X.py` + registrar en `app.py` | Grep `include_router` en app.py |
| Cambiar pool de proxies / failover | `proxy_pool.py` | `call_with_proxy_failover` es la API recomendada |
| Cambiar lógica de grading | `web_grading.py` + `shared/betmexico_payment_analyzer.py` | Algoritmo V10 |
| Cambiar autenticación / sesiones | `auth.py` + `web_auth.py` | |
| Ver logs en vivo (endpoint) | `web_routes_logs.py` | Lee `/data/logs/dashboard.log` |
| Modificar watchdog de balance | `web_watchdog.py` | Loop background |
| Cambiar esquema BD | `app.py` → `_migrate()` | Migraciones aditivas solamente |
| Agregar evento SSE | `app.py` → `_broadcast()` + `docs/SSE_EVENTS.md` | |
| Cambiar caps duros de depósito | `deposits.py` L28–L35 | DEP_MAX_PER_TXN, DEP_MAX_24H, AUTOLOCK_HOURS_* |
| Analizar si una tarjeta/pasarela está quemada | `shared/betmexico_payment_analyzer.py` | Algoritmo V10 |
| Ver estado funcional de features | `docs/AUDIT.md` | ✅❌⚠️🔵❓ |
| Ver errores conocidos + fix | `docs/ERRORS.md` | |
| Deploy a KVM4 | `DEPLOY.md` + `docs/protocols/deploy-protocol.md` | |
| Endpoints completos con params | `docs/ENDPOINTS.md` | |
| Mapa de funciones dentro de un módulo | `MAP_DEEP.md` | Solo cuando vas a navegar código interno |

---

## Flujos principales `[MANUAL]`

### Depósito único
```
web_routes_deposits.py → deposits.py (_run_deposit)
  → betmexico_login_api (JWT/login)  [dep del bot, runtime import]
  → proxy_pool.py (call_with_proxy_failover)
  → CapMonster API (reCAPTCHA v3)
  → BetMexico API: BeginDeposit → makePayment → verify
  → web_grading.py (recalc_grade_from_db)
  → app.py _broadcast() → SSE → frontend
```

### Misión batch (matchmaker)
```
web_routes_missions.py → deposits.py _run_deposit (cuenta×tarjeta)
  max 5 cuentas × 5 tarjetas · gap aleatorio 3-8s
  APROBADA → vincular tarjeta↔cuenta
  Rechazo específico (TARJETA_INVALIDA/INSUF/EXPIRED) → marcar tarjeta, siguiente
  Gateway 5xx ×2 → PAUSE TOTAL
```

### Misión programada (scheduled)
```
web_routes_missions.py → loop 60s → deposits.py _run_deposit
  APROBADO → completed
  Rechazo → STOP (no reintentar, requiere override manual)
  Captcha pool prefetchea tokens; TOKEN_MAX_AGE=55s
```

### Prewarm
```
web_routes_prewarm.py → prewarm.py
  Cap: 30 pre-warms/operador/10min · skip si JWT vigente y last_check < 5min
  Timeout 25s/task · logs en process_log (process_type='prewarm')
```

---

## Gotchas críticos — no repetir `[MANUAL]`

| # | Síntoma | Causa raíz | Fix |
|---|---------|------------|-----|
| 1 | SSE no llega al frontend aunque backend emite | Doble-import de `app.py` = dos instancias de `_sse_queues` | `app.py` L18–32: `sys.modules.setdefault("app", sys.modules[__name__])` |
| 2 | 406 FAILURE_IN_CAPTCHA masivo (build v26.5.25+) | BetMexico migró a reCAPTCHA **v3**; enviábamos v2 | `deposits.py`: usar v3 site key `6LdoqOUk...` |
| 3 | Logs no cargan en dashboard tras restart | Antes: journalctl (VPS). KVM4 es Docker sin systemd | `app.py` L40–62: RotatingFileHandler a `/data/logs/dashboard.log` |
| 4 | Token captcha expirado en scheduled | TOKEN_MAX_AGE=55s · sleep(60) = token viejo al despertar | Captcha pool prefetchea; ver `deposits.py` sección "captcha pool" |
| 5 | `create_task(gather())` crashea Py3.11+ | Bug asyncio en multi-depósito | Fix en `web_routes_deposits.py` |
| 6 | BANK_REJECTED ≠ error de captcha | BANK_REJECTED = banco rechazó la tarjeta, no el captcha | No reintentar en BANK_REJECTED |
| 7 | LitPort falla 0% | Reputación IP baja para BetMexico | Excluido via `_EXCLUDED_PROXY_HOSTS` en `proxy_pool.py` |

---

## Módulos `[AUTO métricas / MANUAL propósito]`

> Edita la columna **Propósito** directamente — el script la preserva al regenerar.

<!-- GEN:start:modulos -->
<!-- GEN:end:modulos -->

---

## Constantes operacionales `[AUTO]`

<!-- GEN:start:constantes -->
<!-- GEN:end:constantes -->

---

## Variables de entorno `[AUTO]`

<!-- GEN:start:env -->
<!-- GEN:end:env -->

---

## Cambios recientes `[AUTO]`

<!-- GEN:start:recientes -->
<!-- GEN:end:recientes -->

---

## Logs `[MANUAL]`

| Log | Path (container) | Rotación |
|-----|-----------------|----------|
| Dashboard principal | `/data/logs/dashboard.log` | 10 MB × 3 |
| Tail en vivo | `GET /api/logs/stream` (SSE) | — |
| Logger raíz | `betmexico.dashboard` | `app.py` L47 |

---

## Directorios críticos `[MANUAL]`

| Path (container) | Propósito |
|-----------------|-----------|
| `/data/betmexico_accounts.db` | BD SQLite principal (compartida con bot TG) |
| `/data/logs/` | Log files persistentes (volumen Docker) |
| `static/` | Frontend: index.html, app.js, style.css |
| `docs/` | Documentación operativa completa |
| `infra/` | Dockerfile + docker-compose.yml |
| `shared/` | Módulos compartidos con bot Telegram |

---

## Docs de referencia `[MANUAL]`

| Doc | Qué tiene |
|-----|-----------|
| `docs/ARCHITECTURE.md` | Esquema BD, flujos, decisiones de diseño |
| `docs/ENDPOINTS.md` | Endpoints completos con params y ejemplos |
| `docs/AUDIT.md` | Estado por función (✅ ❌ ⚠️ 🔵 ❓) |
| `docs/ERRORS.md` | Errores conocidos: síntoma / causa / fix |
| `docs/SSE_EVENTS.md` | Catálogo de eventos SSE (kind, payload) |
| `DEPLOY.md` | Deploy a KVM4 |
| `MAP_DEEP.md` | Mapa de funciones por módulo (rangos de líneas) |

---

## Bóveda — código canónico protegido `[MANUAL]`

> Si algo se rompe en el repo activo, aquí está la versión protegida para restaurar.
> **No modificar la Bóveda** — es de solo lectura. Copiar al repo y modificar ahí.

**Path absoluto (Dropbox local):** `C:\\Users\\rober\\Dropbox\\TESTING DEV\\repos\\Boveda\\`
**Path relativo desde repos/:** `../Boveda/` (o `Boveda/` si estás parado en `repos/`)

| Archivo en Bóveda | Descripción |
|-------------------|-------------|
| `Boveda/Ruthopia/RGates/telcel_cipher_v1.0.py` | Cipher canónico Telcel v1.0 (Ruthopia/RGates) |
| `Boveda/Ruthopia/RGates/wabox_bypass_v1.0.py` | Bypass WABox v1.0 (Ruthopia/RGates) |

**Estructura:** `Boveda/<proyecto>/<módulo>/<archivo_vX.Y.py>` — versionado explícito en nombre.

---

## Notas de sesión `[MANUAL]`

<!-- Apuntes rápidos de sesión activa — borrar entre sesiones -->
"""

INITIAL_MAP_DEEP = """\
# MAP_DEEP — botmex-dashboard
### Mapa de funciones por módulo — leer solo cuando navegas código interno

> Generado por `scripts/gen_map.py`. No editar manualmente.
> Regenerar: `python scripts/gen_map.py`
> Para orientación general (flujos, gotchas, módulos): ver `MAP.md`.

---

## Símbolos por módulo `[AUTO]`

Busca el nombre de la función con Ctrl+F y obtén el rango de líneas exacto.

<!-- GEN:start:simbolos -->
<!-- GEN:end:simbolos -->

---

## Endpoints completos `[AUTO]`

<!-- GEN:start:endpoints -->
<!-- GEN:end:endpoints -->

---

## Loggers `[AUTO]`

<!-- GEN:start:loggers -->
<!-- GEN:end:loggers -->
"""


# ── Función core: aplica secciones a un archivo ───────────────────────────────

def _apply_sections(file_path, sections, initial_content):
    if not file_path.exists():
        file_path.write_text(initial_content, encoding="utf-8")
        print(f"[gen_map] {file_path.name} creado")

    content = file_path.read_text(encoding="utf-8")
    for section_id, gen_fn in sections.items():
        start_tag = f"<!-- GEN:start:{section_id} -->"
        end_tag   = f"<!-- GEN:end:{section_id} -->"
        pattern = re.compile(re.escape(start_tag) + r".*?" + re.escape(end_tag), re.DOTALL)
        new_block = f"{start_tag}\n{gen_fn()}\n{end_tag}"
        if pattern.search(content):
            content = pattern.sub(new_block, content)
        else:
            print(f"[gen_map] WARN seccion '{section_id}' no encontrada en {file_path.name}")

    file_path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    _apply_sections(MAP_PATH,  MAP_SECTIONS,  INITIAL_MAP)
    _apply_sections(DEEP_PATH, DEEP_SECTIONS, INITIAL_MAP_DEEP)
    print("[gen_map] OK MAP.md + MAP_DEEP.md actualizados")

"""bet_policy — política centralizada del flujo `/bet` (auto-depósito + matchmaking).

Refactor a nodos (`docs/BET_POLICY.md`): las constantes/umbrales que hoy viven
dispersos como módulo-nivel en `auto_deposit.py` / `deposits.py` se centralizan en
un objeto **congelado** y versionado.

- **FASE 1** entregó el dataclass + `DEFAULT` (defaults = valores exactos actuales
  → cero cambio de conducta).
- **FASE 2** (este archivo): `load_policy()` lee un override en disco
  (`$BET_POLICY_FILE` o `/data/bet_policy.json`), `_SANE_BOUNDS` acota cada campo
  tuneable, `digest()` identifica la política exacta que produjo unos outcomes y el
  CLI `apply()` valida + escribe un diff aprobado.

`load_policy()` **nunca lanza**: sin archivo / JSON malo / versión distinta / valor
fuera de bounds / campo `_LOCKED` → ese aporte se descarta y el campo cae al
default horneado en código.

Campos `_LOCKED`: protegen las invariantes canónicas 4/5/7/10. Ni `load_policy()`
ni el CLI `apply()` ni el `bet_tuner` (FASE 4) los modifican jamás.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

# Versión del esquema de política. Un override de disco con otra versión se ignora
# entero. Subir esto en cada cambio de FORMA del dataclass (campos nuevos/renombrados).
POLICY_VERSION = 2


@dataclass(frozen=True)
class BetPolicyConfig:
    """Snapshot inmutable de la política. Se congela una vez al arranque de la
    misión — un cambio del tuner a mitad de vuelo nunca afecta una misión viva."""

    # ── montos / reintentos ──────────────────────────────────────────────────
    probe_amount: float = 10.0            # D1: probe de matchmaking (dinero real)
    match_transient_retries: int = 4      # reintentos por PAR ante fallo transitorio (nuestro lado)
    transient_backoff_s: int = 25         # espera entre reintentos transitorios (enfría IP en 406)

    # ── FASE 2 (scheduled) — retries por rep (= deposits.SCHED_*) ─────────────
    sched_max_transient_retries: int = 4  # reintentos por REP ante fallo transitorio
    sched_retry_backoff_s: int = 25       # espera entre reintentos de rep
    sched_rep_gap_s: int = 60             # ritmo entre reps exitosas (N×amount/60s, SP-2)
    sched_first_dep_floor_min_s: float = 45.0  # piso anti-fuga antes de la 1a rep (random.uniform lo)
    sched_first_dep_floor_max_s: float = 60.0  # piso anti-fuga antes de la 1a rep (random.uniform hi)

    # ── ritmo anti-rafagueo ──────────────────────────────────────────────────
    mm_cooldown_s: int = 45               # piso entre reusos de la MISMA cuenta
    cross_account_gap_s: int = 5          # respiro entre cuentas DISTINTAS

    # ── topes que protegen invariantes canónicas (_LOCKED) ───────────────────
    account_max_declines_per_run: int = 2      # invariante 5 — anti-taladro de cuenta
    card_max_declines: int = 3                 # invariante 4 — 3 rechazos en 3 cuentas → jubilar tarjeta
    card_max_attempts: int = 3                 # invariante 7 — hasta 3 cuentas A+ por tarjeta vía 3DS
    circuit_breaker_consecutive_429: int = 2   # invariante 10 — 2 cuentas 429 seguidas → abortar

    # ── tope duro de corrida ─────────────────────────────────────────────────
    max_accounts_hard_cap: int = 10      # Robert 2026-08-05: tope duro por corrida


# Campos que el tuner NUNCA toca y que `load_policy()` / `apply()` rechazan de un
# override de disco. Cambiarlos = code review, no un knob.
_LOCKED_FIELDS = frozenset({
    "account_max_declines_per_run",
    "card_max_declines",
    "card_max_attempts",
    "circuit_breaker_consecutive_429",
})


# Rango sano por campo TUNEABLE (todo campo no `_LOCKED` debe tener una entrada —
# lo verifica `tests/test_bet_policy.py`). Un override fuera de rango se descarta y
# ese campo cae al default. `(lo, hi)` inclusivo.
_SANE_BOUNDS: dict[str, tuple[float, float]] = {
    "probe_amount": (5.0, 50.0),
    "match_transient_retries": (1, 12),
    "transient_backoff_s": (5, 180),
    "sched_max_transient_retries": (1, 12),
    "sched_retry_backoff_s": (5, 180),
    "sched_rep_gap_s": (20, 600),
    "sched_first_dep_floor_min_s": (0, 300),
    "sched_first_dep_floor_max_s": (0, 600),
    "mm_cooldown_s": (10, 600),
    "cross_account_gap_s": (0, 120),
    "max_accounts_hard_cap": (1, 25),
}


# Política horneada en código. El shell usa esto como fallback duro.
DEFAULT = BetPolicyConfig()

_POLICY_FILE_ENV = "BET_POLICY_FILE"
_DEFAULT_POLICY_PATH = "/data/bet_policy.json"


def _policy_path() -> Path:
    return Path(os.environ.get(_POLICY_FILE_ENV) or _DEFAULT_POLICY_PATH)


def _field_names() -> set[str]:
    return {f.name for f in dataclasses.fields(BetPolicyConfig)}


def digest(cfg: BetPolicyConfig | None = None) -> str:
    """`sha1[:12]` estable de la política — une outcomes a la config exacta que los
    produjo (columna `auto_missions.policy_digest`). Mismo `cfg` → mismo digest."""
    c = cfg if cfg is not None else DEFAULT
    payload = {f.name: getattr(c, f.name) for f in dataclasses.fields(c)}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]


def _coerce_in_bounds(field: str, value) -> bool:
    """True si `value` es un número (no bool) dentro de `_SANE_BOUNDS[field]`."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    lo_hi = _SANE_BOUNDS.get(field)
    if lo_hi is None:
        return False
    return lo_hi[0] <= value <= lo_hi[1]


def _sanitize_overrides(overrides: dict) -> dict:
    """Filtra un dict de overrides: descarta claves desconocidas, `_LOCKED` y
    valores fuera de `_SANE_BOUNDS`. Devuelve solo los pares aplicables."""
    valid: dict = {}
    names = _field_names()
    for k, v in (overrides or {}).items():
        if k == "version" or k not in names or k in _LOCKED_FIELDS:
            continue
        if not _coerce_in_bounds(k, v):
            continue
        # respeta el tipo declarado del campo (int vs float)
        declared = next(f.type for f in dataclasses.fields(BetPolicyConfig) if f.name == k)
        if declared in ("int", int) and isinstance(v, float) and v.is_integer():
            v = int(v)
        valid[k] = v
    return valid


def load_policy() -> BetPolicyConfig:
    """Lee el override de disco y lo funde sobre `DEFAULT`. NUNCA lanza; cualquier
    problema (sin archivo, JSON malo, versión distinta, todo fuera de bounds) →
    `DEFAULT` horneado. Un campo fuera de bounds cae a su default sin tumbar el
    resto del merge."""
    try:
        raw = json.loads(_policy_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError, TypeError):
        return DEFAULT
    if not isinstance(raw, dict) or raw.get("version") != POLICY_VERSION:
        return DEFAULT
    section = raw.get("policy")
    overrides = section if isinstance(section, dict) else raw
    valid = _sanitize_overrides(overrides)
    if not valid:
        return DEFAULT
    try:
        return dataclasses.replace(DEFAULT, **valid)
    except TypeError:
        return DEFAULT


def apply(proposal_path: str) -> int:
    """CLI: `python -m bet_policy apply <proposal.json>`. Valida el diff propuesto
    contra `_SANE_BOUNDS` + `_LOCKED_FIELDS` y, si algo queda aplicable, lo escribe
    a `_policy_path()` en el formato que lee `load_policy()`. Devuelve 0 si escribió,
    1 si no había nada aplicable, 2 si el archivo no se pudo leer."""
    try:
        prop = json.loads(Path(proposal_path).read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError) as e:
        print(f"[x] no pude leer {proposal_path}: {e}")
        return 2
    section = prop.get("policy") if isinstance(prop, dict) else None
    overrides = section if isinstance(section, dict) else (prop if isinstance(prop, dict) else {})

    names = _field_names()
    accepted: dict = {}
    for k, v in overrides.items():
        if k == "version":
            continue
        if k not in names:
            print(f"  [x] {k}: campo desconocido")
        elif k in _LOCKED_FIELDS:
            print(f"  [x] {k}: campo _LOCKED (protege invariante canonica) - rechazado")
        elif not _coerce_in_bounds(k, v):
            print(f"  [x] {k}={v}: fuera de _SANE_BOUNDS {_SANE_BOUNDS.get(k)}")
        else:
            accepted[k] = v

    if not accepted:
        print("Nada aplicable - no se escribio nada.")
        return 1

    merged = dataclasses.replace(DEFAULT, **_sanitize_overrides(accepted))
    out = {
        "version": POLICY_VERSION,
        "policy": {k: getattr(merged, k) for k in accepted},
        "digest": digest(merged),
    }
    path = _policy_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[ok] aplicado a {path} - {len(accepted)} campo(s), digest {out['digest']}")
    return 0


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3 and sys.argv[1] == "apply":
        raise SystemExit(apply(sys.argv[2]))
    print("uso: python -m bet_policy apply <proposal.json>")
    raise SystemExit(2)

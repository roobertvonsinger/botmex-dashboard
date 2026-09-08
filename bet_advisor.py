"""bet_advisor.py — operador LLM de pre-selección de cuentas para `/bet` (Fase 3).

Qué es
------
El "operador inteligente" que pidió Robert: un asesor consultado en los puntos de
**selección de cuentas** de una misión `/bet` (plan inicial + recálculo dinámico a
mitad de misión), NUNCA en el hot path por-depósito. Devuelve *hints* — un `boost`
por cuenta en `[-3, +3]` — que el núcleo Python determinista puede ignorar. La
autoridad sigue siendo `select_accounts_for_auto` / `bet_retry_policy`.

Garantías
---------
* **Default OFF.** Sin `BET_ADVISOR_ENABLED` en el entorno → `maybe_advise` retorna
  `None` sin tocar red ni BD. El plan queda idéntico al de hoy.
* **Cero PII al 9router.** `_build_advisor_request` arma el payload campo por campo
  (jamás `dict(row)`); `_assert_no_pii` re-escanea y **lanza antes de cualquier
  request** (fail-closed). El fallback `openrouter/free` también es terceros: la
  redacción corre igual.
* **Fallback determinista.** Timeout (6 s), JSON malformado, router caído, respuesta
  con claves raras → `None` → plan determinista. El advisor nunca es load-bearing.
* **Costo medido.** Una fila en `bet_llm_calls` por llamada, incluso los fallos.
  Tokens del evento `done` del stream (medido, no estimado).

Ver `docs/BET_POLICY.md` (Fase 3) y el plan
`~/.claude/plans/como-podriamos-hacer-un-dynamic-cupcake.md`.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import support_llm

logger = logging.getLogger("betmexico.dashboard.bet_advisor")

# Techo duro de latencia: el recálculo dinámico ocurre en el evento de expansión
# de respaldo (una pausa de re-plan que YA existe), donde 6 s caben. Nunca por-depósito.
ADVISOR_TIMEOUT_S = 6.0
BOOST_MIN, BOOST_MAX = -3, 3

# Cadena por defecto: primario y respaldo, ambos $0 en el 9router. Se fija tras
# probar tool-calling contra el router vivo vía BET_ADVISOR_MODEL_CHAIN="a,b,c"
# (mismo patrón que support_llm.SUPPORT_MODEL_CHAIN).
_DEFAULT_CHAIN = ["ag/gemini-3.8-flash-high", "openrouter/openrouter/free"]

# Costo USD por 1k tokens de salida por modelo. Ambos de la cadena default son
# gratuitos en el router → 0.0. Se llena si algún día se mete un modelo pago.
_MODEL_COST_PER_1K: dict[str, float] = {}

# Copia FIEL de support_tools._SENSITIVE_HINTS (ese módulo no está vendored) +
# 3 hints extra para la superficie de este payload. Ningún campo whitelisted de
# `_build_advisor_request` contiene estas subcadenas (ver test_build_request_shape).
_SENSITIVE_HINTS = (
    "password", "jwt", "token", "proxy", "cvv", "card_number",
    "api_key", "secret", "cookie", "authorization", "email", "curp", "phone",
)
_DIGIT_RUN = re.compile(r"\d{13,19}")


def _enabled() -> bool:
    return os.environ.get("BET_ADVISOR_ENABLED", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _chain() -> list[str]:
    raw = os.environ.get("BET_ADVISOR_MODEL_CHAIN", "").strip()
    parsed = [m.strip() for m in raw.split(",") if m.strip()]
    return parsed or list(_DEFAULT_CHAIN)


# ────────────────────────────────────────────────────────────── tipos de datos

@dataclass
class AdvisorInputs:
    """Todo lo que el asesor necesita, YA redactado por el caller.

    `candidates` son dicts con `ref` (opaco, "A0"/"A1"…) + `email` (SOLO para
    traducir de vuelta el resultado; el builder lo descarta) + los ~13 campos
    whitelisted. `cards` con `ref` ("C0"…) + BIN(6) + métricas de BIN.
    """
    candidates: list[dict]
    cards: list[dict]
    mission_meta: dict
    recent_history: dict


@dataclass(frozen=True)
class CleanAdvice:
    boosts: dict            # ref opaco -> int en [-3, 3]
    pairings: tuple         # ((account_ref, card_ref), ...)
    avoid: tuple            # ((ref, why), ...)
    rationale: str

    def boost_map(self, ref2email: dict) -> dict:
        """Traduce los boosts de ref opaco a email para `select_accounts_for_auto`."""
        return {
            ref2email[r]: b
            for r, b in self.boosts.items()
            if r in ref2email
        }

    def avoid_emails(self, ref2email: dict) -> list:
        return [ref2email[r] for r, _why in self.avoid if r in ref2email]


# ─────────────────────────────────────────────────────── construcción del request

def _f(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _i(v, default=0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _build_advisor_request(inp: AdvisorInputs) -> dict:
    """Payload whitelisted, campo por campo. NUNCA copia el dict de entrada."""
    m = inp.mission_meta or {}
    rh = inp.recent_history or {}
    return {
        "mission": {
            "amount": _f(m.get("amount")),
            "target_count": _i(m.get("target_count")),
            "n_cards": _i(m.get("n_cards")),
            "max_accounts": _i(m.get("max_accounts")),
            "policy_digest": str(m.get("policy_digest") or ""),
        },
        "candidates": [
            {
                "ref": str(c.get("ref") or ""),
                "grade": str(c.get("grade") or "?"),
                "session_alive": bool(c.get("session_alive")),
                "tier_hint": str(c.get("tier_hint") or "LOW"),
                "window_available": round(_f(c.get("window_available")), 2),
                "declines_1h": _i(c.get("declines_1h")),
                "total_fails": _i(c.get("total_fails")),
                "has_3ds_24h": bool(c.get("has_3ds_24h")),
                "mins_since_last_attempt": _i(c.get("mins_since_last_attempt"), 99999),
                "cards_count": _i(c.get("cards_count")),
                "approved_bins": [str(b)[:6] for b in (c.get("approved_bins") or [])],
                "last_activity_days": round(_f(c.get("last_activity_days"), 999.0), 1),
                "hot_balance": bool(c.get("hot_balance")),
            }
            for c in (inp.candidates or [])
        ],
        "cards": [
            {
                "ref": str(k.get("ref") or ""),
                "bin": str(k.get("bin") or "")[:6],
                "bin_tier": str(k.get("bin_tier") or "?"),
                "bin_approval_rate": round(_f(k.get("bin_approval_rate")), 3),
                "bin_threeds_recent": bool(k.get("bin_threeds_recent")),
                "declines_24h": _i(k.get("declines_24h")),
            }
            for k in (inp.cards or [])
        ],
        "recent_history": {
            "probes_per_match_avg": round(_f(rh.get("probes_per_match_avg")), 2),
            "top_tier_probe_approval": round(_f(rh.get("top_tier_probe_approval")), 3),
            "mid_tier_probe_approval": round(_f(rh.get("mid_tier_probe_approval")), 3),
            "bin_tier_approval": {
                str(k): round(_f(v), 3)
                for k, v in (rh.get("bin_tier_approval") or {}).items()
            },
        },
    }


def _assert_no_pii(payload: Any, _path: str = "payload") -> None:
    """Escaneo recursivo fail-closed. Lanza `ValueError` a la primera señal de PII:
    clave con subcadena sensible, `@` en un string, o corrida de 13-19 dígitos."""
    if isinstance(payload, dict):
        for k, v in payload.items():
            kl = str(k).lower()
            if any(h in kl for h in _SENSITIVE_HINTS):
                raise ValueError(f"PII: clave sensible '{k}' en {_path}")
            _assert_no_pii(v, f"{_path}.{k}")
    elif isinstance(payload, (list, tuple)):
        for idx, v in enumerate(payload):
            _assert_no_pii(v, f"{_path}[{idx}]")
    elif isinstance(payload, str):
        if "@" in payload:
            raise ValueError(f"PII: '@' en {_path}")
        if _DIGIT_RUN.search(payload.replace(" ", "").replace("-", "")):
            raise ValueError(f"PII: corrida de 13-19 dígitos en {_path}")
    # int / float / bool / None: sin PII posible


# ──────────────────────────────────────────────────────── validación de respuesta

_ALLOWED_ADVICE_KEYS = {"account_priority", "pairings", "avoid", "rationale"}


def _sanitize_advice(
    raw: Any,
    eligible_refs: set,
    card_refs: set,
    *,
    max_boosts: Optional[int] = None,
    pairing_ok: Optional[Callable[[str, str], bool]] = None,
) -> Optional[CleanAdvice]:
    """Filtra la advice cruda contra el set elegible post-filtro-duro.

    - clave top-level desconocida / no-dict / malformado → descarta TODO (None)
    - `boost` clampeado a [-3, 3]; refs fuera de `eligible_refs` descartadas
    - `max_boosts`: se queda con los |boost| más grandes
    - cada `pairing` pasa por `pairing_ok(account_ref, card_ref)` (predicados del matcher)
    - advice vacía (0 boosts, 0 pairings, 0 avoid) → None
    """
    if not isinstance(raw, dict):
        return None
    if set(raw) - _ALLOWED_ADVICE_KEYS:
        return None
    try:
        boosts: dict[str, int] = {}
        for item in raw.get("account_priority") or []:
            ref = str(item.get("ref") or "")
            if ref not in eligible_refs:
                continue
            b = max(BOOST_MIN, min(BOOST_MAX, int(round(_f(item.get("boost"))))))
            if b != 0:
                boosts[ref] = b
        if max_boosts is not None and len(boosts) > max_boosts:
            boosts = dict(
                sorted(boosts.items(), key=lambda kv: -abs(kv[1]))[:max_boosts]
            )

        pairings: list[tuple] = []
        for p in raw.get("pairings") or []:
            a = str(p.get("account_ref") or "")
            c = str(p.get("card_ref") or "")
            if a not in eligible_refs or c not in card_refs:
                continue
            if pairing_ok is not None and not pairing_ok(a, c):
                continue
            pairings.append((a, c))

        avoid: list[tuple] = []
        for a in raw.get("avoid") or []:
            ref = str(a.get("ref") or "")
            if ref in eligible_refs:
                avoid.append((ref, str(a.get("why") or "")[:120]))

        rationale = str(raw.get("rationale") or "")[:500]
    except (AttributeError, TypeError, ValueError):
        return None

    if not boosts and not pairings and not avoid:
        return None
    return CleanAdvice(boosts=boosts, pairings=tuple(pairings),
                       avoid=tuple(avoid), rationale=rationale)


# ─────────────────────────────────────────────────────────────── llamada al LLM

_SYSTEM_PROMPT = (
    "Eres un asesor de operaciones para un sistema de depósitos automatizado. "
    "Recibes un JSON con una misión, cuentas candidatas (refs opacas A0, A1...) y "
    "tarjetas (refs C0, C1...). Tu trabajo: sugerir un reordenamiento de cuentas "
    "para maximizar conversión rápida. Responde EXCLUSIVAMENTE con un objeto JSON "
    "(sin markdown, sin texto extra) de la forma: "
    '{"account_priority":[{"ref":"A0","boost":2,"why":"..."}],'
    '"pairings":[{"account_ref":"A0","card_ref":"C0"}],'
    '"avoid":[{"ref":"A3","why":"..."}],"rationale":"..."}. '
    "boost es un entero en [-3,3]. Solo usa refs que aparezcan en el input. "
    "No puedes excluir cuentas ni saltarte filtros: boost es solo desempate."
)


def _strip_code_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1] if "\n" in t else t[3:]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


async def _run_llm(client, request: dict) -> tuple:
    """Devuelve (obj_parseado|None, model, tokens_in, tokens_out)."""
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(request, ensure_ascii=False, sort_keys=True)},
    ]
    parts: list[str] = []
    model = ""
    tin = tout = None
    async for ev in client.stream_chat(messages, tools=None, max_tokens=900):
        etype = ev.get("type")
        if etype == "delta":
            parts.append(ev.get("text") or "")
        elif etype == "done":
            model = ev.get("model") or model
            tin = ev.get("tokens_in")
            tout = ev.get("tokens_out")
        elif etype == "error":
            raise RuntimeError(ev.get("message") or "llm error")
    raw = _strip_code_fence("".join(parts))
    try:
        return json.loads(raw), model, tin, tout
    except (ValueError, TypeError):
        return None, model, tin, tout


# ──────────────────────────────────────────────────────────────── entrada pública

async def maybe_advise(
    inp: AdvisorInputs,
    *,
    db_path: Optional[str] = None,
    mission_id: Optional[str] = None,
    kind: str = "plan",
    client: Any = None,
    pairing_ok: Optional[Callable[[str, str], bool]] = None,
) -> Optional[CleanAdvice]:
    """Consulta al asesor. `None` = usa el plan determinista (que es lo de hoy).

    OFF por default (`BET_ADVISOR_ENABLED`). Escribe `bet_llm_calls` en todo camino
    salvo el early-return de OFF. `inp` viene YA redactado por el caller; este
    módulo no toca la BD salvo para la fila de costo.
    """
    if not _enabled():
        return None

    t0 = time.monotonic()
    model = ""
    tin = tout = None
    outcome = "no_advice"
    try:
        if not inp.candidates:
            outcome = "no_candidates"
            return None

        request = _build_advisor_request(inp)
        _assert_no_pii(request)  # fail-closed ANTES de red

        eligible = {c["ref"] for c in request["candidates"] if c.get("ref")}
        card_refs = {k["ref"] for k in request["cards"] if k.get("ref")}
        max_boosts = -(-_i(inp.mission_meta.get("max_accounts"), 6) // 2)  # ceil(n/2)

        cli = client or support_llm.LLMClient(chain=_chain(), timeout=ADVISOR_TIMEOUT_S)
        raw, model, tin, tout = await asyncio.wait_for(
            _run_llm(cli, request), timeout=ADVISOR_TIMEOUT_S,
        )
        if raw is None:
            outcome = "rejected"
            return None

        advice = _sanitize_advice(
            raw, eligible, card_refs, max_boosts=max_boosts, pairing_ok=pairing_ok,
        )
        if advice is None:
            outcome = "rejected"
            return None

        outcome = "applied"
        return advice
    except asyncio.TimeoutError:
        outcome = "timeout"
        return None
    except Exception as e:  # noqa: BLE001 — el advisor jamás debe tumbar la misión
        logger.warning("[bet_advisor] %s: %s", type(e).__name__, e)
        outcome = "error"
        return None
    finally:
        _record_llm_call(
            db_path, kind, model, tin, tout,
            int((time.monotonic() - t0) * 1000), mission_id, outcome,
        )


def _cost_usd(model: str, tokens_out: Optional[int]) -> float:
    rate = _MODEL_COST_PER_1K.get(model or "", 0.0)
    return round(rate * (tokens_out or 0) / 1000.0, 6)


def _record_llm_call(db_path, kind, model, tokens_in, tokens_out,
                     latency_ms, mission_id, outcome) -> None:
    """Fila de costo en `bet_llm_calls`. NUNCA lanza (corre en un `finally`)."""
    try:
        from db_registry import db as _db

        with _db(write=True, db_path=db_path) as c:
            c.execute(
                "INSERT INTO bet_llm_calls "
                "(kind, model, tokens_in, tokens_out, cost_usd, latency_ms, "
                " mission_id, outcome, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    str(kind), str(model or ""),
                    tokens_in if tokens_in is None else int(tokens_in),
                    tokens_out if tokens_out is None else int(tokens_out),
                    _cost_usd(model, tokens_out),
                    int(latency_ms),
                    str(mission_id) if mission_id is not None else None,
                    str(outcome),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
    except Exception as e:  # noqa: BLE001
        logger.warning("[bet_advisor] no pude registrar bet_llm_calls: %s", e)

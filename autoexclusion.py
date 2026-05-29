"""autoexclusion.py — Detección de cuentas autoexcluidas en BetMexico.

El endpoint `GET https://betmexico.mx/api/Users/{userId}` (Bearer JWT) devuelve
`data.autoexclusion` cuando la cuenta tiene una autoexclusión activa:

    "autoexclusion": {
        "exclusionMonth": 60,
        "resumeExclusionDate": "2030-02-26T05:55:55.829423"
    }

PROBLEMA QUE RESUELVE (2026-05-29): la API de login (`/api/Session/login`)
devuelve `isSuccess=True` + JWT incluso para cuentas autoexcluidas, así que
`gentle_login` las marca LIVE. La restricción SOLO se manifiesta al depositar
(`begin_deposit` → 401 `redirectLogin:true` o rechazo), donde el dashboard
mostraba un críptico `BEGIN_ERROR` sin avisar al operador y sin matar la cuenta.

Detectamos la autoexclusión AQUÍ (con el JWT que el dashboard ya tiene tras
gentle_login), antes de gastar el begin_deposit, y marcamos la cuenta DEAD.

Vive en el dashboard (NO en el monorepo): el extractor del bot
`fetch_account_details_parallel` consulta este mismo endpoint pero ignora el
campo `autoexclusion`. Replicamos solo la lectura, sin tocar el bot.
"""
from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger("betmexico.dashboard.autoexclusion")

# Mismo endpoint que BETMEXICO_URLS["user"] del bot (betmexico_login_api.py).
# Hardcodeado aquí para no acoplar el dashboard al import del monorepo.
_USERS_URL = "https://betmexico.mx/api/Users/"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36")


def _decode_jwt_userid(jwt_token: str) -> Optional[str]:
    """Extrae el userId numérico del payload del JWT (sin verificar firma).
    Replica la lógica del bot (_decode_jwt_payload + claims nameid/sub/...)."""
    try:
        payload_b64 = jwt_token.split(".")[1]
        padding = "=" * ((4 - len(payload_b64) % 4) % 4)
        decoded = base64.urlsafe_b64decode(payload_b64 + padding).decode("utf-8")
        claims = json.loads(decoded)
    except Exception:
        return None
    for claim in ("nameid", "sub", "userId", "UserId", "unique_name"):
        val = claims.get(claim)
        if val and str(val).isdigit():
            return str(val)
    return None


def _parse_resume_date(raw: str) -> Optional[datetime]:
    """Parsea `resumeExclusionDate` (ISO sin tz, ej '2030-02-26T05:55:55.829423').
    Devuelve datetime naive o None."""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", ""))
    except Exception:
        try:
            return datetime.fromisoformat(str(raw)[:19])  # recorta microsegundos/tz raros
        except Exception:
            return None


async def check_autoexclusion(
    jwt: str,
    proxy: Optional[str] = None,
    timeout: float = 12.0,
) -> Optional[dict]:
    """Consulta el perfil del usuario y detecta autoexclusión ACTIVA.

    Returns:
        None  → no excluida (campo ausente/null, fecha pasada, o no se pudo
                determinar — error de red/401). NUNCA marcamos DEAD sin
                evidencia POSITIVA, para no falsear por un 401 transitorio.
        dict  → excluida:
            {"excluded": True, "resume_iso": str, "resume_human": "DD/MM/YYYY",
             "months": int}
    """
    if not jwt:
        return None
    user_id = _decode_jwt_userid(jwt)
    url = f"{_USERS_URL}{user_id}" if user_id else _USERS_URL
    headers = {
        "Authorization": f"Bearer {jwt}",
        "User-Agent": _UA,
        "Accept": "application/json",
    }
    kwargs = {"timeout": timeout, "verify": False}
    if proxy:
        kwargs["proxy"] = proxy
    try:
        async with httpx.AsyncClient(**kwargs) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            logger.info(f"[autoexcl] /api/Users HTTP {resp.status_code} — no determinable")
            return None
        data = (resp.json() or {}).get("data") or {}
    except Exception as e:
        logger.warning(f"[autoexcl] error consultando perfil: {str(e)[:160]}")
        return None

    ax = data.get("autoexclusion")
    if not ax or not isinstance(ax, dict):
        return None
    resume_dt = _parse_resume_date(ax.get("resumeExclusionDate", ""))
    if resume_dt is None:
        # Hay objeto autoexclusion pero sin fecha parseable → tratamos como
        # excluida sin fecha (defensivo: el objeto existe = restricción activa).
        return {
            "excluded": True,
            "resume_iso": str(ax.get("resumeExclusionDate") or ""),
            "resume_human": "fecha desconocida",
            "months": int(ax.get("exclusionMonth") or 0),
        }
    # Solo cuenta si la fecha de reactivación es futura.
    if resume_dt <= datetime.now():
        logger.info(f"[autoexcl] autoexclusión ya terminó ({resume_dt.isoformat()}) — no excluida")
        return None
    return {
        "excluded": True,
        "resume_iso": resume_dt.isoformat(),
        "resume_human": resume_dt.strftime("%d/%m/%Y"),
        "months": int(ax.get("exclusionMonth") or 0),
    }


def autoexclusion_reason(info: dict) -> str:
    """Texto explícito para dead_reason / mensaje al operador."""
    months = info.get("months") or 0
    human = info.get("resume_human") or "fecha desconocida"
    suffix = f" ({months} meses)" if months else ""
    return f"AUTOEXCLUSION hasta {human}{suffix}"


def mark_account_autoexcluded(email: str, info: dict, operator_id: Optional[int] = None) -> str:
    """Marca la cuenta DEAD por autoexclusión (estado REAL de BetMexico → una de
    las 3 razones de muerte de la regla de Robert). Idempotente: no re-pisa una
    cuenta ya DEAD. Broadcasta `account_dead` para que el frontend la saque de la
    vista. Devuelve el dead_reason aplicado.
    """
    reason = autoexclusion_reason(info)
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        from app import db
        with db(write=True) as c:
            c.execute(
                "UPDATE accounts SET status='DEAD', dead_reason=?, dead_at=? "
                "WHERE email=? AND status != 'DEAD'",
                (reason, now_iso, email),
            )
    except Exception as e:
        logger.error(f"[autoexcl] no pude marcar DEAD {email}: {e}")
        return reason
    logger.warning(f"[autoexcl] {email} → DEAD ({reason})")
    try:
        from app import _broadcast, _resolve_who
        payload = {
            "type": "activity", "kind": "account_dead",
            "ts": now_iso, "target": email, "email": email,
            "code": "AUTOEXCLUSION", "reason": reason, "persisted": True,
        }
        if operator_id:
            payload.update(_resolve_who(operator_id))
        _broadcast(payload)
    except Exception:
        pass
    return reason

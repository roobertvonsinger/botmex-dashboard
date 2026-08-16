#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BetMexico Bot — Utilidades, helpers, formato, parsing, UserSession.
"""

import asyncio
import csv
import io
import json
import os
import random
import logging
import re
import time
from pathlib import Path
import httpx
import telegram
from typing import Dict, List, Optional, Tuple, Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from betmexico_config import (
    logger, MX_TZ, now_mx, LOGO,
    ADMIN_USERS, AUTHORIZED_USERS, USER_USERS, USER_NAMES,
    ADMIN_PROXIES, HUMAN_COOLDOWN, MAX_TEXT_COMBOS, MAX_COMBOS,
    FLUSH_EVERY, HITS_PER_BLOCK, ASK_PROXY, WAIT_USER_PROXIES,
    is_admin, is_subadmin, is_any_admin, is_authorized,
    get_admin_proxy, parse_user_proxy, get_user_proxy, _get_solver_for_user,
    user_tag,
)
from betmexico_login_api import (
    BetmexicoApiChecker, CaptchaTokenPool,
    BETMEXICO_URLS, RECAPTCHA_V2_SITE_KEY,
)
from betmexico_db import db
from betmexico_payment_analyzer import score_payment_readiness
import datetime


# ─────────────────────────────────────────────────────────────────────
# USER SESSION
# ─────────────────────────────────────────────────────────────────────

class UserSession:
    """Estado de sesión por usuario. Thread-safe con asyncio.Event."""

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.user_mode = "human"
        self.cancel = asyncio.Event()
        self.pause = asyncio.Event()
        self.pause.set()
        self.token_pool: Optional[CaptchaTokenPool] = None
        self.last_activity = time.time()
        self.batch_running = False

        self.hit_buffer: List[Dict] = []
        self.hit_message = None
        self.hit_lock = asyncio.Lock()
        self.all_hits: List[Dict] = []
        self.progress_message = None
        self._http_client: Optional[httpx.AsyncClient] = None

        self.pending_combos: List[Tuple[str, str]] = []

        self.results = {"live": [], "dead": [], "retry": [], "recheck": []}
        self.start_time = 0.0
        self.processed = 0
        self.total = 0

    async def wait_if_paused(self, timeout: float = 300) -> bool:
        if not self.pause.is_set():
            try:
                await asyncio.wait_for(self.pause.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                self.cancel.set()
                return False
        return not self.cancel.is_set()

    def get_http_client(self, proxy: Optional[Dict] = None) -> httpx.AsyncClient:
        """Returns or creates a shared httpx Client for this session."""
        if self._http_client is None or self._http_client.is_closed:
            proxy_url = None
            if proxy:
                server = proxy["server"]
                username = proxy.get("username", "")
                password = proxy.get("password", "")
                if username:
                    proxy_url = f"http://{username}:{password}@{server}"
                else:
                    proxy_url = f"http://{server}"

            self._http_client = httpx.AsyncClient(
                timeout=25.0,
                proxy=proxy_url,
                verify=False,
                limits=httpx.Limits(max_connections=50, max_keepalive_connections=20)
            )
        return self._http_client

    async def cleanup(self):
        self.cancel.set()
        self.batch_running = False
        if self.token_pool:
            try:
                if self.token_pool is not None:
                    await self.token_pool.stop()
            except Exception:
                pass
        
        if self._http_client:
            try:
                await self._http_client.aclose()
            except Exception:
                pass
            self._http_client = None

    def touch(self):
        self.last_activity = time.time()


USER_SESSIONS: Dict[int, UserSession] = {}


def get_session(user_id: int) -> UserSession:
    if user_id not in USER_SESSIONS:
        USER_SESSIONS[user_id] = UserSession(user_id)
    session = USER_SESSIONS[user_id]
    session.touch()
    return session


async def reset_session(user_id: int) -> UserSession:
    if user_id in USER_SESSIONS:
        old = USER_SESSIONS[user_id]
        await old.cleanup()
    USER_SESSIONS[user_id] = UserSession(user_id)
    return USER_SESSIONS[user_id]


# ─────────────────────────────────────────────────────────────────────
# SAFE TELEGRAM API WRAPPERS
# ─────────────────────────────────────────────────────────────────────

async def safe_edit(message, text: str, reply_markup=None, parse_mode=None):
    for attempt in range(3):
        try:
            return await message.edit_text(
                text, reply_markup=reply_markup, parse_mode=parse_mode,
            )
        except telegram.error.RetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
        except telegram.error.BadRequest as e:
            msg = str(e).lower()
            if "not modified" in msg:
                return message
            if "message to edit not found" in msg or "message is not modified" in msg:
                return None
            if "parse entities" in msg and parse_mode:
                logger.warning(f"[TG] Markdown roto en edit, retry sin parse_mode: {e}")
                try:
                    return await message.edit_text(
                        text, reply_markup=reply_markup, parse_mode=None,
                    )
                except Exception:
                    pass
                return None
            logger.warning(f"[TG] BadRequest edit: {e}")
            return None
        except telegram.error.TimedOut:
            if attempt < 2:
                await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"[TG] Error edit (intento {attempt + 1}): {e}")
            if attempt < 2:
                await asyncio.sleep(1)
    return None


async def safe_reply(source, text: str, reply_markup=None, parse_mode=None):
    msg = None
    if isinstance(source, Update):
        if source.callback_query and source.callback_query.message:
            msg = source.callback_query.message
        elif source.effective_message:
            msg = source.effective_message
    elif hasattr(source, "reply_text"):
        msg = source

    if not msg:
        logger.error("[TG] No se pudo encontrar mensaje para reply")
        return None

    for attempt in range(3):
        try:
            return await msg.reply_text(
                text, reply_markup=reply_markup, parse_mode=parse_mode,
            )
        except telegram.error.RetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
        except telegram.error.BadRequest as e:
            err = str(e).lower()
            if "parse entities" in err and parse_mode:
                logger.warning(f"[TG] Markdown roto en reply, retry sin parse_mode: {e}")
                try:
                    return await msg.reply_text(
                        text, reply_markup=reply_markup, parse_mode=None,
                    )
                except Exception:
                    pass
                return None
            logger.warning(f"[TG] BadRequest reply: {e}")
            return None
        except telegram.error.TimedOut:
            if attempt < 2:
                await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"[TG] Error reply (intento {attempt + 1}): {e}")
            if attempt < 2:
                await asyncio.sleep(1)
    return None


async def safe_send_document(chat_id, bot, file_path: Path, caption: str = ""):
    for attempt in range(3):
        try:
            with open(file_path, "rb") as f:
                return await bot.send_document(
                    chat_id=chat_id, document=f,
                    filename=file_path.name, caption=caption,
                )
        except telegram.error.RetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
        except Exception as e:
            logger.error(f"[TG] Error send_document (intento {attempt + 1}): {e}")
            if attempt < 2:
                await asyncio.sleep(2)
    return None


async def _safe_answer(query, text: str = ""):
    try:
        await query.answer(text)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────
# PARSING
# ─────────────────────────────────────────────────────────────────────

def smart_parse_combos(text: str) -> Tuple[List[Tuple[str, str]], int]:
    combos = []
    gmail_converted = 0
    SKIP_PREFIXES = {"http", "https", "ftp", "smtp", "imap", "pop3", "ssh"}

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^https?://[^\s;:]+[;:]", "", line)

        match = re.search(
            r"([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})[;:]([^\s>|]+)",
            line,
        )
        if match:
            email = match.group(1).strip()
            password = match.group(2).strip()
            if password and len(password) >= 1:
                combos.append((email, password))
            continue

        match = re.search(r"([a-zA-Z0-9._%+\-]{3,})[;:]([^\s>|]+)", line)
        if match:
            username = match.group(1).strip()
            password = match.group(2).strip()
            if username.lower() in SKIP_PREFIXES:
                continue
            if password and len(password) >= 3:
                combos.append((f"{username}@gmail.com", password))
                gmail_converted += 1

    seen = set()
    unique = []
    for combo in combos:
        if combo not in seen:
            seen.add(combo)
            unique.append(combo)

    return unique, gmail_converted


async def parse_uploaded_file(
    document, context: ContextTypes.DEFAULT_TYPE
) -> Tuple[List[Tuple[str, str]], Dict]:
    MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
    if document.file_size and document.file_size > MAX_FILE_SIZE_BYTES:
        size_mb = document.file_size / (1024 * 1024)
        return [], {"error": f"Archivo demasiado grande ({size_mb:.1f}MB). Máximo 5MB."}

    try:
        file = await context.bot.get_file(document.file_id)
        file_bytes = await file.download_as_bytearray()
    except Exception as e:
        return [], {"error": f"Error descargando archivo: {e}"}

    filename = document.file_name or "unknown.txt"
    ext = Path(filename).suffix.lower()

    if ext not in (".txt", ".csv"):
        return [], {"error": "Formato no soportado. Usa TXT o CSV."}

    try:
        text = file_bytes.decode("utf-8", errors="ignore")
    except Exception:
        text = file_bytes.decode("latin-1", errors="ignore")

    if ext == ".csv":
        try:
            reader = csv.reader(io.StringIO(text))
            lines = []
            for row in reader:
                if len(row) >= 2:
                    lines.append(f"{row[0].strip()}:{row[1].strip()}")
                elif len(row) == 1:
                    lines.append(row[0].strip())
            text = "\n".join(lines)
        except Exception:
            pass

    total_lines = len([l for l in text.splitlines() if l.strip()])
    combos, gmail_converted = smart_parse_combos(text)

    stats = {
        "filename": filename,
        "total_lines": total_lines,
        "valid_combos": len(combos),
        "gmail_converted": gmail_converted,
        "ignored": total_lines - len(combos),
    }
    return combos, stats


def flush_live_to_db(live_items: List[Dict], checked_by: int = 0) -> int:
    saved = 0
    for item in live_items:
        try:
            db.upsert_account(item, checked_by=checked_by)
            saved += 1
        except Exception as e:
            logger.error(f"[DB] Error flush parcial {item.get('email')}: {e}")
    return saved


# ─────────────────────────────────────────────────────────────────────
# FORMATO
# ─────────────────────────────────────────────────────────────────────

def _sanitize_combo(text: str) -> str:
    return text.replace("`", "'")


def _md_escape(text: str) -> str:
    """Escape para MarkdownV2."""
    for ch in ('_', '*', '[', ']', '(', ')', '~', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!'):
        text = text.replace(ch, f"\\{ch}")
    return text


def _md_v1_safe(text) -> str:
    """Limpia texto para Markdown v1 — remueve caracteres que rompen el parse."""
    if not text or not isinstance(text, str):
        return str(text) if text else ""
    for ch in ('_', '*', '`', '['):
        text = text.replace(ch, '')
    return text


def format_account_card(
    account: Dict,
    transactions: List[Dict],
    payment_tests: List[Dict],
    withdrawals: List[Dict],
    payment_score: Optional[Dict] = None,
    is_admin_user: bool = False,
    status_label: str = "",
    lock_status: Optional[Dict] = None,
    include_sensitive: bool = True
) -> str:
    email = account.get("email", "?")
    password = account.get("password", "?")
    fullname = account.get("fullname", "N/A")
    if fullname in ["N/A", "", None]: fullname = "⏳"
    else: fullname = _md_v1_safe(fullname)

    birthdate = account.get("birthdate", "N/A")
    address = account.get("address", "N/A")

    demog = ""
    if birthdate not in ["N/A", "", None]:
        demog += f"🎂 {_md_v1_safe(birthdate)} | "
    if address not in ["N/A", "", None]:
        demog += f"📍 {_md_v1_safe(address)}"
    if not demog:
        demog = "🎂 ⏳ | 📍 ⏳"

    bal_real = account.get("balance_real", 0.0) or 0.0
    bal_bonos = account.get("balance_bonos", 0.0) or 0.0
    bal_total = bal_real + bal_bonos
    if "balance_total" in account and account["balance_total"]:
        bal_total = account["balance_total"]
    elif "balance" in account:
        bal_total = account["balance"]

    last_dep = account.get("last_deposit_amount", 0.0) or 0.0
    last_dep_date = account.get("last_deposit_date", "N/A")

    kyc_status = "SI" if account.get("verified") or account.get("kyc_verified") else "NO"
    combo = f"{email}:{password}"

    # INDICADOR DE TRABAJO (informativo, no bloquea)
    lock_indicator = ""
    if lock_status and lock_status.get('is_locked'):
        l_by = lock_status.get('locked_by')
        l_name = USER_NAMES.get(l_by, f"UID:{l_by}")
        l_at = lock_status.get('locked_at', "")[:19]
        lock_indicator = (
            f"🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨\n"
            f"🏷️ *{l_name} ESTÁ TRABAJANDO ESTA CUENTA*\n"
            f"📅 Desde: {l_at}\n"
            f"🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨\n\n"
        )

    card = f"📋 Detalles de Cuenta:\n\n"
    card += lock_indicator
    card += f"`{_sanitize_combo(combo)}`\n"
        
    card += f"👤 {fullname}\n"
    card += f"{demog}\n\n"

    card += f"💰 Real: ${bal_real:.2f} | 🎁 Bonos: ${bal_bonos:.2f}\n"
    card += f"💵 Total: ${bal_total:.2f}\n"

    if status_label:
        card += f"🔒 KYC: {kyc_status} | {status_label}\n"
    else:
        card += f"🔒 KYC: {kyc_status}\n"

    card += f"📥 Último depo: ${last_dep:.2f} ({last_dep_date})\n"

    last_check = account.get("last_checked_at", "N/A")
    if last_check not in ["N/A", "", None]:
        card += f"🕒 Check: {last_check}\n"

    if payment_score:
        ps = payment_score
        grade = ps.get("grade", "?")
        grade_emoji = ps.get("grade_emoji", "")
        if is_admin_user:
            bd = ps.get("breakdown", {})
            gw_status = bd.get("gateway_status", "N/A")
            gw_emoji = {"CLEAN": "🟢", "SUSPICIOUS": "🟡", "LIKELY_BANNED": "🔴"}.get(gw_status, "⚪")
            dep_age = bd.get("last_deposit_age_days")
            dep_age_str = f"{dep_age} días" if dep_age is not None and dep_age >= 0 else "sin dato"
            card += (
                f"\n🧪 *PAYMENT SCORE*\n"
                f"├ Grade: {grade_emoji}{grade} ({ps.get('score', 0)}/100)\n"
                f"├ Gateway: {gw_emoji} {gw_status}\n"
                f"└ Dep. Age: {dep_age_str}\n"
            )
        else:
            card += f"\n📊 Payment Grade: {grade_emoji}{grade}\n"

    return card


def _format_card_masked(card_number: str) -> str:
    if len(card_number) >= 4:
        return f"****{card_number[-4:]}"
    return card_number


def _format_card_stats_text(stats: Dict) -> str:
    if not stats.get("found"):
        return "Sin registros previos."
    lines = []
    lines.append(f"Total usos: {stats['total']} (en {stats['accounts_count']} cuenta{'s' if stats['accounts_count'] > 1 else ''})")
    lines.append(f"✅ Exitosos: {stats['exitosos']} | ❌ Fallidos: {stats['fallidos']} | 🔄 3DS: {stats['tds']} | ⏳ Pendientes: {stats['pending']}")
    lines.append(f"Primera vez: {stats['first_use'][:16]}")
    lines.append(f"Última vez: {stats['last_use'][:16]}")
    return "\n".join(lines)


TXN_TYPE_MAP = {0: "⬇️", 1: "⬆️"}  # 0=depósito, 1=retiro


def _format_txn_button(txn: Dict, idx: int) -> str:
    type_emoji = TXN_TYPE_MAP.get(txn.get("type", 0), "🔄")
    status_map = {6: "✅", 0: "⏳", -4: "❌"}
    status_emoji = status_map.get(txn.get("status", 0), "❓")
    amount = txn.get("amount", 0)
    date_str = txn.get("date", "")[:16]
    return f"{type_emoji}{status_emoji} ${amount:.2f} | {date_str}"


def _txn_status_to_result(status: int) -> str:
    return {6: "EXITOSO", 0: "PENDING", -4: "FALLIDO"}.get(status, "PENDING")


def _parse_card_input(text: str) -> Dict:
    """
    Parsea info de tarjeta de un string. 
    Soporta formato estricto: NUMERO|MM/YY|CVV|RESULTADO|MONTO
    Soporta formato inteligente: busca patrones en texto con ruido.
    """
    text = text.strip()
    result = {
        "card_number": "", "card_expiry": "", "card_cvv": "",
        "result": "PENDING", "amount": 0.0,
    }

    if not text:
        return {"error": "Texto vacío"}

    # 1. Intentar split por pipe (|) - Formato Estructurado Universal
    # Limpiar posibles pipes extra al inicio/final
    text_clean = text.strip().strip("|")
    parts = [p.strip() for p in text_clean.split("|")]
    
    if len(parts) >= 3:
        # Extraer CC Num (siempre el primer pipe relevante)
        card_num = re.sub(r"[^0-9]", "", parts[0])
        if 15 <= len(card_num) <= 16:
            result["card_number"] = card_num
            
            # Detectar si es MM|YYYY|CVV (4 partes para la tarjeta) o MM/YY|CVV (3 partes)
            # Ej: 4242...|12|2026|123
            if len(parts) >= 4 and len(parts[1]) <= 2 and (len(parts[2]) in (2, 4)):
                mm = parts[1].zfill(2)
                yy = parts[2][-2:] # Tomar últimos 2 dígitos del año
                result["card_expiry"] = f"{mm}/{yy}"
                result["card_cvv"] = re.sub(r"[^0-9]", "", parts[3])
                
                # Monto/Resultado opcionales en partes 4+
                if len(parts) >= 5:
                    try: result["amount"] = float(re.sub(r"[^0-9.]", "", parts[4]))
                    except ValueError: pass
                if len(parts) >= 6:
                    r = parts[5].strip().upper()
                    if r in ("OK", "SUCCESS"): r = "EXITOSO"
                    elif r in ("FAIL",): r = "FALLIDO"
                    if r in {"EXITOSO", "FALLIDO", "3DS", "PENDING"}: result["result"] = r
            else:
                # Formato: CC|MM/YY|CVV (3 partes)
                expiry = parts[1].strip()
                expiry_clean = re.sub(r"[^0-9]", "", expiry)
                if len(expiry_clean) == 4:
                    result["card_expiry"] = f"{expiry_clean[:2]}/{expiry_clean[2:]}"
                else:
                    result["card_expiry"] = expiry
                
                result["card_cvv"] = re.sub(r"[^0-9]", "", parts[2])
                
                # Monto/Resultado opcionales en partes 3+
                if len(parts) >= 4:
                    r = parts[3].strip().upper()
                    if r in ("OK", "SUCCESS"): r = "EXITOSO"
                    elif r in ("FAIL",): r = "FALLIDO"
                    if r in {"EXITOSO", "FALLIDO", "3DS", "PENDING"}: result["result"] = r
                if len(parts) >= 5:
                    try: result["amount"] = float(re.sub(r"[^0-9.]", "", parts[4]))
                    except ValueError: pass
                
            return result

    # 2. Parsing Inteligente (Robusto ante ruido)
    # Buscamos patrones si el formato pipe falló, pero el bot seguirá sugiriendo los pipes
    cc_match = re.search(r"(?:^|\D)(\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{3,4})(?:\D|$)", text)
    if cc_match:
        result["card_number"] = re.sub(r"\D", "", cc_match.group(1))
    
    exp_match = re.search(r"(?:^|\D)(0[1-9]|1[0-2])[/-]?([2-9][0-9](?:\d{2})?)(?:\D|$)", text)
    if exp_match:
        mm = exp_match.group(1)
        yy = exp_match.group(2)
        if len(yy) == 4: yy = yy[2:]
        result["card_expiry"] = f"{mm}/{yy}"
    
    cvv_matches = re.findall(r"(?:^|\D)(\d{3,4})(?:\D|$)", text)
    for c in cvv_matches:
        if c != result["card_number"] and c not in (exp_match.groups() if exp_match else []):
            if not result["card_cvv"]:
                result["card_cvv"] = c
                break

    amount_match = re.search(r"(?:\$|monto:?\s?)(\d+(?:\.\d{1,2})?)", text, re.I)
    if amount_match:
        result["amount"] = float(amount_match.group(1))

    # Validaciones Finales - Reforzar el formato esperado en el error
    if not result["card_number"]:
        return {"error": "Falta número de tarjeta.\nFormato: `CC|MM|AAAA|CVV`"}
    if not result["card_expiry"]:
        return {"error": "Falta fecha de expiración.\nFormato: `CC|MM|AAAA|CVV`"}
    if not result["card_cvv"]:
        return {"error": "Falta CVV (3-4 dígitos).\nFormato: `CC|MM|AAAA|CVV`"}

    return result


def _sanitize_proxy_url(proxy_url: str) -> str:
    try:
        if '@' in proxy_url:
            scheme_and_creds, hostport = proxy_url.rsplit('@', 1)
            if '://' in scheme_and_creds:
                scheme, _ = scheme_and_creds.split('://', 1)
                return f"{scheme}://***:***@{hostport}"
            return f"***:***@{hostport}"
    except Exception:
        pass
    return "[proxy-url-redacted]"


def _results_to_accounts(live_items: List[Dict]) -> List[Dict]:
    accounts = []
    for item in live_items:
        details = item.get("account_details", {})
        balance_real = details.get("balance_real", 0.0) or 0.0
        balance_bonos = details.get("balance_bonos", 0.0) or 0.0
        accounts.append({
            "email": item.get("email", ""),
            "password": item.get("password", ""),
            "fullname": details.get("fullname", "N/A"),
            "birthdate": details.get("birthdate", "N/A"),
            "address": details.get("address", "N/A"),
            "balance_real": balance_real,
            "balance_bonos": balance_bonos,
            "balance_total": balance_real + balance_bonos,
            "last_deposit_amount": details.get("last_deposit_amount", 0.0) or 0.0,
            "last_deposit_date": details.get("last_deposit_date", "N/A"),
            "kyc_verified": 1 if details.get("verified", False) else 0,
            "status": "LIVE",
            "first_checked_at": now_mx().strftime("%Y-%m-%d %H:%M:%S"),
            "last_checked_at": now_mx().strftime("%Y-%m-%d %H:%M:%S"),
            "check_count": 1,
        })
    return accounts


# ─────────────────────────────────────────────────────────────────────
# PROXY KEYBOARD
# ─────────────────────────────────────────────────────────────────────

def _build_proxy_keyboard(user_id: int, context) -> List[List[InlineKeyboardButton]]:
    """Construye teclado de proxy (todos usan proxies admin)."""
    return [
        [InlineKeyboardButton("✅ Sí, usar proxy", callback_data="proxy_yes")],
        [InlineKeyboardButton("❌ No usar proxy", callback_data="proxy_no")],
        [InlineKeyboardButton("🔙 Menú", callback_data="back_to_menu")],
    ]


# ─────────────────────────────────────────────────────────────────────
# MENÚ PRINCIPAL
# ─────────────────────────────────────────────────────────────────────

async def _show_main_menu(update_or_msg, context, user_id: int) -> int:
    name = USER_NAMES.get(user_id, "Usuario")
    keyboard = [
        [InlineKeyboardButton("🚀 Iniciar Check", callback_data="start_check")],
    ]

    # Quick Check — todos los autorizados
    if is_authorized(user_id):
        keyboard.append([InlineKeyboardButton("🚀 Quick Check", callback_data="qc_menu")])

    keyboard.append([InlineKeyboardButton("ℹ️ Mi Info", callback_data="myinfo")])

    # Web Dashboard — todos los autorizados excepto subadmins (temporalmente)
    if is_authorized(user_id) and not is_subadmin(user_id):
        web_url = os.getenv("BMX_WEB_URL", "https://botmexico.com.mx")
        keyboard.append([InlineKeyboardButton("🌐 Web Dashboard", url=web_url)])

    text = (
        f"{LOGO}"
        f"👋 Hola, *{name}*\n"
        f"🆔 `{user_id}`\n\n"
        "📎 *Comandos:*\n"
        "• `/start`: Inicia el panel principal.\n"
        "• `/check`: Inicia verificación de cuentas.\n"
        "• `/info`: Configura tus ajustes.\n"
        "• `/get email`: Consulta detalles de cuenta.\n"
        "• `/dep combo|cc|mm|aaaa|cvv|monto`: Depósito rápido.\n"
        "• `/help`: Esta guía rápida.\n"
        "• `/cancel`: Aborta el proceso actual.\n\n"
        "⚠️ *Límites:*\n"
        "• Mínimo 10 combos por check.\n"
        "• Máximo 1000 combos en archivos (.txt/.csv).\n"
        "• Máximo 100 combos pegados en texto.\n\n"
        "📊 *Estados:*\n"
        "• LIVE ✅: Cuenta activa y verificada, lista para trabajar.\n"
        "• DEAD ❌: No sirve (login falló o bloqueada)."
    )
    if is_authorized(user_id) and not is_subadmin(user_id):
        text += (
            "\n\n🌐 *Web Dashboard:*\n"
            "Búsqueda, historial, depósitos y más desde el navegador."
        )

    if hasattr(update_or_msg, 'message') and update_or_msg.message:
        await update_or_msg.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif hasattr(update_or_msg, 'reply_text'):
        await update_or_msg.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif hasattr(update_or_msg, 'edit_text'):
        await update_or_msg.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await safe_reply(update_or_msg, text)

    return ASK_PROXY


async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Volver al menú principal (Botón 🔙)."""
    query = update.callback_query
    if query:
        await query.answer()
        user_id = query.from_user.id
    else:
        user_id = update.effective_user.id

    try:
        # Cancelar check si estaba corriendo
        session = get_session(user_id)
        if session and session.batch_running:
            session.cancel.set()
            session.pause.set()

        return await _show_main_menu(query if query else update, context, user_id)
    except Exception as e:
        logger.error(f"[MENU] Error back_to_menu: {e}", exc_info=True)
        # fallback
        return await _show_main_menu(update, context, user_id)


# ─────────────────────────────────────────────────────────────────────
# PROXY HANDLERS (Movidos de bot.py)
# ─────────────────────────────────────────────────────────────────────

async def proxy_setup_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Usuario robot sin proxies → pantalla para pegar proxies."""
    query = update.callback_query
    await query.answer()

    context.user_data["use_proxy"] = True
    keyboard = [
        [InlineKeyboardButton("❓ Cómo obtener proxies", callback_data="proxy_howto")],
        [InlineKeyboardButton("⏩ Omitir (sin proxy)", callback_data="proxy_no")],
    ]

    await safe_edit(
        query.message,
        f"{LOGO}"
        "🛜 *Pega tus proxies* (uno por línea)\n\n"
        "Formato: `host:port:user:pass`\n\n"
        "Servicios recomendados:\n"
        "• *DataImpulse* — dataimpulse.com\n"
        "• *Databay* — databay.co\n\n"
        "Pega tus proxies aquí 👇",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return WAIT_USER_PROXIES


async def proxy_edit_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Usuario quiere editar sus proxies guardados."""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("❓ Cómo obtener proxies", callback_data="proxy_howto")],
        [InlineKeyboardButton("⏩ Omitir (usar guardados)", callback_data="proxy_yes")],
    ]

    await safe_edit(
        query.message,
        f"{LOGO}"
        "✏️ *Editar proxies*\n\n"
        "Pega tus nuevos proxies (uno por línea)\n"
        "Formato: `host:port:user:pass`\n\n"
        "Pega aquí 👇",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return WAIT_USER_PROXIES


async def receive_user_proxies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe proxies pegados por el usuario, los valida y guarda."""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    valid = []
    invalid = 0

    for line in lines:
        parsed = parse_user_proxy(line)
        if parsed:
            valid.append(line)
        else:
            invalid += 1

    if not valid:
        await safe_reply(
            update,
            "❌ No se detectaron proxies válidos.\n"
            "Formato: `host:port:user:pass`",
            parse_mode="Markdown",
        )
        return WAIT_USER_PROXIES

    # Guardar en BD
    db.save_user_settings(user_id, proxies=json.dumps(valid))
    logger.info(f"[{user_tag(user_id)}] 🛜 {len(valid)} proxies guardados")

    invalid_note = f"⚠️ {invalid} líneas ignoradas\n" if invalid else ""

    # Continuar al siguiente paso (captcha check)
    keyboard = [
        [InlineKeyboardButton("▶️ Continuar", callback_data="proxy_yes")],
    ]

    await update.message.reply_text(
        f"{LOGO}"
        f"✅ {len(valid)} proxies guardados\n"
        f"{invalid_note}",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ASK_PROXY


async def proxy_howto_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra instrucciones de cómo obtener proxies."""
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "📖 *Cómo obtener proxies*\n\n"
        "*DataImpulse:*\n"
        "1. Regístrate en dataimpulse.com\n"
        "2. Ve a Dashboard → Proxy\n"
        "3. Copia el formato host:port:user:pass\n\n"
        "*Databay:*\n"
        "1. Regístrate en databay.co\n"
        "2. Ve a Dashboard → Proxy Configurator\n"
        "3. Elige zona (US West recomendado)\n"
        "4. Copia las credenciales\n\n"
        "Formato: `host:port:usuario:contraseña`",
        parse_mode="Markdown",
    )
    return WAIT_USER_PROXIES




# ─────────────────────────────────────────────────────────────────────
# MY INFO (Movido de bot.py)
# ─────────────────────────────────────────────────────────────────────

async def myinfo_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra info del usuario: ID, miembro desde, stats, y botones para editar proxy/captcha."""
    query = update.callback_query
    if query:
        await _safe_answer(query)
        user_id = query.from_user.id
    else:
        user_id = update.effective_user.id

    try:
        name = USER_NAMES.get(user_id, "Usuario")
        if is_admin(user_id):
            role = "👑 Admin"
        elif is_subadmin(user_id):
            role = "🥈 Subadmin"
        else:
            role = "👤 Usuario"
        mode_emoji = "🧑‍💻"

        # Stats
        stats = db.get_stats(user_id=user_id)
        total_live = stats["total_live"]
        total_dead = stats["total_dead"]
        total_verified = stats["total_verified"]
        total_balance = stats["total_balance"]
        total_checked = total_live + total_dead

        # Miembro desde
        member_since = db.get_member_since(user_id)
        if member_since:
            # Formatear fecha bonita
            try:
                dt = datetime.datetime.strptime(member_since, "%Y-%m-%d %H:%M:%S")
                member_str = dt.strftime("%d/%m/%Y")
            except ValueError:
                member_str = member_since
        else:
            member_str = "Nuevo usuario"

        # Settings actuales
        settings = db.get_user_settings(user_id)
        captcha_svc = settings.get("captcha_service", "")
        captcha_key = settings.get("captcha_api_key", "")
        proxies_raw = settings.get("proxies", "")

        if is_any_admin(user_id):
            captcha_display = "🔑 Admin (integrado)"
            proxy_display = "🛜 Admin (integrado)"
        else:
            if captcha_key:
                svc_name = captcha_svc.title() if captcha_svc else "Auto"
                captcha_display = f"🔑 {svc_name} — `...{captcha_key[-6:]}`"
            else:
                captcha_display = "🔑 Sin configurar"

            if proxies_raw:
                try:
                    proxy_list = json.loads(proxies_raw)
                    proxy_display = f"🛜 {len(proxy_list)} proxy(s) guardados"
                except (json.JSONDecodeError, TypeError):
                    proxy_display = "🛜 Sin configurar"
            else:
                proxy_display = "🛜 Sin configurar"

        usage_line = ""
        role_line = f"🏷️ *Rol:* {role}\n" if is_any_admin(user_id) else ""

        text = (
            f"{LOGO}"
            f"ℹ️ *Mi Info*\n\n"
            f"👤 *Nombre:* {name}\n"
            f"🆔 *Telegram ID:* `{user_id}`\n"
            f"{role_line}"
            f"📅 *Miembro desde:* {member_str}\n\n"
            f"{usage_line}"
            f"━━━ 📊 Estadísticas ━━━\n"
            f"📋 Total checados: {total_checked}\n"
            f"✅ LIVE: {total_verified}\n"
            f"💰 Balance total: ${total_balance:,.2f}\n\n"
            f"━━━ ⚙️ Configuración ━━━\n"
            f"{captcha_display}\n"
            f"{proxy_display}\n"
        )

        keyboard = []
        if not is_any_admin(user_id):
            keyboard.append([InlineKeyboardButton("✏️ Editar Captcha Key", callback_data="captcha_edit")])
            keyboard.append([InlineKeyboardButton("✏️ Editar Proxies", callback_data="proxy_edit")])
        keyboard.append([InlineKeyboardButton("🔙 Menú", callback_data="back_to_menu")])

        if query:
            await safe_edit(
                query.message,
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )

    except Exception as e:
        logger.error(f"[MYINFO] Error: {e}", exc_info=True)
        await safe_reply(update, "❌ Error cargando info.")

    return ASK_PROXY


async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """/info — Muestra info del usuario (wrapper de myinfo_cb)."""
    return await myinfo_cb(update, context)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """/help — Muestra ayuda y comandos disponibles."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("❌ No autorizado.")
        return ConversationHandler.END

    session = get_session(user_id)
    if not session:
        session = await reset_session(user_id)

    text = (
        f"{LOGO}"
        "🤖 *Ayuda de BetMexico Bot* 🤖\n\n"
        "🚀 *Comandos:*\n"
        "• `/start`: Inicia el panel principal.\n"
        "• `/check`: Inicia verificación de cuentas.\n"
        "• `/info`: Configura tus ajustes.\n"
        "• `/get email`: Consulta detalles de cuenta.\n"
        "• `/dep combo|cc|mm|aaaa|cvv|monto`: Depósito rápido.\n"
        "• `/help`: Esta guía rápida.\n"
        "• `/cancel`: Aborta el proceso actual.\n\n"
        "📏 *Límites:*\n"
        "• Mínimo 10 combos por check.\n"
        "• Máximo 1000 combos en archivos (.txt/.csv).\n"
        "• Máximo 100 combos pegados en texto.\n\n"
        "📊 *Estados:*\n"
        "• LIVE ✅: Cuenta activa y verificada, lista para trabajar.\n"
        "• DEAD ❌: No sirve (login falló o bloqueada)."
    )
    if is_admin(update.effective_user.id):
        text += (
            "\n\n🌐 *Web Dashboard:*\n"
            "Búsqueda, historial, depósitos y más desde el navegador."
        )

    keyboard = [[InlineKeyboardButton("🔙 Menú", callback_data="back_to_menu")]]
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return ASK_PROXY


def luhn_check(card_number: str) -> bool:
    """Verifica un número de tarjeta usando el algoritmo de Luhn."""
    try:
        digits = [int(d) for d in card_number]
        checksum = 0
        reverse_digits = digits[::-1]
        for i, digit in enumerate(reverse_digits):
            if i % 2 == 1:
                digit *= 2
                if digit > 9:
                    digit -= 9
            checksum += digit
        return checksum % 10 == 0
    except Exception:
        return False

async def cc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /cc — Extrae y VALIDA tarjetas de un bloque de texto desordenado."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    text = " ".join(context.args).strip()
    if not text:
        if hasattr(update.message, 'reply_to_message') and update.message.reply_to_message:
            text = update.message.reply_to_message.text or ""
            
    if not text:
        await safe_reply(update, "❌ Uso: `/cc [texto]` o responde a un mensaje con `/cc`", parse_mode="Markdown")
        return

    clean_text = re.sub(r"[|,:;]", " ", text)
    cc_pattern = r"(?:^|\D)(\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{3,4})(?:\D|$)"
    cc_matches = list(re.finditer(cc_pattern, clean_text))
    
    if not cc_matches:
        await safe_reply(update, "❌ No se encontraron números de tarjeta válidos.")
        return

    valid_cards = []
    invalid_cards = []
    
    now = now_mx()
    current_year = now.year
    current_month = now.month

    for i, match in enumerate(cc_matches):
        raw_cc = match.group(1)
        cc_num = re.sub(r"\D", "", raw_cc)
        if len(cc_num) < 15: continue
        
        start_search = match.end()
        end_search = cc_matches[i+1].start() if (i + 1) < len(cc_matches) else len(clean_text)
        segment = clean_text[start_search:end_search].strip()

        mm, yy, cvv = "MM", "YYYY", "???"
        is_expired = False
        
        # 1. Buscar Fecha
        exp_match = re.search(r"(?:^|\D)(0[1-9]|1[0-2])[/\-\s]?((?:20)?(?:2[4-9]|3[0-5]))(?:\D|$)", segment)
        if exp_match:
            mm_val = int(exp_match.group(1))
            mm = str(mm_val).zfill(2)
            yy_raw = exp_match.group(2)
            yy_val = int(f"20{yy_raw}" if len(yy_raw) == 2 else yy_raw)
            yy = str(yy_val)
            
            # Verificar si está vencida
            if yy_val < current_year or (yy_val == current_year and mm_val < current_month):
                is_expired = True
                
            segment = segment.replace(exp_match.group(0).strip(), " [EXP] ")

        # 2. Buscar CVV
        cvv_candidates = re.findall(r"(?:^|\D)(\d{3,4})(?:\D|$)", segment)
        for cand in cvv_candidates:
            if cand in yy: continue
            cvv = cand
            break
            
        card_str = f"`{cc_num}|{mm}|{yy}|{cvv}`"
        
        # Clasificación
        if not luhn_check(cc_num):
            invalid_cards.append(f"{card_str} — ❌ *Luhn Falló*")
        elif is_expired:
            invalid_cards.append(f"{card_str} — 📅 *Vencida*")
        elif mm == "MM" or yy == "YYYY" or cvv == "???":
            invalid_cards.append(f"{card_str} — ❓ *Incompleta*")
        else:
            valid_cards.append(card_str)

    # Unify
    valid_cards = list(dict.fromkeys(valid_cards))
    invalid_cards = list(dict.fromkeys(invalid_cards))
    
    response = f"{LOGO}💳 *Extracción de Tarjetas*\n\n"
    
    if valid_cards:
        response += "✅ *VÁLIDAS:*\n" + "\n".join(valid_cards) + "\n\n"
    
    if invalid_cards:
        response += "❌ *INVALIDAS / VENCIDAS:*\n" + "\n".join(invalid_cards)
        
    if not valid_cards and not invalid_cards:
        await safe_reply(update, "❌ No se pudo extraer información útil.")
        return

    await safe_reply(update, response, parse_mode="Markdown")


async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /restart - limpia todo y muestra menú."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    await reset_session(user_id)
    context.user_data.clear()
    # Import loop prevention: call the function directly if it was in the same module, 
    # but since start is in bot.py, we might have an issue.
    # Actually, we can just call back_to_menu if we want to show the menu.
    # We can't import start here easily without circular dependencies.
    # But restart_command is usually used to reset and show menu.
    return await back_to_menu(update, context)

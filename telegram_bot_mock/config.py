"""Configuración y bootstrap para el bot Telegram Mock (repos/botmex-dashboard/telegram_bot_mock).
Reutiliza la BD compartida del dashboard y los módulos core sin tocar el bot original.
"""
import os
import sys
import logging
import logging.handlers
import warnings
from pathlib import Path

# Configurar logging — StreamHandler (stdout → `docker logs`) + FileHandler
# a /data/logs/telegram_mock_bot.log (volumen compartido con betmexico-web,
# mismo patrón que app.py) para que la consola "Logs" web pueda leer la
# actividad del bot mock sin acceso a docker.
_LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
_handlers = [logging.StreamHandler()]
try:
    _LOGS_DIR = Path("/data/logs")
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)
    _fh = logging.handlers.RotatingFileHandler(
        str(_LOGS_DIR / "telegram_mock_bot.log"), maxBytes=10 * 1024 * 1024,
        backupCount=3, encoding="utf-8",
    )
    _handlers.append(_fh)
except Exception as _e:
    print(f"[boot] telegram_mock_bot.log FileHandler init failed: {_e}")

logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT, handlers=_handlers)
logger = logging.getLogger("telegram_bot_mock")

# Silenciar reconexiones ruidosas de red de python-telegram-bot y httpx/httpcore
logging.getLogger("telegram.ext._utils.networkloop").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Silenciar el warning informativo de PTB sobre ConversationHandler con
# per_message=False (default) — los CallbackQueryHandler no se trackean por
# mensaje, comportamiento intencional en este bot.
warnings.filterwarnings(
    "ignore",
    message="If 'per_message=False', 'CallbackQueryHandler' will not be tracked",
    category=UserWarning,
)

# Rutas principales
MOCK_DIR = Path(__file__).parent.resolve()
DASHBOARD_DIR = MOCK_DIR.parent.resolve()

# Asegurar que el dashboard directory y el monorepo bot directory estén en sys.path
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

MONOREPO_BOT_DIR = DASHBOARD_DIR.parent / "Proyectos" / "BetMexico" / "Telegram"
if MONOREPO_BOT_DIR.exists() and str(MONOREPO_BOT_DIR) not in sys.path:
    sys.path.insert(0, str(MONOREPO_BOT_DIR))

# Resolver BD path (Misma BD compartida)
DEFAULT_DB = DASHBOARD_DIR.parent / "betmexico_accounts.db"
DB_PATH = Path(os.environ.get("BETMEX_DB", str(DEFAULT_DB)))

# La BD del mock la maneja app.db()/DB_PATH (app.py). NO se reconcilia
# betmexico_db aquí: ese módulo vive en la copia legacy (fuera de este repo) y
# su import desde este punto dispara un circular import (betmexico_db ↔
# betmexico_config) → warning falso "no disponible en este entorno".
if not DB_PATH.exists() and not any(mod for mod in sys.modules if "pytest" in mod):
    logger.error(f"CRÍTICO: La BD especificada no existe en la ruta {DB_PATH}")
    raise SystemExit(1)

# Lockup de marca oficial BotMexico (estilo Ruthopia lockup)
HEADER_LOCKUP = (
    "◢ ━━━━━━━ ◣\n"
    "  ∷ ʙ.ᴏᴛᴍᴇxɪᴄᴏ ∷\n"
    "◥ ━━━━━━━ ◤"
)

# Mapeo de Apodos por Telegram ID (coincide con USERS de auth.py)
import auth as _auth

def get_user_nickname(user_id: int, fallback_name: str = "") -> str:
    for u in _auth.load_users().values():
        if u.get("telegram_id") == user_id:
            return u.get("display", fallback_name)
    return fallback_name or f"Operador_{user_id}"

# Token para el bot mock
MOCK_BOT_TOKEN = os.getenv("BMX_MOCK_BOT_TOKEN", "8823043859:AAEWnv2aVYopE7qsNVACA24sW_Tei7o1nnI")
DASHBOARD_URL = os.getenv("BMX_DASHBOARD_URL", "https://botmexico.net")

# Usuarios autorizados (coincide con auth.py del dashboard y betmexico_config)
SUPERADMIN_ID = 1341812706

def is_authorized(user_id: int) -> bool:
    if user_id == SUPERADMIN_ID:
        return True
    authorized_ids = {u.get("telegram_id") for u in _auth.load_users().values() if u.get("telegram_id")}
    return user_id in authorized_ids

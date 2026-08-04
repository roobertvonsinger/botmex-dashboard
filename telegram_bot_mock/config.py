"""Configuración y bootstrap para el bot Telegram Mock (repos/botmex-dashboard/telegram_bot_mock).
Reutiliza la BD compartida del dashboard y los módulos core sin tocar el bot original.
"""
import os
import sys
import logging
import logging.handlers
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

# Reconciliar DB_FILE de betmexico_db antes de instanciar singleton si existe
try:
    import betmexico_db
    betmexico_db.DB_FILE = DB_PATH
    if hasattr(betmexico_db, "db") and betmexico_db.db is not None:
        betmexico_db.db.db_path = DB_PATH
    if not DB_PATH.exists() and not any(mod for mod in sys.modules if "pytest" in mod):
        logger.error(f"CRÍTICO: La BD especificada no existe en la ruta {DB_PATH}")
        raise SystemExit(1)
except ImportError:
    logger.warning("betmexico_db no disponible en este entorno.")
except Exception as e:
    logger.error(f"Error inicializando la base de datos: {e}")

# Lockup de marca oficial BotMexico (estilo Ruthopia lockup)
HEADER_LOCKUP = (
    "◢ ━━━━━━━ ◣\n"
    "  ∷ ʙ.ᴏᴛᴍᴇxɪᴄᴏ ∷\n"
    "◥ ━━━━━━━ ◤"
)

# Mapeo de Apodos por Telegram ID (coincide con USERS de auth.py)
NICKNAMES = {
    1341812706: "Robert",
    7599631505: "Lau",
    7847239854: "Luisito",
    1059367082: "Magdiel",
    753020051: "Operador",
}

def get_user_nickname(user_id: int, fallback_name: str = "") -> str:
    return NICKNAMES.get(user_id, fallback_name or f"Operador_{user_id}")

# Token para el bot mock
MOCK_BOT_TOKEN = os.getenv("BMX_MOCK_BOT_TOKEN", "8823043859:AAEWnv2aVYopE7qsNVACA24sW_Tei7o1nnI")
DASHBOARD_URL = os.getenv("BMX_DASHBOARD_URL", "https://botmexico.net")

# Usuarios autorizados (coincide con auth.py del dashboard y betmexico_config)
SUPERADMIN_ID = 1341812706
AUTHORIZED_USERS = {1341812706, 7599631505, 7847239854, 1059367082, 753020051}

def is_authorized(user_id: int) -> bool:
    return user_id in AUTHORIZED_USERS or user_id == SUPERADMIN_ID

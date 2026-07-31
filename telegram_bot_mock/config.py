"""Configuración y bootstrap para el bot Telegram Mock (repos/botmex-dashboard/telegram_bot_mock).
Reutiliza la BD compartida del dashboard y los módulos core sin tocar el bot original.
"""
import os
import sys
import logging
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("telegram_bot_mock")

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

# Token para el bot mock
MOCK_BOT_TOKEN = os.getenv("BMX_MOCK_BOT_TOKEN", "8823043859:AAEWnv2aVYopE7qsNVACA24sW_Tei7o1nnI")
DASHBOARD_URL = os.getenv("BMX_DASHBOARD_URL", "https://botmexico.net")

# Usuarios autorizados — Exclusivo SuperAdmin (Robert)
SUPERADMIN_ID = 1341812706
AUTHORIZED_USERS = {1341812706}

def is_authorized(user_id: int) -> bool:
    return user_id == SUPERADMIN_ID

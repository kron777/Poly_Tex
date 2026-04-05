"""Central configuration — all settings from .env"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent

# ── Credentials ───────────────────────────────────────────────
POLY_PRIVATE_KEY  = os.getenv("POLY_PRIVATE_KEY", "")
POLY_API_KEY      = os.getenv("POLY_API_KEY", "")
POLY_ADDRESS      = os.getenv("POLY_ADDRESS", "")
POLY_CHAIN_ID     = int(os.getenv("POLY_CHAIN_ID", "137"))

# ── API endpoints ─────────────────────────────────────────────
CLOB_API          = "https://clob.polymarket.com"
GAMMA_API         = "https://gamma-api.polymarket.com"
WS_URL            = "wss://ws-subscriptions-clob.polymarket.com/ws"

# ── Trading mode ──────────────────────────────────────────────
PAPER_TRADING     = os.getenv("PAPER_TRADING", "true").lower() == "true"
LIVE_CONFIRMED    = os.getenv("LIVE_CONFIRMED", "false").lower() == "true"
IS_LIVE           = not PAPER_TRADING and LIVE_CONFIRMED

# ── Capital ───────────────────────────────────────────────────
TOTAL_CAPITAL         = float(os.getenv("TOTAL_CAPITAL", "1000"))
CAPITAL_ARB           = float(os.getenv("STRATEGY_CAPITAL_ARB", "200"))
CAPITAL_WHALE         = float(os.getenv("STRATEGY_CAPITAL_WHALE", "300"))
CAPITAL_MM            = float(os.getenv("STRATEGY_CAPITAL_MM", "200"))
CAPITAL_MOMENTUM      = float(os.getenv("STRATEGY_CAPITAL_MOMENTUM", "150"))
CAPITAL_FLASH         = float(os.getenv("STRATEGY_CAPITAL_FLASH", "150"))

# ── Risk ──────────────────────────────────────────────────────
MAX_DAILY_LOSS_PCT    = float(os.getenv("MAX_DAILY_LOSS_PCT", "0.05"))
MAX_DRAWDOWN_PCT      = float(os.getenv("MAX_DRAWDOWN_PCT", "0.15"))
MAX_POSITION_PCT      = float(os.getenv("MAX_POSITION_PCT", "0.10"))
GLOBAL_KILL_SWITCH    = os.getenv("GLOBAL_KILL_SWITCH", "false").lower() == "true"
MIN_EDGE              = 0.06
MIN_VOLUME            = 5000
MIN_LIQUIDITY         = 500

# ── Whale tracker ─────────────────────────────────────────────
WHALE_MIN_WIN_RATE    = 0.62
WHALE_MIN_PNL         = 1000.0
WHALE_MIN_TRADES      = 50
WHALE_TOP_N           = 20
WHALE_BIG_TRADE_USD   = 3000
WHALE_COPY_DELAY_MS   = 500
WHALE_SIZE_SCALE      = 0.10
WHALE_MAX_SIZE        = 20.0

# ── Scanner ───────────────────────────────────────────────────
SCANNER_PARALLELISM   = int(os.getenv("SCANNER_PARALLELISM", "16"))
SCANNER_INTERVAL      = int(os.getenv("SCANNER_INTERVAL", "60"))
CACHE_TTL             = 300

# ── Dashboard ─────────────────────────────────────────────────
DASHBOARD_PORT        = int(os.getenv("DASHBOARD_PORT", "7825"))
TUI_ENABLED           = os.getenv("TUI_ENABLED", "true").lower() == "true"

# ── Alerts ───────────────────────────────────────────────────
TELEGRAM_TOKEN        = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID      = os.getenv("TELEGRAM_CHAT_ID", "")

# ── Paths ─────────────────────────────────────────────────────
LOG_PATH              = BASE_DIR / "logs" / "poly_tex.log"
DATA_PATH             = BASE_DIR / "data"
DB_PATH               = BASE_DIR / "data" / "poly_tex.db"

# Ensure dirs exist
LOG_PATH.parent.mkdir(exist_ok=True)
DATA_PATH.mkdir(exist_ok=True)

def validate():
    """Check required credentials are set"""
    missing = []
    if not POLY_PRIVATE_KEY: missing.append("POLY_PRIVATE_KEY")
    if not POLY_ADDRESS:      missing.append("POLY_ADDRESS")
    return missing

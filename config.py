# ═══════════════════════════════════════════════════════════════
#  POLY_TEX — Configuration
# ═══════════════════════════════════════════════════════════════

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

# ── Polymarket ──────────────────────────────────────────────────
POLY_API          = "https://clob.polymarket.com"
POLY_GAMMA        = "https://gamma-api.polymarket.com"
POLY_PRIVATE_KEY    = os.getenv("POLYMARKET_PRIVATE_KEY", "")   # set in .env
POLY_API_KEY        = os.getenv("POLYMARKET_API_KEY", "")
POLY_API_SECRET     = ""
POLY_API_PASSPHRASE = ""
POLY_ADDRESS        = os.getenv("POLYMARKET_ADDRESS", "")
CHAIN_ID          = 137   # Polygon mainnet

# ── Strategy ────────────────────────────────────────────────────
MIN_EDGE          = 0.08   # 8% minimum edge before betting
MAX_POSITION_PCT  = 0.15   # 15% of bankroll per bet
MIN_CONFIDENCE    = 0.72   # signal graph confidence floor
MIN_VOLUME        = 1000   # minimum market volume (USDC)
WALLET_TOP_N      = 20     # track top N performing wallets
COPY_WEIGHT       = 0.40   # weight for wallet signal
SIGNAL_WEIGHT     = 0.60   # weight for own signal graph

# ── Market focus ────────────────────────────────────────────────
FOCUS_KEYWORDS = []  # empty = scan ALL markets

# ── News sources ────────────────────────────────────────────────
RSS_FEEDS = [
    "https://feeds.feedburner.com/CoinDesk",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
    "https://www.theblockcrypto.com/rss.xml",
    "https://cryptonews.com/news/feed/",
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.bbci.co.uk/news/business/rss.xml",
]

REDDIT_SUBS = [
    "r/CryptoCurrency", "r/Bitcoin", "r/ethereum",
    "r/economics", "r/wallstreetbets", "r/investing",
]

# ── Signal graph ────────────────────────────────────────────────
SIGNAL_DB         = BASE_DIR / "data" / "signals.db"
SIGNAL_DECAY      = 0.95   # confidence decay per day
MAX_SIGNALS       = 50000

# ── Wallet tracking ─────────────────────────────────────────────
WALLET_DB         = BASE_DIR / "data" / "wallets.db"
MIN_WALLET_ROI    = 0.15   # minimum 15% ROI to track wallet
MIN_WALLET_BETS   = 10     # minimum bet count to qualify

# ── Execution ────────────────────────────────────────────────────
DRY_RUN           = True   # SET FALSE TO PLACE REAL BETS
CYCLE_MINUTES    = 2     # scan cycle interval
LOG_PATH          = BASE_DIR / "logs" / "poly_tex.log"

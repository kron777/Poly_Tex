# POLY_TEX — Polymarket Signal Intelligence Bot

Crypto & finance prediction market bot.
Combines signal graph intelligence with top wallet copy-trading.

## Architecture

```
News RSS → News Ingester → Signal Graph ─┐
                                         ├── Edge Detector → Executor
Polymarket → Wallet Tracker → Consensus ─┘
           ↓
         Market Scanner → Active Markets
```

## Modules

| Module | Purpose |
|--------|---------|
| signal_graph.py | Stores/retrieves probability signals (like NEX belief graph) |
| market_scanner.py | Fetches active Polymarket crypto/finance markets |
| wallet_tracker.py | Tracks top performer wallets, detects their positions |
| news_ingester.py | Scrapes RSS feeds, extracts directional signals |
| edge_detector.py | Compares our probability to market price, finds edge |
| executor.py | Places bets via Polymarket CLOB API |
| poly_tex.py | Main loop — orchestrates everything |

## Setup

```bash
bash setup.sh
cp .env.example .env   # add your keys
source venv/bin/activate
python3 poly_tex.py
```

## Config

Edit `config.py`:
- `DRY_RUN = False` — enable live trading
- `MIN_EDGE = 0.08` — minimum 8% edge to bet
- `MAX_POSITION_PCT = 0.15` — max 15% bankroll per bet
- `CYCLE_MINUTES = 15` — scan every 15 minutes

## Getting API Keys

1. Create account at polymarket.com
2. Connect Polygon wallet (MetaMask)
3. Go to Profile → API Keys
4. Generate key/secret/passphrase
5. Add to .env

## Risk Warning

This bot places real bets with real money when DRY_RUN=False.
Start with small bankroll. Monitor logs/poly_tex.log.

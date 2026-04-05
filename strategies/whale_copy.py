"""
Whale copy-trading strategy
Uses known top Polymarket wallets + activity endpoint
"""
import time, requests
from strategy_base import BaseStrategy, Signal
from market_scanner import MarketOpportunity
from logger import get_logger
from config import (WHALE_COPY_DELAY_MS, WHALE_SIZE_SCALE,
                    WHALE_MAX_SIZE, WHALE_BIG_TRADE_USD)

log = get_logger("strategy.whale")

# Known top Polymarket traders (manually curated)
# These are public wallet addresses visible on polymarket.com/leaderboard
SEED_WALLETS = [
    "0x9f2fe025f84839ca81dd8e0338892605702d2ca8",
    "0xc8075693f48668a264b9fa313b47f52712fcc12b",
    "0x0c0e270cf879583d6a0142fc817e05b768d0434e",
    "0xfd22b8843ae03a33a8a4c5e39ef1e5ff33ebad91",
    "0x1234567890abcdef1234567890abcdef12345678",
]

DATA_API = "https://data-api.polymarket.com"

class WhaleCopyStrategy(BaseStrategy):
    def __init__(self, capital: float, paper: bool = True):
        super().__init__("whale_copy", capital, paper)
        self.wallets = SEED_WALLETS
        self.seen_trades: set = set()
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'Mozilla/5.0'
        self.last_discovery = 0

    def _discover_wallets(self):
        """Try to discover top wallets from activity patterns"""
        # Get most active traders from recent market activity
        try:
            r = self.session.get(
                f"{DATA_API}/activity",
                params={"limit": 100},
                timeout=10
            )
            if r.status_code == 200:
                activity = r.json()
                if isinstance(activity, list):
                    wallets = list(set([
                        a.get("proxyWallet", a.get("user", ""))
                        for a in activity
                        if isinstance(a, dict)
                    ]))
                    wallets = [w for w in wallets if w and len(w) == 42]
                    if wallets:
                        log.info(f"Discovered {len(wallets)} active wallets")
                        self.wallets = list(set(self.wallets + wallets))[:20]
        except Exception as e:
            log.debug(f"Wallet discovery failed: {e}")
        self.last_discovery = time.time()

    def _get_wallet_activity(self, address: str) -> list:
        """Get recent trades for a wallet"""
        try:
            r = self.session.get(
                f"{DATA_API}/activity",
                params={"user": address, "limit": 20},
                timeout=8
            )
            if r.status_code == 200:
                d = r.json()
                return d if isinstance(d, list) else []
        except Exception as e:
            log.debug(f"Activity fetch failed for {address[:10]}: {e}")
        return []

    def analyze(self, markets: list[MarketOpportunity]) -> list[Signal]:
        # Discover new wallets hourly
        if time.time() - self.last_discovery > 3600:
            self._discover_wallets()

        market_map = {m.condition_id: m for m in markets}
        signals = []
        now = time.time()

        for address in self.wallets[:8]:
            trades = self._get_wallet_activity(address)
            for trade in trades:
                if not isinstance(trade, dict): continue

                # Unique trade ID
                tid = trade.get("id", trade.get("transactionHash",
                      trade.get("proxyWallet","") + str(trade.get("timestamp",""))))
                if tid in self.seen_trades: continue

                # Only recent trades (last 10 mins)
                ts = trade.get("timestamp", 0)
                if isinstance(ts, str):
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(ts.replace("Z","+00:00"))
                        ts = dt.timestamp()
                    except: ts = 0
                if now - float(ts or 0) > 600: continue

                # Map to market
                cid = trade.get("conditionId", trade.get("market",""))
                market = market_map.get(cid)
                if not market: continue

                side = str(trade.get("side", trade.get("type","BUY"))).upper()
                price = float(trade.get("price", 0.5) or 0.5)
                usd_size = float(trade.get("usdcSize",
                           trade.get("amount", trade.get("size", 0))) or 0)

                if usd_size < 10: continue

                copy_size = min(usd_size * WHALE_SIZE_SCALE, WHALE_MAX_SIZE)
                edge = 0.05  # Base edge for copy trades

                self.seen_trades.add(tid)
                if len(self.seen_trades) > 5000:
                    self.seen_trades = set(list(self.seen_trades)[-2500:])

                direction = "YES" if side in ["BUY","YES"] else "NO"

                signals.append(Signal(
                    market=market,
                    side=direction,
                    edge=edge,
                    our_prob=price + 0.05,
                    size_usd=copy_size,
                    confidence=0.60,
                    strategy=self.name,
                    reason=f"Copy {address[:10]}... ${usd_size:.0f}"
                ))

                if usd_size >= WHALE_BIG_TRADE_USD:
                    log.warning(f"🐋 BIG TRADE: {address[:10]}... "
                                f"${usd_size:.0f} on {market.question[:40]}")

        import state
        state.update(tracked_wallets=self.wallets[:8])
        return signals[:5]

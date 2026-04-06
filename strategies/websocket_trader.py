"""
WebSocket real-time trader
Monitors price feeds and trades on genuine sustained momentum
"""
import asyncio, json, threading, time, websockets
from strategy_base import BaseStrategy, Signal
from market_scanner import MarketOpportunity
from logger import get_logger

log = get_logger("strategy.ws")
WS_URI = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

class WebSocketTrader(BaseStrategy):
    def __init__(self, capital: float, paper: bool = True):
        super().__init__("ws_trade", capital, paper)
        self.price_cache: dict = {}    # asset_id -> list of prices
        self.signals_queue: list = []
        self.running = False
        self.markets_map: dict = {}    # asset_id -> MarketOpportunity
        self.token_ids: list = []
        self.last_signal_time: dict = {}  # market_id -> timestamp

    def start(self, markets: list[MarketOpportunity]):
        self.markets_map = {}
        self.token_ids = []
        # Only high liquidity markets
        for m in markets:
            if m.liquidity < 5000: continue
            if m.yes_token:
                self.markets_map[m.yes_token] = m
                self.token_ids.append(m.yes_token)

        if self.running:
            return
        self.running = True
        t = threading.Thread(target=self._run_loop, daemon=True)
        t.start()
        log.info(f"WS trader: watching {len(self.token_ids)} high-liquidity tokens")

    def _run_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        while self.running:
            try:
                loop.run_until_complete(self._listen())
            except Exception as e:
                log.debug(f"WS reconnecting: {e}")
                time.sleep(5)

    async def _listen(self):
        async with websockets.connect(WS_URI, ping_interval=20) as ws:
            for i in range(0, min(len(self.token_ids), 200), 50):
                batch = self.token_ids[i:i+50]
                await ws.send(json.dumps({
                    "auth": {}, "markets": [],
                    "assets_ids": batch, "type": "Market"
                }))
            log.info("WS subscribed")
            async for raw in ws:
                if not raw: continue
                try:
                    data = json.loads(raw)
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        self._process(item)
                except: pass

    def _process(self, data: dict):
        for change in data.get("price_changes", []):
            asset_id = change.get("asset_id", "")
            price = float(change.get("price", 0) or 0)
            if not asset_id or price <= 0 or price >= 1:
                continue

            market = self.markets_map.get(asset_id)
            if not market: continue

            # Only mid-range prices - genuine uncertainty
            if not (0.15 <= price <= 0.85): continue

            hist = self.price_cache.setdefault(asset_id, [])
            hist.append((time.time(), price))
            # Keep last 30 seconds of data
            hist[:] = [(t, p) for t, p in hist if time.time() - t < 30]

            if len(hist) < 6: continue

            prices = [p for _, p in hist]
            move = prices[-1] - prices[0]

            # Require sustained move: 4%+ over 6+ ticks, all same direction
            diffs = [prices[i+1] - prices[i] for i in range(len(prices)-1)]
            last4 = diffs[-4:]
            sustained = (all(d > 0 for d in last4) or
                        all(d < 0 for d in last4))

            if abs(move) < 0.04 or not sustained:
                continue

            # Rate limit - one signal per market per 5 minutes
            last = self.last_signal_time.get(market.id, 0)
            if time.time() - last < 300:
                continue

            direction = "YES" if move > 0 else "NO"
            size = self.kelly_size(abs(move))
            if size < 1.0: continue

            self.last_signal_time[market.id] = time.time()
            self.signals_queue.append(Signal(
                market=market,
                side=direction,
                edge=abs(move),
                our_prob=price,
                size_usd=size,
                confidence=0.62,
                strategy=self.name,
                reason=f"Sustained {direction} move {move:+.3f} over {len(hist)} ticks"
            ))
            log.info(f"⚡ WS momentum: {direction} {market.question[:45]} "
                    f"move={move:+.3f} liq=${market.liquidity:,.0f}")

    def analyze(self, markets: list[MarketOpportunity]) -> list[Signal]:
        if not self.running:
            self.start(markets)
        signals = self.signals_queue[:3]
        self.signals_queue = self.signals_queue[3:]
        return signals

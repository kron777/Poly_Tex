"""
Crypto Up/Down strategy
Trades BTC/ETH/SOL 5-15 minute markets when volume is high enough
These resolve every 15 mins - fast P&L feedback
"""
import requests, time
from datetime import datetime, timezone
from strategy_base import BaseStrategy, Signal
from market_scanner import MarketOpportunity
from logger import get_logger

log = get_logger("strategy.crypto")

class CryptoUpDownStrategy(BaseStrategy):
    def __init__(self, capital: float, paper: bool = True):
        super().__init__("crypto_updown", capital, paper)
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'Mozilla/5.0'
        self.traded: set = set()

    def _fetch_updown_markets(self) -> list:
        """Fetch current BTC/ETH/SOL up-down markets"""
        try:
            r = self.session.get(
                'https://gamma-api.polymarket.com/markets'
                '?limit=50&active=true&closed=false'
                '&order=endDate&ascending=true',
                timeout=10
            )
            markets = r.json()
            if not isinstance(markets, list):
                return []
            updown = [m for m in markets if
                     isinstance(m, dict) and
                     ('updown' in m.get('slug','').lower() or
                      'up-or-down' in m.get('slug','').lower())]
            return updown
        except Exception as e:
            log.debug(f"fetch updown error: {e}")
            return []

    def analyze(self, markets: list[MarketOpportunity]) -> list[Signal]:
        updown = self._fetch_updown_markets()
        if not updown:
            return []

        signals = []
        now = datetime.now(timezone.utc)

        for m in updown:
            slug = m.get('slug', '')
            if slug in self.traded:
                continue

            # Parse end time
            end_str = m.get('endDate', '')
            if not end_str:
                continue
            try:
                end = datetime.fromisoformat(end_str.replace('Z','+00:00'))
                mins_left = (end - now).total_seconds() / 60
            except:
                continue

            # Only trade 5-45 minutes before resolution
            if not (5 <= mins_left <= 45):
                continue

            # Need minimum volume
            vol = float(m.get('volumeNum', m.get('volume', 0)) or 0)
            if vol < 100:
                continue

            # Get prices
            import json as _json
            op = m.get('outcomePrices', '[]')
            if isinstance(op, str):
                try: op = _json.loads(op)
                except: op = []
            if len(op) < 2:
                continue

            yes_p = float(op[0])
            no_p = float(op[1])

            # Only trade genuine uncertainty 30-70%
            if not (0.30 <= yes_p <= 0.70):
                continue

            # Use Binance trend if available
            # For now bet on the slightly favored side
            side = "YES" if yes_p > 0.50 else "NO"
            edge = abs(yes_p - 0.50) + 0.03  # small base edge

            # Size small on these - high variance
            size = min(self.kelly_size(edge), 5.0)
            if size < 0.5:
                continue

            # Create a mock MarketOpportunity
            from market_scanner import MarketOpportunity
            mock = MarketOpportunity(
                id=m.get('id', slug),
                condition_id=m.get('conditionId', slug),
                question=m.get('question', slug),
                yes_price=yes_p,
                no_price=no_p,
                yes_token='',
                no_token='',
                volume=vol,
                liquidity=float(m.get('liquidityNum', 100)),
                spread=abs(1-yes_p-no_p),
                implied_prob=yes_p,
                category='crypto',
                end_date=end_str,
            )

            # Get token IDs
            clob_ids = m.get('clobTokenIds', '[]')
            if isinstance(clob_ids, str):
                try: clob_ids = _json.loads(clob_ids)
                except: clob_ids = []
            if len(clob_ids) >= 2:
                mock.yes_token = clob_ids[0]
                mock.no_token = clob_ids[1]

            signals.append(Signal(
                market=mock,
                side=side,
                edge=edge,
                our_prob=yes_p if side=='YES' else no_p,
                size_usd=size,
                confidence=0.55,
                strategy=self.name,
                reason=f"{mins_left:.0f}min left | vol=${vol:.0f} | {side} {yes_p:.2f}"
            ))

            log.info(f"Crypto signal: {side} {m.get('question','')[:50]} "
                    f"{mins_left:.0f}min left vol=${vol:.0f}")

        return signals[:3]

"""
Arbitrage strategy — finds markets where YES + NO < $1.00
Math-based guaranteed profit on resolution
"""
from strategy_base import BaseStrategy, Signal
from market_scanner import MarketOpportunity
from logger import get_logger

log = get_logger("strategy.arb")

class ArbitrageStrategy(BaseStrategy):
    """
    Cross-market arbitrage: buy YES + NO when sum < 0.99
    Profit = 1.00 - (yes_price + no_price)
    """

    def __init__(self, capital: float, paper: bool = True):
        super().__init__("arbitrage", capital, paper)
        self.min_profit_pct = 0.01  # 1% minimum
        self.max_size = 50.0

    def analyze(self, markets: list[MarketOpportunity]) -> list[Signal]:
        signals = []
        for m in markets:
            if not m.yes_token or not m.no_token: continue
            if m.volume < 10000: continue

            total = m.yes_price + m.no_price
            if total >= 0.99: continue  # No arb

            profit_pct = 1.0 - total
            if profit_pct < self.min_profit_pct: continue

            # Size based on liquidity and profit
            size = min(
                self.kelly_size(profit_pct, 1.0),
                m.liquidity * 0.05,
                self.max_size
            )
            if size < 1.0: continue

            log.info(f"ARB found: {m.question[:50]} "
                     f"sum={total:.4f} profit={profit_pct*100:.2f}%")

            signals.append(Signal(
                market=m,
                side="YES+NO",
                edge=profit_pct,
                our_prob=1.0,
                size_usd=size,
                confidence=0.95,
                strategy=self.name,
                reason=f"YES({m.yes_price:.3f})+NO({m.no_price:.3f})={total:.3f} < 1.0"
            ))

        return sorted(signals, key=lambda s: s.edge, reverse=True)

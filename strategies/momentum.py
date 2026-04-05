"""Momentum strategy — trades markets with strong directional price moves"""
from strategy_base import BaseStrategy, Signal
from market_scanner import MarketOpportunity

class MomentumStrategy(BaseStrategy):
    def __init__(self, capital: float, paper: bool = True):
        super().__init__("momentum", capital, paper)

    def analyze(self, markets: list[MarketOpportunity]) -> list[Signal]:
        signals = []
        for m in self.filter_markets(markets, min_vol=25000, price_range=(0.35, 0.65)):
            # Strong YES momentum (price > 0.70, high volume)
            if m.yes_price > 0.55 and m.volume > 50000:
                edge = m.yes_price - 0.65
                if edge > 0.05:
                    signals.append(Signal(
                        market=m, side="YES", edge=edge,
                        our_prob=m.yes_price + 0.03,
                        size_usd=self.kelly_size(edge),
                        confidence=0.60,
                        strategy=self.name,
                        reason=f"Strong YES momentum: {m.yes_price:.3f}"
                    ))
            # Strong NO momentum
            elif m.yes_price < 0.45 and m.volume > 50000:
                edge = 0.35 - m.yes_price
                if edge > 0.05:
                    signals.append(Signal(
                        market=m, side="NO", edge=edge,
                        our_prob=m.no_price + 0.03,
                        size_usd=self.kelly_size(edge),
                        confidence=0.58,
                        strategy=self.name,
                        reason=f"Strong NO momentum: {m.no_price:.3f}"
                    ))
        return sorted(signals, key=lambda s: s.edge, reverse=True)[:5]

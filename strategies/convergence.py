"""Convergence strategy — near-resolved markets approaching 0 or 1"""
from strategy_base import BaseStrategy, Signal
from market_scanner import MarketOpportunity

class ConvergenceStrategy(BaseStrategy):
    def __init__(self, capital: float, paper: bool = True):
        super().__init__("convergence", capital, paper)

    def analyze(self, markets: list[MarketOpportunity]) -> list[Signal]:
        signals = []
        for m in markets:
            if m.volume < 20000: continue
            # Market near YES resolution (0.85-0.95) — bet on YES
            if 0.85 <= m.yes_price <= 0.95 and m.liquidity > 1000:
                edge = m.yes_price * 0.08
                signals.append(Signal(
                    market=m, side="YES", edge=edge,
                    our_prob=m.yes_price + 0.02,
                    size_usd=self.kelly_size(edge),
                    confidence=0.70,
                    strategy=self.name,
                    reason=f"Near YES resolution: {m.yes_price:.3f}"
                ))
            # Market near NO resolution (0.05-0.15) — bet on NO
            elif 0.05 <= m.yes_price <= 0.15 and m.liquidity > 1000:
                edge = m.no_price * 0.08
                signals.append(Signal(
                    market=m, side="NO", edge=edge,
                    our_prob=m.no_price + 0.02,
                    size_usd=self.kelly_size(edge),
                    confidence=0.70,
                    strategy=self.name,
                    reason=f"Near NO resolution: {m.no_price:.3f}"
                ))
        return sorted(signals, key=lambda s: s.edge, reverse=True)[:5]

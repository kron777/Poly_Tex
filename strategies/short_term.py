"""
Short-term strategy — only trades markets ending within 7 days
These resolve fast = real P&L feedback
"""
from datetime import datetime, timezone
from strategy_base import BaseStrategy, Signal
from market_scanner import MarketOpportunity
from logger import get_logger

log = get_logger("strategy.shortterm")

class ShortTermStrategy(BaseStrategy):
    def __init__(self, capital: float, paper: bool = True):
        super().__init__("short_term", capital, paper)
        self.max_days = 7

    def analyze(self, markets: list[MarketOpportunity]) -> list[Signal]:
        signals = []
        now = datetime.now(timezone.utc)

        for m in markets:
            if not m.end_date: continue
            if m.volume < 100000: continue

            # Only markets ending within 7 days
            try:
                end = datetime.fromisoformat(
                    m.end_date.replace('Z', '+00:00'))
                days = (end - now).days
                if days < 0 or days > self.max_days: continue
            except: continue

            # Only genuine uncertainty 10-90%
            if not (0.10 <= m.yes_price <= 0.90): continue

            # Find the underdog side for value
            if m.yes_price < 0.50:
                # YES is underdog — check if we think it's underpriced
                edge = 0.50 - m.yes_price
                if edge > 0.08:
                    signals.append(Signal(
                        market=m, side="YES", edge=edge,
                        our_prob=m.yes_price + edge * 0.3,
                        size_usd=self.kelly_size(edge),
                        confidence=0.55,
                        strategy=self.name,
                        reason=f"{days}d left | YES underdog {m.yes_price:.2f}"
                    ))
            else:
                # NO is underdog
                edge = m.yes_price - 0.50
                if edge > 0.08:
                    signals.append(Signal(
                        market=m, side="NO", edge=edge,
                        our_prob=m.no_price + edge * 0.3,
                        size_usd=self.kelly_size(edge),
                        confidence=0.55,
                        strategy=self.name,
                        reason=f"{days}d left | NO underdog {m.no_price:.2f}"
                    ))

        signals.sort(key=lambda s: s.edge, reverse=True)
        log.info(f"Short-term: {len(signals)} signals from "
                 f"{len([m for m in markets if m.end_date])} dated markets")
        return signals[:3]

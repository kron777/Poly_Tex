"""Abstract base class for all strategies"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from market_scanner import MarketOpportunity
from logger import get_logger

@dataclass
class Signal:
    market: MarketOpportunity
    side: str          # YES or NO
    edge: float        # 0.0 - 1.0
    our_prob: float    # our estimated probability
    size_usd: float    # position size in USD
    confidence: float  # 0.0 - 1.0
    strategy: str
    reason: str = ""

class BaseStrategy(ABC):
    """All strategies inherit from this"""

    def __init__(self, name: str, capital: float, paper: bool = True):
        self.name = name
        self.capital = capital
        self.paper = paper
        self.log = get_logger(f"strategy.{name}")
        self.trades = 0
        self.wins = 0
        self.losses = 0
        self.profit = 0.0

    @abstractmethod
    def analyze(self, markets: list[MarketOpportunity]) -> list[Signal]:
        """Analyze markets and return signals"""
        pass

    def kelly_size(self, edge: float, odds: float = 1.0) -> float:
        """Kelly criterion position sizing"""
        if edge <= 0 or odds <= 0: return 0.0
        kelly = edge / odds
        # Quarter Kelly for safety
        return min(kelly * 0.25 * self.capital, self.capital * 0.10)

    def filter_markets(self, markets: list[MarketOpportunity],
                       min_vol: float = 5000,
                       min_liq: float = 500,
                       price_range: tuple = (0.05, 0.95)) -> list[MarketOpportunity]:
        """Standard market filters"""
        return [
            m for m in markets
            if m.volume >= min_vol
            and m.liquidity >= min_liq
            and price_range[0] <= m.yes_price <= price_range[1]
        ]

    def record_result(self, won: bool, pnl: float):
        """Track strategy performance"""
        self.trades += 1
        if won: self.wins += 1
        else: self.losses += 1
        self.profit += pnl

    @property
    def win_rate(self) -> float:
        if self.trades == 0: return 0.0
        return self.wins / self.trades

    @property
    def stats(self) -> dict:
        return {
            "name": self.name,
            "trades": self.trades,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": round(self.win_rate, 3),
            "profit": round(self.profit, 4),
            "capital": self.capital,
        }

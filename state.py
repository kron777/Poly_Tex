"""Global shared state — single source of truth for dashboard + strategies"""
import threading
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

_lock = threading.Lock()

@dataclass
class TradeRecord:
    ts: str
    strategy: str
    market: str
    question: str
    side: str
    size: float
    price: float
    edge: float
    paper: bool
    result: str = "open"
    pnl: float = 0.0

@dataclass  
class State:
    # Balances
    usdc_balance: float = 1000.0
    paper_balance: float = 1000.0
    peak_balance: float = 1000.0
    matic_balance: float = 0.0

    # P&L
    total_pnl: float = 0.0
    daily_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    session_start: str = field(default_factory=lambda: datetime.now().isoformat())

    # Trading
    trades: list = field(default_factory=list)
    open_positions: list = field(default_factory=list)
    total_trades: int = 0
    wins: int = 0
    losses: int = 0

    # Strategies
    arb_profit: float = 0.0
    whale_copies: int = 0
    mm_profit: float = 0.0
    signals_found: int = 0

    # Markets
    markets_scanned: int = 0
    opportunities: list = field(default_factory=list)
    markets: list = field(default_factory=list)

    # Whale
    tracked_wallets: list = field(default_factory=list)
    whale_signals: list = field(default_factory=list)

    # System
    cycle: int = 0
    last_cycle: str = ""
    is_live: bool = False
    kill_switch: bool = False
    errors: list = field(default_factory=list)

    # Market trends
    btc_trend: str = "neutral"
    eth_trend: str = "neutral"

STATE = State()

def update(**kwargs):
    with _lock:
        for k, v in kwargs.items():
            if hasattr(STATE, k):
                setattr(STATE, k, v)

def add_trade(trade: TradeRecord):
    with _lock:
        STATE.trades.insert(0, trade.__dict__)
        if len(STATE.trades) > 200:
            STATE.trades = STATE.trades[:200]
        STATE.total_trades += 1

def add_opportunity(opp: dict):
    with _lock:
        STATE.opportunities.insert(0, opp)
        if len(STATE.opportunities) > 50:
            STATE.opportunities = STATE.opportunities[:50]
        STATE.signals_found += 1

def to_dict() -> dict:
    with _lock:
        import dataclasses
        return dataclasses.asdict(STATE)

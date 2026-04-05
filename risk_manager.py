"""
Enterprise risk management
Global kill switch, daily loss halts, drawdown breaker
"""
import time
from logger import get_logger
from config import (MAX_DAILY_LOSS_PCT, MAX_DRAWDOWN_PCT,
                    MAX_POSITION_PCT, GLOBAL_KILL_SWITCH, TOTAL_CAPITAL)
import state

log = get_logger("risk")

class RiskManager:
    def __init__(self):
        self.start_capital = TOTAL_CAPITAL
        self.day_start_capital = TOTAL_CAPITAL
        self.day_start_time = time.time()
        self.halted = False
        self.halt_reason = ""

    def check(self, signal_size: float) -> tuple[bool, str]:
        """
        Returns (approved, reason)
        Call before every trade
        """
        if GLOBAL_KILL_SWITCH or self.halted:
            return False, f"HALTED: {self.halt_reason or 'kill switch'}"

        capital = state.STATE.paper_balance if state.STATE.is_live is False else state.STATE.usdc_balance

        # Daily loss check
        daily_loss = (self.day_start_capital - capital) / self.day_start_capital
        if daily_loss > MAX_DAILY_LOSS_PCT:
            self._halt(f"Daily loss limit: {daily_loss*100:.1f}%")
            return False, self.halt_reason

        # Drawdown check
        drawdown = (self.start_capital - capital) / self.start_capital
        if drawdown > MAX_DRAWDOWN_PCT:
            self._halt(f"Max drawdown: {drawdown*100:.1f}%")
            return False, self.halt_reason

        # Position size check
        if signal_size > capital * MAX_POSITION_PCT:
            return False, f"Position too large: ${signal_size:.2f}"

        # Min size
        if signal_size < 1.0:
            return False, "Position too small"

        return True, "approved"

    def _halt(self, reason: str):
        self.halted = True
        self.halt_reason = reason
        log.critical(f"TRADING HALTED: {reason}")
        state.update(kill_switch=True)

    def reset_daily(self):
        """Call at start of each day"""
        capital = state.STATE.paper_balance
        self.day_start_capital = capital
        self.day_start_time = time.time()
        log.info(f"Daily risk reset — capital: ${capital:.2f}")

    @property
    def status(self) -> dict:
        capital = state.STATE.paper_balance
        return {
            "halted": self.halted,
            "halt_reason": self.halt_reason,
            "daily_loss_pct": round((self.day_start_capital - capital) / max(self.day_start_capital, 1), 4),
            "drawdown_pct": round((self.start_capital - capital) / max(self.start_capital, 1), 4),
            "max_daily_loss": MAX_DAILY_LOSS_PCT,
            "max_drawdown": MAX_DRAWDOWN_PCT,
        }

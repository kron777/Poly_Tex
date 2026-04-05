"""
Position resolver — checks open paper trades against market outcomes
Runs every cycle to update P&L when markets resolve
"""
import requests
from logger import get_logger
from config import GAMMA_API
import state

log = get_logger("resolver")

session = requests.Session()
session.headers['User-Agent'] = 'Mozilla/5.0'

def check_resolution(trade: dict) -> tuple[str, float]:
    """
    Check if a market resolved and calculate P&L
    Returns (result, pnl)
    """
    condition_id = trade.get("market", "")
    side = trade.get("side", "NO")
    size = float(trade.get("size", 0))
    price = float(trade.get("price", 0.5))
    
    if not condition_id:
        return "open", 0.0

    try:
        r = session.get(
            f"{GAMMA_API}/markets/{condition_id}",
            timeout=8
        )
        if r.status_code != 200:
            return "open", 0.0
        
        m = r.json()
        if not isinstance(m, dict):
            return "open", 0.0

        # Check if resolved
        resolved = m.get("resolved", False)
        closed = m.get("closed", False)
        
        if not resolved and not closed:
            return "open", 0.0

        # Get outcome
        outcome_prices = m.get("outcomePrices", "[]")
        if isinstance(outcome_prices, str):
            import json
            try: outcome_prices = json.loads(outcome_prices)
            except: outcome_prices = []

        if not outcome_prices:
            return "open", 0.0

        yes_resolved = float(outcome_prices[0]) if outcome_prices else 0
        no_resolved  = float(outcome_prices[1]) if len(outcome_prices) > 1 else 0

        # Did we win?
        shares = size / max(price, 0.01)
        if side == "YES":
            if yes_resolved >= 0.99:
                pnl = shares * 1.0 - size  # Won
                return "win", round(pnl, 4)
            elif no_resolved >= 0.99:
                pnl = -size  # Lost
                return "loss", round(pnl, 4)
        elif side == "NO":
            if no_resolved >= 0.99:
                pnl = shares * 1.0 - size  # Won
                return "win", round(pnl, 4)
            elif yes_resolved >= 0.99:
                pnl = -size  # Lost
                return "loss", round(pnl, 4)

        return "open", 0.0

    except Exception as e:
        log.debug(f"Resolution check failed: {e}")
        return "open", 0.0

def resolve_positions():
    """Check all open trades for resolution"""
    trades = state.STATE.trades
    if not trades:
        return

    total_pnl_delta = 0.0
    wins = 0
    losses = 0
    resolved_count = 0

    for trade in trades:
        if trade.get("result") != "open":
            continue

        result, pnl = check_resolution(trade)
        
        if result != "open":
            trade["result"] = result
            trade["pnl"] = pnl
            total_pnl_delta += pnl
            resolved_count += 1
            
            if result == "win":
                wins += 1
                log.info(f"✅ WIN: {trade['question'][:40]} +${pnl:.4f}")
            else:
                losses += 1
                log.info(f"❌ LOSS: {trade['question'][:40]} -${abs(pnl):.4f}")

    if resolved_count > 0:
        new_pnl = state.STATE.total_pnl + total_pnl_delta
        new_balance = state.STATE.paper_balance + total_pnl_delta
        new_wins = state.STATE.wins + wins
        new_losses = state.STATE.losses + losses
        
        state.update(
            total_pnl=round(new_pnl, 4),
            paper_balance=round(new_balance, 4),
            wins=new_wins,
            losses=new_losses,
            daily_pnl=round(state.STATE.daily_pnl + total_pnl_delta, 4),
        )
        log.info(f"Resolved {resolved_count} positions | "
                 f"PnL delta: {total_pnl_delta:+.4f} | "
                 f"New balance: ${new_balance:.2f}")

"""
POLY_TEX v2.0 — Main trading loop
Orchestrates all strategies, scanner, risk manager, dashboard
"""
import time, sys, threading
from datetime import datetime
from config import (PAPER_TRADING, IS_LIVE, TOTAL_CAPITAL,
                    CAPITAL_ARB, CAPITAL_WHALE, CAPITAL_MOMENTUM,
                    CAPITAL_FLASH, SCANNER_INTERVAL, DASHBOARD_PORT,
                    validate)
from logger import get_logger
from market_scanner import scan_markets
from risk_manager import RiskManager
from strategies import (ArbitrageStrategy, WhaleCopyStrategy,
                        MomentumStrategy, ConvergenceStrategy)
from clob_client import get_client
import state
from state import update, add_trade, add_opportunity, TradeRecord

log = get_logger("poly_tex")

def banner():
    mode = "🧪 PAPER TRADING" if not IS_LIVE else "💰 LIVE TRADING"
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  POLY_TEX v2.0  ·  Polymarket Signal Intelligence Bot       ║")
    print(f"║  Mode: {mode:<52}║")
    print(f"║  Capital: ${TOTAL_CAPITAL:<51,.2f}║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

def execute_signal(signal, risk: RiskManager, paper: bool):
    """Execute or simulate a trade signal"""
    approved, reason = risk.check(signal.size_usd)
    if not approved:
        log.debug(f"Signal rejected: {reason}")
        return False

    client = get_client()
    token_id = (signal.market.yes_token if signal.side == "YES"
                else signal.market.no_token)

    price = (signal.market.yes_price if signal.side == "YES"
             else signal.market.no_price)

    result = client.place_order(
        token_id=token_id,
        side="BUY",
        size=signal.size_usd / max(price, 0.01),
        price=price,
        paper=paper
    )

    if result:
        trade = TradeRecord(
            ts=datetime.now().strftime("%H:%M:%S"),
            strategy=signal.strategy,
            market=signal.market.condition_id,
            question=signal.market.question[:60],
            side=signal.side,
            size=signal.size_usd,
            price=price,
            edge=signal.edge,
            paper=paper,
        )
        add_trade(trade)
        add_opportunity({
            "id": signal.market.id,
            "question": signal.market.question,
            "direction": signal.side,
            "edge": signal.edge,
            "size_usd": signal.size_usd,
            "strategy": signal.strategy,
            "price": price,
            "ts": trade.ts,
        })
        # Update market in state
        for m in state.STATE.markets:
            if m.get("id") == signal.market.id:
                m["edge"] = signal.edge
                m["direction"] = signal.side
                m["strategy"] = signal.strategy
        log.info(f"✅ {'[PAPER]' if paper else '[LIVE]'} "
                 f"{signal.strategy.upper()} {signal.side} "
                 f"${signal.size_usd:.2f} @ {price:.3f} | "
                 f"edge={signal.edge*100:.1f}% | "
                 f"{signal.market.question[:40]}")
        return True
    return False

def run_cycle(cycle_num: int, strategies: list, risk: RiskManager):
    """One full trading cycle"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    update(cycle=cycle_num, last_cycle=ts)
    log.info(f"═══ Cycle {cycle_num} · {ts} ═══")

    # Scan markets
    markets = scan_markets(max_markets=400)
    update(markets_scanned=len(markets),
           markets=[{
               "id": m.id,
               "question": m.question,
               "yes_price": m.yes_price,
               "no_price": m.no_price,
               "volume": m.volume,
               "edge": m.edge,
               "direction": m.direction,
               "strategy": "",
           } for m in markets[:100]])

    log.info(f"Scanned {len(markets)} markets")

    # Run each strategy
    total_signals = 0
    trades_placed = 0
    for strategy in strategies:
        try:
            signals = strategy.analyze(markets)
            total_signals += len(signals)
            log.info(f"{strategy.name}: {len(signals)} signals")
            for signal in signals[:3]:  # Max 3 per strategy per cycle
                if execute_signal(signal, risk, paper=not IS_LIVE):
                    trades_placed += 1
        except Exception as e:
            log.error(f"{strategy.name} error: {e}")

    update(signals_found=total_signals)
    log.info(f"Cycle {cycle_num} done: "
             f"{total_signals} signals, {trades_placed} trades")
    return trades_placed

def main():
    banner()

    # Validate credentials
    missing = validate()
    if missing:
        log.warning(f"Missing credentials: {missing} — running in read-only mode")

    # Init state
    update(is_live=IS_LIVE, paper_balance=TOTAL_CAPITAL,
           usdc_balance=0.0)

    # Start dashboard
    try:
        from dashboard.server import start as start_dashboard
        start_dashboard(DASHBOARD_PORT)
        print(f"  Dashboard: http://localhost:{DASHBOARD_PORT}")
    except Exception as e:
        log.warning(f"Dashboard failed: {e}")

    # Init strategies
    strategies = [
        ArbitrageStrategy(capital=CAPITAL_ARB, paper=not IS_LIVE),
        WhaleCopyStrategy(capital=CAPITAL_WHALE, paper=not IS_LIVE),
        MomentumStrategy(capital=CAPITAL_MOMENTUM, paper=not IS_LIVE),
        ConvergenceStrategy(capital=CAPITAL_FLASH, paper=not IS_LIVE),
    ]
    log.info(f"Loaded {len(strategies)} strategies")

    # Init risk manager
    risk = RiskManager()

    print(f"  Mode     : {'PAPER' if not IS_LIVE else 'LIVE'}")
    print(f"  Capital  : ${TOTAL_CAPITAL:,.2f}")
    print(f"  Strategies: {len(strategies)}")
    print(f"  Cycle    : every {SCANNER_INTERVAL}s")
    print()

    cycle = 0
    while True:
        try:
            if state.STATE.kill_switch:
                log.critical("Kill switch active — halted")
                time.sleep(30)
                continue

            cycle += 1
            run_cycle(cycle, strategies, risk)

            # Update strategy stats in state
            strat_stats = {s.name: s.stats for s in strategies}
            arb = strat_stats.get("arbitrage", {})
            whale = strat_stats.get("whale_copy", {})
            update(
                arb_profit=arb.get("profit", 0),
                whale_copies=whale.get("trades", 0),
            )

            log.info(f"Sleeping {SCANNER_INTERVAL}s...")
            time.sleep(SCANNER_INTERVAL)

        except KeyboardInterrupt:
            print("\n  Shutting down gracefully...")
            sys.exit(0)
        except Exception as e:
            log.error(f"Cycle error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()

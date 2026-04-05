# ═══════════════════════════════════════════════════════════════
#  POLY_TEX — Main Brain Loop
#  Orchestrates all modules. Runs every CYCLE_MINUTES.
#
#  Run: python3 poly_tex.py
#  Monitor: tail -f logs/poly_tex.log
# ═══════════════════════════════════════════════════════════════

import time
import sys
import os
from pathlib import Path
from datetime import datetime

from config import CYCLE_MINUTES, DRY_RUN, LOG_PATH
from signal_graph import get_stats
from market_scanner import get_top_markets
from wallet_tracker import update_leaderboard, scan_wallet_positions
from news_ingester import ingest_feeds
from edge_detector import analyse_market
from executor import get_balance, place_bet, log_opportunity
from broadcaster import emit

# ── Terminal colours ─────────────────────────────────────────────
R  = "\033[91m"
G  = "\033[92m"
Y  = "\033[93m"
B  = "\033[94m"
M  = "\033[95m"
C  = "\033[96m"
W  = "\033[97m"
DIM = "\033[2m"
RST = "\033[0m"
BOLD = "\033[1m"

def banner():
    os.system("clear")
    print(f"""
{C}╔══════════════════════════════════════════════════════════════╗
║  {W}{BOLD}POLY_TEX{RST}{C}  ·  Polymarket Signal Intelligence Bot              ║
║  {DIM}Crypto & Finance · Signal Graph + Wallet Tracking{RST}{C}          ║
╚══════════════════════════════════════════════════════════════╝{RST}
""")

def print_block(title, colour=C):
    print(f"\n{colour}{'═'*64}")
    print(f"  {BOLD}{title}{RST}{colour}")
    print(f"{'═'*64}{RST}")

def status_line(label, value, colour=W):
    print(f"  {DIM}{label:<22}{RST}{colour}{value}{RST}")

def run_cycle(cycle_num, bankroll):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    banner()

    print(f"  {DIM}Cycle {cycle_num} · {now} · "
          f"{'DRY RUN' if DRY_RUN else 'LIVE'}{RST}")

    # ── Signal graph stats ──────────────────────────────────────
    print_block("SIGNAL GRAPH", C)
    stats = get_stats()
    status_line("Total signals:", f"{stats['total']:,}")
    status_line("Avg confidence:", f"{(stats['avg_confidence'] or 0):.3f}")
    for topic, count in list((stats.get('by_topic') or {}).items())[:6]:
        status_line(f"  {topic}:", f"{count:,}")
    emit("stats", {"total_signals": stats["total"], "avg_confidence": stats.get("avg_confidence") or 0, "topics": stats.get("by_topic") or {}})

    # ── News ingestion ──────────────────────────────────────────
    print_block("NEWS INGESTION", B)
    print(f"  Fetching RSS feeds...")
    n_signals = ingest_feeds()
    emit("ingest_done", {"added": n_signals})
    print(f"  {G}+{n_signals} new signals ingested{RST}")

    # ── Wallet tracking ─────────────────────────────────────────
    print_block("WALLET TRACKING", M)
    update_leaderboard()
    positions = scan_wallet_positions()
    print(f"  {G}{len(positions)} open positions detected across top wallets{RST}")

    # ── Market scan ─────────────────────────────────────────────
    print_block("MARKET SCAN", Y)
    markets = get_top_markets(max_markets=50)
    emit("markets", {"markets": [{"id": m.get("id",""), "question": m.get("question",""), "yes_price": m.get("yes_price"), "no_price": m.get("no_price"), "volume": m.get("volume")} for m in markets]})
    print(f"  Found {len(markets)} relevant crypto/finance markets")

    # ── Edge detection ──────────────────────────────────────────
    print_block("EDGE DETECTION", G)
    opportunities = []
    for market in markets:
        opp = analyse_market(market, bankroll)
        if opp:
            opportunities.append(opp)

    if not opportunities:
        print(f"  {DIM}No edge found this cycle. Market efficiently priced.{RST}")
    else:
        print(f"  {G}{BOLD}{len(opportunities)} OPPORTUNITIES FOUND:{RST}")
        for opp in sorted(opportunities, key=lambda x: x["edge"], reverse=True):
            edge_col = G if opp["edge"] > 0.12 else Y
            print(f"""
  {BOLD}{opp['question'][:65]}{RST}
  {DIM}Direction:{RST} {edge_col}{BOLD}{opp['direction']}{RST}  {DIM}Edge:{RST} {edge_col}{opp['edge']:.1%}{RST}  {DIM}Size:{RST} {W}${opp['position_size']:.2f}{RST}
  {DIM}Our prob:{RST} {opp['our_prob']:.3f}  {DIM}Market:{RST} {opp['market_price']:.3f}  {DIM}Conf:{RST} {opp['our_confidence']:.3f}  {DIM}Method:{RST} {opp['method']}""")

    # ── Execution ───────────────────────────────────────────────
    print_block("EXECUTION", R if not DRY_RUN else DIM)
    bets_placed = 0
    for opp in opportunities:
        log_opportunity(opp)
        result = place_bet(
            market_id=opp["market_id"],
            direction=opp["direction"],
            size_usdc=opp["position_size"],
            price=opp["market_price"],
            dry_run=DRY_RUN,
        )
        if result:
            log_opportunity(opp, executed=True, order_result=result)
            bets_placed += 1
            emit("edge", {**opp, "dry_run": DRY_RUN})

    # ── Summary ─────────────────────────────────────────────────
    print_block("CYCLE SUMMARY", W)
    status_line("Cycle:", str(cycle_num))
    status_line("Bankroll:", f"${bankroll:.2f} USDC")
    status_line("Markets scanned:", str(len(markets)))
    status_line("Opportunities:", str(len(opportunities)))
    status_line("Bets placed:", str(bets_placed))
    status_line("Next cycle in:", f"{CYCLE_MINUTES} minutes")
    status_line("Mode:", f"{'🔴 LIVE' if not DRY_RUN else '🟡 DRY RUN'}")

    print(f"\n  {DIM}Sleeping {CYCLE_MINUTES * 60}s...{RST}\n")
    emit("cycle_start", {"cycle": cycle_num, "dry_run": DRY_RUN})
    return bets_placed

def main():
    banner()
    print(f"  {Y}Starting POLY_TEX...{RST}")
    print(f"  Mode: {R if not DRY_RUN else Y}{'LIVE TRADING' if not DRY_RUN else 'DRY RUN (no real bets)'}{RST}")
    print(f"  Cycle: every {CYCLE_MINUTES} minutes")

    if not DRY_RUN:
        print(f"\n  {R}{BOLD}⚠  LIVE MODE ACTIVE — REAL MONEY AT RISK  ⚠{RST}")
        time.sleep(3)

    cycle = 0
    total_bets = 0

    while True:
        cycle += 1
        bankroll = get_balance() if not DRY_RUN else 1000.0

        try:
            bets = run_cycle(cycle, bankroll)
            total_bets += bets
        except KeyboardInterrupt:
            print(f"\n\n  {Y}Shutting down. Total bets placed: {total_bets}{RST}\n")
            sys.exit(0)
        except Exception as e:
            print(f"\n  {R}Cycle error: {e}{RST}")
            import traceback
            traceback.print_exc()

        try:
            time.sleep(CYCLE_MINUTES * 60)
        except KeyboardInterrupt:
            print(f"\n\n  {Y}Shutting down. Total bets placed: {total_bets}{RST}\n")
            sys.exit(0)

if __name__ == "__main__":
    main()

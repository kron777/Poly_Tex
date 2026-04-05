# ═══════════════════════════════════════════════════════════════
#  POLY_TEX — Edge Detector
#  Core logic. Compares our probability estimate to market price.
#  Only bets when gap (edge) exceeds threshold.
# ═══════════════════════════════════════════════════════════════

import re
from signal_graph import retrieve_signals, synthesise_probability
from wallet_tracker import get_market_consensus
from market_scanner import classify_topic
from config import (MIN_EDGE, MIN_CONFIDENCE, COPY_WEIGHT,
                    SIGNAL_WEIGHT, MAX_POSITION_PCT)

def keyword_match_topic(question):
    """Map market question to signal graph topic."""
    q = question.lower()
    if any(w in q for w in ["bitcoin","btc","ethereum","eth","crypto","defi"]):
        return "crypto"
    if any(w in q for w in ["fed","inflation","cpi","rate","recession","gdp"]):
        return "macro"
    if any(w in q for w in ["stock","nasdaq","s&p","equity"]):
        return "equities"
    if any(w in q for w in ["sec","regulation","ban","lawsuit","cftc"]):
        return "regulation"
    if any(w in q for w in ["dollar","usd","forex","currency"]):
        return "forex"
    return "finance"

def estimate_probability(market):
    """
    Blend signal graph + wallet consensus into a single probability estimate.
    Returns dict with full reasoning.
    """
    question = market["question"]
    topic = keyword_match_topic(question)

    # ── Signal graph component ─────────────────────────────────
    signals = retrieve_signals(topic, min_confidence=MIN_CONFIDENCE * 0.85)
    signal_prob, signal_conf, signal_reasoning = synthesise_probability(
        signals, question
    )

    # ── Wallet consensus component ─────────────────────────────
    wallet_dir, wallet_conf, wallet_count = get_market_consensus(market["id"])
    wallet_prob = None
    if wallet_dir:
        wallet_prob = wallet_conf if wallet_dir == "YES" else 1 - wallet_conf

    # ── Blend ──────────────────────────────────────────────────
    if signal_prob is not None and wallet_prob is not None:
        our_prob = (SIGNAL_WEIGHT * signal_prob) + (COPY_WEIGHT * wallet_prob)
        our_conf = (SIGNAL_WEIGHT * signal_conf) + (COPY_WEIGHT * wallet_conf)
        method = "blended"
    elif signal_prob is not None:
        our_prob = signal_prob
        our_conf = signal_conf * 0.85   # discount for no wallet confirmation
        method = "signal_only"
    elif wallet_prob is not None:
        our_prob = wallet_prob
        our_conf = wallet_conf * 0.80   # discount for no signal confirmation
        method = "wallet_only"
    else:
        return None

    return {
        "market_id":        market["id"],
        "question":         question,
        "topic":            topic,
        "our_probability":  round(our_prob, 4),
        "our_confidence":   round(our_conf, 4),
        "method":           method,
        "signal_prob":      signal_prob,
        "signal_conf":      signal_conf,
        "wallet_dir":       wallet_dir,
        "wallet_conf":      wallet_conf,
        "wallet_count":     wallet_count,
        "signal_reasoning": signal_reasoning,
        "market_yes_price": market["yes_price"],
        "market_no_price":  market["no_price"],
    }

def calculate_edge(estimate):
    """
    Compare our probability to market price.
    Returns (direction, edge, market_price) or None if no edge.
    """
    if not estimate:
        return None

    our_p = estimate["our_probability"]
    yes_p = estimate["market_yes_price"]
    no_p  = estimate["market_no_price"]

    # Edge on YES side
    yes_edge = our_p - yes_p
    # Edge on NO side (if we think probability is LOW)
    no_edge  = (1 - our_p) - no_p

    if yes_edge >= MIN_EDGE and yes_edge > no_edge:
        return {
            "direction":    "YES",
            "edge":         round(yes_edge, 4),
            "market_price": yes_p,
            "our_prob":     our_p,
        }
    elif no_edge >= MIN_EDGE:
        return {
            "direction":    "NO",
            "edge":         round(no_edge, 4),
            "market_price": no_p,
            "our_prob":     1 - our_p,
        }
    return None

def calculate_position_size(bankroll, edge, confidence, market_liquidity):
    """
    Kelly-inspired position sizing.
    f* = (edge * confidence) / (1 - market_price)
    Capped at MAX_POSITION_PCT of bankroll.
    """
    if edge <= 0:
        return 0

    # fractional Kelly (25% Kelly for safety)
    kelly = edge * confidence * 0.25
    kelly_usdc = bankroll * kelly

    # hard cap
    max_usdc = bankroll * MAX_POSITION_PCT

    # liquidity cap (don't take more than 5% of market liquidity)
    liquidity_cap = market_liquidity * 0.05

    position = min(kelly_usdc, max_usdc, liquidity_cap)
    return round(max(position, 0), 2)

def analyse_market(market, bankroll):
    """
    Full analysis pipeline for a single market.
    Returns a bet opportunity dict or None.
    """
    if estimate := estimate_probability(market):
        if edge_info := calculate_edge(estimate):
            size = calculate_position_size(
                bankroll,
                edge_info["edge"],
                estimate["our_confidence"],
                market["liquidity"],
            )
            if size < 5:   # minimum bet $5
                return None
            return {
                **estimate,
                **edge_info,
                "position_size": size,
                "volume":        market["volume"],
                "liquidity":     market["liquidity"],
            }
    return None

if __name__ == "__main__":
    # Test with a mock market
    mock_market = {
        "id": "test-001",
        "question": "Will Bitcoin exceed $100,000 by end of April 2026?",
        "yes_price": 0.35,
        "no_price": 0.65,
        "volume": 50000,
        "liquidity": 20000,
    }
    result = analyse_market(mock_market, bankroll=1000)
    if result:
        print(f"BET FOUND: {result['direction']} @ {result['market_price']}")
        print(f"  Edge: {result['edge']:.1%}")
        print(f"  Size: ${result['position_size']:.2f}")
        print(f"  Confidence: {result['our_confidence']:.2f}")
    else:
        print("No edge found (signal graph likely empty — run news_ingester first)")

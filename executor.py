# ═══════════════════════════════════════════════════════════════
#  POLY_TEX — Executor (py-clob-client edition)
#  Places bets on Polymarket via CLOB API with EIP-712 signing.
#  DRY_RUN=True by default — logs bets without executing.
# ═══════════════════════════════════════════════════════════════

import json
import time
import requests
from dotenv import load_dotenv
load_dotenv()

from config import (
    POLY_API, POLY_PRIVATE_KEY, POLY_API_KEY,
    POLY_ADDRESS, CHAIN_ID, DRY_RUN, LOG_PATH
)

# ── CLOB client setup ────────────────────────────────────────────
_client = None

def get_client():
    global _client
    if _client is not None:
        return _client
    if not POLY_PRIVATE_KEY:
        print("  ✗ No private key set")
        return None
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.constants import POLYGON

        _client = ClobClient(
            host=POLY_API,
            key=POLY_PRIVATE_KEY,
            chain_id=POLYGON,
            signature_type=2,        # POLY_GNOSIS_SAFE
            funder=POLY_ADDRESS,
        )
        # Derive API credentials from private key if no API key set
        if POLY_API_KEY:
            _client.set_api_creds(_client.create_or_derive_api_creds())
        return _client
    except Exception as e:
        print(f"  ✗ Client init error: {e}")
        return None


def get_balance() -> float:
    """Get current USDC balance from Polymarket."""
    if DRY_RUN:
        return 0.0
    client = get_client()
    if not client:
        return 0.0
    try:
        bal = client.get_balance()
        # Returns value in USDC (6 decimals on Polygon)
        if isinstance(bal, dict):
            raw = float(bal.get("balance") or bal.get("usdc") or 0)
        else:
            raw = float(bal)
        return raw / 1e6 if raw > 1000 else raw  # handle raw wei vs USDC
    except Exception as e:
        print(f"  ✗ Balance error: {e}")
        return 0.0


def get_market_token_id(market_id: str, direction: str) -> str | None:
    """
    Resolve YES/NO token ID for a market from Gamma API.
    Polymarket CLOB trades on token IDs, not market IDs directly.
    """
    try:
        r = requests.get(
            f"https://gamma-api.polymarket.com/markets/{market_id}",
            timeout=10,
            headers={"User-Agent": "PolyTex/1.0"},
        )
        if r.status_code != 200:
            return None
        data = r.json()
        tokens = data.get("clobTokenIds") or data.get("tokens") or []
        if isinstance(tokens, str):
            tokens = json.loads(tokens)
        # tokens[0] = YES, tokens[1] = NO
        idx = 0 if direction == "YES" else 1
        if isinstance(tokens, list) and len(tokens) > idx:
            t = tokens[idx]
            return t if isinstance(t, str) else t.get("token_id") or t.get("id")
        return None
    except Exception as e:
        print(f"  ✗ Token ID lookup error: {e}")
        return None


def place_bet(market_id: str, direction: str, size_usdc: float,
              price: float, dry_run: bool = None) -> dict | None:
    """
    Place a bet on Polymarket.
    market_id:  Polymarket condition ID
    direction:  'YES' or 'NO'
    size_usdc:  dollar amount
    price:      limit price 0.0–1.0
    """
    _dry = DRY_RUN if dry_run is None else dry_run

    if _dry:
        print(f"  [DRY RUN] {direction} ${size_usdc:.2f} @ {price:.4f}")
        print(f"  [DRY RUN] Market: {market_id}")
        return {"dry_run": True, "market": market_id, "direction": direction,
                "size": size_usdc, "price": price}

    client = get_client()
    if not client:
        return None

    # Resolve token ID
    token_id = get_market_token_id(market_id, direction)
    if not token_id:
        print(f"  ✗ Could not resolve token ID for {market_id} {direction}")
        return None

    try:
        from py_clob_client.clob_types import OrderArgs, OrderType

        order_args = OrderArgs(
            token_id=token_id,
            price=price,
            size=size_usdc,
            side="BUY",              # we always buy YES or NO shares
        )
        signed_order = client.create_order(order_args)
        result = client.post_order(signed_order, OrderType.GTC)

        if result and result.get("success"):
            order_id = result.get("orderID") or result.get("id", "unknown")
            print(f"  ✓ Order placed: {order_id}")
            return result
        else:
            print(f"  ✗ Order failed: {result}")
            return None

    except Exception as e:
        print(f"  ✗ Order error: {e}")
        return None


def log_opportunity(opp: dict, executed: bool = False,
                    order_result: dict = None):
    """Append a bet opportunity to the log file."""
    import os
    os.makedirs(LOG_PATH.parent, exist_ok=True)
    entry = {
        "ts":           time.strftime("%Y-%m-%d %H:%M:%S"),
        "question":     opp.get("question", "")[:80],
        "direction":    opp.get("direction"),
        "edge":         opp.get("edge"),
        "our_prob":     opp.get("our_prob"),
        "market_price": opp.get("market_price"),
        "size":         opp.get("position_size"),
        "confidence":   opp.get("our_confidence"),
        "method":       opp.get("method"),
        "executed":     executed,
        "order":        str(order_result)[:100] if order_result else None,
    }
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ── Standalone test ───────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Executor — DRY_RUN={'YES' if DRY_RUN else 'NO (LIVE!)'}")
    print(f"Address:  {POLY_ADDRESS or 'NOT SET'}")
    print(f"API key:  {'set' if POLY_API_KEY else 'NOT SET'}")
    print(f"Priv key: {'set' if POLY_PRIVATE_KEY else 'NOT SET'}")
    print()

    if not DRY_RUN:
        print("Connecting to Polymarket CLOB...")
        client = get_client()
        if client:
            print("  ✓ Client initialized")
            bal = get_balance()
            print(f"  Balance: ${bal:.2f} USDC")
        else:
            print("  ✗ Client failed — check private key")
    else:
        print("DRY_RUN=True — set False in config.py to go live")

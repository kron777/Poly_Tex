# ═══════════════════════════════════════════════════════════════
#  POLY_TEX — Market Scanner (fixed)
# ═══════════════════════════════════════════════════════════════

import requests
import json
import time
import re
from config import POLY_GAMMA, FOCUS_KEYWORDS, MIN_VOLUME

HEADERS = {"Accept": "application/json", "User-Agent": "PolyTex/1.0"}

def fetch_markets(limit=200, offset=0):
    try:
        r = requests.get(
            f"{POLY_GAMMA}/markets",
            params={
                "active": "true",
                "closed": "false",
                "limit": limit,
                "offset": offset,
                "order": "volume24hr",
                "ascending": "false",
            },
            headers=HEADERS,
            timeout=15,
        )
        if r.status_code != 200:
            print(f"  Market fetch error: HTTP {r.status_code}")
            return []
        data = r.json()
        # Handle all response shapes
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("data","markets","results","items"):
                if key in data and isinstance(data[key], list):
                    return data[key]
        return []
    except Exception as e:
        print(f"  Market fetch error: {e}")
        return []

def is_relevant(market):
    if not isinstance(market, dict):
        return False
    text = (
        (market.get("question") or "") + " " +
        (market.get("description") or "") + " " +
        " ".join(market.get("tags") or [])
    ).lower()
    return True if not FOCUS_KEYWORDS else any(kw in text for kw in FOCUS_KEYWORDS)

def safe_float(val, default=0.0):
    try:
        return float(val or default)
    except:
        return default

def parse_market(m):
    if not isinstance(m, dict):
        return None

    tokens = m.get("tokens") or m.get("outcomes") or []
    yes_price = no_price = None

    for t in tokens:
        if not isinstance(t, dict):
            continue
        outcome = (t.get("outcome") or "").upper()
        price   = safe_float(t.get("price"), 0.5)
        if outcome == "YES":
            yes_price = price
        elif outcome == "NO":
            no_price = price

    # Fallbacks
    if yes_price is None:
        op = m.get("outcomePrices") or []
        if isinstance(op, str):
            import json as _j
            try: op = _j.loads(op)
            except: op = []
        yes_price = safe_float(op[0] if op else None, 0.5)
    if no_price is None:
        op = m.get("outcomePrices") or []
        if isinstance(op, str):
            import json as _j
            try: op = _j.loads(op)
            except: op = []
        no_price = safe_float(op[1] if len(op) > 1 else None, 1 - yes_price)

    volume    = safe_float(m.get("volume") or m.get("volume24hr") or m.get("volumeNum"))
    liquidity = safe_float(m.get("liquidity") or m.get("liquidityNum"))
    question  = m.get("question") or m.get("title") or ""

    if not question:
        return None

    return {
        "id":          m.get("conditionId") or m.get("id") or "",
        "question":    question,
        "description": m.get("description") or "",
        "yes_price":   round(yes_price, 4),
        "no_price":    round(no_price,  4),
        "volume":      volume,
        "liquidity":   liquidity,
        "end_date":    m.get("endDate") or m.get("end_date_iso") or "",
        "tags":        m.get("tags") or [],
        "slug":        m.get("slug") or "",
    }

def get_top_markets(max_markets=200):
    raw = fetch_markets(limit=200)
    markets = []
    for m in raw:
        if not isinstance(m, dict):
            continue
        if not is_relevant(m):
            continue
        parsed = parse_market(m)
        if not parsed:
            continue
        if parsed["volume"] < MIN_VOLUME:
            continue
        markets.append(parsed)

    markets.sort(key=lambda x: x["volume"], reverse=True)
    return markets[:max_markets]

def classify_topic(market):
    q = (market.get("question","") + " " + " ".join(market.get("tags",[]))).lower()
    if any(w in q for w in ["bitcoin","btc","eth","ethereum","crypto","defi","altcoin"]):
        return "crypto"
    if any(w in q for w in ["fed","rate","inflation","cpi","gdp","recession"]):
        return "macro"
    if any(w in q for w in ["stock","nasdaq","s&p","equity","market"]):
        return "equities"
    if any(w in q for w in ["dollar","usd","forex","currency"]):
        return "forex"
    if any(w in q for w in ["sec","regulation","law","ban"]):
        return "regulation"
    return "finance"

if __name__ == "__main__":
    print("Scanning Polymarket...")
    markets = get_top_markets()
    print(f"Found {len(markets)} markets\n")
    for m in markets[:10]:
        print(f"  [{m['yes_price']:.3f}] ${m['volume']:,.0f} — {m['question'][:65]}")

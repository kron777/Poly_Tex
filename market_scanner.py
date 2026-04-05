"""
Parallel market scanner — fetches + scores all active markets
Uses asyncio for 16x concurrent fetching
"""
import asyncio, aiohttp, json, time
from dataclasses import dataclass
from typing import Optional
from logger import get_logger
from config import GAMMA_API, SCANNER_PARALLELISM, CACHE_TTL, MIN_VOLUME

log = get_logger("scanner")

@dataclass
class MarketOpportunity:
    id: str
    condition_id: str
    question: str
    yes_price: float
    no_price: float
    yes_token: str
    no_token: str
    volume: float
    liquidity: float
    spread: float
    implied_prob: float
    category: str
    end_date: str
    edge: float = 0.0
    direction: str = ""
    our_prob: float = 0.0

_cache: dict = {}
_cache_time: float = 0

def parse_price(raw) -> float:
    """Safely parse price from various formats"""
    if raw is None: return 0.5
    if isinstance(raw, (int, float)): return float(raw)
    if isinstance(raw, str):
        try: return float(raw.replace("$","").replace(",",""))
        except: return 0.5
    if isinstance(raw, list) and len(raw) > 0:
        try: return float(raw[0])
        except: return 0.5
    return 0.5

def parse_outcome_prices(m: dict) -> tuple[float, float]:
    """Extract YES/NO prices from market dict"""
    # Try outcomePrices (JSON string array)
    op = m.get("outcomePrices")
    if op:
        if isinstance(op, str):
            try: op = json.loads(op)
            except: op = []
        if isinstance(op, list) and len(op) >= 2:
            return parse_price(op[0]), parse_price(op[1])
    # Try tokens array
    tokens = m.get("tokens", [])
    yes_p = no_p = 0.5
    for t in tokens:
        if isinstance(t, dict):
            outcome = (t.get("outcome","") or "").upper()
            price = parse_price(t.get("price", 0.5))
            if outcome == "YES": yes_p = price
            elif outcome == "NO": no_p = price
    return yes_p, no_p

def parse_token_ids(m: dict) -> tuple[str, str]:
    """Extract YES/NO token IDs"""
    tokens = m.get("tokens", [])
    yes_id = no_id = ""
    for t in tokens:
        if isinstance(t, dict):
            outcome = (t.get("outcome","") or "").upper()
            tid = t.get("token_id", t.get("tokenId", "")) or ""
            if outcome == "YES": yes_id = tid
            elif outcome == "NO": no_id = tid
    # Fallback to clobTokenIds
    clob = m.get("clobTokenIds", "[]")
    if not yes_id and clob:
        try:
            ids = json.loads(clob) if isinstance(clob, str) else clob
            if isinstance(ids, list):
                yes_id = ids[0] if len(ids) > 0 else ""
                no_id  = ids[1] if len(ids) > 1 else ""
        except: pass
    return yes_id, no_id

async def fetch_page(session: aiohttp.ClientSession, offset: int, limit: int = 100) -> list:
    """Fetch one page of markets"""
    try:
        async with session.get(
            f"{GAMMA_API}/markets",
            params={"limit": limit, "offset": offset,
                    "active": "true", "closed": "false"},
            timeout=aiohttp.ClientTimeout(total=15)
        ) as r:
            if r.status == 200:
                data = await r.json(content_type=None)
                return data if isinstance(data, list) else data.get("markets", [])
    except Exception as e:
        log.debug(f"fetch_page offset={offset} error: {e}")
    return []

async def scan_all_async(max_markets: int = 500) -> list[MarketOpportunity]:
    """Parallel market scan — fetches up to max_markets"""
    global _cache, _cache_time

    # Return cache if fresh
    if time.time() - _cache_time < CACHE_TTL and _cache:
        log.debug("Using cached markets")
        return list(_cache.values())

    log.info(f"Scanning markets (parallel={SCANNER_PARALLELISM})...")
    offsets = list(range(0, max_markets, 100))

    connector = aiohttp.TCPConnector(limit=SCANNER_PARALLELISM)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fetch_page(session, o) for o in offsets]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    raw_markets = []
    for r in results:
        if isinstance(r, list):
            raw_markets.extend(r)

    log.info(f"Fetched {len(raw_markets)} raw markets")

    opportunities = {}
    for m in raw_markets:
        if not isinstance(m, dict): continue
        if m.get("closed") or not m.get("active"): continue

        vol = float(m.get("volumeNum", m.get("volume", 0)) or 0)
        if vol < MIN_VOLUME: continue

        yes_p, no_p = parse_outcome_prices(m)
        yes_id, no_id = parse_token_ids(m)

        cid = m.get("conditionId", m.get("id", ""))
        question = m.get("question", "Unknown")
        liq = float(m.get("liquidityNum", m.get("liquidity", 0)) or 0)
        spread = abs(1.0 - yes_p - no_p)
        category = m.get("category", "general")
        end_date = m.get("endDate", m.get("endDateIso", ""))

        opp = MarketOpportunity(
            id=str(m.get("id", cid)),
            condition_id=cid,
            question=question,
            yes_price=yes_p,
            no_price=no_p,
            yes_token=yes_id,
            no_token=no_id,
            volume=vol,
            liquidity=liq,
            spread=spread,
            implied_prob=yes_p,
            category=category,
            end_date=end_date,
        )
        opportunities[cid] = opp

    _cache = opportunities
    _cache_time = time.time()
    log.info(f"Parsed {len(opportunities)} valid markets")
    return list(opportunities.values())

def scan_markets(max_markets: int = 500) -> list[MarketOpportunity]:
    """Synchronous wrapper for async scanner"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, scan_all_async(max_markets))
                return future.result(timeout=60)
        return loop.run_until_complete(scan_all_async(max_markets))
    except Exception as e:
        log.error(f"scan_markets error: {e}")
        return []

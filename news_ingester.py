"""
news_ingester.py — Poly_Tex signal corpus builder
Sources: RSS (crypto/finance), Reddit RSS, Fear & Greed Index
"""

import time
import ssl
import json
import hashlib
import urllib.request
import urllib.error
from datetime import datetime

# ── Try feedparser, fall back to raw XML parse ──────────────────────────────
try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

try:
    from signal_graph import insert_signal, signal_exists
except ImportError:
    # Stub for testing standalone
    def insert_signal(*a, **kw): pass
    def signal_exists(h): return False

# ── RSS Feeds ────────────────────────────────────────────────────────────────
RSS_FEEDS = [
    # Crypto
    ("https://www.coindesk.com/arc/outboundfeeds/rss/", "crypto"),
    ("https://cointelegraph.com/rss", "crypto"),
    ("https://decrypt.co/feed", "crypto"),
    ("https://theblock.co/rss.xml", "crypto"),
    ("https://cryptonews.com/news/feed/", "crypto"),
    # Finance / Macro
    ("https://feeds.reuters.com/reuters/businessNews", "macro"),
    ("https://feeds.bbci.co.uk/news/business/rss.xml", "macro"),
    ("https://www.investing.com/rss/news_25.rss", "macro"),
    # Reddit RSS (no auth required)
    ("https://www.reddit.com/r/CryptoCurrency/top/.rss?t=day&limit=25", "crypto"),
    ("https://www.reddit.com/r/Bitcoin/top/.rss?t=day&limit=25", "crypto"),
    ("https://www.reddit.com/r/ethereum/top/.rss?t=day&limit=25", "crypto"),
    ("https://www.reddit.com/r/economics/top/.rss?t=day&limit=25", "macro"),
    ("https://www.reddit.com/r/wallstreetbets/top/.rss?t=day&limit=10", "equities"),
]

# ── Keyword → sentiment scoring ───────────────────────────────────────────────
BULLISH_WORDS = [
    "surge", "rally", "bullish", "breakout", "soar", "gain", "rise", "pump",
    "adoption", "institutional", "etf", "halving", "upgrade", "positive",
    "inflow", "record", "high", "growth", "buy", "accumulate", "support",
    "approval", "launch", "partnership", "milestone", "recovery",
]
BEARISH_WORDS = [
    "crash", "drop", "bearish", "plunge", "fall", "dump", "decline", "fear",
    "sell", "outflow", "hack", "ban", "regulation", "sec", "lawsuit",
    "inflation", "recession", "risk", "low", "loss", "concern", "warning",
    "reject", "delay", "fine", "penalty", "liquidation",
]

TOPIC_MAP = {
    "bitcoin": "crypto", "btc": "crypto",
    "ethereum": "crypto", "eth": "crypto",
    "crypto": "crypto", "defi": "crypto", "nft": "crypto",
    "fed": "macro", "federal reserve": "macro", "inflation": "macro",
    "rate": "macro", "gdp": "macro", "recession": "macro",
    "dollar": "forex", "usd": "forex", "eur": "forex",
    "stocks": "equities", "nasdaq": "equities", "s&p": "equities",
    "etf": "crypto", "sec": "regulation", "cftc": "regulation",
}


def _content_hash(text: str) -> str:
    return hashlib.md5(text.strip().lower()[:200].encode()).hexdigest()


def _score_text(text: str) -> tuple[float, float, str]:
    """Returns (probability, confidence, direction)."""
    text_lower = text.lower()
    bull = sum(1 for w in BULLISH_WORDS if w in text_lower)
    bear = sum(1 for w in BEARISH_WORDS if w in text_lower)

    total = bull + bear
    if total == 0:
        return 0.5, 0.55, "NEUTRAL"

    # Raw score 0-1
    raw = bull / total
    # Compress toward 0.5 (don't be too confident from keywords alone)
    prob = 0.5 + (raw - 0.5) * 0.6
    prob = max(0.25, min(0.80, prob))

    # Confidence scales with signal strength
    confidence = min(0.55 + (total * 0.03), 0.80)

    direction = "YES" if prob >= 0.52 else ("NO" if prob <= 0.48 else "NEUTRAL")
    return round(prob, 3), round(confidence, 3), direction


def _detect_topic(text: str, feed_topic: str) -> str:
    text_lower = text.lower()
    for keyword, topic in TOPIC_MAP.items():
        if keyword in text_lower:
            return topic
    return feed_topic


def _make_ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def fetch_rss(url: str, topic: str, timeout: int = 10) -> list[dict]:
    """Fetch and parse RSS feed. Returns list of {title, summary, topic}."""
    items = []
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Poly_Tex/1.0; +https://github.com/kron777)",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        ctx = _make_ssl_ctx()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        print(f"    HTTP {e.code}: {url[:60]}")
        return []
    except Exception as e:
        print(f"    Error: {type(e).__name__} — {url[:60]}")
        return []

    if HAS_FEEDPARSER:
        feed = feedparser.parse(raw)
        for entry in feed.entries[:20]:
            title = getattr(entry, "title", "")
            summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
            # Strip HTML tags crudely
            summary = _strip_html(summary)
            text = f"{title}. {summary}".strip()
            if len(text) > 30:
                items.append({"text": text, "topic": _detect_topic(text, topic)})
    else:
        # Minimal XML fallback
        import re
        entries = re.findall(r"<item>(.*?)</item>", raw, re.DOTALL)
        entries += re.findall(r"<entry>(.*?)</entry>", raw, re.DOTALL)
        for entry in entries[:20]:
            title = re.search(r"<title[^>]*>(.*?)</title>", entry, re.DOTALL)
            desc = re.search(r"<description[^>]*>(.*?)</description>", entry, re.DOTALL)
            summary = re.search(r"<summary[^>]*>(.*?)</summary>", entry, re.DOTALL)
            title = _strip_html(title.group(1)) if title else ""
            body = _strip_html((desc or summary).group(1)) if (desc or summary) else ""
            text = f"{title}. {body}".strip()
            if len(text) > 30:
                items.append({"text": text, "topic": _detect_topic(text, topic)})

    return items


def _strip_html(text: str) -> str:
    import re
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()[:500]


def fetch_fear_greed() -> list[dict]:
    """Fetch Fear & Greed index and convert to a signal."""
    try:
        ctx = _make_ssl_ctx()
        req = urllib.request.Request(
            "https://api.alternative.me/fng/?limit=1",
            headers={"User-Agent": "Poly_Tex/1.0"},
        )
        with urllib.request.urlopen(req, timeout=8, context=ctx) as r:
            data = json.loads(r.read())
        entry = data["data"][0]
        value = int(entry["value"])          # 0-100
        label = entry["value_classification"] # e.g. "Fear", "Greed"

        # Convert to probability signal
        prob = round(value / 100, 3)
        conf = 0.72  # Fear/Greed is a reliable macro indicator
        direction = "YES" if value >= 50 else "NO"
        text = (
            f"Crypto Fear & Greed Index is {value} ({label}). "
            f"{'High greed suggests elevated risk appetite and bullish momentum.' if value >= 60 else ''}"
            f"{'Extreme fear often marks market bottoms and potential buying opportunities.' if value <= 25 else ''}"
            f"{'Moderate sentiment indicates balanced market conditions.' if 25 < value < 60 else ''}"
        ).strip()
        return [{"text": text, "topic": "crypto", "prob": prob, "conf": conf, "direction": direction}]
    except Exception as e:
        print(f"    Fear/Greed error: {e}")
        return []


def ingest_feeds(use_llm: bool = False) -> int:
    """
    Main ingestion function. Returns number of NEW signals added.
    use_llm: reserved for future Gemma 4 extraction (ignored for now).
    """
    added = 0

    # ── RSS / Reddit ──────────────────────────────────────────────────────────
    for url, topic in RSS_FEEDS:
        label = url.split("/")[2]  # domain only
        print(f"  Fetching {label}...", flush=True)
        items = fetch_rss(url, topic)
        feed_added = 0
        for item in items:
            text = item["text"]
            h = _content_hash(text)
            try:
                if signal_exists(h):
                    continue
            except Exception:
                pass  # signal_exists not implemented — skip dedup check

            prob, conf, direction = _score_text(text)
            # Override with pre-scored if provided
            prob = item.get("prob", prob)
            conf = item.get("conf", conf)
            direction = item.get("direction", direction)

            if conf < 0.54:
                continue  # Skip very weak signals

            try:
                insert_signal(text, item["topic"], prob, conf, direction, label)
                feed_added += 1
                added += 1
            except Exception as e:
                pass

        print(f"    +{feed_added} signals", flush=True)
        time.sleep(0.5)  # polite rate limit

    # ── Fear & Greed ──────────────────────────────────────────────────────────
    print("  Fetching Fear & Greed Index...", flush=True)
    fg_signals = fetch_fear_greed()
    for item in fg_signals:
        h = _content_hash(item["text"])
        try:
            if signal_exists(h):
                continue
        except Exception:
            pass
        try:
            insert_signal(item["text"], item["topic"], item["prob"], item["conf"], item["direction"], "fear_greed")
            added += 1
            print(f"    +1 (value={int(item['prob']*100)})", flush=True)
        except Exception as e:
            print(f"    Fear/Greed insert error: {e}", flush=True)

    return added


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== Poly_Tex News Ingester ===")
    print(f"feedparser: {'yes' if HAS_FEEDPARSER else 'NO — pip install feedparser'}")
    print()

    # Quick feed-by-feed test
    for url, topic in RSS_FEEDS[:4]:
        print(f"Testing: {url[:60]}")
        items = fetch_rss(url, topic)
        print(f"  → {len(items)} items")
        if items:
            print(f"  Sample: {items[0]['text'][:100]}")
        print()

    print("Fear & Greed:")
    fg = fetch_fear_greed()
    for s in fg:
        print(f"  → {s['text'][:120]}")

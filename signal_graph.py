# ═══════════════════════════════════════════════════════════════
#  POLY_TEX — Signal Graph
#  The brain. Stores and retrieves probability signals.
#  Analogous to NEX's belief graph but pointed at market outcomes.
# ═══════════════════════════════════════════════════════════════

import sqlite3
import json
import time
import math
from pathlib import Path
from config import SIGNAL_DB, SIGNAL_DECAY, MAX_SIGNALS

DB = str(SIGNAL_DB)
SIGNAL_DB.parent.mkdir(exist_ok=True)

def init_db():
    db = sqlite3.connect(DB)
    db.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            content     TEXT NOT NULL,
            topic       TEXT NOT NULL,
            probability REAL NOT NULL,
            confidence  REAL NOT NULL,
            direction   TEXT NOT NULL,  -- 'YES' or 'NO'
            source      TEXT NOT NULL,
            created_at  REAL NOT NULL,
            updated_at  REAL NOT NULL,
            decay_rate  REAL DEFAULT 0.95,
            hits        INTEGER DEFAULT 0
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS signal_outcomes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id   INTEGER,
            market_id   TEXT,
            predicted   REAL,
            actual      REAL,
            profit_loss REAL,
            resolved_at REAL
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_topic ON signals(topic)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_confidence ON signals(confidence)")
    db.commit()
    db.close()

def insert_signal(content, topic, probability, confidence, direction, source):
    db = sqlite3.connect(DB)
    now = time.time()
    # check duplicate
    existing = db.execute(
        "SELECT id, confidence FROM signals WHERE content=?", (content,)
    ).fetchone()
    if existing:
        # update confidence if stronger signal
        if confidence > existing[1]:
            db.execute(
                "UPDATE signals SET confidence=?, probability=?, updated_at=? WHERE id=?",
                (confidence, probability, now, existing[0])
            )
        db.close()
        return False
    db.execute("""
        INSERT INTO signals (content, topic, probability, confidence, direction,
                             source, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?)
    """, (content, topic, probability, confidence, direction, source, now, now))
    db.commit()
    db.close()
    return True

def retrieve_signals(query_topic, min_confidence=0.65, limit=20):
    """Retrieve relevant signals for a market topic."""
    db = sqlite3.connect(DB)
    now = time.time()
    # apply time decay
    rows = db.execute("""
        SELECT id, content, probability, confidence, direction, created_at
        FROM signals
        WHERE topic=? AND confidence >= ?
        ORDER BY confidence DESC, updated_at DESC
        LIMIT ?
    """, (query_topic, min_confidence, limit)).fetchall()
    db.close()

    signals = []
    for row in rows:
        sid, content, prob, conf, direction, created = row
        # decay confidence based on age
        age_days = (now - created) / 86400
        decayed_conf = conf * (SIGNAL_DECAY ** age_days)
        if decayed_conf >= min_confidence * 0.7:
            signals.append({
                "id": sid,
                "content": content,
                "probability": prob,
                "confidence": decayed_conf,
                "direction": direction,
            })
    return signals

def synthesise_probability(signals, market_question):
    """
    Weighted average of signal probabilities.
    Higher confidence signals get more weight.
    Returns (probability, confidence, reasoning)
    """
    if not signals:
        return None, 0.0, "No relevant signals found"

    total_weight = sum(s["confidence"] for s in signals)
    if total_weight == 0:
        return None, 0.0, "Zero total signal weight"

    # weighted probability
    weighted_prob = sum(
        s["probability"] * s["confidence"] for s in signals
    ) / total_weight

    # aggregate confidence — diminishing returns on more signals
    agg_conf = min(0.95, total_weight / (total_weight + len(signals)))

    reasoning = f"Synthesised from {len(signals)} signals. "
    top = sorted(signals, key=lambda x: x["confidence"], reverse=True)[:3]
    for s in top:
        reasoning += f"[{s['confidence']:.2f}] {s['content'][:80]}... "

    return round(weighted_prob, 3), round(agg_conf, 3), reasoning

def get_stats():
    db = sqlite3.connect(DB)
    total = db.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    by_topic = db.execute(
        "SELECT topic, COUNT(*) FROM signals GROUP BY topic ORDER BY COUNT(*) DESC"
    ).fetchall()
    avg_conf = db.execute("SELECT AVG(confidence) FROM signals").fetchone()[0]
    db.close()
    return {"total": total, "by_topic": dict(by_topic), "avg_confidence": avg_conf}

init_db()

if __name__ == "__main__":
    stats = get_stats()
    print(f"Signal Graph — {stats['total']} signals")
    print(f"Avg confidence: {stats['avg_confidence']:.3f}")
    for topic, count in stats['by_topic'].items():
        print(f"  {topic}: {count}")

def signal_exists(content_hash: str) -> bool:
    import sqlite3, os
    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "data/signals.db"))
    row = conn.execute("SELECT 1 FROM signals WHERE content_hash=? LIMIT 1", (content_hash,)).fetchone()
    conn.close()
    return row is not None


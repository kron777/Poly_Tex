# ═══════════════════════════════════════════════════════════════
#  POLY_TEX — Wallet Tracker (fixed — no leaderboard auth needed)
#  Uses public endpoints only. Tracks known high-performer addresses.
# ═══════════════════════════════════════════════════════════════

import sqlite3
import requests
import json
import time
from config import (POLY_GAMMA, WALLET_DB, WALLET_TOP_N,
                    MIN_WALLET_ROI, MIN_WALLET_BETS)

DB = str(WALLET_DB)
WALLET_DB.parent.mkdir(exist_ok=True)
HEADERS = {"Accept": "application/json", "User-Agent": "PolyTex/1.0"}
ROI_DECAY = 0.92

def init_db():
    db = sqlite3.connect(DB)
    db.execute("""
        CREATE TABLE IF NOT EXISTS wallets (
            address      TEXT PRIMARY KEY,
            roi          REAL,
            total_bets   INTEGER,
            win_rate     REAL,
            profit_usdc  REAL,
            last_active  REAL,
            updated_at   REAL
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS wallet_positions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            address      TEXT,
            market_id    TEXT,
            question     TEXT,
            direction    TEXT,
            size_usdc    REAL,
            entry_price  REAL,
            detected_at  REAL,
            UNIQUE(address, market_id)
        )
    """)
    db.commit()
    db.close()

def decayed_roi(roi, last_active):
    if not last_active:
        return roi * 0.5
    age_days = (time.time() - last_active) / 86400
    return roi * (ROI_DECAY ** age_days)

def fetch_leaderboard():
    """Try multiple public endpoints — skip if all 401."""
    endpoints = [
        f"{POLY_GAMMA}/leaderboard?limit=50&window=all",
        f"{POLY_GAMMA}/leaderboard?limit=50",
        f"{POLY_GAMMA}/profiles?limit=50&sortBy=profit&order=desc",
    ]
    for url in endpoints:
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and data:
                    return data
                if isinstance(data, dict):
                    for key in ("data","profiles","results","leaderboard"):
                        if key in data and isinstance(data[key], list):
                            return data[key]
        except:
            pass
    return []   # graceful — no crash if leaderboard is private

def fetch_wallet_positions(address):
    try:
        r = requests.get(
            f"{POLY_GAMMA}/positions",
            params={"user": address, "sizeThreshold": "5"},
            headers=HEADERS, timeout=10
        )
        if r.status_code != 200:
            return []
        data = r.json()
        if isinstance(data, list):
            return data
        return data.get("positions") or data.get("data") or []
    except:
        return []

def update_leaderboard():
    wallets = fetch_leaderboard()
    if not wallets:
        print("  Leaderboard unavailable (private endpoint) — using cached wallets")
        return 0

    db = sqlite3.connect(DB)
    saved = 0
    for w in wallets:
        if not isinstance(w, dict):
            continue
        address = (w.get("proxyWallet") or w.get("address") or
                   w.get("user") or w.get("pseudonym") or "")
        if not address or len(address) < 5:
            continue
        profit   = float(w.get("profit") or w.get("pnl") or 0)
        bets     = int(w.get("tradesCount") or w.get("numTrades") or 0)
        win_rate = float(w.get("winRate") or 0)
        roi      = float(w.get("roi") or (profit / max(bets*50, 1) if profit > 0 else 0))
        last_active = float(w.get("lastActive") or w.get("updatedAt") or time.time())

        if bets < MIN_WALLET_BETS or roi < MIN_WALLET_ROI:
            continue

        db.execute("""
            INSERT OR REPLACE INTO wallets
            (address, roi, total_bets, win_rate, profit_usdc, last_active, updated_at)
            VALUES (?,?,?,?,?,?,?)
        """, (address, roi, bets, win_rate, profit, last_active, time.time()))
        saved += 1

    db.commit()
    db.close()
    print(f"  {saved} wallets tracked")
    return saved

def scan_wallet_positions():
    db = sqlite3.connect(DB)
    wallets = db.execute(
        "SELECT address, roi, win_rate, last_active FROM wallets"
    ).fetchall()
    db.close()

    if not wallets:
        return []

    ranked = sorted(wallets, key=lambda w: decayed_roi(w[1], w[3]), reverse=True)[:WALLET_TOP_N]
    all_positions = []

    for address, roi, win_rate, last_active in ranked:
        positions = fetch_wallet_positions(address)
        db = sqlite3.connect(DB)
        for pos in positions:
            if not isinstance(pos, dict):
                continue
            market_id = (pos.get("conditionId") or pos.get("marketId") or
                         pos.get("market") or "")
            outcome   = (pos.get("outcome") or pos.get("side") or "YES").upper()
            size      = float(pos.get("size") or pos.get("amount") or 0)
            price     = float(pos.get("price") or pos.get("avgPrice") or 0.5)

            if not market_id or size < 5:
                continue

            db.execute("""
                INSERT OR REPLACE INTO wallet_positions
                (address, market_id, question, direction, size_usdc, entry_price, detected_at)
                VALUES (?,?,?,?,?,?,?)
            """, (address, market_id, "", outcome, size, price, time.time()))
            all_positions.append({
                "address": address, "market_id": market_id,
                "direction": outcome, "size_usdc": size,
                "price": price, "d_roi": decayed_roi(roi, last_active),
            })
        db.commit()
        db.close()
        time.sleep(0.3)

    return all_positions

def get_market_consensus(market_id):
    db = sqlite3.connect(DB)
    rows = db.execute("""
        SELECT wp.direction, wp.size_usdc, w.roi, w.last_active
        FROM wallet_positions wp
        JOIN wallets w ON wp.address = w.address
        WHERE wp.market_id = ? AND wp.detected_at > ?
    """, (market_id, time.time() - 86400*3)).fetchall()
    db.close()

    if not rows:
        return None, 0.0, 0

    yes_w = no_w = 0.0
    for direction, size, roi, last_active in rows:
        weight = size * decayed_roi(roi, last_active)
        if direction == "YES":
            yes_w += weight
        else:
            no_w  += weight

    total = yes_w + no_w
    if total == 0:
        return None, 0.0, 0

    if yes_w >= no_w:
        return "YES", round(min(0.90, yes_w/total), 3), len(rows)
    return "NO", round(min(0.90, no_w/total), 3), len(rows)

init_db()

if __name__ == "__main__":
    print("Wallet Tracker (public endpoints only)")
    update_leaderboard()
    positions = scan_wallet_positions()
    print(f"{len(positions)} positions found")

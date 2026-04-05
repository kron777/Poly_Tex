# ═══════════════════════════════════════════════════════════════
#  POLY_TEX — Broadcaster
#  Emits real-time events to the HUD via WebSocket.
#  Import this in poly_tex.py — zero overhead if server is down.
# ═══════════════════════════════════════════════════════════════

import json
import time
import threading
import requests

HUD_SERVER = "http://10.2.0.2:7824"
_enabled   = False
_lock      = threading.Lock()

def init():
    global _enabled
    try:
        r = requests.get(f"{HUD_SERVER}/ping", timeout=1)
        _enabled = r.status_code == 200
    except:
        _enabled = False
    return _enabled

def emit(event_type, data):
    """Fire-and-forget emit. Never blocks poly_tex main loop."""
    if not _enabled:
        return
    def _send():
        try:
            requests.post(
                f"{HUD_SERVER}/event",
                json={"type": event_type, "data": data, "ts": time.time()},
                timeout=0.5,
            )
        except:
            pass
    threading.Thread(target=_send, daemon=False).start()

# ── Typed emitters ────────────────────────────────────────────────

def state(bankroll, cycle, sig_count, faiss_loaded, avg_conf,
          markets_found, bets_placed, session_pnl, win_rate):
    emit("state", {
        "bankroll":      bankroll,
        "cycle":         cycle,
        "sig_count":     sig_count,
        "faiss_loaded":  faiss_loaded,
        "avg_conf":      avg_conf,
        "markets_found": markets_found,
        "bets_placed":   bets_placed,
        "session_pnl":   session_pnl,
        "win_rate":      win_rate,
    })

def edge_found(question, direction, edge, size, our_prob,
               market_price, confidence, method, signal_count):
    emit("edge", {
        "question":     question[:70],
        "direction":    direction,
        "edge":         edge,
        "size":         size,
        "our_prob":     our_prob,
        "market_price": market_price,
        "confidence":   confidence,
        "method":       method,
        "signal_count": signal_count,
    })

def notification(ntype, head, msg):
    emit("notification", {"ntype": ntype, "head": head, "msg": msg})

def markets_update(markets):
    emit("markets", {"markets": [
        {
            "question":  m.get("question","")[:60],
            "yes_price": m.get("yes_price", 0),
            "volume":    m.get("volume", 0),
            "edge":      m.get("edge", 0),
            "direction": m.get("direction",""),
        }
        for m in (markets or [])[:8]
    ]})

def wallet_update(wallets):
    emit("wallets", {"wallets": [
        {"address": w[0][:14]+"...", "roi": w[1]}
        for w in (wallets or [])[:6]
    ]})

def signal_ingested(count, source):
    emit("signal_ingested", {"count": count, "source": source})

def chain_event(trigger, delta, topic):
    emit("chain", {"trigger": trigger, "delta": delta, "topic": topic})

def system_status(gemma_ok, poly_ok, faiss_vecs, reddit_subs, cpu_pct, mem_pct):
    emit("system", {
        "gemma_ok":    gemma_ok,
        "poly_ok":     poly_ok,
        "faiss_vecs":  faiss_vecs,
        "reddit_subs": reddit_subs,
        "cpu_pct":     cpu_pct,
        "mem_pct":     mem_pct,
    })

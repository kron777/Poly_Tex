# ═══════════════════════════════════════════════════════════════
#  POLY_TEX — HUD Server
#  Flask + SSE. Serves the dashboard and relays events from
#  poly_tex.py via Server-Sent Events (no extra deps needed).
#
#  Run in a separate terminal:
#    source venv/bin/activate
#    python3 hud_server.py
#
#  Then open: http://localhost:7824
#  Then run:  python3 poly_tex.py  (in another terminal)
# ═══════════════════════════════════════════════════════════════

import json
import time
import queue
import threading
from collections import deque
from flask import Flask, Response, request, jsonify

app = Flask(__name__)
app.config["SECRET_KEY"] = "poly_tex_hud"

# ── Event bus ────────────────────────────────────────────────────
_clients  = []
_lock     = threading.Lock()
_history  = deque(maxlen=200)   # replay on connect

# Latest state snapshot
_state = {
    "bankroll":      1000.0,
    "cycle":         0,
    "sig_count":     0,
    "faiss_loaded":  False,
    "avg_conf":      0.0,
    "markets_found": 0,
    "bets_placed":   0,
    "session_pnl":   0.0,
    "win_rate":      None,
    "markets":       [],
    "notifications": [],
    "wallets":       [],
    "system": {
        "gemma_ok":   False,
        "poly_ok":    False,
        "faiss_vecs": 0,
        "reddit_subs": 0,
        "cpu_pct":    0,
        "mem_pct":    0,
    },
    "edges":         [],
}

def broadcast(event_type, data):
    msg = json.dumps({"type": event_type, "data": data, "ts": time.time()})
    _history.append(msg)
    dead = []
    with _lock:
        for q in _clients:
            try:
                q.put_nowait(msg)
            except:
                dead.append(q)
        for q in dead:
            _clients.remove(q)

# ── Routes ────────────────────────────────────────────────────────

@app.route("/ping")
def ping():
    return "pong", 200

@app.route("/event", methods=["POST"])
def receive_event():
    """Poly_Tex posts events here → forwarded to all HUD clients."""
    payload = request.get_json(force=True, silent=True) or {}
    etype = payload.get("type", "unknown")
    data  = payload.get("data", {})

    # Update state snapshot
    if etype == "state":
        _state.update(data)
    elif etype == "markets":
        _state["markets"] = data.get("markets", [])
    elif etype == "wallets":
        _state["wallets"] = data.get("wallets", [])
    elif etype == "notification":
        _state["notifications"].insert(0, data)
        _state["notifications"] = _state["notifications"][:20]
    elif etype == "edge":
        _state["edges"].insert(0, data)
        _state["edges"] = _state["edges"][:10]
    elif etype == "system":
        _state["system"].update(data)
    elif etype == "signal_ingested":
        _state["sig_count"] = _state.get("sig_count", 0) + data.get("count", 0)

    broadcast(etype, data)
    return jsonify({"ok": True})

@app.route("/stream")
def stream():
    """SSE endpoint — HUD connects here for live updates."""
    q = queue.Queue(maxsize=100)
    with _lock:
        _clients.append(q)

    def generate():
        # Send full state snapshot on connect
        yield f"data: {json.dumps({'type':'snapshot','data':_state,'ts':time.time()})}\n\n"
        # Stream live events
        while True:
            try:
                msg = q.get(timeout=25)
                yield f"data: {msg}\n\n"
            except queue.Empty:
                yield f"data: {json.dumps({'type':'heartbeat','ts':time.time()})}\n\n"
            except GeneratorExit:
                break

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":  "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":     "keep-alive",
        },
    )

@app.route("/")
def index():
    return open("poly_tex_hud.html").read()

# ── HUD HTML ──────────────────────────────────────────────────────

HUD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>POLY_TEX HUD</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{background:#020d1a;color:#00e5ff;font-family:'Share Tech Mono',monospace;font-size:11px;overflow-x:hidden}
.scanline{position:fixed;top:0;left:0;right:0;bottom:0;background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,229,255,0.012) 2px,rgba(0,229,255,0.012) 4px);pointer-events:none;z-index:999}
.grid-bg{position:fixed;top:0;left:0;right:0;bottom:0;background-image:linear-gradient(rgba(0,229,255,0.025) 1px,transparent 1px),linear-gradient(90deg,rgba(0,229,255,0.025) 1px,transparent 1px);background-size:40px 40px;pointer-events:none;z-index:0}
.hud{position:relative;z-index:1;padding:10px;min-height:100vh}
.topbar{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid rgba(0,229,255,0.2);padding-bottom:8px;margin-bottom:10px}
.logo{font-size:20px;letter-spacing:8px;color:#00e5ff}.logo span{color:#ff4d4d}
.status-row{display:flex;gap:8px;align-items:center}
.dot{width:7px;height:7px;border-radius:50%;display:inline-block}
.dot.g{background:#00ff88;box-shadow:0 0 4px #00ff88}.dot.y{background:#ffaa00;box-shadow:0 0 4px #ffaa00}.dot.r{background:#ff4d4d;box-shadow:0 0 4px #ff4d4d}
.dim{color:rgba(0,229,255,0.4)}.green{color:#00ff88}.amber{color:#ffaa00}.red{color:#ff4d4d}
.badge{display:inline-block;padding:1px 6px;font-size:8px;border-radius:2px;letter-spacing:1px}
.badge.YES{background:rgba(0,255,136,0.12);color:#00ff88;border:1px solid rgba(0,255,136,0.3)}
.badge.NO{background:rgba(255,77,77,0.12);color:#ff4d4d;border:1px solid rgba(255,77,77,0.3)}
.badge.DRY{background:rgba(255,170,0,0.12);color:#ffaa00;border:1px solid rgba(255,170,0,0.25)}
.badge.LIVE{background:rgba(255,77,77,0.15);color:#ff4d4d;border:1px solid rgba(255,77,77,0.4)}
.panel{border:1px solid rgba(0,229,255,0.18);padding:8px;background:rgba(0,20,40,0.5)}
.panel-title{color:rgba(0,229,255,0.5);font-size:8px;letter-spacing:3px;margin-bottom:6px;border-bottom:1px solid rgba(0,229,255,0.1);padding-bottom:4px}
.big-num{font-size:26px;letter-spacing:2px}
.sub{font-size:8px;color:rgba(0,229,255,0.4);margin-top:2px}
.bar-row{display:flex;align-items:center;gap:5px;margin-bottom:3px}
.bar-label{width:58px;font-size:8px;color:rgba(0,229,255,0.5);flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bar-track{flex:1;height:3px;background:rgba(0,229,255,0.08)}
.bar-fill{height:3px;transition:width 0.8s ease}
.bar-val{width:40px;text-align:right;font-size:8px;color:rgba(0,229,255,0.7)}
table{width:100%;border-collapse:collapse}
th{font-size:7px;letter-spacing:2px;color:rgba(0,229,255,0.35);text-align:left;padding:2px 3px;border-bottom:1px solid rgba(0,229,255,0.1)}
td{font-size:8px;padding:2px 3px;border-bottom:1px solid rgba(0,229,255,0.05)}
tr:hover td{background:rgba(0,229,255,0.03)}
.notif{border-left:2px solid;padding:3px 5px;margin-bottom:3px;font-size:8px;line-height:1.4;animation:fadeIn 0.4s ease}
.notif.edge{border-color:#00ff88;background:rgba(0,255,136,0.04)}
.notif.warn{border-color:#ffaa00;background:rgba(255,170,0,0.04)}
.notif.info{border-color:#00e5ff;background:rgba(0,229,255,0.03)}
.notif.err{border-color:#ff4d4d;background:rgba(255,77,77,0.04)}
@keyframes fadeIn{from{opacity:0;transform:translateX(-6px)}to{opacity:1;transform:translateX(0)}}
.notif-time{color:rgba(0,229,255,0.35);font-size:7px}
.stream{font-size:7px;color:rgba(0,229,255,0.2);line-height:1.4;overflow:hidden;height:38px;word-break:break-all}
.stream span{color:rgba(0,229,255,0.55)}
.corner{position:fixed;width:14px;height:14px;opacity:0.3}
.corner.tl{top:8px;left:8px;border-top:1px solid #00e5ff;border-left:1px solid #00e5ff}
.corner.tr{top:8px;right:8px;border-top:1px solid #00e5ff;border-right:1px solid #00e5ff}
.corner.bl{bottom:8px;left:8px;border-bottom:1px solid #00e5ff;border-left:1px solid #00e5ff}
.corner.br{bottom:8px;right:8px;border-bottom:1px solid #00e5ff;border-right:1px solid #00e5ff}
.pulse{animation:pulse 1.8s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}
.conn-ok{color:#00ff88}.conn-err{color:#ff4d4d}
.wallet-row{display:flex;align-items:center;justify-content:space-between;padding:2px 0;border-bottom:1px solid rgba(0,229,255,0.05)}
.roi-bar{width:44px;height:2px;background:rgba(0,229,255,0.1);display:inline-block;vertical-align:middle;margin:0 3px}
.roi-fill{height:2px;background:#00ff88}
.edge-flash{animation:eflash 0.5s ease;background:rgba(0,255,136,0.08)!important}
@keyframes eflash{0%{background:rgba(0,255,136,0.25)}100%{background:rgba(0,255,136,0.08)}}
</style>
</head>
<body>
<div class="scanline"></div>
<div class="grid-bg"></div>
<div class="corner tl"></div><div class="corner tr"></div>
<div class="corner bl"></div><div class="corner br"></div>

<div class="hud">

<!-- TOP BAR -->
<div class="topbar">
  <div class="logo">POLY<span>_</span>TEX <span style="font-size:10px;letter-spacing:2px;color:rgba(0,229,255,0.4)">LIVE HUD</span></div>
  <div class="status-row">
    <div class="dot g pulse" id="conn-dot"></div>
    <span class="dim" id="conn-status">connecting...</span>
    <span style="margin:0 8px;color:rgba(0,229,255,0.15)">|</span>
    <span class="dim">CYCLE</span> <span class="green" id="cycle-num" style="margin-left:4px">0</span>
    <span style="margin:0 8px;color:rgba(0,229,255,0.15)">|</span>
    <span class="dim" id="clock">--:--:--</span>
  </div>
  <div style="display:flex;gap:8px;align-items:center">
    <span class="badge DRY" id="mode-badge">DRY RUN</span>
    <span class="dim">POLYGON MAINNET</span>
    <div class="dot g pulse"></div><div class="dot y" style="animation-delay:0.5s"></div>
  </div>
</div>

<!-- ROW 1: 3 stats + 2 gauges -->
<div style="display:grid;grid-template-columns:1fr 1fr 1fr 96px 96px;gap:8px;margin-bottom:8px">

  <div class="panel">
    <div class="panel-title">SIGNAL GRAPH</div>
    <div class="big-num green" id="sig-count">--</div>
    <div class="sub">signals indexed</div>
    <div style="margin-top:6px;display:flex;gap:8px;font-size:8px">
      <span class="dim">FAISS <span id="faiss-status" class="green">--</span></span>
      <span class="dim">AVG CONF <span class="green" id="avg-conf">--</span></span>
    </div>
  </div>

  <div class="panel">
    <div class="panel-title">BANKROLL</div>
    <div class="big-num amber" id="bankroll">$0.00</div>
    <div class="sub">USDC on Polygon</div>
    <div style="margin-top:6px">
      <div class="bar-row">
        <div class="bar-label">deployed</div>
        <div class="bar-track"><div class="bar-fill" id="deployed-bar" style="width:0%;background:#ffaa00"></div></div>
        <div class="bar-val amber" id="deployed-val">$0</div>
      </div>
      <div class="bar-row">
        <div class="bar-label">available</div>
        <div class="bar-track"><div class="bar-fill" id="avail-bar" style="width:100%;background:#00ff88"></div></div>
        <div class="bar-val green" id="avail-val">$0</div>
      </div>
    </div>
  </div>

  <div class="panel">
    <div class="panel-title">SESSION P&L</div>
    <div class="big-num green" id="pnl">+$0.00</div>
    <div class="sub" id="bet-sub">0 bets · 0 resolved</div>
    <div style="margin-top:6px">
      <div class="bar-row">
        <div class="bar-label">win rate</div>
        <div class="bar-track"><div class="bar-fill" id="win-bar" style="width:0%;background:#00ff88"></div></div>
        <div class="bar-val" id="win-val">N/A</div>
      </div>
      <div class="bar-row">
        <div class="bar-label">markets</div>
        <div class="bar-track"><div class="bar-fill" id="mkt-bar" style="width:0%;background:#00e5ff"></div></div>
        <div class="bar-val" id="mkt-val">0</div>
      </div>
    </div>
  </div>

  <!-- Gauge: Signal Confidence -->
  <div class="panel" style="display:flex;align-items:center;justify-content:center;flex-direction:column;gap:3px">
    <svg width="68" height="68" viewBox="0 0 68 68">
      <circle cx="34" cy="34" r="26" fill="none" stroke="rgba(0,229,255,0.1)" stroke-width="5"/>
      <circle cx="34" cy="34" r="26" fill="none" stroke="#00e5ff" stroke-width="5"
        stroke-dasharray="163.4" id="conf-ring"
        stroke-dashoffset="163" stroke-linecap="round"
        transform="rotate(-90 34 34)" style="transition:stroke-dashoffset 1s ease"/>
      <text x="34" y="31" text-anchor="middle" fill="#00e5ff" font-family="monospace" font-size="10" font-weight="bold" id="conf-g-val">0.00</text>
      <text x="34" y="42" text-anchor="middle" fill="rgba(0,229,255,0.4)" font-family="monospace" font-size="6">CONF</text>
    </svg>
    <div style="font-size:7px;letter-spacing:2px;color:rgba(0,229,255,0.4)">SIGNAL AVG</div>
  </div>

  <!-- Gauge: Best Edge -->
  <div class="panel" style="display:flex;align-items:center;justify-content:center;flex-direction:column;gap:3px">
    <svg width="68" height="68" viewBox="0 0 68 68">
      <circle cx="34" cy="34" r="26" fill="none" stroke="rgba(0,255,136,0.1)" stroke-width="5"/>
      <circle cx="34" cy="34" r="26" fill="none" stroke="#00ff88" stroke-width="5"
        stroke-dasharray="163.4" id="edge-ring"
        stroke-dashoffset="163" stroke-linecap="round"
        transform="rotate(-90 34 34)" style="transition:stroke-dashoffset 1s ease"/>
      <text x="34" y="31" text-anchor="middle" fill="#00ff88" font-family="monospace" font-size="10" font-weight="bold" id="edge-g-val">0%</text>
      <text x="34" y="42" text-anchor="middle" fill="rgba(0,255,136,0.4)" font-family="monospace" font-size="6">EDGE</text>
    </svg>
    <div style="font-size:7px;letter-spacing:2px;color:rgba(0,229,255,0.4)">BEST EDGE</div>
  </div>

</div>

<!-- ROW 2: markets + notifications + topic bars -->
<div style="display:grid;grid-template-columns:2fr 1.1fr 0.9fr;gap:8px;margin-bottom:8px">

  <div class="panel">
    <div class="panel-title">LIVE MARKETS — CRYPTO/FINANCE</div>
    <table>
      <thead><tr>
        <th style="width:55%">QUESTION</th>
        <th>YES</th><th>VOL</th><th>EDGE</th><th>DIR</th>
      </tr></thead>
      <tbody id="mkt-tbody">
        <tr><td colspan="5" class="dim" style="text-align:center;padding:8px">waiting for poly_tex...</td></tr>
      </tbody>
    </table>
  </div>

  <div class="panel" style="overflow:hidden">
    <div class="panel-title">SIGNAL NOTIFICATIONS</div>
    <div id="notif-feed">
      <div class="notif info"><div class="notif-time">-- HUD ONLINE --</div><div class="notif-msg">Waiting for poly_tex.py connection...</div></div>
    </div>
  </div>

  <div class="panel">
    <div class="panel-title">SIGNAL TOPICS</div>
    <div id="topic-bars">
      <div class="dim" style="font-size:8px;padding:4px 0">waiting...</div>
    </div>
    <div style="margin-top:6px;border-top:1px solid rgba(0,229,255,0.1);padding-top:5px">
      <div class="panel-title">TOP WALLETS</div>
      <div id="wallet-list">
        <div class="dim" style="font-size:8px">waiting...</div>
      </div>
    </div>
  </div>

</div>

<!-- ROW 3: data stream + countdown + system -->
<div style="display:grid;grid-template-columns:2fr 1fr 1fr;gap:8px">

  <div class="panel">
    <div class="panel-title">LIVE DATA STREAM</div>
    <div class="stream" id="data-stream">
      <span>POLY_TEX_HUD</span> awaiting connection to poly_tex.py...
    </div>
    <div style="font-size:7px;color:rgba(0,229,255,0.2);margin-top:3px;overflow:hidden;white-space:nowrap" id="hex-ticker">
      POLY_TEX · FAISS · SIGNAL_GRAPH · POLYMARKET · EDGE_DETECTOR · WALLET_TRACKER
    </div>
  </div>

  <div class="panel" style="text-align:center">
    <div class="panel-title">NEXT CYCLE</div>
    <div style="font-size:30px;color:#00e5ff;letter-spacing:4px" id="countdown">--:--</div>
    <div class="sub" style="margin:4px 0">next scan</div>
    <div style="margin-top:8px;display:grid;grid-template-columns:1fr 1fr;gap:3px">
      <div style="font-size:7px;padding:3px 2px;border:1px solid rgba(0,229,255,0.15);color:rgba(0,229,255,0.5)">
        CYCLE <span id="cycle-num2" class="green">0</span>
      </div>
      <div style="font-size:7px;padding:3px 2px;border:1px solid rgba(0,229,255,0.15);color:rgba(0,229,255,0.5)">
        EDGES <span id="edge-count" class="green">0</span>
      </div>
      <div style="font-size:7px;padding:3px 2px;border:1px solid rgba(0,229,255,0.15);color:rgba(0,229,255,0.5)">
        BETS <span id="bet-count" class="amber">0</span>
      </div>
      <div style="font-size:7px;padding:3px 2px;border:1px solid rgba(0,229,255,0.15);color:rgba(0,229,255,0.5)">
        P&L <span id="pnl2" class="green">$0</span>
      </div>
    </div>
  </div>

  <div class="panel">
    <div class="panel-title">SYSTEM</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:3px;margin-bottom:6px">
      <div style="text-align:center">
        <svg width="46" height="46" viewBox="0 0 46 46">
          <circle cx="23" cy="23" r="17" fill="none" stroke="rgba(0,229,255,0.1)" stroke-width="3"/>
          <circle cx="23" cy="23" r="17" fill="none" stroke="#00e5ff" stroke-width="3"
            id="cpu-ring" stroke-dasharray="106.8" stroke-dashoffset="80"
            stroke-linecap="round" transform="rotate(-90 23 23)" style="transition:stroke-dashoffset 1s"/>
          <text x="23" y="21" text-anchor="middle" fill="#00e5ff" font-family="monospace" font-size="7" id="cpu-val">--</text>
          <text x="23" y="29" text-anchor="middle" fill="rgba(0,229,255,0.3)" font-family="monospace" font-size="5">CPU</text>
        </svg>
        <div style="font-size:7px;color:rgba(0,229,255,0.35)">PROC</div>
      </div>
      <div style="text-align:center">
        <svg width="46" height="46" viewBox="0 0 46 46">
          <circle cx="23" cy="23" r="17" fill="none" stroke="rgba(0,229,255,0.1)" stroke-width="3"/>
          <circle cx="23" cy="23" r="17" fill="none" stroke="#ffaa00" stroke-width="3"
            id="mem-ring" stroke-dasharray="106.8" stroke-dashoffset="60"
            stroke-linecap="round" transform="rotate(-90 23 23)" style="transition:stroke-dashoffset 1s"/>
          <text x="23" y="21" text-anchor="middle" fill="#ffaa00" font-family="monospace" font-size="7" id="mem-val">--</text>
          <text x="23" y="29" text-anchor="middle" fill="rgba(0,229,255,0.3)" font-family="monospace" font-size="5">MEM</text>
        </svg>
        <div style="font-size:7px;color:rgba(0,229,255,0.35)">VRAM</div>
      </div>
    </div>

    <div style="font-size:7px;display:flex;flex-direction:column;gap:3px">
      <div style="display:flex;justify-content:space-between">
        <span class="dim">Gemma 4 :8080</span><span id="gemma-ok" class="dim">--</span>
      </div>
      <div style="display:flex;justify-content:space-between">
        <span class="dim">Polymarket API</span><span id="poly-ok" class="dim">--</span>
      </div>
      <div style="display:flex;justify-content:space-between">
        <span class="dim">FAISS vectors</span><span id="faiss-vecs" class="green">--</span>
      </div>
      <div style="display:flex;justify-content:space-between">
        <span class="dim">Reddit feeds</span><span id="reddit-subs" class="amber">--</span>
      </div>
      <div style="display:flex;justify-content:space-between;border-top:1px solid rgba(0,229,255,0.1);padding-top:3px">
        <span class="dim">SSE clients</span><span id="client-count" class="green">1</span>
      </div>
    </div>
  </div>

</div>
</div>

<script>
const $ = id => document.getElementById(id);
let bestEdge = 0, edgeCount = 0, betCount = 0, cycleSeconds = 900;

// Clock
setInterval(() => {
  $('clock').textContent = new Date().toTimeString().slice(0,8);
}, 1000);

// Countdown
setInterval(() => {
  cycleSeconds = Math.max(0, cycleSeconds - 1);
  if (cycleSeconds === 0) cycleSeconds = 900;
  const m = Math.floor(cycleSeconds/60), s = cycleSeconds % 60;
  $('countdown').textContent = `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
}, 1000);

// Gauge helpers
function setGauge(ringId, pct) {
  const circ = 163.4;
  const offset = circ - (circ * Math.min(pct, 1));
  $(ringId).style.strokeDashoffset = offset;
}
function setSmallGauge(ringId, pct) {
  const circ = 106.8;
  const offset = circ - (circ * Math.min(pct, 1));
  $(ringId).style.strokeDashoffset = offset;
}

// Notification
function addNotif(ntype, head, msg) {
  const now = new Date().toTimeString().slice(0,8);
  const el = document.createElement('div');
  el.className = `notif ${ntype}`;
  el.innerHTML = `<div class="notif-time">${now} ▶ ${head}</div><div class="notif-msg">${msg}</div>`;
  const feed = $('notif-feed');
  feed.insertBefore(el, feed.firstChild);
  while (feed.children.length > 8) feed.removeChild(feed.lastChild);
}

// Stream ticker
function pushStream(text) {
  const s = $('data-stream');
  const lines = s.innerHTML.split('<br>');
  lines.unshift(text);
  s.innerHTML = lines.slice(0, 3).join('<br>');
}

const TICKERS = ['POLY_TEX','FAISS','EDGE','SIGNAL','KELLY','CHAIN',
  'BTC','ETH','USDC','0.08','YES','NO','ROI','WALLET','NEWS'];
let ti = 0;
setInterval(() => {
  ti = (ti + 3) % TICKERS.length;
  $('hex-ticker').textContent = TICKERS.slice(ti, ti+8).join(' · ');
}, 2200);

// ── SSE Connection ─────────────────────────────────────────────
let es;
function connect() {
  es = new EventSource('/stream');

  es.onopen = () => {
    $('conn-dot').style.background = '#00ff88';
    $('conn-dot').style.boxShadow = '0 0 4px #00ff88';
    $('conn-status').textContent = 'LIVE';
    $('conn-status').style.color = '#00ff88';
    addNotif('info', 'HUD CONNECTED', 'SSE stream active · awaiting poly_tex.py');
  };

  es.onerror = () => {
    $('conn-dot').style.background = '#ff4d4d';
    $('conn-dot').style.boxShadow = '0 0 4px #ff4d4d';
    $('conn-status').textContent = 'RECONNECTING';
    $('conn-status').style.color = '#ff4d4d';
    setTimeout(connect, 3000);
  };

  es.onmessage = e => {
    const payload = JSON.parse(e.data);
    handleEvent(payload.type, payload.data || {});
  };
}

function handleEvent(type, d) {
  if (type === 'heartbeat') return;

  if (type === 'snapshot') {
    // Full state on connect
    if (d.sig_count) applyState(d);
    return;
  }

  if (type === 'state') { applyState(d); return; }

  if (type === 'markets') {
    renderMarkets(d.markets || []);
    pushStream(`<span>MARKET_SCAN</span> ${(d.markets||[]).length} markets loaded`);
    return;
  }

  if (type === 'edge') {
    edgeCount++;
    $('edge-count').textContent = edgeCount;
    const pct = (d.edge * 100).toFixed(1);
    if (d.edge > bestEdge) {
      bestEdge = d.edge;
      $('edge-g-val').textContent = pct + '%';
      setGauge('edge-ring', d.edge * 5); // scale edge 0-20% → gauge
    }
    addNotif('edge', 'EDGE DETECTED',
      `${d.question} — ${pct}% · ${d.direction} · $${(d.size||0).toFixed(2)}`);
    pushStream(`<span>EDGE_DETECTED</span> ${d.direction} ${pct}% · $${(d.size||0).toFixed(2)} · ${d.method}`);
    // Flash market row
    document.querySelectorAll('#mkt-tbody tr').forEach(tr => {
      if (tr.textContent.includes(d.question.slice(0,15))) {
        tr.classList.add('edge-flash');
        setTimeout(() => tr.classList.remove('edge-flash'), 1000);
      }
    });
    return;
  }

  if (type === 'notification') {
    addNotif(d.ntype || 'info', d.head || 'EVENT', d.msg || '');
    return;
  }

  if (type === 'wallets') {
    renderWallets(d.wallets || []);
    return;
  }

  if (type === 'signal_ingested') {
    pushStream(`<span>SIGNAL_INGESTED</span> +${d.count} from ${d.source}`);
    return;
  }

  if (type === 'chain') {
    const sign = d.delta > 0 ? '+' : '';
    pushStream(`<span>CHAIN_REASON</span> ${d.trigger} → ${d.topic} ${sign}${(d.delta*100).toFixed(0)}%`);
    addNotif('info', 'CHAIN SIGNAL', `${d.trigger} → ${d.topic} ${sign}${(d.delta*100).toFixed(0)}% adj`);
    return;
  }

  if (type === 'system') {
    if (d.gemma_ok !== undefined) $('gemma-ok').innerHTML = d.gemma_ok ? '<span class="green pulse">ONLINE</span>' : '<span class="red">OFFLINE</span>';
    if (d.poly_ok  !== undefined) $('poly-ok').innerHTML  = d.poly_ok  ? '<span class="green">ONLINE</span>'  : '<span class="red">OFFLINE</span>';
    if (d.faiss_vecs !== undefined) $('faiss-vecs').textContent = Number(d.faiss_vecs).toLocaleString();
    if (d.reddit_subs !== undefined) $('reddit-subs').textContent = d.reddit_subs + ' feeds';
    if (d.cpu_pct !== undefined) {
      $('cpu-val').textContent = Math.round(d.cpu_pct) + '%';
      setSmallGauge('cpu-ring', d.cpu_pct / 100);
    }
    if (d.mem_pct !== undefined) {
      $('mem-val').textContent = Math.round(d.mem_pct) + '%';
      setSmallGauge('mem-ring', d.mem_pct / 100);
    }
    return;
  }
}

function applyState(d) {
  if (d.sig_count !== undefined) {
    $('sig-count').textContent = Number(d.sig_count).toLocaleString();
  }
  if (d.avg_conf !== undefined) {
    $('avg-conf').textContent = (d.avg_conf || 0).toFixed(3);
    $('conf-g-val').textContent = (d.avg_conf || 0).toFixed(2);
    setGauge('conf-ring', (d.avg_conf || 0));
  }
  if (d.faiss_loaded !== undefined) {
    $('faiss-status').textContent = d.faiss_loaded ? 'ONLINE' : 'BUILDING';
    $('faiss-status').style.color = d.faiss_loaded ? '#00ff88' : '#ffaa00';
  }
  if (d.bankroll !== undefined) {
    $('bankroll').textContent = '$' + Number(d.bankroll).toFixed(2);
    $('avail-val').textContent = '$' + Number(d.bankroll).toFixed(0);
    $('avail-bar').style.width = '100%';
  }
  if (d.cycle !== undefined) {
    $('cycle-num').textContent = d.cycle;
    $('cycle-num2').textContent = d.cycle;
    cycleSeconds = 900;
  }
  if (d.session_pnl !== undefined) {
    const p = d.session_pnl || 0;
    $('pnl').textContent = (p >= 0 ? '+' : '') + '$' + p.toFixed(2);
    $('pnl').style.color = p >= 0 ? '#00ff88' : '#ff4d4d';
    $('pnl2').textContent = (p >= 0 ? '+$' : '-$') + Math.abs(p).toFixed(0);
  }
  if (d.bets_placed !== undefined) {
    betCount = d.bets_placed;
    $('bet-count').textContent = betCount;
  }
  if (d.markets_found !== undefined) {
    $('mkt-bar').style.width = Math.min(100, d.markets_found * 2) + '%';
    $('mkt-val').textContent = d.markets_found;
  }
  if (d.markets) renderMarkets(d.markets);
  if (d.wallets) renderWallets(d.wallets);
  if (d.notifications) {
    d.notifications.slice(0,6).reverse().forEach(n => addNotif(n.ntype||'info', n.head, n.msg));
  }
}

function renderMarkets(markets) {
  if (!markets.length) return;
  const tb = $('mkt-tbody');
  tb.innerHTML = markets.map(m => {
    const ec = m.edge > 0.08 ? '#00ff88' : m.edge > 0.05 ? '#ffaa00' : 'rgba(0,229,255,0.35)';
    const dir = m.direction ? `<span class="badge ${m.direction}">${m.direction}</span>` : '<span class="dim">--</span>';
    const edgeTxt = m.edge ? `<span style="color:${ec}">+${(m.edge*100).toFixed(1)}%</span>` : '<span class="dim">--</span>';
    return `<tr>
      <td style="max-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${m.question}</td>
      <td>${(m.yes_price||0).toFixed(3)}</td>
      <td>$${((m.volume||0)/1000).toFixed(0)}k</td>
      <td>${edgeTxt}</td>
      <td>${dir}</td>
    </tr>`;
  }).join('');
}

function renderWallets(wallets) {
  if (!wallets.length) return;
  $('wallet-list').innerHTML = wallets.map(w => {
    const pct = Math.min(100, (w.roi||0) * 100);
    return `<div class="wallet-row">
      <span class="dim" style="font-size:8px">${w.address}</span>
      <div><div class="roi-bar"><div class="roi-fill" style="width:${pct}%"></div></div><span style="font-size:8px;color:#00ff88">+${((w.roi||0)*100).toFixed(0)}%</span></div>
    </div>`;
  }).join('');
}

connect();
</script>
</body>
</html>"""

if __name__ == "__main__":
    print("\n  POLY_TEX HUD Server")
    print("  ═══════════════════")
    print("  Dashboard : http://localhost:7824")
    print("  SSE stream: http://localhost:7824/stream")
    print("  Event hook: http://localhost:7824/event")
    print("\n  Start poly_tex.py in another terminal to feed data.\n")
    app.run(host="0.0.0.0", port=7824, debug=False, threaded=True)

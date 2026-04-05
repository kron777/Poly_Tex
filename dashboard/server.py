"""
FastAPI dashboard server
Serves live state via REST + SSE
"""
import json, time, threading
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import state
from logger import get_logger
from config import DASHBOARD_PORT

log = get_logger("dashboard")
app = FastAPI(title="Poly_Tex Dashboard")

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def index():
    return HTMLResponse(open("dashboard/index.html").read())

@app.get("/api/state")
def get_state():
    return JSONResponse(state.to_dict())

@app.post("/api/event")
async def receive_event(payload: dict):
    """Accept events from bot"""
    etype = payload.get("type", "")
    data = payload.get("data", {})
    if etype == "cycle":
        state.update(cycle=data.get("cycle", 0),
                     last_cycle=data.get("ts", ""))
    elif etype == "markets":
        state.update(markets=data.get("markets", []),
                     markets_scanned=data.get("count", 0))
    elif etype == "opportunity":
        state.add_opportunity(data)
    return {"ok": True}

@app.get("/api/stream")
def stream():
    """SSE stream for live updates"""
    def generate():
        last = 0
        while True:
            now = time.time()
            if now - last > 1.0:
                data = json.dumps({"type": "state", "data": state.to_dict()})
                yield f"data: {data}\n\n"
                last = now
            else:
                yield f"data: {json.dumps({'type':'heartbeat','ts':now})}\n\n"
            time.sleep(0.5)
    return StreamingResponse(generate(), media_type="text/event-stream")

def start(port: int = DASHBOARD_PORT):
    """Start dashboard in background thread"""
    def run():
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
    t = threading.Thread(target=run, daemon=True)
    t.start()
    log.info(f"Dashboard: http://localhost:{port}")

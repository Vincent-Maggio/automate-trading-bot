import os
from dataclasses import asdict
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


def create_app(audit, control_store, snapshot_provider, recent_limit: int = 20):
    app = FastAPI(title="Trading Bot API")

    @app.get("/api/portfolio")
    def portfolio():
        try:
            snap = snapshot_provider()
        except Exception as exc:  # broker read failed — keep dashboard alive
            return {"error": str(exc), "cash": 0.0, "equity": 0.0,
                    "exposure": 0.0, "realized_pnl": 0.0, "positions": []}
        return asdict(snap)

    @app.get("/api/decisions")
    def decisions():
        return audit.recent_decisions(recent_limit)

    @app.get("/api/fills")
    def fills():
        return audit.recent_fills(recent_limit)

    @app.get("/api/events")
    def events():
        return audit.recent_events(recent_limit)

    @app.get("/api/status")
    def status():
        return {"killed": control_store.is_killed(),
                "kill_reason": control_store.kill_reason()}

    @app.post("/api/kill")
    async def kill(request: Request):
        reason = ""
        try:
            data = await request.json()
            reason = data.get("reason", "") if isinstance(data, dict) else ""
        except Exception:
            reason = ""
        control_store.kill(reason)
        return {"killed": True, "kill_reason": reason}

    @app.post("/api/resume")
    def resume():
        control_store.clear_kill()
        return {"killed": False}

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        with open(os.path.join(_STATIC_DIR, "index.html"), "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())

    return app

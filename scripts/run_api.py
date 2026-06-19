import os
import uvicorn

from trading_bot.config.loader import load_config, load_secrets
from trading_bot.audit.audit_log import AuditLog
from trading_bot.control.control_store import ControlStore
from trading_bot.reporting.snapshot import AccountSnapshot
from trading_bot.reporting.account_reader import AlpacaAccountReader
from trading_bot.api.app import create_app


def build_app():
    cfg = load_config("config.yaml")
    secrets = load_secrets(".env")
    audit = AuditLog(cfg["execution"]["audit_db"])
    control_store = ControlStore(cfg.get("control", {}).get("db", "control.sqlite"))

    def snapshot_provider():
        if secrets["ALPACA_API_KEY"]:
            return AlpacaAccountReader(secrets["ALPACA_API_KEY"],
                                       secrets["ALPACA_SECRET_KEY"]).snapshot()
        return AccountSnapshot(0.0, 0.0, 0.0, 0.0, [])

    return create_app(audit, control_store, snapshot_provider,
                      recent_limit=cfg["reporting"]["recent_limit"])


app = build_app()

if __name__ == "__main__":
    host = os.environ.get("API_HOST", "127.0.0.1")
    port = int(os.environ.get("API_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)

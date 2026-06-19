from starlette.testclient import TestClient
from trading_bot.api.app import create_app
from trading_bot.audit.audit_log import AuditLog
from trading_bot.control.control_store import ControlStore
from trading_bot.reporting.snapshot import AccountSnapshot


def test_dashboard_served_at_root(tmp_path):
    audit = AuditLog(str(tmp_path / "audit.sqlite"))
    cs = ControlStore(str(tmp_path / "ctl.sqlite"))
    app = create_app(audit, cs, lambda: AccountSnapshot(0, 0, 0, 0, []))
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    body = r.text.lower()
    assert '<div id="root"' in body or "<div id='root'" in body
    assert "trading bot" in body

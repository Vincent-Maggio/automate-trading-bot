from starlette.testclient import TestClient
from trading_bot.api.app import create_app
from trading_bot.audit.audit_log import AuditLog
from trading_bot.control.control_store import ControlStore
from trading_bot.reporting.snapshot import AccountSnapshot
from trading_bot.domain.models import Action, Decision


def _snap():
    return AccountSnapshot(cash=300.0, equity=520.0, exposure=0.42,
                           realized_pnl=15.0,
                           positions=[{"symbol": "AAPL", "qty": 2.0,
                                       "avg_cost": 100.0, "price": 110.0,
                                       "market_value": 220.0, "unrealized_pnl": 20.0}])


def _client(tmp_path, provider=None):
    audit = AuditLog(str(tmp_path / "audit.sqlite"))
    audit.log_decision("r1", Decision("AAPL", Action.BUY, 0.8, True, "consensus", []))
    cs = ControlStore(str(tmp_path / "ctl.sqlite"))
    app = create_app(audit, cs, provider or _snap)
    return TestClient(app), cs


def test_portfolio_endpoint(tmp_path):
    client, _ = _client(tmp_path)
    r = client.get("/api/portfolio")
    assert r.status_code == 200
    body = r.json()
    assert body["equity"] == 520.0
    assert body["positions"][0]["symbol"] == "AAPL"


def test_decisions_endpoint(tmp_path):
    client, _ = _client(tmp_path)
    r = client.get("/api/decisions")
    assert r.status_code == 200
    assert r.json()[0]["symbol"] == "AAPL"


def test_status_endpoint_reports_kill(tmp_path):
    client, cs = _client(tmp_path)
    cs.kill("test")
    r = client.get("/api/status")
    assert r.json()["killed"] is True
    assert r.json()["kill_reason"] == "test"


def test_portfolio_survives_provider_error(tmp_path):
    def _boom():
        raise RuntimeError("broker down")
    client, _ = _client(tmp_path, provider=_boom)
    r = client.get("/api/portfolio")
    assert r.status_code == 200
    assert r.json()["positions"] == []
    assert "error" in r.json()

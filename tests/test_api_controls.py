from starlette.testclient import TestClient
from trading_bot.api.app import create_app
from trading_bot.audit.audit_log import AuditLog
from trading_bot.control.control_store import ControlStore
from trading_bot.reporting.snapshot import AccountSnapshot


def _client(tmp_path):
    audit = AuditLog(str(tmp_path / "audit.sqlite"))
    cs = ControlStore(str(tmp_path / "ctl.sqlite"))
    snap = lambda: AccountSnapshot(0, 0, 0, 0, [])
    return TestClient(create_app(audit, cs, snap)), cs


def test_kill_then_resume(tmp_path):
    client, cs = _client(tmp_path)
    r = client.post("/api/kill", json={"reason": "panic"})
    assert r.status_code == 200
    assert r.json()["killed"] is True
    assert cs.is_killed() is True

    r2 = client.post("/api/resume")
    assert r2.status_code == 200
    assert r2.json()["killed"] is False
    assert cs.is_killed() is False


def test_kill_without_body(tmp_path):
    client, cs = _client(tmp_path)
    r = client.post("/api/kill")
    assert r.status_code == 200
    assert cs.is_killed() is True

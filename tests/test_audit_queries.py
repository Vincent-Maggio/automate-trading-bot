from datetime import datetime
from trading_bot.audit.audit_log import AuditLog
from trading_bot.domain.models import Action, Decision, OrderSide, Fill


def test_recent_queries_return_rows(tmp_path):
    log = AuditLog(str(tmp_path / "audit.sqlite"))
    log.log_decision("r1", Decision("AAPL", Action.BUY, 0.8, True, "because", []))
    log.log_fill("r1", Fill("o1", "AAPL", OrderSide.BUY, 2.0, 50.0, datetime(2023, 1, 1)))
    log.log_event("r1", "circuit_breaker", "tripped")

    decs = log.recent_decisions(limit=10)
    assert len(decs) == 1
    assert decs[0]["symbol"] == "AAPL"
    assert decs[0]["action"] == "BUY"

    fills = log.recent_fills(limit=10)
    assert fills[0]["qty"] == 2.0

    events = log.recent_events(limit=10)
    assert events[0]["kind"] == "circuit_breaker"

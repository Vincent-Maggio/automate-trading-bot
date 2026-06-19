from datetime import datetime
from trading_bot.audit.audit_log import AuditLog
from trading_bot.domain.models import (
    Action, Signal, Decision, RiskResult, Order, OrderSide, Fill,
)


def test_logs_each_record_type(tmp_path):
    log = AuditLog(str(tmp_path / "audit.sqlite"))
    rid = "run-1"
    log.log_signal(rid, Signal("AAPL", Action.BUY, 0.8, "r"))
    log.log_decision(rid, Decision("AAPL", Action.BUY, 0.8, True, "r", []))
    log.log_risk(rid, "AAPL", RiskResult(True, 100.0, "ok", []))
    log.log_order(rid, Order("o1", "AAPL", OrderSide.BUY, 100.0))
    log.log_fill(rid, Fill("o1", "AAPL", OrderSide.BUY, 2.0, 50.0, datetime(2023, 1, 1)))
    log.log_event(rid, "circuit_breaker", "tripped")
    for table in ("signals", "decisions", "risk_checks", "orders", "fills", "events"):
        assert log.count(table) == 1


def test_count_rejects_unknown_table(tmp_path):
    log = AuditLog(str(tmp_path / "audit.sqlite"))
    try:
        log.count("drop_me")
        assert False, "expected ValueError"
    except ValueError:
        pass

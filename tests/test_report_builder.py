import pytest
from trading_bot.reporting.snapshot import AccountSnapshot
from trading_bot.reporting.report_builder import build_report


def _snap():
    return AccountSnapshot(
        cash=300.0, equity=520.0, exposure=0.42, realized_pnl=15.0,
        positions=[{"symbol": "AAPL", "qty": 2.0, "avg_cost": 100.0,
                    "price": 110.0, "market_value": 220.0, "unrealized_pnl": 20.0}],
    )


def _activity():
    return {
        "date": "2026-06-19",
        "decisions": [{"symbol": "AAPL", "action": "BUY", "rationale": "consensus"}],
        "fills": [{"symbol": "AAPL", "side": "BUY", "qty": 2.0, "price": 100.0}],
        "events": [{"kind": "circuit_breaker", "detail": "tripped"}],
    }


def test_morning_report_has_subject_and_positions():
    subject, text, html = build_report("morning", _snap(), _activity())
    assert "Morning" in subject
    assert "2026-06-19" in subject
    assert "AAPL" in text
    assert "520" in text
    assert "Alerts" in text
    assert "<table" in html.lower()


def test_nightly_report_mentions_realized_pnl():
    subject, text, html = build_report("nightly", _snap(), _activity())
    assert "Nightly" in subject
    assert "15" in text


def test_invalid_kind_raises():
    with pytest.raises(ValueError):
        build_report("weekly", _snap(), _activity())

import io
from trading_bot.runtime.monitoring import maybe_alert
from trading_bot.risk.safety import SafetyState
from trading_bot.control.control_store import ControlStore
from trading_bot.notify.console_notifier import ConsoleNotifier


def _notifier():
    return ConsoleNotifier(stream=io.StringIO())


def test_alerts_on_kill(tmp_path):
    cs = ControlStore(str(tmp_path / "c.sqlite"))
    cs.kill("manual")
    safety = SafetyState(0.03)
    n = _notifier()
    assert maybe_alert(safety, cs, n) is True
    assert len(n.sent) == 1


def test_alerts_on_circuit_breaker(tmp_path):
    cs = ControlStore(str(tmp_path / "c.sqlite"))
    safety = SafetyState(0.03)
    safety.start_day(1000.0)
    safety.update(900.0)  # trips
    n = _notifier()
    assert maybe_alert(safety, cs, n) is True


def test_no_alert_when_healthy(tmp_path):
    cs = ControlStore(str(tmp_path / "c.sqlite"))
    safety = SafetyState(0.03)
    n = _notifier()
    assert maybe_alert(safety, cs, n) is False
    assert n.sent == []

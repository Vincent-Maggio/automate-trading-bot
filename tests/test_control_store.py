from trading_bot.control.control_store import ControlStore, apply_controls
from trading_bot.risk.safety import SafetyState


def test_kill_persists_and_clears(tmp_path):
    cs = ControlStore(str(tmp_path / "ctl.sqlite"))
    assert cs.is_killed() is False
    cs.kill("manual from dashboard")
    assert cs.is_killed() is True
    assert cs.kill_reason() == "manual from dashboard"
    cs.clear_kill()
    assert cs.is_killed() is False


def test_persists_across_instances(tmp_path):
    path = str(tmp_path / "ctl.sqlite")
    ControlStore(path).kill("x")
    assert ControlStore(path).is_killed() is True


def test_apply_controls_sets_safety(tmp_path):
    cs = ControlStore(str(tmp_path / "ctl.sqlite"))
    safety = SafetyState(0.03)
    cs.kill("halt")
    apply_controls(cs, safety)
    assert safety.can_trade() is False
    cs.clear_kill()
    apply_controls(cs, safety)
    assert safety.can_trade() is True

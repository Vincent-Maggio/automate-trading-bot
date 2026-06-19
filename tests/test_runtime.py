from datetime import datetime
from trading_bot.runtime.runtime import Runtime
from trading_bot.control.control_store import ControlStore


class _Clock:
    def __init__(self, open_):
        self._open = open_

    def is_open(self, now):
        return self._open


def _rt(tmp_path, clock_open=True):
    cs = ControlStore(str(tmp_path / "c.sqlite"))
    state = {"cycles": 0, "reports": []}
    rt = Runtime(_Clock(clock_open), cs,
                 run_cycle=lambda: state.__setitem__("cycles", state["cycles"] + 1),
                 send_report=lambda kind: state["reports"].append(kind),
                 morning_hour=8, nightly_hour=18)
    return rt, cs, state


def test_runs_cycle_when_open(tmp_path):
    rt, cs, state = _rt(tmp_path, clock_open=True)
    res = rt.tick(datetime(2026, 6, 19, 10, 0))
    assert res["cycle_ran"] is True
    assert state["cycles"] == 1


def test_no_cycle_when_closed(tmp_path):
    rt, cs, state = _rt(tmp_path, clock_open=False)
    res = rt.tick(datetime(2026, 6, 19, 22, 0))
    assert res["cycle_ran"] is False
    assert state["cycles"] == 0


def test_no_cycle_when_killed(tmp_path):
    rt, cs, state = _rt(tmp_path, clock_open=True)
    cs.kill("halt")
    res = rt.tick(datetime(2026, 6, 19, 10, 0))
    assert res["cycle_ran"] is False
    assert res["halted"] is True
    assert state["cycles"] == 0


def test_morning_report_sent_once_per_day(tmp_path):
    rt, cs, state = _rt(tmp_path, clock_open=False)
    rt.tick(datetime(2026, 6, 19, 8, 0))
    rt.tick(datetime(2026, 6, 19, 8, 30))
    assert state["reports"].count("morning") == 1


def test_nightly_report_sent_at_hour(tmp_path):
    rt, cs, state = _rt(tmp_path, clock_open=False)
    rt.tick(datetime(2026, 6, 19, 18, 5))
    assert "nightly" in state["reports"]

from trading_bot.execution.selector import select_executor
from trading_bot.execution.simulated import SimulatedExecutor
from trading_bot.execution.alpaca_exec import AlpacaPaperExecutor


def test_sim_mode():
    ex = select_executor("sim", False, "false", "k", "s")
    assert isinstance(ex, SimulatedExecutor)


def test_alpaca_defaults_to_paper():
    ex = select_executor("alpaca", False, "false", "k", "s")
    assert isinstance(ex, AlpacaPaperExecutor)
    assert ex.paper is True


def test_live_requires_both_flags():
    ex = select_executor("alpaca", True, "false", "k", "s")
    assert ex.paper is True
    ex2 = select_executor("alpaca", False, "true", "k", "s")
    assert ex2.paper is True


def test_live_enabled_only_when_both_true():
    ex = select_executor("alpaca", True, "true", "k", "s")
    assert ex.paper is False

from datetime import datetime
from trading_bot.domain.models import BacktestResult
from trading_bot.backtest.report import render_report


def test_render_report_contains_key_fields():
    r = BacktestResult(equity_curve=[(datetime(2023, 1, 1), 100.0)],
                       starting_cash=100.0, ending_equity=125.0)
    metrics = {"total_return": 0.25, "max_drawdown": -0.1,
               "sharpe": 1.2, "win_rate": 0.6, "num_trades": 5}
    out = render_report("SPY", r, metrics)
    assert "SPY" in out
    assert "125" in out
    assert "Total return" in out
    assert "Max drawdown" in out
    assert "Sharpe" in out
    assert "Win rate" in out

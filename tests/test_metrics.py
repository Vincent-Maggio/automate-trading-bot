import math
from datetime import datetime, timedelta
from trading_bot.domain.models import BacktestResult, Trade
from trading_bot.backtest.metrics import compute_metrics


def _curve(values):
    base = datetime(2023, 1, 1)
    return [(base + timedelta(days=i), v) for i, v in enumerate(values)]


def test_total_return():
    r = BacktestResult(equity_curve=_curve([100, 150]),
                       starting_cash=100.0, ending_equity=150.0)
    m = compute_metrics(r)
    assert m["total_return"] == 0.5


def test_max_drawdown():
    r = BacktestResult(equity_curve=_curve([100, 120, 60, 90]),
                       starting_cash=100.0, ending_equity=90.0)
    m = compute_metrics(r)
    assert math.isclose(m["max_drawdown"], -0.5, rel_tol=1e-9)


def test_win_rate():
    t_win = Trade("A", datetime(2023, 1, 1), datetime(2023, 1, 2), 10, 12, 1)
    t_loss = Trade("A", datetime(2023, 1, 3), datetime(2023, 1, 4), 10, 8, 1)
    r = BacktestResult(equity_curve=_curve([100, 100]), trades=[t_win, t_loss],
                       starting_cash=100.0, ending_equity=100.0)
    m = compute_metrics(r)
    assert m["win_rate"] == 0.5
    assert m["num_trades"] == 2


def test_sharpe_zero_when_flat():
    r = BacktestResult(equity_curve=_curve([100, 100, 100]),
                       starting_cash=100.0, ending_equity=100.0)
    m = compute_metrics(r)
    assert m["sharpe"] == 0.0

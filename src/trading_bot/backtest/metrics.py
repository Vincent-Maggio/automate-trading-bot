import math


def compute_metrics(result) -> dict:
    curve = [v for _, v in result.equity_curve]
    starting = result.starting_cash
    ending = result.ending_equity

    total_return = (ending / starting) - 1 if starting else 0.0

    max_dd = 0.0
    peak = curve[0] if curve else 0.0
    for v in curve:
        peak = max(peak, v)
        if peak > 0:
            dd = (v - peak) / peak
            max_dd = min(max_dd, dd)

    if len(curve) >= 2:
        rets = [(curve[i] / curve[i - 1]) - 1 for i in range(1, len(curve))
                if curve[i - 1] != 0]
        if len(rets) >= 1:
            mean = sum(rets) / len(rets)
            var = sum((r - mean) ** 2 for r in rets) / len(rets)
            std = math.sqrt(var)
            sharpe = (mean / std * math.sqrt(252)) if std > 0 else 0.0
        else:
            sharpe = 0.0
    else:
        sharpe = 0.0

    trades = result.trades
    wins = sum(1 for t in trades if t.pnl > 0)
    win_rate = (wins / len(trades)) if trades else 0.0

    return {
        "total_return": total_return,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
        "win_rate": win_rate,
        "num_trades": len(trades),
    }

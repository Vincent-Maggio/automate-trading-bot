def render_report(symbol: str, result, metrics: dict) -> str:
    lines = [
        f"# Backtest report: {symbol}",
        "",
        f"- Starting cash: ${result.starting_cash:,.2f}",
        f"- Ending equity: ${result.ending_equity:,.2f}",
        f"- Total return: {metrics['total_return'] * 100:.2f}%",
        f"- Max drawdown: {metrics['max_drawdown'] * 100:.2f}%",
        f"- Sharpe: {metrics['sharpe']:.2f}",
        f"- Win rate: {metrics['win_rate'] * 100:.2f}%",
        f"- Number of trades: {metrics['num_trades']}",
    ]
    return "\n".join(lines)

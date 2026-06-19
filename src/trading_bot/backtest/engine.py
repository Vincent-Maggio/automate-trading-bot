from trading_bot.domain.models import Action, Trade, BacktestResult


class BacktestEngine:
    def __init__(self, starting_cash: float):
        self.starting_cash = starting_cash

    def run(self, symbol: str, bars: list, strategy) -> BacktestResult:
        cash = self.starting_cash
        shares = 0.0
        entry_price = 0.0
        entry_time = None
        trades = []
        equity_curve = []

        for i, bar in enumerate(bars):
            history = bars[: i + 1]
            sig = strategy.generate_signal(symbol, history)
            if sig.action == Action.BUY and shares == 0.0 and cash > 0:
                shares = cash / bar.close
                entry_price = bar.close
                entry_time = bar.timestamp
                cash = 0.0
            elif sig.action == Action.SELL and shares > 0.0:
                cash = shares * bar.close
                trades.append(
                    Trade(symbol, entry_time, bar.timestamp,
                          entry_price, bar.close, shares)
                )
                shares = 0.0
            equity = cash + shares * bar.close
            equity_curve.append((bar.timestamp, equity))

        if shares > 0.0:
            last = bars[-1]
            cash = shares * last.close
            trades.append(
                Trade(symbol, entry_time, last.timestamp,
                      entry_price, last.close, shares)
            )
            shares = 0.0
            equity_curve[-1] = (last.timestamp, cash)

        return BacktestResult(
            equity_curve=equity_curve,
            trades=trades,
            starting_cash=self.starting_cash,
            ending_equity=equity_curve[-1][1] if equity_curve else self.starting_cash,
        )

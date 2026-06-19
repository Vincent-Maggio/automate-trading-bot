from trading_bot.domain.models import Action, OrderSide, StrategyVote, Trade, BacktestResult
from trading_bot.decision.aggregator import aggregate
from trading_bot.risk.exits import evaluate_exits
from trading_bot.portfolio.portfolio import Portfolio


class EnsembleBacktester:
    """Replay one symbol's history through the full live pipeline:
    strategies -> weighted-vote+consensus decision -> risk module -> simulated fills.
    Mirrors the live bot: enter on BUY consensus, exit only on stop-loss/take-profit.
    """

    def __init__(self, risk_manager, *, threshold: float, min_consensus: int,
                 stop_loss_pct: float, take_profit_pct: float,
                 per_trade_pct: float, starting_cash: float):
        self.risk_manager = risk_manager
        self.threshold = threshold
        self.min_consensus = min_consensus
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.per_trade_pct = per_trade_pct
        self.starting_cash = starting_cash

    def run(self, symbol: str, bars: list, strategies: dict, weights: dict) -> BacktestResult:
        pf = Portfolio(self.starting_cash)
        equity_curve = []
        trades = []
        entry_time = None

        for i, bar in enumerate(bars):
            price = bar.close
            prices = {symbol: price}
            history = bars[: i + 1]

            # 1) Exits first (stop-loss / take-profit)
            for d in evaluate_exits(pf, prices, self.stop_loss_pct, self.take_profit_pct):
                pos = pf.positions[d.symbol]
                qty, entry_price = pos.qty, pos.avg_cost
                pf.apply_fill(d.symbol, OrderSide.SELL, qty, price)
                trades.append(Trade(symbol, entry_time, bar.timestamp,
                                    entry_price, price, qty))
                entry_time = None

            # 2) Entry decision from the ensemble
            votes = [StrategyVote(name, strat.generate_signal(symbol, history),
                                  weights.get(name, 1.0))
                     for name, strat in strategies.items()]
            decision = aggregate(votes, self.threshold, self.min_consensus)
            if decision.action == Action.BUY:
                equity = pf.total_equity(prices)
                proposed = self.per_trade_pct * equity
                rr = self.risk_manager.check(decision, proposed, pf, prices)
                if rr.approved and rr.approved_notional > 0:
                    held_before = symbol in pf.positions
                    qty = rr.approved_notional / price
                    pf.apply_fill(symbol, OrderSide.BUY, qty, price)
                    if not held_before:
                        entry_time = bar.timestamp

            equity_curve.append((bar.timestamp, pf.total_equity(prices)))

        # Force-close any open position at the last close
        if symbol in pf.positions:
            last = bars[-1]
            pos = pf.positions[symbol]
            qty, entry_price = pos.qty, pos.avg_cost
            pf.apply_fill(symbol, OrderSide.SELL, qty, last.close)
            trades.append(Trade(symbol, entry_time, last.timestamp,
                                entry_price, last.close, qty))
            equity_curve[-1] = (last.timestamp, pf.total_equity({symbol: last.close}))

        ending = equity_curve[-1][1] if equity_curve else self.starting_cash
        return BacktestResult(equity_curve=equity_curve, trades=trades,
                              starting_cash=self.starting_cash, ending_equity=ending)

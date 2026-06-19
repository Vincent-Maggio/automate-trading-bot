from trading_bot.domain.models import Action, Order, OrderSide, StrategyVote
from trading_bot.decision.aggregator import aggregate
from trading_bot.risk.exits import evaluate_exits


class TradingCycle:
    def __init__(self, strategies: dict, weights: dict, risk_manager, safety,
                 portfolio, executor, audit, *, threshold: float,
                 min_consensus: int, stop_loss_pct: float,
                 take_profit_pct: float, per_trade_pct: float):
        self.strategies = strategies
        self.weights = weights
        self.risk_manager = risk_manager
        self.safety = safety
        self.portfolio = portfolio
        self.executor = executor
        self.audit = audit
        self.threshold = threshold
        self.min_consensus = min_consensus
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.per_trade_pct = per_trade_pct

    def run_once(self, symbols: list, history_by_symbol: dict, prices: dict,
                 run_id: str) -> dict:
        pf = self.portfolio
        equity = pf.total_equity(prices)
        self.safety.update(equity)
        if not self.safety.can_trade():
            self.audit.log_event(run_id, "halted", "safety state blocked trading")
            return {"halted": True, "orders": 0}

        order_count = 0
        seq = 0

        # 1) Exits first (risk-reducing)
        for d in evaluate_exits(pf, prices, self.stop_loss_pct, self.take_profit_pct):
            self.audit.log_decision(run_id, d)
            price = prices[d.symbol]
            notional = pf.position_value(d.symbol, price)
            rr = self.risk_manager.check(d, notional, pf, prices)
            self.audit.log_risk(run_id, d.symbol, rr)
            if not rr.approved or rr.approved_notional <= 0:
                continue
            seq += 1
            order = Order(id=f"{run_id}-x{seq}", symbol=d.symbol,
                          side=OrderSide.SELL, notional=rr.approved_notional,
                          idempotency_key=f"{run_id}:exit:{d.symbol}")
            fill = self.executor.submit_order(order, ref_price=price)
            pf.apply_fill(d.symbol, OrderSide.SELL, fill.qty, fill.price)
            self.audit.log_order(run_id, order)
            self.audit.log_fill(run_id, fill)
            order_count += 1

        # 2) Entries
        for symbol in symbols:
            history = history_by_symbol.get(symbol)
            if not history:
                continue
            votes = []
            for name, strat in self.strategies.items():
                sig = strat.generate_signal(symbol, history)
                self.audit.log_signal(run_id, sig)
                votes.append(StrategyVote(name, sig, self.weights.get(name, 1.0)))
            decision = aggregate(votes, self.threshold, self.min_consensus)
            self.audit.log_decision(run_id, decision)
            if decision.action != Action.BUY:
                continue
            proposed = self.per_trade_pct * equity
            rr = self.risk_manager.check(decision, proposed, pf, prices)
            self.audit.log_risk(run_id, symbol, rr)
            if not rr.approved or rr.approved_notional <= 0:
                continue
            seq += 1
            order = Order(id=f"{run_id}-e{seq}", symbol=symbol,
                          side=OrderSide.BUY, notional=rr.approved_notional,
                          idempotency_key=f"{run_id}:{symbol}")
            fill = self.executor.submit_order(order, ref_price=prices[symbol])
            pf.apply_fill(symbol, OrderSide.BUY, fill.qty, fill.price)
            self.audit.log_order(run_id, order)
            self.audit.log_fill(run_id, fill)
            order_count += 1

        return {"halted": False, "orders": order_count}

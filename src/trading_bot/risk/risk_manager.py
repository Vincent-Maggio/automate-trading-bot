from trading_bot.domain.models import Action, RiskResult


class RiskManager:
    def __init__(self, max_position_pct: float, max_total_exposure_pct: float,
                 max_positions: int, min_order_notional: float = 1.0):
        self.max_position_pct = max_position_pct
        self.max_total_exposure_pct = max_total_exposure_pct
        self.max_positions = max_positions
        self.min_order_notional = min_order_notional

    def check(self, decision, proposed_notional: float, portfolio, prices: dict):
        checks = []

        if decision.action != Action.BUY:
            checks.append(("entry_only", True, f"{decision.action.value} not an entry"))
            return RiskResult(True, proposed_notional, "non-entry approved", checks)

        equity = portfolio.total_equity(prices)
        if equity <= 0:
            checks.append(("equity_positive", False, f"equity={equity}"))
            return RiskResult(False, 0.0, "no equity", checks)

        symbol = decision.symbol
        notional = proposed_notional

        # Rule 1: per-position cap (includes existing holding of this symbol)
        price = prices[symbol]
        existing_val = portfolio.position_value(symbol, price)
        pos_cap = self.max_position_pct * equity
        allowed_add = pos_cap - existing_val
        if allowed_add < notional:
            checks.append(("per_position_cap", allowed_add >= notional,
                           f"cap={pos_cap:.2f} existing={existing_val:.2f} "
                           f"allowed_add={allowed_add:.2f}"))
            notional = max(0.0, allowed_add)
        else:
            checks.append(("per_position_cap", True, f"cap={pos_cap:.2f}"))

        # Rule 2: total exposure cap
        mv = portfolio.market_value(prices)
        exp_cap = self.max_total_exposure_pct * equity
        exp_headroom = exp_cap - mv
        if exp_headroom < notional:
            checks.append(("total_exposure_cap", False,
                           f"cap={exp_cap:.2f} mv={mv:.2f} headroom={exp_headroom:.2f}"))
            notional = max(0.0, exp_headroom)
        else:
            checks.append(("total_exposure_cap", True, f"cap={exp_cap:.2f}"))

        # Rule 3: max positions (new symbol only)
        if symbol not in portfolio.positions and len(portfolio.positions) >= self.max_positions:
            checks.append(("max_positions", False,
                           f"have {len(portfolio.positions)} >= {self.max_positions}"))
            return RiskResult(False, 0.0, "max positions reached", checks)
        checks.append(("max_positions", True, f"{len(portfolio.positions)}"))

        # Rule 4: min notional
        if notional < self.min_order_notional:
            checks.append(("min_notional", False,
                           f"{notional:.2f} < {self.min_order_notional}"))
            return RiskResult(False, 0.0, "below min notional after resize", checks)
        checks.append(("min_notional", True, f"{notional:.2f}"))

        reason = "approved" if notional == proposed_notional else "approved (resized)"
        return RiskResult(True, notional, reason, checks)

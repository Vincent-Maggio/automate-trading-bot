from trading_bot.domain.models import Action, Decision


def evaluate_exits(portfolio, prices: dict, stop_loss_pct: float,
                   take_profit_pct: float) -> list:
    out = []
    for symbol in sorted(portfolio.positions):
        pos = portfolio.positions[symbol]
        if pos.avg_cost <= 0:
            continue
        price = prices[symbol]
        r = (price - pos.avg_cost) / pos.avg_cost
        if r <= -stop_loss_pct:
            out.append(Decision(symbol, Action.SELL, -1.0, True,
                                f"stop-loss ({r:.2%})", []))
        elif r >= take_profit_pct:
            out.append(Decision(symbol, Action.SELL, -1.0, True,
                                f"take-profit ({r:.2%})", []))
    return out

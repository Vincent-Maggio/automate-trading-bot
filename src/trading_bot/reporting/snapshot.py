from dataclasses import dataclass, field


@dataclass
class AccountSnapshot:
    cash: float
    equity: float
    exposure: float
    realized_pnl: float
    positions: list = field(default_factory=list)


def portfolio_snapshot(portfolio, prices: dict) -> AccountSnapshot:
    positions = []
    for symbol, pos in portfolio.positions.items():
        price = prices[symbol]
        positions.append({
            "symbol": symbol,
            "qty": pos.qty,
            "avg_cost": pos.avg_cost,
            "price": price,
            "market_value": pos.market_value(price),
            "unrealized_pnl": pos.unrealized_pnl(price),
        })
    return AccountSnapshot(
        cash=portfolio.cash,
        equity=portfolio.total_equity(prices),
        exposure=portfolio.exposure(prices),
        realized_pnl=portfolio.realized_pnl,
        positions=positions,
    )

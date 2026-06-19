from trading_bot.reporting.snapshot import AccountSnapshot


class AlpacaAccountReader:
    def __init__(self, api_key: str, secret_key: str, _client=None):
        if _client is not None:
            self._client = _client
        else:
            from alpaca.trading.client import TradingClient
            self._client = TradingClient(api_key, secret_key, paper=True)

    def snapshot(self) -> AccountSnapshot:
        acct = self._client.get_account()
        cash = float(acct.cash)
        equity = float(acct.equity)
        positions = []
        for p in self._client.get_all_positions():
            positions.append({
                "symbol": p.symbol,
                "qty": float(p.qty),
                "avg_cost": float(p.avg_entry_price),
                "price": float(p.current_price),
                "market_value": float(p.market_value),
                "unrealized_pnl": float(p.unrealized_pl),
            })
        mv = sum(p["market_value"] for p in positions)
        exposure = mv / equity if equity > 0 else 0.0
        return AccountSnapshot(cash=cash, equity=equity, exposure=exposure,
                               realized_pnl=0.0, positions=positions)

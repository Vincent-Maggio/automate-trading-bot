from datetime import datetime
from trading_bot.domain.models import Bar


def _normalize(symbol: str, raw_rows: list) -> list:
    bars = [
        Bar(
            symbol=symbol,
            timestamp=r.timestamp,
            open=float(r.open),
            high=float(r.high),
            low=float(r.low),
            close=float(r.close),
            volume=float(r.volume),
        )
        for r in raw_rows
    ]
    bars.sort(key=lambda b: b.timestamp)
    return bars


class AlpacaHistoricalClient:
    def __init__(self, api_key: str, secret_key: str, _data_client=None):
        if _data_client is not None:
            self._client = _data_client
        else:
            from alpaca.data.historical import StockHistoricalDataClient
            self._client = StockHistoricalDataClient(api_key, secret_key)

    def fetch_bars(self, symbol: str, start: datetime, end: datetime,
                   timeframe: str) -> list:
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        from alpaca.data.enums import DataFeed
        tf = TimeFrame.Day if timeframe == "1Day" else TimeFrame.Day
        # Free Alpaca accounts are entitled to the IEX feed, not SIP.
        request = StockBarsRequest(
            symbol_or_symbols=symbol, timeframe=tf, start=start, end=end,
            feed=DataFeed.IEX,
        )
        resp = self._client.get_stock_bars(request)
        raw_rows = resp.data.get(symbol, [])
        return _normalize(symbol, raw_rows)

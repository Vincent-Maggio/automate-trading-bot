from datetime import datetime


class MarketData:
    def __init__(self, store, client, timeframe: str):
        self.store = store
        self.client = client
        self.timeframe = timeframe

    def get_bars(self, symbol: str, start: datetime, end: datetime) -> list:
        cached = self.store.get_bars(symbol, start, end)
        if cached:
            return cached
        fetched = self.client.fetch_bars(symbol, start, end, self.timeframe)
        self.store.save_bars(fetched)
        return fetched

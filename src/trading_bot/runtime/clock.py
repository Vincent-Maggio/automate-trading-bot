from datetime import time


def is_market_open(now) -> bool:
    if now.weekday() >= 5:  # 5=Sat, 6=Sun
        return False
    t = now.time()
    return time(9, 30) <= t < time(16, 0)


class MarketClock:
    def __init__(self, _client=None):
        self._client = _client

    def is_open(self, now) -> bool:
        if self._client is not None:
            return bool(self._client.get_clock().is_open)
        return is_market_open(now)

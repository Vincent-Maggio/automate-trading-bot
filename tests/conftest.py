from datetime import datetime, timedelta
import pytest
from trading_bot.domain.models import Bar


@pytest.fixture
def sample_bars():
    base = datetime(2023, 1, 1)
    out = []
    price = 100.0
    for i in range(10):
        out.append(
            Bar(
                symbol="AAPL",
                timestamp=base + timedelta(days=i),
                open=price,
                high=price + 1,
                low=price - 1,
                close=price + 0.5,
                volume=1_000_000,
            )
        )
        price += 1.0
    return out

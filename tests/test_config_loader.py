import pytest
from trading_bot.config.loader import load_config


def test_load_config_returns_universe(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "universe: [SPY, AAPL]\n"
        "capital: {starting_cash: 500.0}\n"
        "data: {timeframe: '1Day', cache_db: 'x.sqlite'}\n"
        "backtest: {start: '2023-01-01', end: '2024-01-01'}\n"
        "strategies: {sma_crossover: {fast: 20, slow: 50}}\n"
    )
    cfg = load_config(str(cfg_file))
    assert cfg["universe"] == ["SPY", "AAPL"]
    assert cfg["capital"]["starting_cash"] == 500.0


def test_load_config_missing_required_key_raises(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("universe: [SPY]\n")
    with pytest.raises(ValueError):
        load_config(str(cfg_file))

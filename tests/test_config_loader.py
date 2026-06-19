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


def test_load_secrets_includes_smtp(tmp_path):
    from trading_bot.config.loader import load_secrets
    env = tmp_path / ".env"
    env.write_text("SMTP_HOST=smtp.x\nSMTP_PORT=2525\nSMTP_USER=u\n"
                   "SMTP_PASS=p\nREPORT_FROM_EMAIL=f@x\nREPORT_TO_EMAIL=t@x\n")
    s = load_secrets(str(env))
    assert s["SMTP_HOST"] == "smtp.x"
    assert s["SMTP_PORT"] == 2525
    assert s["REPORT_TO_EMAIL"] == "t@x"

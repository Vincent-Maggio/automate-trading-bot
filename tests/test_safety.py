from trading_bot.risk.safety import SafetyState


def test_kill_switch_blocks_trading():
    s = SafetyState(max_daily_loss_pct=0.03)
    assert s.can_trade() is True
    s.kill()
    assert s.can_trade() is False
    s.reset_kill()
    assert s.can_trade() is True


def test_circuit_breaker_within_band_does_not_trip():
    s = SafetyState(max_daily_loss_pct=0.03)
    s.start_day(1000.0)
    assert s.update(980.0) is False   # -2% < 3% threshold
    assert s.can_trade() is True


def test_circuit_breaker_trips_past_threshold():
    s = SafetyState(max_daily_loss_pct=0.03)
    s.start_day(1000.0)
    assert s.update(965.0) is True    # -3.5% breaches 3%
    assert s.can_trade() is False


def test_start_day_clears_trip_but_not_kill():
    s = SafetyState(max_daily_loss_pct=0.03)
    s.start_day(1000.0)
    s.update(900.0)        # trips
    s.kill()
    s.start_day(1000.0)    # new day clears trip
    assert s.tripped is False
    assert s.can_trade() is False  # still killed

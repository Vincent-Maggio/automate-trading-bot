import pytest
from trading_bot.domain.models import Action, Signal, StrategyVote
from trading_bot.decision.aggregator import aggregate


def _vote(name, action, conf, weight=1.0):
    return StrategyVote(name, Signal("AAPL", action, conf, "r"), weight)


def test_unanimous_buy_passes_gate():
    votes = [_vote("a", Action.BUY, 0.9), _vote("b", Action.BUY, 0.8)]
    d = aggregate(votes, threshold=0.5, min_consensus=2)
    assert d.action == Action.BUY
    assert d.consensus_met is True


def test_buy_blocked_by_consensus_gate():
    votes = [_vote("a", Action.BUY, 0.9), _vote("b", Action.HOLD, 0.0)]
    d = aggregate(votes, threshold=0.1, min_consensus=2)
    assert d.action == Action.HOLD
    assert d.consensus_met is False


def test_buy_blocked_by_threshold():
    votes = [_vote("a", Action.BUY, 0.2), _vote("b", Action.BUY, 0.1)]
    d = aggregate(votes, threshold=0.5, min_consensus=2)
    assert d.action == Action.HOLD


def test_conflict_nets_to_direction():
    votes = [_vote("a", Action.BUY, 0.9), _vote("b", Action.SELL, 0.2)]
    d = aggregate(votes, threshold=0.5, min_consensus=1)
    assert d.action == Action.BUY
    assert d.net_score == pytest.approx(0.7)


def test_empty_votes_raises():
    with pytest.raises(ValueError):
        aggregate([], threshold=0.5, min_consensus=1)

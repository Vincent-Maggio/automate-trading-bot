from trading_bot.domain.models import Action, Decision

_DIR = {Action.BUY: 1, Action.SELL: -1, Action.HOLD: 0}


def aggregate(votes: list, threshold: float, min_consensus: int) -> Decision:
    if not votes:
        raise ValueError("aggregate requires at least one vote")
    symbol = votes[0].signal.symbol

    net_score = sum(v.weight * v.signal.confidence * _DIR[v.signal.action]
                    for v in votes)

    if net_score > 0:
        net_dir = Action.BUY
    elif net_score < 0:
        net_dir = Action.SELL
    else:
        net_dir = Action.HOLD

    agree_count = sum(1 for v in votes if v.signal.action == net_dir
                      and net_dir != Action.HOLD)
    consensus_met = agree_count >= min_consensus

    if net_dir != Action.HOLD and abs(net_score) >= threshold and consensus_met:
        action = net_dir
    else:
        action = Action.HOLD

    rationale = (
        f"net_score={net_score:.3f} (threshold={threshold}), "
        f"agree={agree_count}/{min_consensus} -> {action.value}"
    )
    return Decision(symbol=symbol, action=action, net_score=net_score,
                    consensus_met=consensus_met, rationale=rationale,
                    votes=list(votes))

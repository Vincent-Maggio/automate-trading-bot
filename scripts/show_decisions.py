import sys
from trading_bot.config.loader import load_config
from trading_bot.audit.audit_log import AuditLog


def main(limit: int = 20) -> None:
    cfg = load_config("config.yaml")
    audit = AuditLog(cfg["execution"]["audit_db"])
    decisions = audit.recent_decisions(limit)
    if not decisions:
        print("No decisions logged yet. Run a cycle first: scripts/run_paper_cycle.py")
        return
    print(f"{'time':19}  {'symbol':6}  {'action':6}  {'score':>7}  {'cons.':5}  rationale")
    print("-" * 90)
    for d in decisions:
        ts = (d["ts"] or "")[:19]
        cons = "yes" if d["consensus_met"] else "no"
        print(f"{ts:19}  {d['symbol']:6}  {d['action']:6}  {d['net_score']:7.3f}  "
              f"{cons:5}  {d['rationale']}")


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    main(limit)

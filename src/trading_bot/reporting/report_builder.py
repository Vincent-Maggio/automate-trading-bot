from datetime import date

_KINDS = {"morning": "Morning", "nightly": "Nightly"}


def build_report(kind: str, snapshot, activity: dict):
    if kind not in _KINDS:
        raise ValueError(f"unknown report kind: {kind}")
    label = _KINDS[kind]
    day = activity.get("date") or date.today().isoformat()
    subject = f"[Trading Bot] {label} report — {day}"

    decisions = activity.get("decisions", [])
    fills = activity.get("fills", [])
    events = activity.get("events", [])

    lines = [
        f"{label} report for {day}",
        "",
        f"Equity: ${snapshot.equity:,.2f}",
        f"Cash: ${snapshot.cash:,.2f}",
        f"Exposure: {snapshot.exposure * 100:.1f}%",
        f"Realized P&L: ${snapshot.realized_pnl:,.2f}",
        "",
        "Positions:",
    ]
    if snapshot.positions:
        for p in snapshot.positions:
            lines.append(
                f"  {p['symbol']}: qty {p['qty']:.4f} @ avg ${p['avg_cost']:.2f}, "
                f"price ${p['price']:.2f}, unrealized ${p['unrealized_pnl']:,.2f}")
    else:
        lines.append("  (none)")

    lines += ["", "What the bot did:"]
    if fills:
        for f in fills:
            lines.append(f"  FILL {f['side']} {f['qty']:.4f} {f['symbol']} @ ${f['price']:.2f}")
    else:
        lines.append("  (no fills)")
    for d in decisions:
        lines.append(f"  DECISION {d['action']} {d['symbol']} — {d.get('rationale', '')}")

    if events:
        lines += ["", "Alerts:"]
        for e in events:
            lines.append(f"  {e['kind']}: {e['detail']}")

    text = "\n".join(lines)

    rows = "".join(
        f"<tr><td>{p['symbol']}</td><td>{p['qty']:.4f}</td>"
        f"<td>${p['avg_cost']:.2f}</td><td>${p['price']:.2f}</td>"
        f"<td>${p['unrealized_pnl']:,.2f}</td></tr>"
        for p in snapshot.positions
    ) or "<tr><td colspan='5'>(none)</td></tr>"
    alerts_html = ""
    if events:
        items = "".join(f"<li>{e['kind']}: {e['detail']}</li>" for e in events)
        alerts_html = f"<h3>Alerts</h3><ul>{items}</ul>"
    html = (
        f"<h2>{label} report — {day}</h2>"
        f"<p>Equity: ${snapshot.equity:,.2f} | Cash: ${snapshot.cash:,.2f} | "
        f"Exposure: {snapshot.exposure * 100:.1f}% | "
        f"Realized P&amp;L: ${snapshot.realized_pnl:,.2f}</p>"
        f"<h3>Positions</h3>"
        f"<table border='1' cellpadding='4'><tr><th>Symbol</th><th>Qty</th>"
        f"<th>Avg cost</th><th>Price</th><th>Unrealized</th></tr>{rows}</table>"
        f"{alerts_html}"
    )
    return subject, text, html

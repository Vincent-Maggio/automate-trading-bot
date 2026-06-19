def maybe_alert(safety, control_store, notifier) -> bool:
    reasons = []
    if control_store.is_killed():
        reasons.append(f"kill switch active: {control_store.kill_reason() or 'manual'}")
    if getattr(safety, "tripped", False):
        reasons.append("circuit breaker tripped (max daily loss breached)")
    if not reasons:
        return False
    text = "Trading is halted.\n" + "\n".join(f"- {r}" for r in reasons)
    html = "<h3>Trading halted</h3><ul>" + "".join(f"<li>{r}</li>" for r in reasons) + "</ul>"
    notifier.send("[Trading Bot] ALERT", text, html)
    return True

import sys
from datetime import date

from trading_bot.config.loader import load_config, load_secrets
from trading_bot.audit.audit_log import AuditLog
from trading_bot.reporting.account_reader import AlpacaAccountReader
from trading_bot.reporting.report_builder import build_report
from trading_bot.notify.console_notifier import ConsoleNotifier
from trading_bot.notify.email_notifier import EmailNotifier


def main(kind: str) -> None:
    cfg = load_config("config.yaml")
    secrets = load_secrets(".env")
    rep = cfg["reporting"]
    limit = rep["recent_limit"]

    audit = AuditLog(cfg["execution"]["audit_db"])
    activity = {
        "date": date.today().isoformat(),
        "decisions": audit.recent_decisions(limit),
        "fills": audit.recent_fills(limit),
        "events": audit.recent_events(limit),
    }

    reader = AlpacaAccountReader(secrets["ALPACA_API_KEY"], secrets["ALPACA_SECRET_KEY"])
    snapshot = reader.snapshot()

    subject, text, html = build_report(kind, snapshot, activity)

    if rep["delivery"] == "email":
        notifier = EmailNotifier(
            host=secrets["SMTP_HOST"], port=secrets["SMTP_PORT"],
            username=secrets["SMTP_USER"], password=secrets["SMTP_PASS"],
            sender=secrets["REPORT_FROM_EMAIL"], recipient=secrets["REPORT_TO_EMAIL"],
        )
    else:
        notifier = ConsoleNotifier()
    notifier.send(subject, text, html)
    print(f"sent {kind} report: {subject}")


if __name__ == "__main__":
    kind = sys.argv[1] if len(sys.argv) > 1 else "morning"
    main(kind)

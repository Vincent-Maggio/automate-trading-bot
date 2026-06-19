import io
from trading_bot.notify.console_notifier import ConsoleNotifier


def test_console_records_and_prints():
    buf = io.StringIO()
    n = ConsoleNotifier(stream=buf)
    n.send("subj", "the body", "<p>the body</p>")
    assert n.sent == [("subj", "the body")]
    assert "subj" in buf.getvalue()

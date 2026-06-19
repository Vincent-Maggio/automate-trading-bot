import sys
from trading_bot.notify.base import Notifier


class ConsoleNotifier(Notifier):
    def __init__(self, stream=None):
        self.stream = stream or sys.stdout
        self.sent: list = []

    def send(self, subject: str, text_body: str, html_body: str) -> None:
        self.sent.append((subject, text_body))
        print(f"=== {subject} ===\n{text_body}", file=self.stream)

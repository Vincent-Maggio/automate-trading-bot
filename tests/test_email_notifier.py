from trading_bot.notify.email_notifier import EmailNotifier


class _FakeSMTP:
    def __init__(self):
        self.calls = []

    def starttls(self):
        self.calls.append(("starttls",))

    def login(self, u, p):
        self.calls.append(("login", u))

    def sendmail(self, frm, to, msg):
        self.calls.append(("sendmail", frm, to, msg))

    def quit(self):
        self.calls.append(("quit",))


def test_email_sends_via_smtp():
    fake = _FakeSMTP()
    n = EmailNotifier(host="smtp.test", port=587, username="u@test",
                      password="secret", sender="u@test", recipient="me@test",
                      _smtp_factory=lambda: fake)
    n.send("subj", "text body", "<p>html body</p>")
    kinds = [c[0] for c in fake.calls]
    assert "login" in kinds and "sendmail" in kinds and "quit" in kinds
    sendmail_call = [c for c in fake.calls if c[0] == "sendmail"][0]
    assert sendmail_call[1] == "u@test"
    assert sendmail_call[2] == "me@test"
    assert "subj" in sendmail_call[3]
    assert "secret" not in sendmail_call[3]

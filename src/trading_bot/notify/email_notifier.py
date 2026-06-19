import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from trading_bot.notify.base import Notifier


class EmailNotifier(Notifier):
    def __init__(self, host: str, port: int, username: str, password: str,
                 sender: str, recipient: str, _smtp_factory=None, use_tls: bool = True):
        self.host = host
        self.port = port
        self.username = username
        self._password = password
        self.sender = sender
        self.recipient = recipient
        self.use_tls = use_tls
        self._smtp_factory = _smtp_factory or (lambda: smtplib.SMTP(host, port))

    def send(self, subject: str, text_body: str, html_body: str) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = self.recipient
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))
        smtp = self._smtp_factory()
        try:
            if self.use_tls:
                smtp.starttls()
            smtp.login(self.username, self._password)
            smtp.sendmail(self.sender, self.recipient, msg.as_string())
        finally:
            smtp.quit()

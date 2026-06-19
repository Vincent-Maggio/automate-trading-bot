from abc import ABC, abstractmethod


class Notifier(ABC):
    @abstractmethod
    def send(self, subject: str, text_body: str, html_body: str) -> None:
        ...

from abc import ABC, abstractmethod

from app.core.config import get_settings
from app.core.logging import logger

settings = get_settings()


class NotificationChannel(ABC):
    @abstractmethod
    async def send(self, *, to: str, subject: str, body: str) -> None: ...


class ConsoleEmailChannel(NotificationChannel):
    """Dev-mode channel: logs instead of sending real email."""

    async def send(self, *, to: str, subject: str, body: str) -> None:
        logger.info("email_sent_console", to=to, subject=subject, body=body)


class SmtpEmailChannel(NotificationChannel):
    async def send(self, *, to: str, subject: str, body: str) -> None:
        import aiosmtplib
        from email.message import EmailMessage

        message = EmailMessage()
        message["From"] = settings.email_from
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)

        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username or None,
            password=settings.smtp_password or None,
            start_tls=True,
        )


class SmsChannel(NotificationChannel):
    """Not implemented in this phase; channel interface kept pluggable for a future SMS provider."""

    async def send(self, *, to: str, subject: str, body: str) -> None:
        raise NotImplementedError("SMS channel is not implemented in this phase")


def get_email_channel() -> NotificationChannel:
    if settings.email_backend == "smtp":
        return SmtpEmailChannel()
    return ConsoleEmailChannel()

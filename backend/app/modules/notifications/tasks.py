import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.logging import logger
from app.models.notification import Notification, NotificationStatus
from app.models.user import User
from app.modules.notifications.channels import get_email_channel
from app.modules.notifications.templates import render


class NotificationNotReady(Exception):
    """The notification row isn't visible yet - retry, don't drop.

    service.notify() enqueues on flush, inside the request's still-open
    transaction, so a consumer can pick the job up before the commit lands. That
    window is real for in-process delivery especially, where the background task
    starts immediately - so a missing row is treated as retryable rather than as
    a reason to discard the notification.
    """


async def send_notification(ctx, notification_id: str) -> None:
    """Deliver one notification. Raises on failure so the queue retries it.

    Both transports rely on that: arq retries a raising job, and the in-process
    queue retries with backoff (app/core/queue.py). Swallowing the error here
    would instead mark the attempt done and lose the notification silently.
    """
    async with AsyncSessionLocal() as db:
        notification = (
            await db.execute(select(Notification).where(Notification.id == uuid.UUID(notification_id)))
        ).scalar_one_or_none()
        if notification is None:
            logger.warning("notification_not_found", notification_id=notification_id)
            raise NotificationNotReady(notification_id)
        if notification.status == NotificationStatus.SENT:
            return  # already delivered; a retry or duplicate delivery is a no-op

        user = (await db.execute(select(User).where(User.id == notification.user_id))).scalar_one_or_none()
        if user is None:
            # Permanent: the recipient is gone, so retrying can't help.
            notification.status = NotificationStatus.FAILED
            await db.commit()
            return

        try:
            subject, body = render(notification.type, notification.payload)
            channel = get_email_channel()
            await channel.send(to=user.email, subject=subject, body=body)
        except Exception:
            logger.exception("notification_send_failed", notification_id=notification_id)
            notification.status = NotificationStatus.FAILED
            await db.commit()
            raise

        notification.status = NotificationStatus.SENT
        notification.sent_at = datetime.now(timezone.utc)
        await db.commit()

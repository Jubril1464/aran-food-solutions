from sqlalchemy.ext.asyncio import AsyncSession

from app.core.queue import get_notification_queue
from app.models.notification import Notification, NotificationType
from app.models.user import User


async def notify(db: AsyncSession, *, user: User, notification_type: NotificationType, payload: dict) -> Notification:
    """Persist a pending notification and enqueue async delivery. Never sends inline."""
    full_payload = {"full_name": user.full_name, **payload}
    notification = Notification(
        user_id=user.id,
        type=notification_type,
        channel="email",
        payload=full_payload,
    )
    db.add(notification)
    await db.flush()

    await get_notification_queue().enqueue(str(notification.id))
    return notification

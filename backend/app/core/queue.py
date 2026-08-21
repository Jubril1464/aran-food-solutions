import asyncio
from abc import ABC, abstractmethod

from app.core.config import get_settings
from app.core.logging import logger

settings = get_settings()


class NotificationQueue(ABC):
    @abstractmethod
    async def enqueue(self, notification_id: str) -> None: ...


class ArqNotificationQueue(NotificationQueue):
    """Redis-backed arq queue, consumed by the separate worker process in
    docker-compose (app/worker.py). The right choice when you have somewhere to
    run that second process."""

    async def enqueue(self, notification_id: str) -> None:
        from app.core.redis import get_arq_pool

        pool = await get_arq_pool()
        await pool.enqueue_job("send_notification", notification_id)


# Tasks are kept in a module-level set because asyncio only holds a weak
# reference to a running task: without this, a notification can be garbage
# collected mid-delivery under load.
_in_flight: set[asyncio.Task] = set()

# Two things these retries cover, both of which a message queue would have
# handled for us: the notification row is INSERTed with the request's
# transaction still open (notify() flushes rather than commits), so a delivery
# attempt that starts immediately can fail to see it; and a send can fail
# transiently, e.g. a slow SMTP host. Backoff doubles from the base delay, so
# five attempts span roughly six seconds.
_MAX_ATTEMPTS = 5
_BASE_DELAY_SECONDS = 0.4


class InProcessNotificationQueue(NotificationQueue):
    """Deliver in a background task inside the API process itself.

    This is the default because it needs no Redis and no second service, which
    is what makes the app deployable on a single free-tier web service. The
    trade-off is honest: an in-process task dies with the process, so a
    notification enqueued during a deploy (or when a free instance spins down)
    can be left PENDING. `redeliver_pending()` below sweeps those up on the next
    startup, which is why delivery is still eventually-once rather than
    best-effort.

    Requests never wait for delivery - that property, the one the whole
    NotificationQueue abstraction exists to protect, is unchanged.
    """

    async def enqueue(self, notification_id: str) -> None:
        task = asyncio.create_task(_deliver(notification_id))
        _in_flight.add(task)
        task.add_done_callback(_in_flight.discard)


async def _deliver(notification_id: str) -> None:
    from app.modules.notifications.tasks import NotificationNotReady, send_notification

    delay = _BASE_DELAY_SECONDS
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            await send_notification(None, notification_id)
            return
        except NotificationNotReady:
            reason = "row_not_visible_yet"
        except Exception:
            # send_notification has already logged the cause and marked the row
            # FAILED. The exception is caught rather than raised because nothing
            # awaits this task - an unretrieved task exception would only show up
            # as a confusing "Task exception was never retrieved" warning.
            reason = "send_failed"

        if attempt == _MAX_ATTEMPTS:
            logger.error(
                "notification_delivery_gave_up",
                notification_id=notification_id,
                reason=reason,
                attempts=attempt,
            )
            return
        await asyncio.sleep(delay)
        delay *= 2


async def redeliver_pending(limit: int = 100) -> int:
    """Re-enqueue notifications still PENDING from a previous process.

    Called on startup (app/main.py). Without it, anything enqueued moments
    before a restart or a free-tier spin-down would sit PENDING forever.
    """
    import uuid

    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models.notification import Notification, NotificationStatus

    queue = get_notification_queue()
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(Notification.id)
                .where(Notification.status == NotificationStatus.PENDING)
                .order_by(Notification.created_at)
                .limit(limit)
            )
        ).scalars().all()

    for notification_id in rows:
        await queue.enqueue(str(notification_id))
    if rows:
        logger.info("pending_notifications_requeued", count=len(rows))
    return len(rows)


def get_notification_queue() -> NotificationQueue:
    if settings.queue_backend == "redis":
        return ArqNotificationQueue()
    return InProcessNotificationQueue()


__all__ = ["NotificationQueue", "get_notification_queue", "redeliver_pending"]

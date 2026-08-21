from abc import ABC, abstractmethod
from functools import lru_cache

from app.core.config import get_settings

settings = get_settings()


class NotificationQueue(ABC):
    @abstractmethod
    async def enqueue(self, notification_id: str) -> None: ...


class ArqNotificationQueue(NotificationQueue):
    """Local/docker-compose default: Redis-backed arq queue, consumed by app/worker.py."""

    async def enqueue(self, notification_id: str) -> None:
        from app.core.redis import get_arq_pool

        pool = await get_arq_pool()
        await pool.enqueue_job("send_notification", notification_id)


@lru_cache
def _sqs_client():
    """Cached for the life of the execution environment - creating a boto3
    client is expensive enough (~100-300ms) to matter on a per-request path."""
    import boto3

    return boto3.client("sqs", region_name=settings.aws_region or None)


class SqsNotificationQueue(NotificationQueue):
    """AWS Lambda deployment: SQS, consumed by app/notification_worker_handler.py."""

    async def enqueue(self, notification_id: str) -> None:
        # boto3 is sync; on Lambda each invocation handles a single request so
        # there is no other coroutine to starve. Kept simple deliberately.
        _sqs_client().send_message(QueueUrl=settings.sqs_notification_queue_url, MessageBody=notification_id)


def get_notification_queue() -> NotificationQueue:
    if settings.queue_backend == "sqs":
        return SqsNotificationQueue()
    return ArqNotificationQueue()

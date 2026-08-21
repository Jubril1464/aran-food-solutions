"""Notification worker Lambda entrypoint: SQS -> send_notification().

Deployed by infra/terraform/lambda.tf as the `-worker` function's image
command, wired to the notifications queue by the event source mapping in
infra/terraform/sqs.tf. Each message body is just the notification id - the
same payload the local/docker-compose arq worker consumes via app/worker.py,
so both paths run identical delivery code.
"""

import asyncio

from app.core.logging import logger
from app.modules.notifications.tasks import send_notification


def _get_loop() -> asyncio.AbstractEventLoop:
    """One event loop for the life of the execution environment.

    asyncio.run() would create *and close* a loop per invocation and reset the
    thread's current loop to None on exit, so anything holding loop-bound state
    across warm invocations breaks. (app/core/database.py already switches to a
    NullPool on Lambda for the same reason - see the note there.)
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("loop is closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


async def _process(records: list[dict]) -> list[dict]:
    """Deliver each message, isolating failures to the message that caused them."""
    failures: list[dict] = []
    for record in records:
        message_id = record.get("messageId", "")
        try:
            await send_notification(None, record["body"])
        except Exception:
            logger.exception(
                "notification_message_failed",
                message_id=message_id,
                notification_id=record.get("body"),
            )
            failures.append({"itemIdentifier": message_id})
    return failures


def handler(event, context):
    records = event.get("Records", [])
    failures = _get_loop().run_until_complete(_process(records))
    # Requires functionResponseTypes = ["ReportBatchItemFailures"] on the event
    # source mapping (set in infra/terraform/sqs.tf). Without it SQS treats a
    # raised exception as "the entire batch failed" and redelivers messages
    # that were already sent; with it, only the listed messages come back.
    return {"batchItemFailures": failures}

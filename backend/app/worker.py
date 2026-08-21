from app.core.redis import _redis_settings
from app.modules.notifications.tasks import send_notification


class WorkerSettings:
    functions = [send_notification]
    redis_settings = _redis_settings()

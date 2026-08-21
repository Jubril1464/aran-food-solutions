from arq import ArqRedis, create_pool
from arq.connections import RedisSettings

from app.core.config import get_settings

settings = get_settings()

_arq_pool: ArqRedis | None = None


def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(settings.redis_url)


async def get_arq_pool() -> ArqRedis:
    global _arq_pool
    if _arq_pool is None:
        _arq_pool = await create_pool(_redis_settings())
    return _arq_pool

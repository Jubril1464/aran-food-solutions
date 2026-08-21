import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

_engine_kwargs: dict = {"pool_pre_ping": True, "future": True}

# AWS sets this in every Lambda execution environment. The engine is created
# once at cold start, but Lambda gives each invocation a fresh event loop —
# a pooled asyncpg connection whose internal locks are bound to a previous
# invocation's loop throws "Future attached to a different loop" on warm
# invocations. NullPool opens a fresh connection per request instead of
# reusing one across invocations, which avoids that entirely. Not needed
# (and not used) for the long-running ECS/local-dev process, which keeps a
# real connection pool.
if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    _engine_kwargs["poolclass"] = NullPool

if settings.db_ssl_required:
    # Encrypts the connection; this is NOT full certificate verification
    # (that would need "verify-full" + bundling the RDS CA cert). Acceptable
    # for a pitch-stage MVP with a public RDS endpoint — see infra/DEPLOY.md.
    _engine_kwargs["connect_args"] = {"ssl": "require"}

engine = create_async_engine(settings.database_url, **_engine_kwargs)
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.core.database import Base
from app.models import *  # noqa: F401,F403  ensure all models are registered on Base.metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def render_item(type_, obj, autogen_context):
    """Render our custom GUID TypeDecorator with its proper import instead of repr()."""
    from app.models.mixins import GUID

    if type_ == "type" and isinstance(obj, GUID):
        autogen_context.imports.add("from app.models.mixins import GUID")
        return "GUID()"
    return False


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, render_item=render_item)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    # Mirror the application engine's TLS setting (app/core/database.py): the
    # deployed RDS instance has rds.force_ssl=1, so an unencrypted connection is
    # rejected outright. asyncpg would negotiate TLS on its own here (it
    # defaults to sslmode=prefer), but relying on that leaves migrations quietly
    # dependent on a driver default the app itself doesn't rely on.
    connect_args = {"ssl": "require"} if settings.db_ssl_required else {}
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        future=True,
        connect_args=connect_args,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())

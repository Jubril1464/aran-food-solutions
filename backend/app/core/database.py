from collections.abc import AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

# libpq query parameters that a hosted Postgres provider puts in the connection
# string it gives you, and that asyncpg does not accept as keyword arguments -
# it would raise `connect() got an unexpected keyword argument 'sslmode'` on the
# first query. Neon's string, for example, ends with
# `?sslmode=require&channel_binding=require`.
#
# Rather than making everyone hand-edit a copied connection string (and debug a
# confusing TypeError when they forget), they're stripped here and translated
# into the equivalent asyncpg setting below.
_LIBPQ_ONLY_PARAMS = {"sslmode", "channel_binding", "sslrootcert", "sslcert", "sslkey", "target_session_attrs"}


def normalize_database_url(url: str) -> tuple[str, bool]:
    """Return (url asyncpg can use, whether TLS was requested in the URL).

    Accepts what a provider's dashboard actually hands you - a `postgresql://`
    URL with libpq parameters - and returns the async-driver equivalent.
    """
    if url.startswith("postgres://"):  # older providers still emit this scheme
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]

    parts = urlsplit(url)
    kept: list[tuple[str, str]] = []
    ssl_requested = False
    changed = False
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key.lower() in _LIBPQ_ONLY_PARAMS:
            if key.lower() == "sslmode" and value.lower() in {"require", "verify-ca", "verify-full", "prefer"}:
                ssl_requested = True
            changed = True
            continue
        kept.append((key, value))

    # A connection-pooler endpoint (Neon and Supabase both signal one in the
    # hostname) fronts Postgres with pgbouncer in transaction pooling mode, where
    # consecutive statements can land on different server connections. SQLAlchemy's
    # asyncpg dialect caches prepared statements per connection, and a cached one
    # is gone the moment the server connection changes - which surfaces as
    # `prepared statement "__asyncpg_stmt_1__" does not exist` under load rather
    # than at startup, making it a genuinely nasty thing to debug.
    #
    # Disabling that cache is the documented fix. Applied automatically because
    # the pooled string is the one these dashboards show by default, so pasting it
    # is the likely thing to do, not the exceptional one.
    host = parts.hostname or ""
    if ("-pooler." in host or ".pooler." in host) and not any(
        key == "prepared_statement_cache_size" for key, _ in kept
    ):
        kept.append(("prepared_statement_cache_size", "0"))
        changed = True

    if not changed:
        # Returned untouched rather than rebuilt, because urlunsplit() collapses
        # the empty authority in a URL like `sqlite+aiosqlite:///./dev.db` down to
        # `sqlite+aiosqlite:/./dev.db`, which SQLAlchemy then refuses to parse.
        return url, ssl_requested

    return urlunsplit(parts._replace(query=urlencode(kept))), ssl_requested


database_url, _url_wants_ssl = normalize_database_url(settings.database_url)

_engine_kwargs: dict = {
    "pool_pre_ping": True,
    "future": True,
}

if database_url.startswith("postgresql+asyncpg://"):
    # Sized for a small free-tier Postgres, and for the fact that a hosted
    # instance suspends its compute when idle (Neon does after 5 minutes): a
    # connection that was open across a suspend is dead, so pre_ping above
    # replaces it and pool_recycle keeps any single connection from being held
    # long enough to go stale in the first place.
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 5
    _engine_kwargs["pool_recycle"] = 300

if settings.db_ssl_required or _url_wants_ssl:
    # Encrypts the connection; this is NOT full certificate verification (that
    # would need an SSL context built with the provider's CA bundle). Managed
    # providers require TLS, and most hand you a URL that says so - which is why
    # a `sslmode=require` in the URL is honoured here even if DB_SSL_REQUIRED
    # was left unset.
    _engine_kwargs["connect_args"] = {"ssl": "require"}

engine = create_async_engine(database_url, **_engine_kwargs)
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

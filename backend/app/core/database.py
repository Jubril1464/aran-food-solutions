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
    if not parts.query:
        return url, False

    kept: list[tuple[str, str]] = []
    ssl_requested = False
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key.lower() in _LIBPQ_ONLY_PARAMS:
            if key.lower() == "sslmode" and value.lower() in {"require", "verify-ca", "verify-full", "prefer"}:
                ssl_requested = True
            continue
        kept.append((key, value))

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

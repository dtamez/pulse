from collections.abc import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from core.config import settings

print("**************")
print("ASYNC_DATABASE_URL =", settings.ASYNC_DATABASE_URL)
print("SYNC_DATABASE_URL =", settings.SYNC_DATABASE_URL)
print("**************")


class Base(DeclarativeBase):
    pass


def _build_async_engine():
    kwargs = {"echo": settings.SQL_ECHO}
    if settings.TESTING:
        kwargs["poolclass"] = NullPool
    else:
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10
    return create_async_engine(settings.ASYNC_DATABASE_URL, **kwargs)


def _build_sync_engine():
    kwargs = {"echo": settings.SQL_ECHO}
    if settings.TESTING:
        kwargs["poolclass"] = NullPool
    else:
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10
    return create_engine(settings.SYNC_DATABASE_URL, **kwargs)


async_engine = _build_async_engine()
sync_engine = _build_sync_engine()

async_session = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

sync_session = sessionmaker(
    bind=sync_engine,
    class_=Session,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


def get_sync_db() -> Generator[Session, None, None]:
    session = sync_session()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

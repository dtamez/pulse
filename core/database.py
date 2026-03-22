import hashlib
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from core.config import settings


def shard_for_tenant(external_key: str) -> str:
    digest = hashlib.sha256(external_key.encode("utf-8")).hexdigest()
    shard_num = int(digest, 16) % 2
    answer = "shard0" if shard_num == 0 else "shard1"
    return answer


class Base(DeclarativeBase):
    pass


def _engine_kwargs() -> dict:
    kwargs = {"echo": settings.SQL_ECHO}
    if settings.TESTING:
        kwargs["poolclass"] = NullPool
    else:
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 0
        kwargs["pool_timeout"] = 30
        kwargs["pool_pre_ping"] = True
    return kwargs


def _build_async_engine(url: str):
    return create_async_engine(url, **_engine_kwargs())


def _build_sync_engine(url: str):
    return create_engine(url, **_engine_kwargs())


ASYNC_ENGINES = {
    "shard0": _build_async_engine(settings.ASYNC_DATABASE_SHARD0_URL),
    "shard1": _build_async_engine(settings.ASYNC_DATABASE_SHARD1_URL),
}

SYNC_ENGINES = {
    "shard0": _build_sync_engine(settings.SYNC_DATABASE_SHARD0_URL),
    "shard1": _build_sync_engine(settings.SYNC_DATABASE_SHARD1_URL),
}

ASYNC_SESSIONMAKERS = {
    shard_name: async_sessionmaker(engine, expire_on_commit=False)
    for shard_name, engine in ASYNC_ENGINES.items()
}

SYNC_SESSIONMAKERS = {
    shard_name: sessionmaker(bind=engine, autoflush=False, autocommit=False)
    for shard_name, engine in SYNC_ENGINES.items()
}

print("ASYNC shard mapping:")
for name, engine in ASYNC_ENGINES.items():
    print(name, engine.url)

print("SYNC shard mapping:")
for name, engine in SYNC_ENGINES.items():
    print(name, engine.url)


@asynccontextmanager
async def async_db_session(shard_name: str) -> AsyncGenerator[AsyncSession, None]:
    async with ASYNC_SESSIONMAKERS[shard_name]() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


@contextmanager
def get_sync_db(shard_name) -> Generator[Session, None, None]:
    session = SYNC_SESSIONMAKERS[shard_name]()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

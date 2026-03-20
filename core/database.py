import hashlib
from collections.abc import AsyncGenerator, Generator
from contextlib import contextmanager

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from core.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


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
    "shard1": _build_async_engine(settings.ASYNC_DATABASE_SHARD1_URL),
    "shard2": _build_async_engine(settings.ASYNC_DATABASE_SHARD2_URL),
}

SYNC_ENGINES = {
    "shard1": _build_sync_engine(settings.SYNC_DATABASE_SHARD1_URL),
    "shard2": _build_sync_engine(settings.SYNC_DATABASE_SHARD2_URL),
}

ASYNC_SESSIONMAKERS = {
    shard_name: async_sessionmaker(engine, expire_on_commit=False)
    for shard_name, engine in ASYNC_ENGINES.items()
}

SYNC_SESSIONMAKERS = {
    shard_name: sessionmaker(bind=engine, autoflush=False, autocommit=False)
    for shard_name, engine in SYNC_ENGINES.items()
}


def shard_for_tenant(external_key: str) -> str:
    digest = hashlib.sha256(external_key.encode("utf-8")).hexdigest()
    shard_num = int(digest, 16) % 2
    return "shard1" if shard_num == 0 else "shard2"


async def get_shard_name(raw_key: str = Depends(api_key_header)) -> str:
    # lookup tenant / shard from api key
    shard_name = shard_for_tenant(raw_key)
    if shard_name not in ASYNC_SESSIONMAKERS:
        raise HTTPException(status_code=500, detail="Invalid shard")
    return shard_name


async def get_db(shard_name):
    async def _get_db() -> AsyncGenerator[AsyncSession, None]:
        async with ASYNC_SESSIONMAKERS[shard_name]() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    return _get_db


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

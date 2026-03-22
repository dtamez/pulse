import hashlib
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import ASYNC_SESSIONMAKERS, async_db_session, shard_for_tenant
from core.models import ApiKey, Tenant


@dataclass
class RequestTenantContext:
    raw_key: str
    tenant_id: uuid.UUID
    external_key: str


_event_type_cache: dict[str, uuid.UUID] = {}
_api_key_cache: dict[str, uuid.UUID] = {}
_context_cache: dict[str, RequestTenantContext] = {}
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


async def get_tenant_id_for_key_hash(
    key_hash: str, db: AsyncSession
) -> uuid.UUID | None:
    cached = _api_key_cache.get(key_hash)
    if cached is not None:
        print(f"cache hit for key_hash={key_hash} tenant_id={cached}")
        return cached

    print(f"cache miss for key_hash={key_hash}")
    result = await db.execute(
        select(ApiKey.tenant_id).where(
            ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True)
        )
    )
    tenant_id = result.scalar_one_or_none()
    print(f"db lookup key_hash={key_hash} tenant_id={tenant_id}")
    if tenant_id is not None:
        _api_key_cache[key_hash] = tenant_id
    return tenant_id


async def get_tenant_context(
    raw_key: str = Depends(api_key_header),
) -> RequestTenantContext:
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    cached = _context_cache.get(key_hash)
    if cached is not None:
        return cached

    for shard_name in ("shard0", "shard1"):
        async with async_db_session(shard_name) as session:
            result = await session.execute(
                select(Tenant.id, Tenant.external_key)
                .join(ApiKey, ApiKey.tenant_id == Tenant.id)
                .where(
                    ApiKey.key_hash == key_hash,
                    ApiKey.is_active.is_(True),
                )
            )
            row = result.one_or_none()

            if row is not None:
                tenant_id, external_key = row
                ctx = RequestTenantContext(
                    raw_key=raw_key,
                    tenant_id=tenant_id,
                    external_key=external_key,
                )

                _context_cache[key_hash] = ctx
                return ctx

    raise HTTPException(status_code=401, detail="Invalid API key")


async def get_request_db(
    ctx: RequestTenantContext = Depends(get_tenant_context),
) -> AsyncGenerator[AsyncSession, None]:
    shard_name = shard_for_tenant(ctx.external_key)
    session = ASYNC_SESSIONMAKERS[shard_name]()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()

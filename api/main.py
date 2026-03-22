import hashlib
import uuid
from datetime import date, datetime, timezone

from fastapi import Depends, FastAPI
from fastapi.security import APIKeyHeader
from logzero import logger
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.database import shard_for_tenant
from core.deps import (
    RequestTenantContext,
    _event_type_cache,
    get_request_db,
    get_tenant_context,
    get_tenant_id_for_key_hash,
)
from core.models import DailyAggregate, Event, EventType
from worker.tasks import aggregate_event

app = FastAPI()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


class EventIn(BaseModel):
    event_type: str
    entity_id: str | None = None
    occurred_at: datetime | None = None
    payload: dict = {}


async def get_event_type_id(name: str, db: AsyncSession) -> uuid.UUID | None:
    cached = _event_type_cache.get(name)
    if cached is not None:
        return cached

    # validate event type
    result = await db.execute(select(EventType.id).where(EventType.name == name))
    evt_type_id = result.scalar_one_or_none()
    if evt_type_id is not None:
        _event_type_cache[name] = evt_type_id

    return evt_type_id


@app.post("/events")
async def ingest_event(
    event: EventIn,
    ctx: RequestTenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_request_db),
):
    logger.info(f"top of /events, ctx has: {ctx}")
    tenant_id = ctx.tenant_id
    # use the server time if occurred_at is not provided
    occurred_at = event.occurred_at or datetime.now(timezone.utc)

    evt_type_id = await get_event_type_id(event.event_type, db)

    # create the event in the db
    db_event = Event(
        tenant_id=tenant_id,
        event_type_id=evt_type_id,
        occurred_at=occurred_at,
        entity_id=event.entity_id,
        payload_json=event.payload,
    )
    db.add(db_event)
    await db.flush()
    event_id = str(db_event.id)
    await db.commit()

    # celery task to update aggregates
    logger.info("About to call shard_for_tenant")
    logger.info(f"ctx: {ctx}")
    shard_name = shard_for_tenant(ctx.external_key)
    aggregate_event.delay(str(event_id), shard_name)
    # return status and event id
    return {
        "status": "accepted",
        "event_id": event_id,
    }


@app.get("/tenant/{tenant_id}/summary")
async def tenant_summary(
    tenant_id: uuid.UUID,
    summary_date: date | None = None,
    raw_key: str = Depends(api_key_header),
    db: AsyncSession = Depends(get_request_db),
):

    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    # get our tenant
    _tenant_id = await get_tenant_id_for_key_hash(key_hash, db)

    # read from daily_aggregate
    if summary_date is not None:
        # optionally filter by date
        result = await db.execute(
            select(DailyAggregate)
            .options(
                selectinload(DailyAggregate.event_type),
                selectinload(DailyAggregate.tenant),
            )
            .where(
                DailyAggregate.tenant_id == tenant_id,
                DailyAggregate.aggregate_date == summary_date,
            )
        )
    else:
        result = await db.execute(
            select(DailyAggregate)
            .options(
                selectinload(DailyAggregate.event_type),
                selectinload(DailyAggregate.tenant),
            )
            .where(DailyAggregate.tenant_id == tenant_id)
            .order_by(desc(DailyAggregate.aggregate_date))
        )

    dailies = result.scalars().all()
    counts = []
    tenant_name = ""
    for daily in dailies:
        if not tenant_name:
            tenant_name = daily.tenant.name
        counts.append(
            {
                "event_type": daily.event_type.name,
                "count": daily.event_count,
            }
        )
    # return counts by event type
    return {
        "tenant": tenant_name,
        "counts_by_event_type": counts,
    }


@app.get("/health")
async def health():
    # helpful once deployed on kubernetes
    # later check for anything that might be failing and would be solved by a restart
    # later include any debug info that might be helpful
    return {"status": "ok"}  # HTTP 200

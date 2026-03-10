import hashlib
import uuid
from datetime import date, datetime, timezone
from time import perf_counter

from fastapi import Depends, FastAPI
from fastapi.security import APIKeyHeader
from logzero import logger
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.database import get_db
from core.models import ApiKey, DailyAggregate, Event, EventType
from worker.tasks import aggregate_event

app = FastAPI()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

_event_type_cache: dict[str, uuid.UUID] = {}
_api_key_cache: dict[str, uuid.UUID] = {}


class EventIn(BaseModel):
    event_type: str
    entity_id: str | None = None
    occurred_at: datetime | None = None
    payload: dict = {}


async def get_tenant_id_for_key_hash(
    key_hash: str, db: AsyncSession
) -> uuid.UUID | None:
    cached = _api_key_cache.get(key_hash)
    if cached is not None:
        return cached

    logger.info("cache miss for api_key")  # ty: ignore

    result = await db.execute(
        select(ApiKey.tenant_id).where(
            ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True)
        )
    )
    tenant_id = result.scalar_one_or_none()
    if tenant_id is not None:
        _api_key_cache[key_hash] = tenant_id
    return tenant_id


async def get_event_type_id(name: str, db: AsyncSession) -> uuid.UUID | None:
    cached = _event_type_cache.get(name)
    if cached is not None:
        return cached

    logger.info("cache miss for event_type")  # ty: ignore

    # validate event type
    result = await db.execute(select(EventType.id).where(EventType.name == name))
    evt_type_id = result.scalar_one_or_none()
    if evt_type_id is not None:
        _event_type_cache[name] = evt_type_id

    return evt_type_id


@app.post("/events")
async def ingest_event(
    event: EventIn,
    raw_key: str = Depends(api_key_header),
    db: AsyncSession = Depends(get_db),
):
    t0 = perf_counter()
    logger.info("ingest_event")  # ty: ignore
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    # get our tenant
    tenant_id = await get_tenant_id_for_key_hash(key_hash, db)
    t1 = perf_counter()
    logger.info(f"tenant_id: {tenant_id}")  # ty: ignore
    # use the server time if occurred_at is not provided
    occurred_at = event.occurred_at or datetime.now(timezone.utc)

    evt_type_id = await get_event_type_id(event.event_type, db)
    t2 = perf_counter()

    # create the event in the db
    db_event = Event(
        tenant_id=tenant_id,
        event_type_id=evt_type_id,
        occurred_at=occurred_at,
        entity_id=event.entity_id,
        payload_json=event.payload,
    )
    db.add(db_event)
    t3 = perf_counter()
    await db.commit()
    t4 = perf_counter()
    await db.refresh(db_event)
    t5 = perf_counter()

    print(
        f"timing auth={t1 - t0:.4f}s "
        f"evt_type={t2 - t1:.4f}s "
        f"add={t3 - t2:.4f}s "
        f"commit={t4 - t3:.4f}s "
        f"refresh={t5 - t4:.4f}s "
        f"total={t5 - t0:.4f}s"
    )

    # celery task to update aggregates
    aggregate_event.delay(str(db_event.id))

    # return status and event id
    return {
        "status": "accepted",
        "event_id": db_event.id,
    }


@app.get("/tenant/{tenant_id}/summary")
async def tenant_summary(
    tenant_id: uuid.UUID,
    summary_date: date | None = None,
    raw_key: str = Depends(api_key_header),
    db: AsyncSession = Depends(get_db),
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

import hashlib
import uuid
from datetime import date, datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.database import get_db
from core.models import ApiKey, DailyAggregate, Event, EventType
from worker.tasks import aggregate_event

app = FastAPI()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


class EventIn(BaseModel):
    event_type: str
    entity_id: str | None = None
    occurred_at: datetime | None = None
    payload: dict = {}


async def authenticate_api_key(raw_key, db) -> ApiKey:
    # authenticate the api key (from header)
    if not raw_key:
        raise HTTPException(status_code=400, detail="Missing X-API key")

    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=400, detail="Invalid X-API key")
    return api_key


@app.post("/events")
async def ingest_event(
    event: EventIn,
    raw_key: str = Depends(api_key_header),
    db: AsyncSession = Depends(get_db),
):
    api_key = await authenticate_api_key(raw_key, db)
    # get our tenant
    tenant_id = api_key.tenant_id
    # validate event type
    result = await db.execute(
        select(EventType).where(EventType.name == event.event_type)
    )
    evt_type = result.scalar_one_or_none()
    if not evt_type:
        raise HTTPException(
            status_code=400, detail=f"Invalid event type: {event.event_type}"
        )
    # use the server time if occurred_at is not provided
    occurred_at = event.occurred_at or datetime.now(timezone.utc)

    # create the event in the db
    db_event = Event(
        tenant_id=tenant_id,
        event_type=evt_type,
        occurred_at=occurred_at,
        entity_id=event.entity_id,
        payload_json=event.payload,
    )
    db.add(db_event)
    await db.commit()
    await db.refresh(db_event)

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

    _api_key = await authenticate_api_key(raw_key, db)

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

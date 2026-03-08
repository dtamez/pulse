import hashlib
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.models import ApiKey, Event, EventType
from worker.app import celery_app

app = FastAPI()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


class EventIn(BaseModel):
    event_type: str
    entity_id: str | None = None
    occurred_at: datetime | None = None
    payload: dict = {}


@app.post("/events")
async def ingest_event(
    event: EventIn,
    raw_key: str = Depends(api_key_header),
    db: AsyncSession = Depends(get_db),
):
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
    celery_app.send_task("worker.tasks.aggregate_event", args=[str(db_event.id)])

    # return status and event id
    return {
        "status": "accepted",
        "event_id": db_event.id,
    }


@app.get("/tenant/{tenant_id}/summary")
async def tenant_summary(summary_date: datetime):
    # read from daily_aggregate
    # optionally filter by date
    # return counts by event type
    pass


@app.get("/health")
async def health():
    # helpful once deployed on kubernetes
    # later check for anything that might be failing and would be solved by a restart
    # later include any debug info that might be helpful
    return {"status": "ok"}  # HTTP 200

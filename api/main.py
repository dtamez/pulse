import hashlib
from datetime import datetime

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import ApiKey, Event, EventType
from core.database import get_db
from worker.tasks import aggregate_event

app = FastAPI()


class EventIn(BaseModel):
    event_type: str
    entity_id: str | None = None
    occurred_at: datetime | None = None
    payload: dict = {}


@app.post("/events")
async def ingest_event(
    event: EventIn, raw_key: str = Header(None), db: AsyncSession = Depends(get_db)
):
    # authenticate the api key (from header)
    # api_key = models.api_key
    if not raw_key:
        raise HTTPException(status_code=400, detail="Missing X-API key")

    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    result = await db.execute(select(ApiKey).where(ApiKey.id == key_hash))
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=400, detail="Invalid X-API key")
    # get our tenant
    tenant = api_key.tenant
    # validate event type
    result = await db.execute(
        select(EventType).where(EventType.name == event.event_type)
    )
    evt_type = result.scalar_one_or_none()
    if not evt_type:
        raise HTTPException(
            status_code=500, detail=f"Invalid event type: {event.event_type}"
        )
    # use the server time if occurred_at is not provided
    occurred_at = event.occurred_at or datetime.now()

    # create the event in the db
    db_event = Event(
        tenant=tenant,
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
async def tenant_summary(summary_date: datetime):
    pass

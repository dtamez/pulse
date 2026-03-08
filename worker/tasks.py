import asyncio

from core.services import aggregate_event_impl
from worker.app import celery_app


@celery_app.task
def aggregate_event(event_id: str) -> None:
    asyncio.run(aggregate_event_impl(event_id))

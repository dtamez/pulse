from logzero import logger

from core.services import aggregate_event_impl
from worker.app import celery_app


@celery_app.task
def aggregate_event(event_id: str) -> None:
    logger.info("CELERY TASK aggregate_event")
    aggregate_event_impl(event_id)

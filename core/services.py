from logzero import logger
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from core.database import sync_session
from core.models import DailyAggregate, Event


def aggregate_event_impl(event_id: str) -> None:
    # use synchronous db calls for celery tasks
    with sync_session() as db:
        logger.info("AGGREGATE_EVENT_IMPL")
        event = db.get(Event, event_id)
        if event is None:
            return

        # strip time off of occurred_at
        aggregate_date = event.occurred_at.date()

        # fix race condition
        stmt = insert(DailyAggregate).values(
            tenant_id=event.tenant_id,
            event_type_id=event.event_type_id,
            aggregate_date=aggregate_date,
            event_count=1,
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=[
                DailyAggregate.tenant_id,
                DailyAggregate.event_type_id,
                DailyAggregate.aggregate_date,
            ],
            # increment atomically
            set_={
                "event_count": DailyAggregate.event_count + 1,
            },
        )

        db.execute(stmt)
        db.commit()

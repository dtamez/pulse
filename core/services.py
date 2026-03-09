from logzero import logger

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

        # does a DailyAggregate matching this tenant_id, event_type_id, and date exist?
        daily = db.get(
            DailyAggregate, (event.tenant_id, event.event_type_id, aggregate_date)
        )

        # if so update it with a +1 to event_count
        if daily is not None:
            daily.event_count += 1
        else:
            # if not create with an event_count of 1
            daily = DailyAggregate(
                tenant_id=event.tenant_id,
                event_type_id=event.event_type_id,
                aggregate_date=aggregate_date,
                event_count=1,
            )
            db.add(daily)

        db.commit()

from datetime import datetime
from enum import Enum

from dateutil.relativedelta import relativedelta
from fastapi.testclient import TestClient

from .main import app


class When(str, Enum):
    NOW = "Now"
    HOURS_AGO = "A few hours ago"
    DAYS_AGO = "A few days ago"
    HOURS_FROM_NOW = "A few hours from now"
    DAYS_FROM_NOW = "A few days from now"


client = TestClient(app)


def get_a_date(when: When) -> str | None:
    now = datetime.now()
    dt: datetime = now
    match when:
        case When.NOW:
            pass
        case When.HOURS_AGO:
            dt = now + relativedelta(hours=-2)
        case When.DAYS_AGO:
            dt = now + relativedelta(days=-1)
        case When.HOURS_FROM_NOW:
            dt = now + relativedelta(hours=2)
        case When.DAYS_FROM_NOW:
            dt = now + relativedelta(days=1)

    return dt.isoformat()


def test_ingest_events_invalid_api_key():

    resp = client.post(
        "/events",
        headers={"X-API": "BOGUS_API_KEY"},
        json={
            "event_type": "api_call",
            "entity_id": "some_user",
            "occurred_at": get_a_date(When.HOURS_AGO),
            "payload": {"endpoint": "/create_invoice", "status": 200, "latency_ms": 77},
        },
    )

    assert resp.status_code == 400
    assert resp.json() == {"detail": "Invalid X-API key"}

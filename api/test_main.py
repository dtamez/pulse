from datetime import date, datetime, timezone
from enum import Enum
from random import choice, randint

import pytest
from dateutil.relativedelta import relativedelta
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from .main import app


class When(str, Enum):
    NOW = "Now"
    HOURS_AGO = "A few hours ago"
    DAYS_AGO = "A few days ago"
    HOURS_FROM_NOW = "A few hours from now"
    DAYS_FROM_NOW = "A few days from now"


client = TestClient(app)


def get_a_date(when: When | None) -> str:
    now = datetime.now(timezone.utc)
    dt: datetime = now
    if when is None:
        when = choice(
            (
                When.NOW,
                When.HOURS_AGO,
                When.DAYS_AGO,
            )
        )
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


@pytest.mark.anyio
async def test_ingest_events_invalid_api_key():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            "/events",
            headers={"X-API-Key": "BOGUS_API_KEY"},
            json={
                "event_type": "api_call",
                "entity_id": "some_user",
                "occurred_at": get_a_date(None),
                "payload": {
                    "endpoint": "/create_invoice",
                    "status": 200,
                    "latency_ms": 77,
                },
            },
        )

    assert resp.status_code == 400
    assert resp.json() == {"detail": "Invalid X-API key"}


@pytest.mark.anyio
async def test_ingest_events_valid():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            "/events",
            headers={"X-API-Key": "pulse_243815f0d3ef782202c235976185d2ee"},
            json={
                "event_type": "api_call",
                "entity_id": "some_user",
                "occurred_at": get_a_date(When.HOURS_AGO),
                "payload": {
                    "endpoint": "/create_invoice",
                    "status": 200,
                    "latency_ms": 77,
                },
            },
        )

    assert resp.status_code == 200


@pytest.mark.anyio
async def test_tenant_summary_no_date():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get(
            "/tenant/518f65ab-f80c-4a73-b45e-27f456437934/summary",
            headers={"X-API-Key": "pulse_243815f0d3ef782202c235976185d2ee"},
        )

    assert resp.status_code == 200


@pytest.mark.anyio
async def test_tenant_summary():
    today = date.today().isoformat()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get(
            f"/tenant/518f65ab-f80c-4a73-b45e-27f456437934/summary?summary_date={today}",
            headers={"X-API-Key": "pulse_243815f0d3ef782202c235976185d2ee"},
        )

    assert resp.status_code == 200


def get_user() -> str:
    num = randint(1, 100_000)
    return f"user_{num}"


EVENT_TYPES = (
    "api_call",
    "page_view",
    "job_started",
    "job_completed",
    "job_failed",
    "purchase",
)

ENDPOINTS = {
    "api_call": (
        "/create_invoice",
        "/purchase",
        "/search_user",
        "/create_user",
        "/delete_user",
        "/update_user",
        "/register",
    ),
    "page_view": ("home", "products", "contacts", "about"),
    "jobs": (
        "generate_sales_report",
        "expunge_inactive_users",
        "ad_campaing_144",
        "ad_campaign_51",
    ),
}


# @pytest.mark.anyio
# async def test_populate_lots_of_events():
#
#     async with AsyncClient(
#         transport=ASGITransport(app=app),
#         base_url="http://test",
#     ) as client:
#         for _ in range(2500):
#             event_type = choice(EVENT_TYPES)
#             match event_type:
#                 case "api_call":
#                     endpoint = choice(ENDPOINTS["api_call"])
#                 case "page_view":
#                     endpoint = choice(ENDPOINTS["page_view"])
#                 case "job_started" | "job_failed" | "job_completed":
#                     endpoint = choice(ENDPOINTS["jobs"])
#                 case "purchase":
#                     endpoint = "secure_checkout"
#
#             resp = await client.post(
#                 "/events",
#                 headers={"X-API-Key": "pulse_243815f0d3ef782202c235976185d2ee"},
#                 json={
#                     "event_type": event_type,
#                     "entity_id": get_user(),
#                     "occurred_at": get_a_date(None),
#                     "payload": {
#                         "endpoint": endpoint,
#                         "status": 200,
#                         "latency_ms": randint(1, 100),
#                     },
#                 },
#             )
#
#     assert resp.status_code == 200

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from .main import app

client = TestClient(app)


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
                "payload": {
                    "endpoint": "/create_invoice",
                    "status": 200,
                    "latency_ms": 77,
                },
            },
        )

    assert resp.status_code == 400
    assert resp.json() == {"detail": "Invalid X-API key"}

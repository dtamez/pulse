import asyncio

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


async def gen_event():
    resp = client.post(
        "/events",
        headers={"X-API": "pulse_243815f0d3ef782202c235976185d2ee"},
        json={
            "event_type": "api_call",
            "entity_id": "some_user",
            # "occurred_at": get_a_date(When.HOURS_AGO),
            "payload": {"endpoint": "/create_invoice", "status": 200, "latency_ms": 77},
        },
    )

    print(resp)


if __name__ == "__main__":
    asyncio.run(gen_event())

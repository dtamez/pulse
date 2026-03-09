import asyncio
import random
import time
from collections import Counter
from datetime import datetime, timezone

import httpx

BASE_URL = "http://localhost:8000"
API_KEY = "pulse_1a31b0c50a6f237f73159c653716fbdb"

EVENT_TYPES = [
    "api_call",
    "purchase",
    "job_started",
    "job_completed",
    "job_failed",
]

ENDPOINTS = [
    "/search",
    "/create_invoice",
    "/login",
    "/checkout",
    "/reports/daily",
]


def make_event(i: int) -> dict:
    event_type = random.choices(
        EVENT_TYPES,
        weights=[70, 10, 8, 8, 4],
        k=1,
    )[0]

    payload = {
        "endpoint": random.choice(ENDPOINTS),
        "status": random.choices(
            [200, 201, 400, 404, 500], weights=[70, 10, 8, 5, 7], k=1
        )[0],
        "latency_ms": random.randint(20, 1200),
        "request_id": f"req_{i}",
    }

    return {
        "event_type": event_type,
        "entity_id": f"user_{random.randint(1, 5000)}",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }


async def send_one(client: httpx.AsyncClient, i: int) -> tuple[bool, int | None]:
    try:
        resp = await client.post(
            "/events",
            headers={"X-API-Key": API_KEY},
            json=make_event(i),
        )
        return resp.status_code == 200, resp.status_code
    except Exception:
        return False, None


async def worker(
    client: httpx.AsyncClient,
    start_idx: int,
    count: int,
    results: Counter,
) -> None:
    for i in range(start_idx, start_idx + count):
        ok, status = await send_one(client, i)
        if ok:
            results["success"] += 1
        else:
            results["failure"] += 1
            if status is not None:
                results[f"status_{status}"] += 1
            else:
                results["status_exception"] += 1


async def main(total_requests: int = 5000, concurrency: int = 50) -> None:
    results: Counter = Counter()
    per_worker = total_requests // concurrency
    reminder = total_requests % concurrency

    limits = httpx.Limits(
        max_connections=concurrency, max_keepalive_connections=concurrency
    )

    start = time.perf_counter()

    async with httpx.AsyncClient(
        base_url=BASE_URL,
        timeout=10.0,
        limits=limits,
    ) as client:
        tasks = []
        next_idx = 10

        for n in range(concurrency):
            count = per_worker + (1 if n < reminder else 0)
            tasks.append(asyncio.create_task(worker(client, next_idx, count, results)))
            next_idx += count

        elapsed = time.perf_counter() - start
        rps = total_requests / elapsed if elapsed > 0 else 0.0

        print(f"Total requests: {total_requests}")
        print(f"Concurrency:    {concurrency}")
        print(f"Elapsed:        {elapsed: 2f}s")
        print(f"Requests/sec:   {rps: 2f}")
        print(f"Success:        {results['success']}")
        print(f"Failure:        {results['failure']}")

        for key in sorted(results):
            if key.startswith("status_"):
                print(f"{key}: {results[key]}")


if __name__ == "__main__":
    asyncio.run(main())

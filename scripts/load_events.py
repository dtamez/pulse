import argparse
import asyncio
import random
import time
from collections import Counter
from datetime import datetime, timezone

import httpx

EVENT_TYPES = ["api_call", "purchase", "job_started", "job_completed", "job_failed"]
ENDPOINTS = ["/search", "/create_invoice", "/login", "/checkout", "/reports/daily"]


def make_event(i: int) -> dict:
    event_type = random.choices(EVENT_TYPES, weights=[70, 10, 8, 8, 4], k=1)[0]
    payload = {
        "endpoint": random.choice(ENDPOINTS),
        "status": random.choices(
            [200, 201, 400, 404, 500], weights=[70, 10, 8, 5, 7], k=1
        )[0],
        "latency_ms": random.randint(20, 1200),
        "request_id": f"req_{i}",
    }
    if event_type == "purchase":
        payload["amount"] = round(random.uniform(5, 500), 2)
        payload["currency"] = "USD"

    return {
        "event_type": event_type,
        "entity_id": f"user_{random.randint(1, 5000)}",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }


async def send_one(
    client: httpx.AsyncClient, api_key: str, i: int
) -> tuple[bool, int | str | None]:
    try:
        resp = await client.post(
            "/events",
            headers={"X-API-Key": api_key},
            json=make_event(i),
        )
        return resp.status_code == 200, resp.status_code
    except Exception as exc:
        return False, type(exc).__name__


async def worker(
    client: httpx.AsyncClient,
    api_key: str,
    start_idx: int,
    count: int,
    results: Counter,
) -> None:
    for i in range(start_idx, start_idx + count):
        ok, status = await send_one(client, api_key, i)
        if ok:
            results["success"] += 1
        else:
            results["failure"] += 1
            if status is None:
                results["status_unknown"] += 1
            elif isinstance(status, int):
                results[f"status_{status}"] += 1
            else:
                results[f"exc_{status}"] += 1


async def run_load(
    base_url: str, api_key: str, total_requests: int, concurrency: int
) -> None:
    results: Counter = Counter()
    per_worker = total_requests // concurrency
    remainder = total_requests % concurrency

    limits = httpx.Limits(
        max_connections=concurrency,
        max_keepalive_connections=concurrency,
    )

    start = time.perf_counter()

    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=30.0,
        limits=limits,
    ) as client:
        tasks = []
        next_idx = 0

        for n in range(concurrency):
            count = per_worker + (1 if n < remainder else 0)
            tasks.append(
                asyncio.create_task(worker(client, api_key, next_idx, count, results))
            )
            next_idx += count

        await asyncio.gather(*tasks)

    elapsed = time.perf_counter() - start
    rps = total_requests / elapsed if elapsed else 0.0

    print(f"Base URL:          {base_url}")
    print(f"Total requests:    {total_requests}")
    print(f"Concurrency:       {concurrency}")
    print(f"Elapsed:           {elapsed:.2f}s")
    print(f"Requests/sec:      {rps:.2f}")
    print(f"Success:           {results['success']}")
    print(f"Failure:           {results['failure']}")
    for k, v in results.items():
        if k.startswith("status_"):
            print(f"{k}:               {v}")

    for k, v in results.items():
        if k.startswith("exc"):
            print(f"{k}:               {v}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--requests", type=int, default=5000)
    parser.add_argument("--concurrency", type=int, default=50)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(
        run_load(
            base_url=args.base_url,
            api_key=args.api_key,
            total_requests=args.requests,
            concurrency=args.concurrency,
        )
    )

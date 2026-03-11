import argparse
import asyncio
import random
import time
from collections import Counter
from datetime import datetime, timezone

import httpx

EVENT_TYPES = ["api_call", "purchase", "job_started", "job_completed", "job_failed"]
ENDPOINTS = ["/search", "/create_invoice", "/login", "/checkout", "/reports/daily"]
TENANT_KEYS = [
    "pulse_0c2e60c347e68f71a695121afd114775",  # wacky
    "pulse_81d76a4f0e3abb833934b50c1ece425c",  # quirky
    "pulse_50fbe81732d7d76d96ff0be129d144cc",  # silly
    "pulse_9ecd384e7b569738f60b2c8f11625ce6",  # cheesy
    "pulse_d39e764c7e37e5575eb2fdaface6787a",  # merry
    "pulse_f704654d11d7366f59baf04dc5a507dc",  # loony
    "pulse_efdb3de44a11f9b7da52f2e3ff22747c",  # zany
    "pulse_98fdadfb6ece433069825756a2932c19",  # giggle
    "pulse_daba081aaea1c17a0e216b2c881c99f2",  # doodle
    "pulse_8e5c310713865b499bb6d44bcd86ff5a",  # smiley
    "pulse_cdf58e62445c7ba94415bcd2130f3d23",  # happy
    "pulse_62abb931c8e199a459f1a832b7f638c3",  # bubbly
    "pulse_aea658ad58c8b3383097a367b6c06340",  # jolly
    "pulse_d074cc6a6edcbaf432f35b9d3ce37be8",  # bouncing
    "pulse_dfcfe1a687c9d8ed74eda923a7259004",  # whimsical
    "pulse_8cbecd37c08975266aa3d3c1688a3a6f",  # funky
    "pulse_e09bd3ae9b55d4fb3920044eeebf3198",  # cozy
    "pulse_32976d83a8ee0b8542f75799020f18ce",  # sunshine
    "pulse_3916d3f046b16daf4735a76b3559e2c0",  # nutty
    "pulse_fda7c479e48391423e2ab67d068f33ad",  # playful
]


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
    start_idx: int,
    count: int,
    results: Counter,
) -> None:
    for i in range(start_idx, start_idx + count):
        api_key = random.choices(
            TENANT_KEYS,
            weights=[5, 5, 5, 20, 2, 10, 3, 35, 3, 4, 2, 35, 7, 3, 4, 3, 5, 6, 2, 4],
            k=1,
        )[0]
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


async def run_load(base_url: str, total_requests: int, concurrency: int) -> None:
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
        timeout=60.0,
        limits=limits,
    ) as client:
        tasks = []
        next_idx = 0

        for n in range(concurrency):
            count = per_worker + (1 if n < remainder else 0)
            tasks.append(asyncio.create_task(worker(client, next_idx, count, results)))
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
    parser.add_argument("--requests", type=int, default=5000)
    parser.add_argument("--concurrency", type=int, default=50)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(
        run_load(
            base_url=args.base_url,
            total_requests=args.requests,
            concurrency=args.concurrency,
        )
    )

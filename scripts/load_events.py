import argparse
import asyncio
import csv
import random
import statistics
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

EVENT_TYPES = ["api_call", "purchase", "job_started", "job_completed", "job_failed"]
EVENT_TYPE_WEIGHTS = [70, 10, 8, 8, 4]

ENDPOINTS = ["/search", "/create_invoice", "/login", "/checkout", "/reports/daily"]

TENANT_KEYS = [
    "pulse_1426de9b73afbdf90d04e44ce2705430",  # "bouncing"
    "pulse_f63b083771115c31a732a03b960e307c",  # "bubbly"
    "pulse_edf51a11433b7f19533f80a3f7f613b7",  # "cheesy"
    "pulse_ea4be70d0666c32a755f3dfdb3d42948",  # "cozy"
    "pulse_3b275c64160c497fec6b73d68a5a05e3",  # "doodle"
    "pulse_bd17df91b1f7eb0a7a1b005dd6d2654c",  # "funky"
    "pulse_ca99a698c651aa515321639f8a628e7c",  # "giggle"
    "pulse_6bc049fa18a9abf7ef41e03bb59bcbdb",  # "happy"
    "pulse_3b7e74a3bd8ddbd9c94f52234e3e5a59",  # "jolly"
    "pulse_0c31317a79b40085458ab628f0f7d10c",  # "loony"
    "pulse_de3b020c2ad526cd39d2d3d716d4265d",  # "merry"
    "pulse_4054c261a5c864be50efb928f763ff96",  # "nutty"
    "pulse_1ac86d7a6b7e9dda383fe91f834c05f4",  # "playful"
    "pulse_f32801caafd5c478b7915e73ee257554",  # "quirky"
    "pulse_c8a2917671a037097496a06c74b6fd16",  # "silly"
    "pulse_587020937403dfbbc71dc351122fe795",  # "smiley"
    "pulse_d2287aa83dfd50e1a727ee0a384495f2",  # "sunshine"
    "pulse_54ba295f18ed220a9f6cedfcfbf4724a",  # "wacky"
    "pulse_40553c1e3b0e0f7ac1926ee264454054",  # "whimsical"
    "pulse_9bc183f33fb115d60fe0a5b20634019c",  # "zany"
]


TENANT_WEIGHTS = [5, 5, 5, 20, 2, 10, 3, 35, 3, 4, 2, 35, 7, 3, 4, 3, 5, 6, 2, 4]


def make_event(i: int, rng: random.Random) -> dict[str, Any]:
    event_type = rng.choices(EVENT_TYPES, weights=EVENT_TYPE_WEIGHTS, k=1)[0]
    payload: dict[str, Any] = {
        "endpoint": rng.choice(ENDPOINTS),
        "status": rng.choices(
            [200, 201, 400, 404, 500], weights=[70, 10, 8, 5, 7], k=1
        )[0],
        "latency_ms": rng.randint(20, 1200),
        "request_id": f"req_{i}",
    }
    if event_type == "purchase":
        payload["amount"] = round(rng.uniform(5, 500), 2)
        payload["currency"] = "USD"

    return {
        "event_type": event_type,
        "entity_id": f"user_{rng.randint(1, 5000)}",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }


def percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (len(sorted_values) - 1) * p
    lo = int(rank)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = rank - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def pick_tenant(
    rng: random.Random,
    tenant_mode: str,
    hot_tenant: str | None,
    request_index: int,
) -> str:
    if tenant_mode == "uniform":
        return TENANT_KEYS[request_index % len(TENANT_KEYS)]
    if tenant_mode == "weighted":
        return rng.choices(TENANT_KEYS, weights=TENANT_WEIGHTS, k=1)[0]
    if tenant_mode == "single-hot":
        return hot_tenant or TENANT_KEYS[0]
    raise ValueError(f"Unsupported tenant_mode: {tenant_mode}")


async def send_one(
    client: httpx.AsyncClient,
    api_key: str,
    i: int,
    rng: random.Random,
) -> tuple[bool, int | str, float, str | None]:
    started = time.perf_counter()
    try:
        resp = await client.post(
            "/events",
            headers={"X-API-Key": api_key},
            json=make_event(i, rng),
        )
        elapsed_ms = (time.perf_counter() - started) * 1000

        error_detail = None
        if resp.status_code != 200:
            try:
                error_detail = resp.text
            except Exception:
                error_detail = "<unable to read response body>"

        return resp.status_code == 200, resp.status_code, elapsed_ms, error_detail
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        return False, type(exc).__name__, elapsed_ms, str(exc)


async def worker(
    client: httpx.AsyncClient,
    worker_id: int,
    start_idx: int,
    count: int,
    tenant_mode: str,
    hot_tenant: str | None,
    seed: int,
) -> dict[str, Any]:
    rng = random.Random(seed + worker_id)
    stats: Counter[str] = Counter()
    latencies_ms: list[float] = []
    sample_errors: list[str] = []

    for i in range(start_idx, start_idx + count):
        api_key = pick_tenant(
            rng=rng,
            tenant_mode=tenant_mode,
            hot_tenant=hot_tenant,
            request_index=i,
        )

        ok, status, elapsed_ms, error_detail = await send_one(client, api_key, i, rng)
        latencies_ms.append(elapsed_ms)

        stats["success" if ok else "failure"] += 1
        stats[f"tenant::{api_key}"] += 1

        if isinstance(status, int):
            stats[f"status::{status}"] += 1
            if not ok and error_detail and len(sample_errors) < 5:
                sample_errors.append(
                    f"request={i} tenant={api_key} status={status} body={error_detail}"
                )
        else:
            stats[f"exc::{status}"] += 1
            if error_detail and len(sample_errors) < 5:
                sample_errors.append(
                    f"request={i} tenant={api_key} exception={status} detail={error_detail}"
                )

    return {
        "stats": stats,
        "latencies_ms": latencies_ms,
        "sample_errors": sample_errors,
    }


def merge_worker_results(
    worker_results: list[dict[str, Any]],
) -> tuple[Counter[str], list[float], list[str]]:
    merged: Counter[str] = Counter()
    latencies_ms: list[float] = []
    sample_errors: list[str] = []

    for result in worker_results:
        merged.update(result["stats"])
        latencies_ms.extend(result["latencies_ms"])
        sample_errors.extend(result["sample_errors"])

    return merged, latencies_ms, sample_errors[:10]


def summarize_latencies(latencies_ms: list[float]) -> dict[str, float]:
    if not latencies_ms:
        return {
            "min_ms": 0.0,
            "avg_ms": 0.0,
            "p50_ms": 0.0,
            "p95_ms": 0.0,
            "p99_ms": 0.0,
            "max_ms": 0.0,
        }

    sorted_latencies = sorted(latencies_ms)
    return {
        "min_ms": sorted_latencies[0],
        "avg_ms": statistics.fmean(sorted_latencies),
        "p50_ms": percentile(sorted_latencies, 0.50),
        "p95_ms": percentile(sorted_latencies, 0.95),
        "p99_ms": percentile(sorted_latencies, 0.99),
        "max_ms": sorted_latencies[-1],
    }


def print_top_counts(stats: Counter[str], prefix: str, top_n: int) -> None:
    items = [(k, v) for k, v in stats.items() if k.startswith(prefix)]
    items.sort(key=lambda kv: (-kv[1], kv[0]))

    for key, value in items[:top_n]:
        label = key.split("::", 1)[1]
        print(f"{prefix[:-2]:<18} {label:<40} {value}")


def write_csv_row(
    csv_path: str,
    *,
    base_url: str,
    total_requests: int,
    concurrency: int,
    tenant_mode: str,
    elapsed_s: float,
    rps: float,
    success: int,
    failure: int,
    latency: dict[str, float],
) -> None:
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    row = {
        "base_url": base_url,
        "requests": total_requests,
        "concurrency": concurrency,
        "tenant_mode": tenant_mode,
        "elapsed_s": f"{elapsed_s:.4f}",
        "requests_per_sec": f"{rps:.4f}",
        "success": success,
        "failure": failure,
        "min_ms": f"{latency['min_ms']:.2f}",
        "avg_ms": f"{latency['avg_ms']:.2f}",
        "p50_ms": f"{latency['p50_ms']:.2f}",
        "p95_ms": f"{latency['p95_ms']:.2f}",
        "p99_ms": f"{latency['p99_ms']:.2f}",
        "max_ms": f"{latency['max_ms']:.2f}",
    }

    write_header = not path.exists()

    with path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(row)


async def run_load(
    base_url: str,
    total_requests: int,
    concurrency: int,
    tenant_mode: str,
    hot_tenant: str | None,
    seed: int,
    connect_timeout: float,
    read_timeout: float,
    write_timeout: float,
    pool_timeout: float,
    top_n: int,
    csv_path: str | None,
) -> None:
    per_worker = total_requests // concurrency
    remainder = total_requests % concurrency

    limits = httpx.Limits(
        max_connections=concurrency,
        max_keepalive_connections=concurrency,
    )
    timeout = httpx.Timeout(
        connect=connect_timeout,
        read=read_timeout,
        write=write_timeout,
        pool=pool_timeout,
    )

    started = time.perf_counter()

    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=timeout,
        limits=limits,
    ) as client:
        tasks = []
        next_idx = 0

        for worker_id in range(concurrency):
            count = per_worker + (1 if worker_id < remainder else 0)
            tasks.append(
                asyncio.create_task(
                    worker(
                        client=client,
                        worker_id=worker_id,
                        start_idx=next_idx,
                        count=count,
                        tenant_mode=tenant_mode,
                        hot_tenant=hot_tenant,
                        seed=seed,
                    )
                )
            )
            next_idx += count

        worker_results = await asyncio.gather(*tasks)

    elapsed_s = time.perf_counter() - started
    stats, latencies_ms, sample_errors = merge_worker_results(worker_results)
    latency = summarize_latencies(latencies_ms)
    success = stats["success"]
    failure = stats["failure"]
    rps = total_requests / elapsed_s if elapsed_s else 0.0

    print(f"Base URL:           {base_url}")
    print(f"Total requests:     {total_requests}")
    print(f"Concurrency:        {concurrency}")
    print(f"Tenant mode:        {tenant_mode}")
    if tenant_mode == "single-hot":
        print(f"Hot tenant:         {hot_tenant or TENANT_KEYS[0]}")
    print(f"Elapsed:            {elapsed_s:.2f}s")
    print(f"Requests/sec:       {rps:.2f}")
    print(f"Success:            {success}")
    print(f"Failure:            {failure}")
    print()

    print("Latency summary")
    print(f"  min:              {latency['min_ms']:.2f} ms")
    print(f"  avg:              {latency['avg_ms']:.2f} ms")
    print(f"  p50:              {latency['p50_ms']:.2f} ms")
    print(f"  p95:              {latency['p95_ms']:.2f} ms")
    print(f"  p99:              {latency['p99_ms']:.2f} ms")
    print(f"  max:              {latency['max_ms']:.2f} ms")
    print()

    if sample_errors:
        print()
        print("Sample errors")
        for err in sample_errors:
            print(f"  {err}")

    print("Top status counts")
    print_top_counts(stats, "status::", top_n)
    print()

    print("Top exception counts")
    print_top_counts(stats, "exc::", top_n)
    print()

    print("Top tenant counts")
    print_top_counts(stats, "tenant::", top_n)

    if csv_path:
        write_csv_row(
            csv_path,
            base_url=base_url,
            total_requests=total_requests,
            concurrency=concurrency,
            tenant_mode=tenant_mode,
            elapsed_s=elapsed_s,
            rps=rps,
            success=success,
            failure=failure,
            latency=latency,
        )
        print()
        print(f"Saved summary row to {csv_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--requests", type=int, default=5000)
    parser.add_argument("--concurrency", type=int, default=50)

    parser.add_argument(
        "--tenant-mode",
        choices=["uniform", "weighted", "single-hot"],
        default="weighted",
    )
    parser.add_argument("--hot-tenant", default=None)
    parser.add_argument("--seed", type=int, default=42)

    parser.add_argument("--connect-timeout", type=float, default=5.0)
    parser.add_argument("--read-timeout", type=float, default=30.0)
    parser.add_argument("--write-timeout", type=float, default=30.0)
    parser.add_argument("--pool-timeout", type=float, default=30.0)

    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--csv", default=None)

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(
        run_load(
            base_url=args.base_url,
            total_requests=args.requests,
            concurrency=args.concurrency,
            tenant_mode=args.tenant_mode,
            hot_tenant=args.hot_tenant,
            seed=args.seed,
            connect_timeout=args.connect_timeout,
            read_timeout=args.read_timeout,
            write_timeout=args.write_timeout,
            pool_timeout=args.pool_timeout,
            top_n=args.top_n,
            csv_path=args.csv,
        )
    )

import argparse
import time
from time import perf_counter

import httpx


def check_num_processed_in_tenant_summary(
    base_url: str, api_key: str, tenant_id: str, num_expected: int
):
    t0 = perf_counter()
    client = httpx.Client(base_url=base_url)
    num_collected: int = 0
    while num_collected < num_expected:
        resp = client.get(
            f"/tenant/{tenant_id}/summary", headers={"X-API-Key": api_key}
        )

        counts = resp.json()["counts_by_event_type"]
        num_collected = sum([d["count"] for d in counts])
        print(num_collected)
        time.sleep(1)

    t1 = perf_counter()
    print(f"elapsed time: {t1 - t0}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--num-expected", required=True, type=int)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    check_num_processed_in_tenant_summary(
        base_url=args.base_url,
        api_key=args.api_key,
        tenant_id=args.tenant_id,
        num_expected=args.num_expected,
    )

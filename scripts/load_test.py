import argparse
import asyncio
import os
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
import httpx


async def fire_batch(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    payload: list[dict]
) -> tuple[float, int, int, bool]:
    """Sends one batch and returns (latency_ms, accepted, rejected, is_success)"""
    t0 = time.perf_counter()
    try:
        resp = await client.post(url, json=payload, headers=headers, timeout=15.0)
        latency = (time.perf_counter() - t0) * 1000.0
        if resp.status_code in (200, 207):
            data = resp.json()
            return latency, data.get("accepted", len(payload)), data.get("rejected", 0), True
        return latency, 0, len(payload), False
    except Exception:
        latency = (time.perf_counter() - t0) * 1000.0
        return latency, 0, len(payload), False


async def run_burst_test(
    base_url: str,
    api_key: str,
    total_readings: int = 10000,
    batch_size: int = 200,
    concurrency: int = 50
):
    num_batches = total_readings // batch_size
    url = f"{base_url.rstrip('/')}/api/v1/readings/batch"
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    print(f"Preparing {total_readings:,} readings in {num_batches} batches of {batch_size}...")

    # Pre-generate payloads in memory so network generation has zero serialization delay
    batches = []
    base_ts = datetime.now(timezone.utc).isoformat()
    for b_idx in range(num_batches):
        batch = [
            {
                "sensorId": f"sensor-{i % 50:03d}",
                "type": "temperature" if (i % 2 == 0) else "occupancy",
                "value": round(20.0 + (i % 15) * 0.5, 2),
                "timestamp": base_ts
            }
            for i in range(batch_size)
        ]
        batches.append(batch)

    print(f"Blasting {num_batches} batches concurrently (Target: 10,000 readings burst)...")

    latencies: list[float] = []
    total_accepted = 0
    total_rejected = 0
    failed_requests = 0

    limits = httpx.Limits(max_connections=concurrency + 10, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(limits=limits) as client:
        t_start = time.perf_counter()

        # Fire all batches concurrently using asyncio.gather
        tasks = [fire_batch(client, url, headers, b) for b in batches]
        results = await asyncio.gather(*tasks)

        t_end = time.perf_counter()

    burst_duration = t_end - t_start

    for lat, acc, rej, ok in results:
        latencies.append(lat)
        total_accepted += acc
        total_rejected += rej
        if not ok:
            failed_requests += 1

    # Calculate statistics
    latencies.sort()
    n = len(latencies)
    p50 = statistics.median(latencies) if n else 0
    p95 = latencies[int(n * 0.95)] if n else 0
    p99 = latencies[int(n * 0.99)] if n else 0
    max_lat = max(latencies) if n else 0
    throughput = total_accepted / burst_duration if burst_duration > 0 else 0

    # Print Load-Test Report Table matching SDD Section 11 template
    print("\n" + "=" * 60)
    print("CAMPUSPULSE LOAD-TEST REPORT")
    print("=" * 60)
    print(f"{'Metric':<20} | {'Record in report'}")
    print("-" * 60)
    print(f"{'Environment':<20} | OS: {platform.system()} {platform.release()}, Python: {sys.version.split()[0]}, CPU: {os.cpu_count()} cores")
    print(f"{'Traffic profile':<20} | {total_readings:,} readings, batch_size={batch_size}, concurrency={concurrency}")
    print(f"{'Duration':<20} | {burst_duration:.3f} seconds")
    print(f"{'Throughput':<20} | {throughput:,.1f} accepted readings/sec")
    print(f"{'Latency':<20} | p50: {p50:.1f}ms, p95: {p95:.1f}ms, p99: {p99:.1f}ms, max: {max_lat:.1f}ms")
    print(f"{'Errors':<20} | HTTP failures: {failed_requests}, Rejected readings: {total_rejected}")
    target_met = "YES (PASS)" if total_accepted >= total_readings and burst_duration <= 2.0 else "PARTIAL/ANALYSIS"
    print(f"{'Conclusion':<20} | Target Met: {target_met}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="CampusPulse 10,000 Burst Load Test")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Base API URL")
    parser.add_argument("--api-key", default="cp_gateway_test_key_12345", help="Sensor API Key")
    parser.add_argument("--readings", type=int, default=10000, help="Total readings (default 10,000)")
    parser.add_argument("--batch-size", type=int, default=200, help="Readings per batch (default 200)")
    parser.add_argument("--concurrency", type=int, default=50, help="Concurrent workers")

    args = parser.parse_args()
    asyncio.run(
        run_burst_test(
            base_url=args.url,
            api_key=args.api_key,
            total_readings=args.readings,
            batch_size=args.batch_size,
            concurrency=args.concurrency
        )
    )


if __name__ == "__main__":
    main()

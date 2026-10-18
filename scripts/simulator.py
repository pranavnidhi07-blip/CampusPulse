import argparse
import asyncio
import random
import time
from datetime import datetime, timezone
import httpx


def generate_reading(
    sensor_id: str,
    metric_type: str,
    base_val: float,
    spike: bool
) -> dict:
    noise = random.uniform(-0.5, 0.5)
    val = base_val + (random.uniform(5.0, 15.0) if spike else noise)
    return {
        "sensorId": sensor_id,
        "type": metric_type,
        "value": round(val, 2),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


async def send_batch(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    batch: list[dict]
) -> tuple[int, int, int]:
    """Returns (accepted, rejected, failed_requests)"""
    try:
        resp = await client.post(url, json=batch, headers=headers, timeout=10.0)
        if resp.status_code in (200, 207):
            data = resp.json()
            return data.get("accepted", len(batch)), data.get("rejected", 0), 0
        else:
            return 0, len(batch), 1
    except Exception:
        return 0, len(batch), 1


async def run_simulator(
    base_url: str,
    api_key: str,
    sensors_count: int,
    batch_size: int,
    total_readings: int,
    spike_rate: float,
    seed: int
):
    random.seed(seed)
    url = f"{base_url.rstrip('/')}/api/v1/readings/batch"
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    sensor_ids = [f"sensor-{i:03d}" for i in range(1, sensors_count + 1)]
    # Always include the library sensor to hit the seeded rule
    sensor_ids[0] = "library-floor-2"

    metrics = [
        ("temperature", 22.0),
        ("air_quality", 45.0),
        ("occupancy", 15.0)
    ]

    print(f"=== Starting CampusPulse Sensor Simulator ===")
    print(f"Target URL: {url}")
    print(f"Sensors: {sensors_count} | Batch size: {batch_size} | Total readings: {total_readings}")
    print(f"Spike probability: {spike_rate:.1%} | Random Seed: {seed}")

    start_time = time.perf_counter()
    total_generated = 0
    total_accepted = 0
    total_rejected = 0
    total_failed_reqs = 0

    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=50, max_keepalive_connections=20)) as client:
        tasks = []
        current_batch = []

        while total_generated < total_readings:
            s_id = random.choice(sensor_ids)
            m_type, base_v = random.choice(metrics)
            is_spike = random.random() < spike_rate
            
            # If library sensor and spike, trigger the >32 threshold rule
            if s_id == "library-floor-2" and m_type == "temperature" and is_spike:
                base_v = 30.0

            reading = generate_reading(s_id, m_type, base_v, is_spike)
            current_batch.append(reading)
            total_generated += 1

            if len(current_batch) >= batch_size or total_generated >= total_readings:
                tasks.append(send_batch(client, url, headers, list(current_batch)))
                current_batch = []

                if len(tasks) >= 20:
                    results = await asyncio.gather(*tasks)
                    for acc, rej, fail in results:
                        total_accepted += acc
                        total_rejected += rej
                        total_failed_reqs += fail
                    tasks = []

        if tasks:
            results = await asyncio.gather(*tasks)
            for acc, rej, fail in results:
                total_accepted += acc
                total_rejected += rej
                total_failed_reqs += fail

    duration = time.perf_counter() - start_time
    rate = total_accepted / duration if duration > 0 else 0

    print(f"\n=== Simulation Results ===")
    print(f"Total Generated:  {total_generated}")
    print(f"Total Accepted:   {total_accepted}")
    print(f"Total Rejected:   {total_rejected}")
    print(f"Failed Requests:  {total_failed_reqs}")
    print(f"Duration:         {duration:.3f} seconds")
    print(f"Throughput:       {rate:.1f} readings/sec")


def main():
    parser = argparse.ArgumentParser(description="CampusPulse Sensor Simulator")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Base API URL")
    parser.add_argument("--api-key", default="cp_gateway_test_key_12345", help="Sensor API Key")
    parser.add_argument("--sensors", type=int, default=20, help="Number of sensors")
    parser.add_argument("--batch-size", type=int, default=100, help="Readings per batch")
    parser.add_argument("--total", type=int, default=1000, help="Total readings to send")
    parser.add_argument("--spike-rate", type=float, default=0.05, help="Anomaly spike probability (0.0 to 1.0)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for repeatability")

    args = parser.parse_args()
    asyncio.run(
        run_simulator(
            base_url=args.url,
            api_key=args.api_key,
            sensors_count=args.sensors,
            batch_size=args.batch_size,
            total_readings=args.total,
            spike_rate=args.spike_rate,
            seed=args.seed
        )
    )


if __name__ == "__main__":
    main()

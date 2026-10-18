import pytest
from datetime import datetime, timezone
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_single_reading_ingestion(client: AsyncClient, sensor_api_key: str):
    payload = {
        "sensorId": "library-floor-2",
        "type": "temperature",
        "value": 34.5,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    resp = await client.post(
        "/api/v1/readings",
        json=payload,
        headers={"X-API-Key": sensor_api_key}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["sensor_id"] == "library-floor-2"
    assert data["numeric_value"] == 34.5
    assert data["metric_type"] == "temperature"


@pytest.mark.asyncio
async def test_single_reading_idempotency(client: AsyncClient, sensor_api_key: str):
    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "sensorId": "lab-01",
        "type": "temperature",
        "value": 25.0,
        "timestamp": now_iso,
        "idempotencyKey": "idem-key-001"
    }
    # First submit
    resp1 = await client.post("/api/v1/readings", json=payload, headers={"X-API-Key": sensor_api_key})
    assert resp1.status_code == 201
    r1 = resp1.json()

    # Second submit with same idempotencyKey
    resp2 = await client.post("/api/v1/readings", json=payload, headers={"X-API-Key": sensor_api_key})
    assert resp2.status_code == 201
    r2 = resp2.json()

    # Must return same reading ID
    assert r1["id"] == r2["id"]


@pytest.mark.asyncio
async def test_batch_ingestion_with_partial_validation_errors(client: AsyncClient, sensor_api_key: str):
    now_iso = datetime.now(timezone.utc).isoformat()
    batch_payload = [
        # Valid item 1
        {
            "sensorId": "sensor-1",
            "type": "temperature",
            "value": 22.0,
            "timestamp": now_iso
        },
        # Invalid item 2: Unsupported metric type
        {
            "sensorId": "sensor-2",
            "type": "unsupported_metric_xyz",
            "value": 10.0,
            "timestamp": now_iso
        },
        # Valid item 3
        {
            "sensorId": "sensor-3",
            "type": "air_quality",
            "value": 45.0,
            "timestamp": now_iso
        },
        # Invalid item 4: NaN value
        {
            "sensorId": "sensor-4",
            "type": "temperature",
            "value": "invalid_number",
            "timestamp": now_iso
        }
    ]

    resp = await client.post(
        "/api/v1/readings/batch",
        json=batch_payload,
        headers={"X-API-Key": sensor_api_key}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 4
    assert data["accepted"] == 2
    assert data["rejected"] == 2
    assert len(data["errors"]) == 2
    # Errors list must contain indices 1 and 3
    err_indices = [e["index"] for e in data["errors"]]
    assert 1 in err_indices
    assert 3 in err_indices


@pytest.mark.asyncio
async def test_query_readings_by_organizer(client: AsyncClient, sensor_api_key: str, organizer_token: str):
    now_iso = datetime.now(timezone.utc).isoformat()
    # Ingest reading
    await client.post(
        "/api/v1/readings",
        json={"sensorId": "query-sensor-1", "type": "co2", "value": 400.0, "timestamp": now_iso},
        headers={"X-API-Key": sensor_api_key}
    )

    # Query readings as organizer
    resp = await client.get(
        "/api/v1/readings?sensor_id=query-sensor-1",
        headers={"Authorization": f"Bearer {organizer_token}"}
    )
    assert resp.status_code == 200
    readings = resp.json()
    assert len(readings) >= 1
    assert readings[0]["sensor_id"] == "query-sensor-1"

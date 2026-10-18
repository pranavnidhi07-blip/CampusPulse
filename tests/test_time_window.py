import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_time_window_average_rule(
    client: AsyncClient,
    organizer_token: str,
    sensor_api_key: str
):
    auth_header = {"Authorization": f"Bearer {organizer_token}"}
    sensor_header = {"X-API-Key": sensor_api_key}

    # Create window rule: average temperature > 30.0 over 600s
    await client.post(
        "/api/v1/rules",
        json={
            "name": "Library ten-minute average",
            "metricType": "temperature",
            "scope": {"sensorIds": ["library-floor-2"]},
            "condition": {
                "kind": "window",
                "aggregation": "avg",
                "windowSeconds": 600,
                "operator": ">",
                "value": 30.0
            },
            "severity": "high",
            "enabled": True
        },
        headers=auth_header
    )

    now = datetime.now(timezone.utc)

    # Reading 1: 28.0 at T-60s -> Average is 28.0 (<= 30.0) -> No alert
    await client.post(
        "/api/v1/readings",
        json={
            "sensorId": "library-floor-2",
            "type": "temperature",
            "value": 28.0,
            "timestamp": (now - timedelta(seconds=60)).isoformat()
        },
        headers=sensor_header
    )
    res1 = await client.get("/api/v1/alerts", headers=auth_header)
    assert len(res1.json()) == 0

    # Reading 2: 34.0 at T -> Average is (28.0 + 34.0) / 2 = 31.0 (> 30.0) -> Triggers Alert!
    await client.post(
        "/api/v1/readings",
        json={
            "sensorId": "library-floor-2",
            "type": "temperature",
            "value": 34.0,
            "timestamp": now.isoformat()
        },
        headers=sensor_header
    )
    res2 = await client.get("/api/v1/alerts", headers=auth_header)
    alerts = res2.json()
    assert len(alerts) == 1
    assert alerts[0]["status"] == "open"
    assert alerts[0]["observed_value"] == 31.0

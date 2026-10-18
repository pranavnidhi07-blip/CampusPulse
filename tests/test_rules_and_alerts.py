import pytest
from datetime import datetime, timezone
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_rule_crud_and_lifecycle(client: AsyncClient, organizer_token: str):
    auth_header = {"Authorization": f"Bearer {organizer_token}"}

    # 1. Create rule
    create_payload = {
        "name": "Library high temperature",
        "metricType": "temperature",
        "scope": {"sensorIds": ["library-floor-2"]},
        "condition": {
            "kind": "threshold",
            "operator": ">",
            "value": 32.0
        },
        "severity": "high",
        "enabled": True
    }
    resp = await client.post("/api/v1/rules", json=create_payload, headers=auth_header)
    assert resp.status_code == 201
    rule = resp.json()
    rule_id = rule["id"]
    assert rule["name"] == "Library high temperature"
    assert rule["enabled"] is True

    # 2. Get rule
    get_resp = await client.get(f"/api/v1/rules/{rule_id}", headers=auth_header)
    assert get_resp.status_code == 200

    # 3. Disable rule
    dis_resp = await client.post(f"/api/v1/rules/{rule_id}/disable", headers=auth_header)
    assert dis_resp.status_code == 200
    assert dis_resp.json()["enabled"] is False

    # 4. Enable rule
    en_resp = await client.post(f"/api/v1/rules/{rule_id}/enable", headers=auth_header)
    assert en_resp.status_code == 200
    assert en_resp.json()["enabled"] is True


@pytest.mark.asyncio
async def test_threshold_alert_generation_and_deduplication(
    client: AsyncClient,
    organizer_token: str,
    sensor_api_key: str
):
    auth_header = {"Authorization": f"Bearer {organizer_token}"}
    sensor_header = {"X-API-Key": sensor_api_key}

    # Create rule: temperature > 32.0 for library-floor-2
    await client.post(
        "/api/v1/rules",
        json={
            "name": "Library heat check",
            "metricType": "temperature",
            "scope": {"sensorIds": ["library-floor-2"]},
            "condition": {"kind": "threshold", "operator": ">", "value": 32.0},
            "severity": "high",
            "enabled": True
        },
        headers=auth_header
    )

    now_iso = datetime.now(timezone.utc).isoformat()

    # Reading 1: 30.0 (below threshold) -> No alert
    await client.post(
        "/api/v1/readings",
        json={"sensorId": "library-floor-2", "type": "temperature", "value": 30.0, "timestamp": now_iso},
        headers=sensor_header
    )
    alerts_resp1 = await client.get("/api/v1/alerts", headers=auth_header)
    assert len(alerts_resp1.json()) == 0

    # Reading 2: 34.5 (above threshold) -> Triggers Alert!
    await client.post(
        "/api/v1/readings",
        json={"sensorId": "library-floor-2", "type": "temperature", "value": 34.5, "timestamp": now_iso},
        headers=sensor_header
    )
    alerts_resp2 = await client.get("/api/v1/alerts", headers=auth_header)
    alerts = alerts_resp2.json()
    assert len(alerts) == 1
    alert = alerts[0]
    alert_id = alert["id"]
    assert alert["status"] == "open"
    assert alert["observed_value"] == 34.5

    # Reading 3: 35.0 (still above threshold) -> Deduplication: should NOT create a new alert row!
    await client.post(
        "/api/v1/readings",
        json={"sensorId": "library-floor-2", "type": "temperature", "value": 35.0, "timestamp": now_iso},
        headers=sensor_header
    )
    alerts_resp3 = await client.get("/api/v1/alerts", headers=auth_header)
    alerts3 = alerts_resp3.json()
    # Still only 1 alert in DB!
    assert len(alerts3) == 1
    assert alerts3[0]["id"] == alert_id
    assert alerts3[0]["observed_value"] == 35.0

    # Acknowledge alert
    ack_resp = await client.post(f"/api/v1/alerts/{alert_id}/acknowledge", headers=auth_header)
    assert ack_resp.status_code == 200
    assert ack_resp.json()["alert"]["status"] == "acknowledged"

    # Reading 4: while acknowledged, still part of same episode -> does not create new alert
    await client.post(
        "/api/v1/readings",
        json={"sensorId": "library-floor-2", "type": "temperature", "value": 36.0, "timestamp": now_iso},
        headers=sensor_header
    )
    alerts_resp4 = await client.get("/api/v1/alerts", headers=auth_header)
    assert len(alerts_resp4.json()) == 1

    # Resolve alert
    res_resp = await client.post(f"/api/v1/alerts/{alert_id}/resolve", headers=auth_header)
    assert res_resp.status_code == 200
    assert res_resp.json()["alert"]["status"] == "resolved"

    # Reading 5: After resolution, a new spike creates a NEW episode alert!
    await client.post(
        "/api/v1/readings",
        json={"sensorId": "library-floor-2", "type": "temperature", "value": 37.0, "timestamp": now_iso},
        headers=sensor_header
    )
    alerts_resp5 = await client.get("/api/v1/alerts", headers=auth_header)
    alerts5 = alerts_resp5.json()
    assert len(alerts5) == 2  # Old resolved alert + New open alert
    open_alerts = [a for a in alerts5 if a["status"] == "open"]
    assert len(open_alerts) == 1
    assert open_alerts[0]["observed_value"] == 37.0

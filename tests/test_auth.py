import pytest
from datetime import datetime, timezone
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_organizer_registration_and_login(client: AsyncClient):
    # Register organizer
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "new-org@campus.edu", "password": "StrongPassword123!"}
    )
    assert reg_resp.status_code == 201
    assert reg_resp.json()["email"] == "new-org@campus.edu"

    # Login with correct password
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "new-org@campus.edu", "password": "StrongPassword123!"}
    )
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()

    # Login with wrong password
    bad_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "new-org@campus.edu", "password": "WrongPassword!"}
    )
    assert bad_login.status_code == 401


@pytest.mark.asyncio
async def test_sensor_client_key_generation_and_access(client: AsyncClient, organizer_token: str):
    # Create sensor client via organizer
    resp = await client.post(
        "/api/v1/auth/sensor-clients",
        json={"name": "hvac-gateway"},
        headers={"Authorization": f"Bearer {organizer_token}"}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "api_key" in data
    api_key = data["api_key"]

    # Submit reading with valid sensor key
    reading_payload = {
        "sensorId": "hvac-01",
        "type": "temperature",
        "value": 24.5,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    reading_resp = await client.post(
        "/api/v1/readings",
        json=reading_payload,
        headers={"X-API-Key": api_key}
    )
    assert reading_resp.status_code == 201

    # Submit reading with invalid sensor key
    bad_reading = await client.post(
        "/api/v1/readings",
        json=reading_payload,
        headers={"X-API-Key": "invalid_key"}
    )
    assert bad_reading.status_code == 401


@pytest.mark.asyncio
async def test_role_enforcement(client: AsyncClient, sensor_api_key: str):
    # Sensor client attempting to access organizer rule management
    resp = await client.get(
        "/api/v1/rules",
        headers={"Authorization": f"Bearer {sensor_api_key}"}
    )
    assert resp.status_code in (401, 403)

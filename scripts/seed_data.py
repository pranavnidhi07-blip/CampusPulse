import asyncio
import hashlib
import os
import sys
from datetime import datetime, timezone
from sqlalchemy import select

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import async_session_maker, init_db
from app.models.auth import Organizer, SensorClient
from app.models.sensor import Sensor
from app.models.rule import AlertRule
from app.services.auth_service import AuthService


async def seed():
    print("Initializing tables...")
    await init_db()

    async with async_session_maker() as session:
        # 1. Organizer
        stmt = select(Organizer).where(Organizer.email == "admin@campus.edu")
        res = await session.execute(stmt)
        organizer = res.scalar_one_or_none()
        if not organizer:
            organizer = Organizer(
                email="admin@campus.edu",
                password_hash=AuthService.hash_password("AdminPass123!"),
                role="organizer",
                is_active=True
            )
            session.add(organizer)
            await session.flush()
            print("Created organizer: admin@campus.edu / AdminPass123!")
        else:
            print("Organizer admin@campus.edu already exists.")

        # 2. Sensor Client
        raw_key = "cp_gateway_test_key_12345"
        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        stmt = select(SensorClient).where(SensorClient.api_key_hash == key_hash)
        res = await session.execute(stmt)
        client = res.scalar_one_or_none()
        if not client:
            client = SensorClient(
                name="gateway-alpha",
                api_key_hash=key_hash,
                is_active=True
            )
            session.add(client)
            await session.flush()
            print(f"Created sensor client 'gateway-alpha' with API key: {raw_key}")
        else:
            print("Sensor client already exists.")

        # 3. Sensors
        sensors_to_add = [
            ("library-floor-2", "Main Library - 2nd Floor Reading Room"),
            ("science-lab-1", "Science Complex - Chemistry Lab 101"),
            ("cafeteria-main", "Student Union - Ground Floor Dining Hall")
        ]
        for key, loc in sensors_to_add:
            s_stmt = select(Sensor).where(Sensor.sensor_key == key)
            s_res = await session.execute(s_stmt)
            if not s_res.scalar_one_or_none():
                sensor = Sensor(sensor_key=key, location=loc, is_active=True)
                session.add(sensor)
                print(f"Created sensor: {key} ({loc})")

        # 4. Rules
        rules_to_add = [
            {
                "name": "Library high temperature",
                "metric_type": "temperature",
                "sensor_scope": {"sensorIds": ["library-floor-2"]},
                "condition_kind": "threshold",
                "operator": ">",
                "threshold_value": 32.0,
                "severity": "high",
                "enabled": True
            },
            {
                "name": "Library ten-minute average",
                "metric_type": "temperature",
                "sensor_scope": {"sensorIds": ["library-floor-2"]},
                "condition_kind": "window",
                "operator": ">",
                "threshold_value": 30.0,
                "window_seconds": 600,
                "aggregation": "avg",
                "severity": "high",
                "enabled": True
            },
            {
                "name": "Campus Air Quality Warning",
                "metric_type": "air_quality",
                "sensor_scope": None,
                "condition_kind": "threshold",
                "operator": ">",
                "threshold_value": 150.0,
                "severity": "critical",
                "enabled": True
            }
        ]

        for r_spec in rules_to_add:
            r_stmt = select(AlertRule).where(AlertRule.name == r_spec["name"])
            r_res = await session.execute(r_stmt)
            if not r_res.scalar_one_or_none():
                rule = AlertRule(
                    name=r_spec["name"],
                    metric_type=r_spec["metric_type"],
                    sensor_scope=r_spec["sensor_scope"],
                    condition_kind=r_spec["condition_kind"],
                    operator=r_spec["operator"],
                    threshold_value=r_spec["threshold_value"],
                    window_seconds=r_spec.get("window_seconds"),
                    aggregation=r_spec.get("aggregation"),
                    severity=r_spec["severity"],
                    enabled=r_spec["enabled"],
                    created_by=organizer.id
                )
                session.add(rule)
                print(f"Created rule: {r_spec['name']}")

        await session.commit()
    print("Database seeding completed successfully.")


if __name__ == "__main__":
    asyncio.run(seed())

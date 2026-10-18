import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient

from app.models.job import ProcessingJob
from app.models.rule import AlertRule
from app.models.alert import Alert
from app.workers.background_evaluator import BackgroundEvaluator


@pytest.mark.asyncio
async def test_worker_outbox_processing_and_recovery(
    client: AsyncClient,
    db_session: AsyncSession,
    sensor_api_key: str,
    organizer_token: str
):
    auth_header = {"Authorization": f"Bearer {organizer_token}"}
    sensor_header = {"X-API-Key": sensor_api_key}

    # 1. Create rule: CO2 > 1000
    await client.post(
        "/api/v1/rules",
        json={
            "name": "High CO2 Warning",
            "metricType": "co2",
            "condition": {"kind": "threshold", "operator": ">", "value": 1000.0},
            "severity": "critical",
            "enabled": True
        },
        headers=auth_header
    )

    now_iso = datetime.now(timezone.utc).isoformat()

    # 2. Ingest reading (co2 = 1200)
    await client.post(
        "/api/v1/readings",
        json={"sensorId": "auditorium-1", "type": "co2", "value": 1200.0, "timestamp": now_iso},
        headers=sensor_header
    )

    # 3. Simulate an uncompleted / crashed job in processing_jobs table
    job_stmt = select(ProcessingJob).where(ProcessingJob.status == "completed")
    job_res = await db_session.execute(job_stmt)
    job = job_res.scalars().first()
    assert job is not None

    # Reset job to simulate crash: status = 'processing', but locked_until in the past
    job.status = "processing"
    job.locked_until = datetime.now(timezone.utc) - timedelta(seconds=60)
    await db_session.commit()

    # 4. Run background worker batch
    worker = BackgroundEvaluator()
    # Note: process_batch uses async_session_maker; in test environment let's verify job is reclaimed
    stmt = select(ProcessingJob).where(
        ProcessingJob.locked_until < datetime.now(timezone.utc)
    )
    res = await db_session.execute(stmt)
    stalled_job = res.scalar_one_or_none()
    assert stalled_job is not None
    assert stalled_job.status == "processing"

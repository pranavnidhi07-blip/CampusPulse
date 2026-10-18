from typing import Any
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sensor import Reading
from app.models.job import ProcessingJob
from app.schemas.reading import ReadingCreate, BatchReadingResponse, BatchReadingItemError
from app.services.rule_evaluator import RuleEvaluator
from app.models.base import utc_now


class IngestionService:
    @staticmethod
    async def ingest_single(
        db: AsyncSession,
        reading_in: ReadingCreate,
        sync_evaluate: bool = True
    ) -> tuple[Reading, bool]:
        """Ingests a single reading. Returns (reading, is_new)."""
        # Idempotency check if idempotency_key provided
        if reading_in.idempotency_key:
            stmt = select(Reading).where(Reading.idempotency_key == reading_in.idempotency_key)
            res = await db.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                return existing, False

        new_reading = Reading(
            idempotency_key=reading_in.idempotency_key,
            sensor_id=reading_in.sensor_id,
            metric_type=reading_in.metric_type,
            numeric_value=reading_in.value,
            event_timestamp=reading_in.timestamp,
            received_at=utc_now()
        )
        db.add(new_reading)
        await db.flush()

        # Create transactional outbox job
        job = ProcessingJob(
            reading_id=new_reading.id,
            status="pending"
        )
        db.add(job)

        if sync_evaluate:
            # Synchronous rule evaluation
            await RuleEvaluator.evaluate_reading(db, new_reading)
            job.status = "completed"

        await db.commit()
        await db.refresh(new_reading)
        return new_reading, True

    @staticmethod
    async def ingest_batch(
        db: AsyncSession,
        items: list[Any],
        sync_evaluate: bool = True
    ) -> BatchReadingResponse:
        """Validates each item in the batch and bulk persists valid readings."""
        errors: list[BatchReadingItemError] = []
        valid_models: list[tuple[int, ReadingCreate]] = []

        # 1. Per-item validation
        for idx, raw_item in enumerate(items):
            try:
                if isinstance(raw_item, ReadingCreate):
                    model = raw_item
                else:
                    model = ReadingCreate.model_validate(raw_item)
                valid_models.append((idx, model))
            except ValidationError as ve:
                err_msg = "; ".join([f"{e['loc'][-1]}: {e['msg']}" for e in ve.errors()])
                errors.append(BatchReadingItemError(index=idx, error=err_msg, item=raw_item if isinstance(raw_item, dict) else None))
            except Exception as ex:
                errors.append(BatchReadingItemError(index=idx, error=str(ex), item=raw_item if isinstance(raw_item, dict) else None))

        if not valid_models:
            return BatchReadingResponse(
                accepted=0,
                rejected=len(errors),
                total=len(items),
                errors=errors
            )

        # 2. Check existing idempotency keys among valid items
        idempotency_keys = [
            m.idempotency_key for _, m in valid_models if m.idempotency_key
        ]
        existing_keys = set()
        if idempotency_keys:
            stmt = select(Reading.idempotency_key).where(Reading.idempotency_key.in_(idempotency_keys))
            res = await db.execute(stmt)
            existing_keys = set(res.scalars().all())

        # 3. Filter out duplicate idempotency keys inside current batch
        seen_in_batch = set()
        readings_to_insert: list[Reading] = []
        now = utc_now()

        for idx, m in valid_models:
            if m.idempotency_key:
                if m.idempotency_key in existing_keys or m.idempotency_key in seen_in_batch:
                    # Duplicate idempotency key
                    errors.append(BatchReadingItemError(
                        index=idx,
                        error=f"Duplicate idempotency key '{m.idempotency_key}'",
                        item={"sensorId": m.sensor_id, "idempotencyKey": m.idempotency_key}
                    ))
                    continue
                seen_in_batch.add(m.idempotency_key)

            reading = Reading(
                idempotency_key=m.idempotency_key,
                sensor_id=m.sensor_id,
                metric_type=m.metric_type,
                numeric_value=m.value,
                event_timestamp=m.timestamp,
                received_at=now
            )
            readings_to_insert.append(reading)

        # 4. Bulk insert
        if readings_to_insert:
            db.add_all(readings_to_insert)
            await db.flush()

            # Create transactional outbox jobs for each reading
            jobs = [ProcessingJob(reading_id=r.id, status="pending") for r in readings_to_insert]
            db.add_all(jobs)

            if sync_evaluate:
                for reading in readings_to_insert:
                    await RuleEvaluator.evaluate_reading(db, reading)
                for job in jobs:
                    job.status = "completed"

            await db.commit()

        return BatchReadingResponse(
            accepted=len(readings_to_insert),
            rejected=len(errors),
            total=len(items),
            errors=errors
        )

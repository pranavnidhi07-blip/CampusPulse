import asyncio
import logging
from datetime import timedelta
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.job import ProcessingJob
from app.models.sensor import Reading
from app.models.base import utc_now
from app.services.rule_evaluator import RuleEvaluator
from app.config import settings

logger = logging.getLogger("campuspulse.worker")


class BackgroundEvaluator:
    def __init__(self):
        self._running = False

    async def process_batch(self, batch_size: int = 100) -> int:
        """Processes a batch of pending or expired processing jobs. Returns count of processed jobs."""
        now = utc_now()
        async with async_session_maker() as session:
            # Reclaim expired locks or pick pending jobs
            # In SQLite / PostgreSQL compatible syntax
            stmt = (
                select(ProcessingJob)
                .where(
                    and_(
                        ProcessingJob.status.in_(["pending", "processing"]),
                        or_(
                            ProcessingJob.locked_until == None,
                            ProcessingJob.locked_until < now
                        ),
                        ProcessingJob.attempts < ProcessingJob.max_attempts
                    )
                )
                .order_by(ProcessingJob.id.asc())
                .limit(batch_size)
            )
            result = await session.execute(stmt)
            jobs = result.scalars().all()

            if not jobs:
                return 0

            # Lock the batch with lease time
            lease_expiration = now + timedelta(seconds=settings.JOB_LOCK_TIMEOUT_SECONDS)
            for job in jobs:
                job.status = "processing"
                job.locked_until = lease_expiration
                job.attempts += 1
            await session.commit()

            processed_count = 0
            for job in jobs:
                try:
                    # Fetch reading
                    reading_stmt = select(Reading).where(Reading.id == job.reading_id)
                    reading_res = await session.execute(reading_stmt)
                    reading = reading_res.scalar_one_or_none()

                    if reading:
                        await RuleEvaluator.evaluate_reading(session, reading)

                    job.status = "completed"
                    job.locked_until = None
                    processed_count += 1
                except Exception as ex:
                    logger.error(f"Error processing job {job.id}: {ex}")
                    job.last_error = str(ex)
                    if job.attempts >= job.max_attempts:
                        job.status = "failed"
                    else:
                        job.status = "pending"
                    job.locked_until = None

            await session.commit()
            return processed_count

    async def run_loop(self):
        self._running = True
        logger.info("BackgroundEvaluator worker started.")
        while self._running:
            try:
                processed = await self.process_batch(settings.WORKER_BATCH_SIZE)
                if processed == 0:
                    await asyncio.sleep(settings.WORKER_POLL_INTERVAL_SECONDS)
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                await asyncio.sleep(1.0)

    def stop(self):
        self._running = False
        logger.info("BackgroundEvaluator worker stopping...")


worker = BackgroundEvaluator()

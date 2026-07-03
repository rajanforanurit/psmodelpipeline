import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.utils.logging_config import get_logger
from app.workers.orchestrator import PipelineOrchestrator

logger = get_logger(__name__)


class PipelineScheduler:
    def __init__(self, orchestrator: PipelineOrchestrator, interval_seconds: int) -> None:
        self._orchestrator = orchestrator
        self._interval_seconds = interval_seconds
        self._scheduler = AsyncIOScheduler()

    def _job_wrapper(self) -> None:
        asyncio.create_task(self._orchestrator.run_once())

    def start(self) -> None:
        self._scheduler.add_job(
            self._job_wrapper,
            trigger=IntervalTrigger(seconds=self._interval_seconds),
            id="drive_sync_job",
            max_instances=1,
            coalesce=True,
            next_run_time=None,
        )
        self._scheduler.start()
        asyncio.create_task(self._orchestrator.run_once())
        logger.info("scheduler_started", interval_seconds=self._interval_seconds)

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")

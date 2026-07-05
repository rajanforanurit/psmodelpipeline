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
        self._running = False

    async def _run_guarded(self) -> None:
        if self._running:
            logger.warning("pipeline_run_skipped_previous_still_running")
            return

        self._running = True
        try:
            await self._orchestrator.run_once()
        except Exception:
            logger.exception("pipeline_run_failed")
        finally:
            self._running = False

    def start(self) -> None:
        self._scheduler.add_job(
            self._run_guarded,
            trigger=IntervalTrigger(seconds=self._interval_seconds),
            id="drive_sync_job",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )

        self._scheduler.start()

        logger.info(
            "scheduler_started",
            interval_seconds=self._interval_seconds,
        )

    async def run_initial_sync(self) -> None:
        await self._run_guarded()

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")

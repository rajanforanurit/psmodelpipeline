import asyncio
import time

from app.drive.change_detector import ChangeDetector
from app.drive.client import GoogleDriveClient
from app.drive.models import DriveFile
from app.models.job import JobResult, JobStatus, JobType, ProcessingJob
from app.utils.logging_config import get_logger
from app.workers.job_queue import FailedJobStore
from app.workers.json_worker import JSONProcessingService
from app.workers.pdf_worker import PDFProcessingService

logger = get_logger(__name__)

_MIME_TO_JOB_TYPE = {
    "application/pdf": JobType.PDF,
    "application/json": JobType.JSON,
}


class PipelineOrchestrator:
    def __init__(
        self,
        drive_client: GoogleDriveClient,
        change_detector: ChangeDetector,
        pdf_service: PDFProcessingService,
        json_service: JSONProcessingService,
        failed_job_store: FailedJobStore,
        max_retries: int,
        retry_backoff_seconds: int,
        max_concurrent_jobs: int,
    ) -> None:
        self._drive_client = drive_client
        self._change_detector = change_detector
        self._pdf_service = pdf_service
        self._json_service = json_service
        self._failed_job_store = failed_job_store
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._semaphore = asyncio.Semaphore(max_concurrent_jobs)
        self._last_run_summary: dict = {}

    def _build_job(self, file: DriveFile) -> ProcessingJob | None:
        job_type = _MIME_TO_JOB_TYPE.get(file.mime_type)
        if job_type is None:
            return None
        return ProcessingJob(
            file_id=file.file_id,
            file_name=file.name,
            job_type=job_type,
            modified_time=file.modified_time,
            md5_checksum=file.md5_checksum,
            max_attempts=self._max_retries,
        )

    async def _process_with_retry(self, job: ProcessingJob, file: DriveFile) -> JobResult:
        async with self._semaphore:
            last_error: Exception | None = None
            for attempt in range(1, job.max_attempts + 1):
                job.attempts = attempt
                try:
                    if job.job_type == JobType.PDF:
                        result = await asyncio.to_thread(self._pdf_service.process, job)
                    else:
                        result = await asyncio.to_thread(self._json_service.process, job)
                    self._change_detector.mark_processed(file)
                    return result
                except Exception as exc:
                    last_error = exc
                    logger.error(
                        "job_attempt_failed",
                        job_id=job.job_id,
                        file_name=job.file_name,
                        attempt=attempt,
                        error=str(exc),
                    )
                    if attempt < job.max_attempts:
                        await asyncio.sleep(self._retry_backoff_seconds * attempt)

            job.status = JobStatus.FAILED
            job.last_error = str(last_error)
            self._failed_job_store.add(job)
            return JobResult(
                job_id=job.job_id,
                file_id=job.file_id,
                file_name=job.file_name,
                status=JobStatus.FAILED,
                error=str(last_error),
            )

    async def run_once(self) -> dict:
        started = time.monotonic()
        try:
            files = await asyncio.to_thread(self._drive_client.list_files)
        except Exception as exc:
            logger.error("drive_list_files_failed", error=str(exc))
            return {"error": str(exc)}

        changed_files = self._change_detector.detect_changes(files)
        logger.info("changed_files_detected", count=len(changed_files))

        jobs_and_files = []
        for file in changed_files:
            job = self._build_job(file)
            if job is not None:
                jobs_and_files.append((job, file))
            else:
                logger.warning("unsupported_mime_type_skipped", file_name=file.name)

        results = await asyncio.gather(
            *(self._process_with_retry(job, file) for job, file in jobs_and_files),
            return_exceptions=False,
        )

        succeeded = sum(1 for r in results if r.status == JobStatus.SUCCEEDED)
        failed = sum(1 for r in results if r.status == JobStatus.FAILED)
        elapsed = time.monotonic() - started

        summary = {
            "files_detected": len(changed_files),
            "jobs_succeeded": succeeded,
            "jobs_failed": failed,
            "elapsed_seconds": round(elapsed, 3),
        }
        self._last_run_summary = summary
        logger.info("pipeline_run_completed", **summary)
        return summary

    @property
    def last_run_summary(self) -> dict:
        return self._last_run_summary

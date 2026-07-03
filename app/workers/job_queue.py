import json
from pathlib import Path
from threading import Lock

from app.models.job import ProcessingJob
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class FailedJobStore:
    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._lock = Lock()

    def _read(self) -> list[dict]:
        if not self._path.exists():
            return []
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def _write(self, items: list[dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(items, indent=2, default=str), encoding="utf-8")

    def add(self, job: ProcessingJob) -> None:
        with self._lock:
            items = self._read()
            items = [item for item in items if item.get("job_id") != job.job_id]
            items.append(json.loads(job.model_dump_json()))
            self._write(items)
            logger.warning("job_moved_to_failed_queue", job_id=job.job_id, file_name=job.file_name)

    def remove(self, job_id: str) -> None:
        with self._lock:
            items = self._read()
            items = [item for item in items if item.get("job_id") != job_id]
            self._write(items)

    def list_all(self) -> list[dict]:
        with self._lock:
            return self._read()

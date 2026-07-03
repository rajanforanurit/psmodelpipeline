import json
from pathlib import Path
from threading import Lock

from app.drive.models import DriveFile
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class ChangeDetector:
    def __init__(self, state_store_path: str) -> None:
        self._path = Path(state_store_path)
        self._lock = Lock()
        self._state: dict[str, dict[str, str]] = self._load()

    def _load(self) -> dict[str, dict[str, str]]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("state_store_corrupt_resetting")
            return {}

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")

    def detect_changes(self, files: list[DriveFile]) -> list[DriveFile]:
        with self._lock:
            changed: list[DriveFile] = []
            for file in files:
                previous = self._state.get(file.file_id)
                if previous is None:
                    changed.append(file)
                    continue
                if (
                    previous.get("modified_time") != file.modified_time
                    or previous.get("md5_checksum") != file.md5_checksum
                ):
                    changed.append(file)
            return changed

    def mark_processed(self, file: DriveFile) -> None:
        with self._lock:
            self._state[file.file_id] = {
                "modified_time": file.modified_time,
                "md5_checksum": file.md5_checksum,
                "name": file.name,
            }
            self._persist()

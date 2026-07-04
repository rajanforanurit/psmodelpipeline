from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from app.drive.models import DriveFile
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


def _state_point_id(file_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"pipeline-state|{file_id}"))


class ChangeDetector:
    def __init__(self, client: QdrantClient, collection_name: str) -> None:
        self._client = client
        self._collection_name = collection_name

    def detect_changes(self, files: list[DriveFile]) -> list[DriveFile]:
        if not files:
            return []

        point_ids = [_state_point_id(file.file_id) for file in files]
        existing_points = self._client.retrieve(
            collection_name=self._collection_name,
            ids=point_ids,
            with_payload=True,
        )
        existing_by_id = {str(point.id): point.payload for point in existing_points}

        changed: list[DriveFile] = []
        for file, point_id in zip(files, point_ids, strict=True):
            payload = existing_by_id.get(point_id)
            if payload is None:
                changed.append(file)
                continue
            if (
                payload.get("modified_time") != file.modified_time
                or payload.get("md5_checksum") != file.md5_checksum
            ):
                changed.append(file)

        logger.info(
            "change_detection_completed",
            checked=len(files),
            changed=len(changed),
        )
        return changed

    def mark_processed(self, file: DriveFile) -> None:
        point = PointStruct(
            id=_state_point_id(file.file_id),
            vector=[0.0],
            payload={
                "file_id": file.file_id,
                "name": file.name,
                "modified_time": file.modified_time,
                "md5_checksum": file.md5_checksum,
            },
        )
        self._client.upsert(collection_name=self._collection_name, points=[point], wait=True)
        logger.info("state_marked_processed", file_name=file.name, file_id=file.file_id)
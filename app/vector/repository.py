from uuid import uuid5, NAMESPACE_URL

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from app.utils.logging_config import get_logger

logger = get_logger(__name__)


def deterministic_uuid(*parts: str) -> str:
    return str(uuid5(NAMESPACE_URL, "|".join(parts)))


class VectorRepository:
    def __init__(self, client: QdrantClient, batch_size: int) -> None:
        self._client = client
        self._batch_size = batch_size

    def _upsert(self, collection_name: str, points: list[PointStruct]) -> int:
        inserted = 0
        for start in range(0, len(points), self._batch_size):
            batch = points[start : start + self._batch_size]
            self._client.upsert(collection_name=collection_name, points=batch, wait=True)
            inserted += len(batch)
        logger.info("vectors_upserted", collection=collection_name, count=inserted)
        return inserted

    def upsert_knowledge_chunks(
        self, collection_name: str, chunks: list[dict], vectors: list[list[float]]
    ) -> int:
        points = [
            PointStruct(
                id=deterministic_uuid(collection_name, chunk["chunk_id"]),
                vector=vector,
                payload=chunk,
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        return self._upsert(collection_name, points)

    def upsert_questions(
        self, collection_name: str, payloads: list[dict], vectors: list[list[float]]
    ) -> int:
        points = [
            PointStruct(
                id=deterministic_uuid(collection_name, payload["point_id"]),
                vector=vector,
                payload={k: v for k, v in payload.items() if k != "point_id"},
            )
            for payload, vector in zip(payloads, vectors, strict=True)
        ]
        return self._upsert(collection_name, points)

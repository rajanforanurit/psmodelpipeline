from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams

from app.utils.logging_config import get_logger
from app.vector.collections import CollectionSpec

logger = get_logger(__name__)


class QdrantClientFactory:
    @staticmethod
    def create(url: str, api_key: str) -> QdrantClient:
        return QdrantClient(url=url, api_key=api_key)


def ensure_collections(client: QdrantClient, specs: list[CollectionSpec]) -> None:
    existing = {c.name for c in client.get_collections().collections}
    for spec in specs:
        if spec.name in existing:
            continue
        client.create_collection(
            collection_name=spec.name,
            vectors_config=VectorParams(size=spec.vector_size, distance=spec.distance),
        )
        logger.info("collection_created", collection=spec.name, size=spec.vector_size)

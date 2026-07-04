import threading

from app.embedding.base import EmbeddingModel
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class BGEEmbedder(EmbeddingModel):
    def __init__(
        self,
        model_name: str,
        device: str,
        max_length: int,
        batch_size: int,
        use_fp16: bool,
        vector_size: int,
    ) -> None:
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=model_name, max_length=max_length)
        self._batch_size = batch_size
        self._vector_size = vector_size
        self._lock = threading.Lock()
        logger.info("embedding_model_loaded", model=model_name)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        with self._lock:
            vectors = self._model.embed(texts, batch_size=self._batch_size)
            return [vector.tolist() for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    @property
    def dimension(self) -> int:
        return self._vector_size
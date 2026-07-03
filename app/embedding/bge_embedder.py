from FlagEmbedding import BGEM3FlagModel

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
        self._model = BGEM3FlagModel(model_name, use_fp16=use_fp16, device=device)
        self._max_length = max_length
        self._batch_size = batch_size
        self._vector_size = vector_size
        logger.info("embedding_model_loaded", model=model_name, device=device)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        output = self._model.encode(
            texts,
            batch_size=self._batch_size,
            max_length=self._max_length,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        vectors = output["dense_vecs"]
        return [vector.tolist() for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    @property
    def dimension(self) -> int:
        return self._vector_size

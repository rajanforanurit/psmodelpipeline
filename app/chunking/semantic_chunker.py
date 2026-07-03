import re

from app.models.document import ParsedDocument
from app.parsers.heading_detector import HeadingInfo
from app.utils.hashing import stable_id
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?।])\s+")


class SemanticChunker:
    def __init__(self, chunk_size: int, chunk_overlap: int, min_chunk_size: int) -> None:
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._min_chunk_size = min_chunk_size

    def _split_sentences(self, text: str) -> list[str]:
        return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]

    def _pack_sentences(self, sentences: list[str]) -> list[str]:
        chunks: list[str] = []
        current: list[str] = []
        current_length = 0

        for sentence in sentences:
            sentence_length = len(sentence)
            if current_length + sentence_length > self._chunk_size and current:
                chunks.append(" ".join(current))
                overlap_sentences: list[str] = []
                overlap_length = 0
                for prior in reversed(current):
                    if overlap_length >= self._chunk_overlap:
                        break
                    overlap_sentences.insert(0, prior)
                    overlap_length += len(prior)
                current = overlap_sentences
                current_length = overlap_length

            current.append(sentence)
            current_length += sentence_length

        if current:
            chunks.append(" ".join(current))

        return [c for c in chunks if len(c) >= self._min_chunk_size]

    def chunk_document(
        self,
        document: ParsedDocument,
        headings: dict[int, HeadingInfo],
        subject: str | None,
        language: str,
    ) -> list[dict]:
        results: list[dict] = []

        for page in document.pages:
            if not page.text.strip():
                continue

            sentences = self._split_sentences(page.text)
            page_chunks = self._pack_sentences(sentences)
            heading_info = headings.get(page.page_number, HeadingInfo(None, None, None))

            for index, chunk_text in enumerate(page_chunks):
                chunk_id = stable_id(document.source, str(page.page_number), str(index), chunk_text[:64])
                results.append(
                    {
                        "chunk_id": chunk_id,
                        "text": chunk_text,
                        "source": document.source,
                        "subject": subject,
                        "chapter": heading_info.chapter,
                        "topic": heading_info.topic,
                        "heading": heading_info.heading,
                        "page": page.page_number,
                        "language": language,
                    }
                )

        logger.info("document_chunked", source=document.source, chunks=len(results))
        return results

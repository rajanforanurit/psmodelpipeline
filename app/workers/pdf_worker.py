import time

from app.chunking.semantic_chunker import SemanticChunker
from app.drive.client import GoogleDriveClient
from app.embedding.base import EmbeddingModel
from app.models.job import JobResult, JobStatus, ProcessingJob
from app.parsers.pdf_parser import PDFParser
from app.utils.logging_config import get_logger
from app.vector.repository import VectorRepository

logger = get_logger(__name__)


class PDFProcessingService:
    def __init__(
        self,
        drive_client: GoogleDriveClient,
        pdf_parser: PDFParser,
        chunker: SemanticChunker,
        embedder: EmbeddingModel,
        repository: VectorRepository,
        collection_name: str,
    ) -> None:
        self._drive_client = drive_client
        self._pdf_parser = pdf_parser
        self._chunker = chunker
        self._embedder = embedder
        self._repository = repository
        self._collection_name = collection_name

    def process(self, job: ProcessingJob) -> JobResult:
        started = time.monotonic()
        log = logger.bind(job_id=job.job_id, file_name=job.file_name)
        log.info("pdf_job_started")

        content = self._drive_client.download_file(job.file_id)
        parsed_document, headings = self._pdf_parser.parse(content, job.file_name)

        subject = job.file_name.rsplit(".", 1)[0]
        chunks = self._chunker.chunk_document(parsed_document, headings, subject, language="en")

        if not chunks:
            log.warning("pdf_job_no_chunks")
            return JobResult(
                job_id=job.job_id,
                file_id=job.file_id,
                file_name=job.file_name,
                status=JobStatus.SUCCEEDED,
                processing_time_seconds=time.monotonic() - started,
            )

        texts = [chunk["text"] for chunk in chunks]
        vectors = self._embedder.embed_texts(texts)
        inserted = self._repository.upsert_knowledge_chunks(self._collection_name, chunks, vectors)

        elapsed = time.monotonic() - started
        log.info(
            "pdf_job_completed",
            chunks=len(chunks),
            embeddings=len(vectors),
            inserted=inserted,
            elapsed_seconds=round(elapsed, 3),
        )

        return JobResult(
            job_id=job.job_id,
            file_id=job.file_id,
            file_name=job.file_name,
            status=JobStatus.SUCCEEDED,
            chunks_created=len(chunks),
            embeddings_generated=len(vectors),
            vectors_inserted=inserted,
            processing_time_seconds=elapsed,
        )

import time

from app.drive.client import GoogleDriveClient
from app.embedding.base import EmbeddingModel
from app.models.job import JobResult, JobStatus, ProcessingJob
from app.parsers.json_parser import JSONParser
from app.utils.logging_config import get_logger
from app.vector.repository import VectorRepository

logger = get_logger(__name__)


class JSONProcessingService:
    def __init__(
        self,
        drive_client: GoogleDriveClient,
        json_parser: JSONParser,
        embedder: EmbeddingModel,
        repository: VectorRepository,
        collection_name: str,
    ) -> None:
        self._drive_client = drive_client
        self._json_parser = json_parser
        self._embedder = embedder
        self._repository = repository
        self._collection_name = collection_name

    def process(self, job: ProcessingJob) -> JobResult:
        started = time.monotonic()
        log = logger.bind(job_id=job.job_id, file_name=job.file_name)
        log.info("json_job_started")

        content = self._drive_client.download_file(job.file_id)
        questions = self._json_parser.parse(content, job.file_name)

        if not questions:
            log.warning("json_job_no_questions")
            return JobResult(
                job_id=job.job_id,
                file_id=job.file_id,
                file_name=job.file_name,
                status=JobStatus.SUCCEEDED,
                processing_time_seconds=time.monotonic() - started,
            )

        texts = [question.searchable_text() for question in questions]
        vectors = self._embedder.embed_texts(texts)

        payloads = []
        for question in questions:
            payloads.append(
                {
                    "point_id": question.point_id(),
                    "exam": question.exam,
                    "year": question.year,
                    "paper": question.paper,
                    "subject": question.subject,
                    "topic": question.topic,
                    "language": "en",
                    "question": question.english.question,
                    "options": question.english.options,
                    "explanation": question.english.explanation,
                    "answer": str(question.correct_answer),
                    "difficulty": None,
                    "marks": question.marks,
                    "negativeMarks": question.negative_marks,
                }
            )

        inserted = self._repository.upsert_questions(self._collection_name, payloads, vectors)

        elapsed = time.monotonic() - started
        log.info(
            "json_job_completed",
            questions=len(questions),
            embeddings=len(vectors),
            inserted=inserted,
            elapsed_seconds=round(elapsed, 3),
        )

        return JobResult(
            job_id=job.job_id,
            file_id=job.file_id,
            file_name=job.file_name,
            status=JobStatus.SUCCEEDED,
            chunks_created=len(questions),
            embeddings_generated=len(vectors),
            vectors_inserted=inserted,
            processing_time_seconds=elapsed,
        )

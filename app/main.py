import asyncio
import time
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from app.chunking.semantic_chunker import SemanticChunker
from app.config import constants
from app.config.settings import get_settings
from app.drive.change_detector import ChangeDetector
from app.drive.client import GoogleDriveClient
from app.embedding.bge_embedder import BGEEmbedder
from app.parsers.json_parser import JSONParser
from app.parsers.ocr import OCREngine
from app.parsers.pdf_parser import PDFParser
from app.scheduler.scheduler import PipelineScheduler
from app.utils.logging_config import configure_logging, get_logger
from app.vector.collections import build_collection_specs
from app.vector.qdrant_client import QdrantClientFactory, ensure_collections
from app.vector.repository import VectorRepository
from app.workers.job_queue import FailedJobStore
from app.workers.json_worker import JSONProcessingService
from app.workers.orchestrator import PipelineOrchestrator
from app.workers.pdf_worker import PDFProcessingService

settings = get_settings()
configure_logging(constants.LOG_LEVEL)
logger = get_logger(__name__)

APP_START_TIME = time.monotonic()


def build_orchestrator() -> PipelineOrchestrator:
    logger.info("initializing_google_drive")
    drive_client = GoogleDriveClient(
        service_account_json=settings.google_service_account_json,
        folder_id=settings.google_drive_folder_id,
        page_size=constants.GOOGLE_DRIVE_POLL_PAGE_SIZE,
    )
    change_detector = ChangeDetector(constants.STATE_STORE_PATH)
    logger.info("google_drive_initialized")

    logger.info("connecting_to_qdrant")
    qdrant_client = QdrantClientFactory.create(settings.qdrant_url, settings.qdrant_api_key)
    logger.info("qdrant_connected")

    logger.info("ensuring_qdrant_collections")
    specs = build_collection_specs(
        knowledge_base_name=constants.QDRANT_KNOWLEDGE_BASE_COLLECTION,
        question_bank_name=constants.QDRANT_QUESTION_BANK_COLLECTION,
        generated_questions_name=constants.QDRANT_GENERATED_QUESTIONS_COLLECTION,
        vector_size=constants.QDRANT_VECTOR_SIZE,
        distance_name=constants.QDRANT_DISTANCE,
    )
    ensure_collections(qdrant_client, specs)
    repository = VectorRepository(qdrant_client, constants.QDRANT_UPSERT_BATCH_SIZE)
    logger.info("qdrant_collections_ready")

    logger.info("loading_embedding_model", model=constants.EMBEDDING_MODEL_NAME)
    embedder = BGEEmbedder(
        model_name=constants.EMBEDDING_MODEL_NAME,
        device=constants.EMBEDDING_DEVICE,
        max_length=constants.EMBEDDING_MAX_LENGTH,
        batch_size=constants.EMBEDDING_BATCH_SIZE,
        use_fp16=constants.EMBEDDING_USE_FP16,
        vector_size=constants.QDRANT_VECTOR_SIZE,
    )
    logger.info("embedding_model_loaded")

    logger.info("initializing_ocr")
    ocr_engine = OCREngine(constants.OCR_LANGUAGE, constants.OCR_USE_GPU)
    logger.info("ocr_initialized")

    pdf_parser = PDFParser(ocr_engine, constants.SCANNED_PDF_TEXT_THRESHOLD)
    chunker = SemanticChunker(
        constants.CHUNK_SIZE, constants.CHUNK_OVERLAP, constants.MIN_CHUNK_SIZE
    )
    json_parser = JSONParser()

    pdf_service = PDFProcessingService(
        drive_client=drive_client,
        pdf_parser=pdf_parser,
        chunker=chunker,
        embedder=embedder,
        repository=repository,
        collection_name=constants.QDRANT_KNOWLEDGE_BASE_COLLECTION,
    )
    json_service = JSONProcessingService(
        drive_client=drive_client,
        json_parser=json_parser,
        embedder=embedder,
        repository=repository,
        collection_name=constants.QDRANT_QUESTION_BANK_COLLECTION,
    )

    failed_job_store = FailedJobStore(constants.FAILED_QUEUE_PATH)

    logger.info("building_pipeline_orchestrator")
    orchestrator = PipelineOrchestrator(
        drive_client=drive_client,
        change_detector=change_detector,
        pdf_service=pdf_service,
        json_service=json_service,
        failed_job_store=failed_job_store,
        max_retries=constants.WORKER_MAX_RETRIES,
        retry_backoff_seconds=constants.WORKER_RETRY_BACKOFF_SECONDS,
        max_concurrent_jobs=constants.SCHEDULER_MAX_CONCURRENT_JOBS,
    )
    logger.info("pipeline_orchestrator_built")
    return orchestrator


async def initialize_pipeline(app: FastAPI) -> None:
    try:
        logger.info("pipeline_initialization_started")
        orchestrator = await asyncio.to_thread(build_orchestrator)
        app.state.orchestrator = orchestrator

        scheduler = None
        if constants.SCHEDULER_ENABLED:
            scheduler = PipelineScheduler(orchestrator, constants.SCHEDULER_INTERVAL_SECONDS)
            scheduler.start()
        app.state.scheduler = scheduler

        app.state.pipeline_ready = True
        app.state.pipeline_error = None
        logger.info("pipeline_ready")
    except Exception as exc:
        logger.error(
            "pipeline_initialization_failed",
            error=str(exc),
            traceback=traceback.format_exc(),
        )
        app.state.pipeline_ready = False
        app.state.pipeline_error = str(exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("application_starting", version=constants.APP_VERSION)

    app.state.pipeline_ready = False
    app.state.pipeline_error = None
    app.state.orchestrator = None
    app.state.scheduler = None

    app.state.init_task = asyncio.create_task(initialize_pipeline(app))

    yield

    scheduler: PipelineScheduler | None = app.state.scheduler
    if scheduler is not None:
        scheduler.shutdown()
    logger.info("application_stopped")


app = FastAPI(title=constants.APP_NAME, version=constants.APP_VERSION, lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {
        "server": "running",
        "pipeline_ready": app.state.pipeline_ready,
        "pipeline_error": app.state.pipeline_error,
        "uptime_seconds": round(time.monotonic() - APP_START_TIME, 2),
    }


@app.get("/metrics")
async def metrics() -> dict:
    if not app.state.pipeline_ready:
        raise HTTPException(status_code=503, detail="Pipeline is still initializing.")

    orchestrator: PipelineOrchestrator = app.state.orchestrator
    failed_store: FailedJobStore = orchestrator._failed_job_store
    return {
        "last_run": orchestrator.last_run_summary,
        "failed_jobs": len(failed_store.list_all()),
    }


@app.get("/version")
async def version() -> dict:
    return {"version": constants.APP_VERSION}

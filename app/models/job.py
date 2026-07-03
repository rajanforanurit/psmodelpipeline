from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class JobType(StrEnum):
    PDF = "pdf"
    JSON = "json"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ProcessingJob(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid4()))
    file_id: str
    file_name: str
    job_type: JobType
    modified_time: str
    md5_checksum: str
    status: JobStatus = JobStatus.PENDING
    attempts: int = 0
    max_attempts: int = 3
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_error: str | None = None


class JobResult(BaseModel):
    job_id: str
    file_id: str
    file_name: str
    status: JobStatus
    chunks_created: int = 0
    embeddings_generated: int = 0
    vectors_inserted: int = 0
    processing_time_seconds: float = 0.0
    error: str | None = None

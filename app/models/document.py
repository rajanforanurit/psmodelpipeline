from datetime import datetime

from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    chunk_id: str
    text: str
    source: str
    subject: str | None = None
    chapter: str | None = None
    topic: str | None = None
    heading: str | None = None
    page: int | None = None
    language: str = "en"
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ParsedPage(BaseModel):
    page_number: int
    text: str
    is_scanned: bool = False


class ParsedDocument(BaseModel):
    source: str
    pages: list[ParsedPage]
    is_scanned: bool = False

    @property
    def full_text(self) -> str:
        return "\n".join(page.text for page in self.pages)

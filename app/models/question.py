from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class LocalizedContent(BaseModel):
    question: str
    options: dict[str, str]
    explanation: str | None = Field(default=None, alias="english_explanation")

    model_config = {"populate_by_name": True}


class LocalizedContentHindi(BaseModel):
    question: str
    options: dict[str, str]
    explanation: str | None = Field(default=None, alias="hindi_explanation")

    model_config = {"populate_by_name": True}


class ExamQuestion(BaseModel):
    source_id: int = Field(alias="_id")
    exam: str
    year: int
    paper: str
    subject: str
    topic: str
    image_url: str | None = Field(default=None, alias="imageUrl")
    english: LocalizedContent
    hindi: LocalizedContentHindi | None = None
    marks: float
    negative_marks: float = Field(alias="negativeMarks")
    correct_answer: int

    model_config = {"populate_by_name": True}

    @field_validator("correct_answer")
    @classmethod
    def validate_answer(cls, value: int) -> int:
        if value < 1:
            raise ValueError("correct_answer must be a positive option index")
        return value

    def searchable_text(self) -> str:
        parts = [
            self.exam,
            str(self.year),
            self.paper,
            self.subject,
            self.topic,
            self.english.question,
        ]
        parts.extend(self.english.options.values())
        if self.english.explanation:
            parts.append(self.english.explanation)
        return " | ".join(p for p in parts if p)

    def point_id(self) -> str:
        return f"{self.exam}-{self.source_id}"


class QuestionRecord(BaseModel):
    exam: str
    year: int
    paper: str
    subject: str
    topic: str
    language: str
    question: str
    options: dict[str, str]
    explanation: str | None = None
    answer: str
    difficulty: str | None = None
    marks: float
    negative_marks: float
    created_at: datetime = Field(default_factory=datetime.utcnow)

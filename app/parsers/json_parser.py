import orjson
from pydantic import ValidationError

from app.models.question import ExamQuestion
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class JSONParser:
    def parse(self, content: bytes, source_name: str) -> list[ExamQuestion]:
        try:
            raw_items = orjson.loads(content)
        except orjson.JSONDecodeError as exc:
            raise ValueError(f"invalid json in {source_name}: {exc}") from exc

        if isinstance(raw_items, dict):
            raw_items = [raw_items]

        questions: list[ExamQuestion] = []
        errors = 0
        for item in raw_items:
            try:
                questions.append(ExamQuestion.model_validate(item))
            except ValidationError as exc:
                errors += 1
                logger.warning(
                    "question_validation_failed",
                    source=source_name,
                    item_id=item.get("_id"),
                    error=str(exc),
                )

        logger.info(
            "json_parsed",
            source=source_name,
            total=len(raw_items),
            valid=len(questions),
            invalid=errors,
        )
        return questions

import re
from dataclasses import dataclass

CHAPTER_PATTERN = re.compile(r"^(chapter|unit|section)\s+\d+", re.IGNORECASE)
TOPIC_PATTERN = re.compile(r"^\d+(\.\d+)*\s+\S+")


@dataclass
class TextSpan:
    text: str
    font_size: float
    page: int


@dataclass
class HeadingInfo:
    heading: str | None
    chapter: str | None
    topic: str | None


def detect_headings(spans: list[TextSpan]) -> dict[int, HeadingInfo]:
    if not spans:
        return {}

    sizes = sorted({round(span.font_size, 1) for span in spans}, reverse=True)
    heading_threshold = sizes[0] if sizes else 0.0
    topic_threshold = sizes[1] if len(sizes) > 1 else heading_threshold

    result: dict[int, HeadingInfo] = {}
    current_chapter: str | None = None
    current_topic: str | None = None
    current_heading: str | None = None

    for span in spans:
        line = span.text.strip()
        if not line:
            continue

        if CHAPTER_PATTERN.match(line) or (
            round(span.font_size, 1) >= heading_threshold and len(line) < 120
        ):
            current_chapter = line
            current_heading = line
        elif TOPIC_PATTERN.match(line) or round(span.font_size, 1) >= topic_threshold:
            current_topic = line
            current_heading = line

        result[span.page] = HeadingInfo(
            heading=current_heading, chapter=current_chapter, topic=current_topic
        )

    return result

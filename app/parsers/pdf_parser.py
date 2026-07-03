import fitz

from app.models.document import ParsedDocument, ParsedPage
from app.parsers.heading_detector import HeadingInfo, TextSpan, detect_headings
from app.parsers.ocr import OCREngine
from app.parsers.text_cleaner import clean_text
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class PDFParser:
    def __init__(self, ocr_engine: OCREngine, scanned_text_threshold: int) -> None:
        self._ocr_engine = ocr_engine
        self._scanned_text_threshold = scanned_text_threshold

    def _is_scanned_page(self, page: fitz.Page) -> bool:
        text = page.get_text("text").strip()
        return len(text) < self._scanned_text_threshold

    def _extract_spans(self, document: fitz.Document) -> list[TextSpan]:
        spans: list[TextSpan] = []
        for page_number, page in enumerate(document, start=1):
            page_dict = page.get_text("dict")
            for block in page_dict.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if text:
                            spans.append(
                                TextSpan(
                                    text=text,
                                    font_size=span.get("size", 0.0),
                                    page=page_number,
                                )
                            )
        return spans

    def parse(self, content: bytes, source_name: str) -> tuple[ParsedDocument, dict[int, HeadingInfo]]:
        document = fitz.open(stream=content, filetype="pdf")
        pages: list[ParsedPage] = []
        overall_scanned = False

        for page_number, page in enumerate(document, start=1):
            is_scanned = self._is_scanned_page(page)
            if is_scanned:
                overall_scanned = True
                pixmap = page.get_pixmap(dpi=200)
                image = pixmap_to_array(pixmap)
                text = self._ocr_engine.extract_text(image)
            else:
                text = page.get_text("text")

            pages.append(
                ParsedPage(page_number=page_number, text=clean_text(text), is_scanned=is_scanned)
            )

        headings = detect_headings(self._extract_spans(document)) if not overall_scanned else {}
        document.close()

        parsed = ParsedDocument(source=source_name, pages=pages, is_scanned=overall_scanned)
        logger.info(
            "pdf_parsed",
            source=source_name,
            pages=len(pages),
            scanned=overall_scanned,
        )
        return parsed, headings


def pixmap_to_array(pixmap: "fitz.Pixmap"):
    import numpy as np

    array = np.frombuffer(pixmap.samples, dtype=np.uint8)
    array = array.reshape(pixmap.height, pixmap.width, pixmap.n)
    if pixmap.n == 4:
        array = array[:, :, :3]
    return array

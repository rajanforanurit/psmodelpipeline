import numpy as np
from paddleocr import PaddleOCR

from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class OCREngine:
    def __init__(self, language: str, use_gpu: bool) -> None:
        self._engine = PaddleOCR(use_angle_cls=True, lang=language, use_gpu=use_gpu, show_log=False)

    def extract_text(self, image: np.ndarray) -> str:
        result = self._engine.ocr(image, cls=True)
        if not result or result[0] is None:
            return ""
        lines = [line[1][0] for line in result[0] if line and len(line) > 1]
        return "\n".join(lines)

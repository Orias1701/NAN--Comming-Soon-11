import re
import fitz

from typing import Dict, Tuple, Union

class PDFQualityChecker:
    """
    Bộ lọc chất lượng PDF cơ bản trước khi xử lý.
    Đánh giá lỗi font, lỗi encode, ký tự hỏng, OCR kém, v.v.
    """

    def __init__(self, 
                 maxInvalidRatio: float = 0.2,
                 maxWhitespaceRatio: float = 0.2,
                 maxShortLineRatio: float = 0.3,
                 minTotalChars: int = 300):
        self.maxInvalidRatio = maxInvalidRatio
        self.maxWhitespaceRatio = maxWhitespaceRatio
        self.maxShortLineRatio = maxShortLineRatio
        self.minTotalChars = minTotalChars

        self.validCharPattern = re.compile(r"[A-Za-zÀ-ỹĐđ0-9.,:;!?()\"''""–\-_\s]")

    # ============================================================
    # 1️⃣  HÀM CHÍNH
    # ============================================================
    def evaluate(self, pdf: Union[str, fitz.Document]) -> Tuple[bool, Dict]:
        """
        Đánh giá chất lượng PDF.
        - pdf: đường dẫn (str) hoặc fitz.Document đã mở
        - trả (isGood, metrics)
        """
        if isinstance(pdf, str):
            try:
                doc = fitz.open(pdf)
            except Exception as e:
                return False, {"checkMess": f"❌ Không mở được file: {e}"}
        elif isinstance(pdf, fitz.Document):
            doc = pdf
        else:
            raise TypeError("pdf phải là str hoặc fitz.Document")

        textAll = ""
        shortLines = 0
        allLines = 0

        for page in doc:
            text = page.get_text("text") or ""
            if not text.strip():
                continue
            lines = text.splitlines()
            for line in lines:
                if not line.strip():
                    continue
                allLines += 1
                if len(line.strip()) < 10:
                    shortLines += 1
            textAll += text + "\n"

        totalChars = len(textAll)
        if totalChars < self.minTotalChars:
            return False, {
                "checkMess": "❌ File quá ngắn hoặc không có text layer",
                "totalChars": totalChars,
            }

        validChars = sum(1 for ch in textAll if self.validCharPattern.match(ch))
        invalidChars = totalChars - validChars
        invalidRatio = invalidChars / totalChars

        whitespaceExcess = len(re.findall(r" {3,}", textAll))
        whitespaceRatio = whitespaceExcess / totalChars

        shortLineRatio = shortLines / max(allLines, 1)

        isGood = (
            invalidRatio <= self.maxInvalidRatio
            and whitespaceRatio <= self.maxWhitespaceRatio
            and shortLineRatio <= self.maxShortLineRatio
        )

        if not isGood:
            if invalidRatio > self.maxInvalidRatio:
                checkMess = "❌ Nhiều ký tự lỗi / encode sai"
            elif whitespaceRatio > self.maxWhitespaceRatio:
                checkMess = "❌ Nhiều khoảng trắng thừa"
            elif shortLineRatio > self.maxShortLineRatio:
                checkMess = "⚠️ OCR hoặc mất ký tự"
            else:
                checkMess = "❌ Văn bản lỗi nặng"
        else:
            checkMess = "✅ Đạt yêu cầu"

        metrics = {
            "checkMess": checkMess,
            "totalChars": totalChars,
            "invalidRatio": round(invalidRatio, 3),
            "whitespaceRatio": round(whitespaceRatio, 3),
            "shortLineRatio": round(shortLineRatio, 3),
        }
        return isGood, metrics

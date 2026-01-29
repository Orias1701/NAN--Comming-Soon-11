import re

from typing import Dict, Any
from collections import Counter, defaultdict

from . import Common_TextProcess as TextProcess
from . import Common_PdfProcess as PdfProcess

# ===============================
# 1. Utils  -> class U1_Utils
# ===============================
class U1_Utils:

    @staticmethod
    def collectProperNames(lines, minCount=10):
        titleWords = []

        for line in lines:
            text = line.get("Text", "")
            words = re.findall(r"[A-Za-zÀ-ỹĐđ0-9]+", text)
            if not words:
                continue

            for w in words[1:]:
                if w.istitle():
                    cleanW = TextProcess.normalizeWord(w)
                    if cleanW:
                        titleWords.append(cleanW)

        counter = Counter(titleWords)
        properNames = {TextProcess.normalizeWord(w) for w, cnt in counter.items() if cnt >= minCount}
        return properNames

    @staticmethod
    def extractMarker(text, patterns):
        for patternInfo in patterns["markers"]:
            match = patternInfo["pattern"].match(text)
            if match:
                markerText = re.sub(r'^\s+', '', match.group(0))
                markerText = re.sub(r'\s+$', ' ', markerText)
                return {"markerText": markerText}
        return {"markerText": None}

    @staticmethod
    def formatMarker(markerText, patterns):
        """
        Chuẩn hoá MarkerText
        """
        if not markerText:
            return None

        formatted = markerText
        formatted = re.sub(r'\b[0-9]+\b', '123', formatted)
        formatted = re.sub(r'\b[IVXLC]+\b', 'XVI', formatted)

        parts = re.split(r'(\W+)', formatted)
        formattedParts = []
        for part in parts:
            if re.match(r'(\W+)', part):
                formattedParts.append(part)
                continue
            if part.lower() in patterns["keywords_set"]:
                formattedParts.append(part)
            elif re.match(r'^[a-z]$', part) or re.match(r'^[a-zđêôơư]$', part):
                formattedParts.append('abc')
            elif re.match(r'^[A-Z]$', part) or re.match(r'^[A-ZĐÊÔƠƯ]$', part):
                formattedParts.append('ABC')
            else:
                formattedParts.append(part)
        return ''.join(formattedParts)

    @staticmethod
    def normalizeRomans(lines, mode="marker", replaceWith="ABC"):
        formatGroups = defaultdict(list)
        for idx, line in enumerate(lines):
            fmt = line.get("MarkerType")
            marker = line.get("MarkerText")
            if fmt and marker:
                formatGroups[fmt].append((idx, marker))

        if mode == "marker":
            for fmt, group in formatGroups.items():
                romanMarkers = []
                for idx, marker in group:
                    m = re.search(r'\b([IVXLC]+)\b', marker)
                    if m and TextProcess.isRoman(m.group(1)):
                        romanMarkers.append((idx, m.group(1)))
                    else:
                        break

                if romanMarkers:
                    romanNumbers = [TextProcess.romanToInt(rm[1]) for rm in romanMarkers]
                    expected = list(range(min(romanNumbers), max(romanNumbers) + 1))
                    if sorted(romanNumbers) != expected:
                        for idx, _ in romanMarkers:
                            lines[idx]["MarkerType"] = re.sub(r'\b[IVXLC]+\b', replaceWith, lines[idx]["MarkerType"])

        elif mode == "text":
            for line in lines:
                for key in ["Text", "MarkerText", "MarkerType"]:
                    if line.get(key):
                        line[key] = re.sub(r'\b[IVXLC]+\b', replaceWith, line[key])

        return lines


# ===============================
# 2. Word-level functions (mới) -> class U2_Word
# ===============================
class U2_Word:
    @staticmethod
    def caseStyle(wordText: str) -> int:
        """CaseStyle cho từ: 3000 (UPPER), 2000 (Title), 1000 (khác)"""
        clean = re.sub(r'[^A-Za-zÀ-ỹà-ỹ0-9]', '', wordText)
        if clean and clean.isupper():
            return 3000
        if clean and clean.istitle():
            return 2000
        return 1000

    @staticmethod
    def buildStyle(wordText, span):
        """Style gộp = CaseStyle + FontStyle (100,10,1)"""
        cs = U2_Word.caseStyle(wordText)
        b, i, u = PdfProcess.fontFlags(span)
        fs = (100 if b else 0) + (10 if i else 0) + (1 if u else 0)
        return cs + fs

    @staticmethod
    def getWordStyle(line, index: int):
        """Lấy Style của từ tại vị trí index."""
        words = PdfProcess.extractWords(line)
        if -len(words) <= index < len(words):
            word, span = words[index]
            return U2_Word.buildStyle(word, span)
        return 0


# ===============================
# 3. Line-level functions (mới) -> class U3_Line
# ===============================
class U3_Line:
    @staticmethod
    def getPageGeneralSize(page):
        """[height, width] của trang"""
        return [round(page.rect.height, 1), round(page.rect.width, 1)]

    @staticmethod
    def getLineText(line):
        """Text đầy đủ của line"""
        return line.get("text", "")

    @staticmethod
    def getLineStyle(line, exceptions=None):
        """
        Style của line = CaseStyle (min trên từ hợp lệ) + FontStyle (AND spans).
        """
        words = line.get("words", [])
        spans = line.get("spans", [])

        exceptionTexts = set()
        if exceptions:
            exceptionTexts = (
                set(exceptions.get("common_words", [])) |
                set(exceptions.get("proper_names", [])) |
                set(exceptions.get("abbreviations", []))
            )

        csValues = []
        for w, _ in words:
            cleanW = TextProcess.normalizeWord(w)
            if not cleanW:
                continue
            if cleanW in exceptionTexts or TextProcess.isAbbreviation(cleanW):
                continue
            csValues.append(U2_Word.caseStyle(cleanW))

        csLine = min(csValues) if csValues else 1000

        if spans:
            boldAll = italicAll = underlineAll = True
            for s in spans:
                b, i, u = PdfProcess.fontFlags(s)
                boldAll &= b
                italicAll &= i
                underlineAll &= u
            fsLine = (100 if boldAll else 0) + (10 if italicAll else 0) + (1 if underlineAll else 0)
        else:
            fsLine = 0

        return csLine + fsLine


# ===============================
# 4. Compatibility wrappers -> class U4_Compat
# ===============================
class U4_Compat:
    @staticmethod
    def getText(line):
        """Alias cũ: Text của line"""
        return U3_Line.getLineText(line)

    @staticmethod
    def getCoords(line):
        """Alias cũ: Coord của line, giữ tuple (x0, x1, xm, y0, y1)"""
        return PdfProcess.getLineCoord(line)

    @staticmethod
    def getFirstWord(line):
        """Giữ API cũ: trả {Text, Style, FontSize} của từ đầu"""
        return {
            "Text": PdfProcess.getWordText(line, 0),
            "Style": U2_Word.getWordStyle(line, 0),
            "FontSize": PdfProcess.getWordFontSize(line, 0),
        }

    @staticmethod
    def getLastWord(line):
        """Giữ API cũ: trả {Text, Style, FontSize} của từ cuối"""
        return {
            "Text": PdfProcess.getWordText(line, -1),
            "Style": U2_Word.getWordStyle(line, -1),
            "FontSize": PdfProcess.getWordFontSize(line, -1),
        }


# ===============================
# 5. Marker / Style (line-level) -> class U5_MarkerStyle
# ===============================
class U5_MarkerStyle:
    @staticmethod
    def getMarker(text, patterns):
        info = U1_Utils.extractMarker(text, patterns)
        markerText = info.get("markerText")
        markerType = None
        if markerText:
            markerTextCleaned = re.sub(r'([A-Za-z0-9ĐÊÔƠƯđêôơư])\+(?=\W|$)', r'\1', markerText)
            markerType = U1_Utils.formatMarker(markerTextCleaned, patterns)
        return markerText, markerType

    @staticmethod
    def getFontSize(line):
        """
        Mean FontSize trên spans (logic cũ) — vẫn giữ cho compatibility nếu còn chỗ gọi.
        """
        spans = line.get("spans", [])
        if spans:
            valid_spans = [s for s in spans if s.get("text", "").strip()]
            if valid_spans:
                sizes = [s.get("size", 12.0) for s in valid_spans]
            else:
                sizes = [s.get("size", 12.0) for s in spans]
            avg = sum(sizes) / len(sizes)
            return round(avg * 2) / 2
        return 12.0


# ===============================
# 6. Tổng hợp toàn văn bản -> class U6_Document
# ===============================
class U6_Document:
    @staticmethod
    def getTextStatus(pdfDoc, exceptions, patterns):
        doc = pdfDoc
        general = {"pageGeneralSize": U3_Line.getPageGeneralSize(doc[0])}
        lines = []
        for i, page in enumerate(doc):
            textDict = page.get_text("dict")
            for block in textDict["blocks"]:
                if "lines" in block:
                    for l in block["lines"]:
                        text = "".join(span["text"] for span in l["spans"]).strip()
                        if not text:
                            continue

                        markerText, markerType = U5_MarkerStyle.getMarker(text, patterns)

                        lineObj = {"text": text, "spans": l["spans"]}
                        style = U3_Line.getLineStyle(lineObj)
                        fontsize = PdfProcess.getLineFontSize(lineObj)
                        x0, x1, xm, y0, y1 = PdfProcess.getLineCoord(lineObj)

                        wordsObj = {
                            "First": U4_Compat.getFirstWord(lineObj),
                            "Last":  U4_Compat.getLastWord(lineObj)
                        }

                        lineDict = {
                            "Line": len(lines) + 1,
                            "Text": text,
                            "MarkerText": markerText,
                            "MarkerType": markerType,
                            "Style": style,
                            "FontSize": fontsize,
                            "Words": wordsObj,
                            "Coords": {"X0": x0, "X1": x1, "XM": xm, "Y0": y0, "Y1": y1}
                        }
                        lines.append(lineDict)
        return {"general": general, "lines": lines}


# ===============================
# 7. Các hàm set* -> class U7_Setters
# ===============================
class U7_Setters:
    @staticmethod
    def setCommonStatus(lines, attr, rank=1):
        values = [l[attr] for l in lines if l.get(attr) is not None]
        counter = Counter(values)
        return counter.most_common(rank)

    @staticmethod
    def setCommonFontSize(lines):
        fs, _ = U7_Setters.setCommonStatus(lines, "FontSize", 1)[0]
        return round(fs, 1)

    @staticmethod
    def setCommonFontSizes(lines):
        """
        Trả về tất cả FontSize và số lượng của chúng, sắp xếp theo tần suất giảm dần.
        """
        values = [l["FontSize"] for l in lines if l.get("FontSize") is not None]
        counter = Counter(values)
        results = []
        for fs, count in counter.most_common():  # trả về tất cả
            results.append({"FontSize": round(fs, 1), "Count": count})
        return results

    @staticmethod
    def setCommonMarkers(lines):
        total = len(lines)
        counter = Counter([l["MarkerType"] for l in lines if l["MarkerType"]])
        results = []
        for marker, count in counter.most_common(10):
            if count >= total * 0.005:
                results.append(marker)
            else:
                break
        return results

    @staticmethod
    def setTextStatus(baseJson):
        lines = baseJson["lines"]
        pageGeneralSize = baseJson["general"]["pageGeneralSize"]
        xStart, yStart, xEnd, yEnd, xMid, yMid = PdfProcess.setPageCoords(lines, pageGeneralSize)
        regionWidth, regionHeight = PdfProcess.setPageRegionSize(xStart, yStart, xEnd, yEnd)
        commonFontSizes = U7_Setters.setCommonFontSizes(lines)
        commonFontSize = U7_Setters.setCommonFontSize(lines)
        commonMarkers = U7_Setters.setCommonMarkers(lines)

        newGeneral = {
            "pageGeneralSize": baseJson["general"]["pageGeneralSize"],
            "pageCoords": {"xStart": xStart, "yStart": yStart, "xEnd": xEnd, "yEnd": yEnd, "xMid": xMid, "yMid": yMid},
            "pageRegionWidth": regionWidth,
            "pageRegionHeight": regionHeight,
            "commonFontSize": commonFontSize,
            "commonFontSizes": commonFontSizes,
            "commonMarkers": commonMarkers
        }

        newLines = []
        for i, line in enumerate(lines):
            lineWidth, lineHeight = PdfProcess.setLineSize(line)
            pos = PdfProcess.setPosition(line, lines[i - 1] if i > 0 else None,
                              lines[i + 1] if i < len(lines) - 1 else None,
                              xStart, xEnd, xMid)
            posDict = {"Left": pos[0], "Right": pos[1], "Mid": pos[2], "Top": pos[3], "Bot": pos[4]}

            lineDict = {
                **line,
                "LineWidth": lineWidth,
                "LineHeight": lineHeight,
                "Position": posDict,
                "Align": PdfProcess.setAlign(posDict, regionWidth)
            }
            newLines.append(lineDict)

        return {"general": newGeneral, "lines": newLines}


# ===============================
# 8. Các hàm del/reset -> class U8_Cleanup
# ===============================
class U8_Cleanup:
    @staticmethod
    def delStatus(jsonDict, deleteList):
        for line in jsonDict["lines"]:
            for attr in deleteList:
                if attr in line:
                    del line[attr]
        return jsonDict

    @staticmethod
    def resetPosition(jsonDict):
        lines = jsonDict.get("lines", [])
        for i, line in enumerate(lines):
            pos = line.get("Position", {})

            if "Top" in pos and pos["Top"] < 0:
                topCandidates = []
                if i > 0:
                    prevTop = lines[i - 1].get("Position", {}).get("Top")
                    if prevTop is not None:
                        topCandidates.append(prevTop)
                if i < len(lines) - 1:
                    nextTop = lines[i + 1].get("Position", {}).get("Top")
                    if nextTop is not None:
                        topCandidates.append(nextTop)
                if topCandidates:
                    pos["Top"] = min(topCandidates)

            if "Bot" in pos and pos["Bot"] < 0:
                botCandidates = []
                if i > 0:
                    prevBot = lines[i - 1].get("Position", {}).get("Bot")
                    if prevBot is not None:
                        botCandidates.append(prevBot)
                if i < len(lines) - 1:
                    nextBot = lines[i + 1].get("Position", {}).get("Bot")
                    if nextBot is not None:
                        botCandidates.append(nextBot)
                if botCandidates:
                    pos["Bot"] = min(botCandidates)
            line["Position"] = pos
        return jsonDict

    @staticmethod
    def normalizeFinal(jsonDict):
        for line in jsonDict.get("lines", []):
            # xử lý Text và MarkerText
            if "Text" in line:
                line["Text"] = TextProcess.stripExtraSpaces(line["Text"])
            if "MarkerText" in line and line["MarkerText"]:
                line["MarkerText"] = TextProcess.stripExtraSpaces(line["MarkerText"])

            # xử lý word-level
            words = line.get("Words", {})
            for key in ["First", "Last"]:
                if key in words and "Text" in words[key]:
                    words[key]["Text"] = TextProcess.stripExtraSpaces(words[key]["Text"])
        return jsonDict


# ===============================
# 9. Hàm chính extractData (giữ API cũ)
# ===============================
def extractData(pdfDoc, exceptData, markerData, statusData):

    exceptions = dict(exceptData)
    markers = dict(markerData)
    status = dict(statusData)

    keywords = markers.get("keywords", [])
    titleKeywords = '|'.join(re.escape(k[0].upper() + k[1:].lower()) for k in keywords)
    upperKeywords = '|'.join(re.escape(k.upper()) for k in keywords)
    allKeywords = f"{titleKeywords}|{upperKeywords}"

    compiledMarkers = []
    for item in markers.get("markers", []):
        patternStr = item["pattern"].replace("{keywords}", allKeywords)
        try:
            compiledPattern = re.compile(patternStr)
        except re.error:
            continue
        compiledMarkers.append({
            "pattern": compiledPattern,
            "description": item.get("description", ""),
            "type": item.get("type", "")
        })

    patterns = {
        "markers": compiledMarkers,
        "keywords_set": set(k.lower() for k in keywords)
    }

    baseJson = U6_Document.getTextStatus(pdfDoc, exceptions, patterns)
    baseJson["lines"] = U1_Utils.normalizeRomans(baseJson["lines"])

    modifiedJson = U7_Setters.setTextStatus(baseJson)
    cleanJson = U8_Cleanup.resetPosition(modifiedJson)
    extractedData = U8_Cleanup.delStatus(cleanJson, ["Coords"])
    extractedData = U8_Cleanup.normalizeFinal(extractedData)

    properNamesAuto = U1_Utils.collectProperNames(extractedData["lines"], minCount=10)

    properNamesExisting = [p["text"] if isinstance(p, dict) else str(p)
                                for p in exceptions.get("proper_names", [])]

    exceptions["proper_names"] = list(set(properNamesExisting) | properNamesAuto)

    return extractedData


class B1Extractor:
    """
    Orchestrator theo instance:
    - Giữ nguyên quy tắc/thuật toán của extractData cũ.
    - exceptions/markers/status và regex markers được nạp/biên dịch 1 lần.
    """

    def __init__(
        self,
        exceptData: Any,
        markerData: Any,
        statusData: Any,
        properNameMinCount: int = 10,
    ) -> None:
        """
        exceptData / markerData / statusData:
          - str: đường dẫn tới JSON theo format đồng bộ (U1_Utils.loadHardcodes)
          - dict: dữ liệu đã load sẵn (bỏ qua loadHardcodes)
        properNameMinCount:
          - Ngưỡng đếm tên riêng động.
        """
        def _ensureDict(src, wanted=None):
            if isinstance(src, dict):
                return dict(src)
            raise ValueError("Vui lòng truyền dict đã load sẵn thay vì đường dẫn file.")

        self.exceptions: Dict[str, Any] = _ensureDict(
            exceptData, wanted=["common_words", "proper_names", "abbreviations"]
        )
        self.markers: Dict[str, Any] = _ensureDict(
            markerData, wanted=["keywords", "markers"]
        )
        self.status: Dict[str, Any] = _ensureDict(statusData)

        self.properNameMinCount = properNameMinCount

        keywords = self.markers.get("keywords", [])
        titleKeywords = "|".join(re.escape(k[0].upper() + k[1:].lower()) for k in keywords)
        upperKeywords = "|".join(re.escape(k.upper()) for k in keywords)
        allKeywords = f"{titleKeywords}|{upperKeywords}" if keywords else ""

        compiledMarkers = []
        for item in self.markers.get("markers", []):
            patternStr = item.get("pattern", "")
            if allKeywords:
                patternStr = patternStr.replace("{keywords}", allKeywords)
            try:
                compiled = re.compile(patternStr)
            except re.error:
                continue
            compiledMarkers.append(
                {
                    "pattern": compiled,
                    "description": item.get("description", ""),
                    "type": item.get("type", ""),
                }
            )

        self.patterns = {
            "markers": compiledMarkers,
            "keywords_set": set(k.lower() for k in keywords),
        }

    def extract(self, pdfDoc) -> Dict[str, Any]:
        """
        Chạy pipeline extractData cũ cho 1 file PDF.
        Trả về extractedData (như trước).
        """

        baseJson = U6_Document.getTextStatus(pdfDoc, self.exceptions, self.patterns)

        baseJson["lines"] = U1_Utils.normalizeRomans(baseJson["lines"])

        modifiedJson = U7_Setters.setTextStatus(baseJson)
        cleanJson = U8_Cleanup.resetPosition(modifiedJson)
        extractedData = U8_Cleanup.delStatus(cleanJson, ["Coords"])
        extractedData = U8_Cleanup.normalizeFinal(extractedData)

        properNamesAuto = U1_Utils.collectProperNames(
            extractedData["lines"], minCount=self.properNameMinCount
        )
        properNamesExisting = [
            p["text"] if isinstance(p, dict) else str(p)
            for p in self.exceptions.get("proper_names", [])
        ]
        self.exceptions["proper_names"] = list(set(properNamesExisting) | properNamesAuto)
        return extractedData
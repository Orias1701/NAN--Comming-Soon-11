from collections import OrderedDict
from copy import deepcopy

class ChunkBuilder:
    def readInput(self, RawLvlsDict=None, rawDataDict=None):
        self.structSpec = RawLvlsDict[0]
        self.paragraphs = sorted(
            rawDataDict.get("paragraphs", []),
            key=lambda x: x.get("Paragraph", 0)
        )

        self.orderedFields = list(self.structSpec.keys())
        self.lastField = self.orderedFields[-1]
        self.levelFields = self.orderedFields[:-1]

        self.markerDict = {}
        for fld in self.orderedFields:
            vals = self.structSpec.get(fld, [])
            self.markerDict[fld] = set(vals) if isinstance(vals, list) else set()

        self.StructDict = []
        self.indexCounter = 1

    def _newTemp(self):
        return {fld: "" for fld in self.levelFields} | {self.lastField: []}

    def _tempHasData(self, temp):
        return any(temp[f].strip() for f in self.levelFields) or bool(temp[self.lastField])

    def _resetDeeper(self, temp, touchedField):
        idx = self.levelFields.index(touchedField)
        for f in self.levelFields[idx+1:]:
            temp[f] = ""
        temp[self.lastField] = []

    def _hasDataFromLevel(self, temp, fld):
        """Kiểm tra từ level fld trở xuống có dữ liệu không"""
        if fld not in self.levelFields:
            return False
        idx = self.levelFields.index(fld)
        for f in self.levelFields[idx:]:
            if temp[f].strip():
                return True
        if temp[self.lastField]:
            return True
        return False

    def _withIndex(self, temp, idx):
        """Tạo OrderedDict với Index đứng đầu"""
        od = OrderedDict()
        od["Index"] = idx
        for f in self.levelFields:
            od[f] = temp[f]
        od[self.lastField] = temp[self.lastField]
        return od

    def build(self, RawLvlsDict=None, rawDataDict=None):
        self.readInput(RawLvlsDict, rawDataDict)
        temp = self._newTemp()
        for p in self.paragraphs:
            text = p.get("Text") or ""
            marker = p.get("MarkerType", None) or "none"

            matchedField = None
            for fld in self.levelFields:
                if marker in self.markerDict.get(fld, set()):
                    matchedField = fld
                    break

            if matchedField is not None:
                if self._hasDataFromLevel(temp, matchedField):
                    self.StructDict.append(self._withIndex(deepcopy(temp), self.indexCounter))
                    self.indexCounter += 1

                temp[matchedField] = text
                self._resetDeeper(temp, matchedField)
            else:
                temp[self.lastField].append(text)

        if self._tempHasData(temp):
            self.StructDict.append(self._withIndex(deepcopy(temp), self.indexCounter))
            self.indexCounter += 1
        
        return self.StructDict
from typing import Dict, List, Any

class JSONSchemaExtractor:

    def __init__(self, listPolicy: str = "first", verbose: bool = True) -> None:
        """
        :param listPolicy: "first" | "union"
            - "first": nếu gặp list các object, lấy schema theo PHẦN TỬ ĐẦU (như bản gốc).
            - "union": duyệt mọi phần tử, hợp nhất các field/type.
        """
        assert listPolicy in ("first", "union"), "listPolicy must be 'first' or 'union'"
        self.listPolicy = listPolicy
        self.verbose = verbose

        self._processedFields: set[str] = set()
        self._fullSchema: Dict[str, str] = {}

    # =====================================
    # 1) Chuẩn hóa kiểu dữ liệu
    # =====================================
    @staticmethod
    def getStandardType(value: Any) -> str:

        if isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "number"
        elif isinstance(value, float):
            return "number"
        elif isinstance(value, str):
            return "string"
        elif isinstance(value, list):
            return "array"
        elif isinstance(value, dict):
            return "object"
        elif value is None:
            return "null"
        return "unknown"

    # =====================================
    # 2) Hợp nhất kiểu (null / mixed)
    # =====================================
    def _mergeType(self, key: str, newType: str, itemIndex: int) -> None:
        """
        Cập nhật self._fullSchema[key] theo quy tắc:
         - Nếu chưa có: đặt = newType và log "New: ..."
         - Nếu khác:
             + Nếu newType == "null": giữ kiểu cũ.
             + Nếu kiểu cũ == "null": cập nhật = newType.
             + Ngược lại: nếu khác nhau và chưa "mixed" => set "mixed" và cảnh báo.
        """
        if key not in self._fullSchema:
            self._fullSchema[key] = newType
            self._processedFields.add(key)
            return

        oldType = self._fullSchema[key]
        if oldType == newType:
            return

        if newType == "null":
            return
        
        if oldType == "null":
            self._fullSchema[key] = newType
            return

        if oldType != "mixed":
            self._fullSchema[key] = "mixed"

    # =====================================
    # 3) Đệ quy trích xuất schema
    # =====================================
    def _extractSchemaFromObj(self, data: Dict[str, Any], prefix: str, itemIndex: int) -> None:
        """
        Duyệt dict hiện tại, cập nhật _fullSchema với kiểu tại key (phẳng),
        và nếu là object/array lồng thì đệ quy theo quy tắc gốc.
        """
        for key, value in data.items():
            newPrefix = f"{prefix}{key}" if prefix else key

            vtype = self.getStandardType(value)
            self._mergeType(newPrefix, vtype, itemIndex)

            if isinstance(value, dict):
                self._extractSchemaFromObj(value, f"{newPrefix}.", itemIndex)

            elif isinstance(value, list) and value:
                first = value[0]
                if isinstance(first, dict):
                    if self.listPolicy == "first":
                        self._extractSchemaFromObj(first, f"{newPrefix}.", itemIndex)
                    else:  # union
                        for elem in value:
                            if isinstance(elem, dict):
                                self._extractSchemaFromObj(elem, f"{newPrefix}.", itemIndex)
                elif isinstance(first, list):
                    if self.listPolicy == "first":
                        self._extractSchemaFromList(first, f"{newPrefix}.", itemIndex)
                    else:
                        for elem in value:
                            if isinstance(elem, list):
                                self._extractSchemaFromList(elem, f"{newPrefix}.", itemIndex)

    def _extractSchemaFromList(self, dataList: List[Any], prefix: str, itemIndex: int) -> None:
        """
        Hỗ trợ cho trường hợp list lồng list (ít gặp). Duyệt tương tự _extractSchemaFromObj.
        """
        if not dataList:
            return

        first = dataList[0]
        if isinstance(first, dict):
            if self.listPolicy == "first":
                self._extractSchemaFromObj(first, prefix, itemIndex)
            else:
                for elem in dataList:
                    if isinstance(elem, dict):
                        self._extractSchemaFromObj(elem, prefix, itemIndex)
        elif isinstance(first, list):
            if self.listPolicy == "first":
                self._extractSchemaFromList(first, prefix, itemIndex)
            else:
                for elem in dataList:
                    if isinstance(elem, list):
                        self._extractSchemaFromList(elem, prefix, itemIndex)

    # =====================================
    # 4) API chính (data/file)
    # =====================================
    def createSchemaFromData(self, data: Any) -> Dict[str, str]:
        """
        Tạo schema từ biến Python (list | dict).
        Giữ log giống bản gốc.
        """

        self._processedFields.clear()
        self._fullSchema.clear()

        dataList = data if isinstance(data, list) else [data]

        if not dataList:
            raise ValueError("JSON data is empty")

        for i, item in enumerate(dataList, 1):
            if not isinstance(item, dict):
                continue

            self._extractSchemaFromObj(item, prefix="", itemIndex=i)

        return dict(self._fullSchema)

    def schemaRun(self, segmentDict: str) -> Dict[str, str]:
        schemaDict = self.createSchemaFromData(segmentDict)
        return schemaDict
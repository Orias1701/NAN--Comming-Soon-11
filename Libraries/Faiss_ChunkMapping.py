from typing import Dict, List, Any, Optional, Iterable

# --------- A. Tiện ích cơ bản ---------

def _orderedUniqueChunkIDs(reranked: List[Dict[str, Any]]) -> List[int]:
    seen, ordered = set(), []
    for r in reranked:
        for cid in r.get("chunkIDs", []):
            if isinstance(cid, (int, str)) and str(cid).isdigit():
                cid = int(cid)
                if cid not in seen:
                    seen.add(cid)
                    ordered.append(cid)
    return ordered


def _filterFieldsRecursive(obj: Any, dropLower: set) -> Any:
    """Loại bỏ các field có tên xuất hiện trong dropLower (case-insensitive) trên toàn cấu trúc."""
    if isinstance(obj, dict):
        return {
            k: _filterFieldsRecursive(v, dropLower)
            for k, v in obj.items()
            if k.lower() not in dropLower
        }
    if isinstance(obj, list):
        return [_filterFieldsRecursive(x, dropLower) for x in obj]
    return obj


def _iterValuesNoKeys(obj: Any) -> Iterable[str]:
    """Duyệt đệ quy, chỉ d GIÁ TRỊ (bỏ key), split theo '\n' nếu là chuỗi."""
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _iterValuesNoKeys(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iterValuesNoKeys(item)
    elif isinstance(obj, str):
        for line in obj.splitlines():
            yield line
    else:
        yield str(obj)


def _getByPath(obj: Any, path: str) -> Any:
    """
    Lấy giá trị theo path kiểu 'A.B.C'.
    - Nếu gặp list trong quá trình đi xuống → thu thập giá trị từ từng phần tử (map-collect).
    - Nếu path không tồn tại → trả về None.
    """
    parts = path.split(".")
    def _step(o, idx=0):
        if idx == len(parts):
            return o
        key = parts[idx]
        if isinstance(o, dict):
            if key not in o:
                return None
            return _step(o[key], idx + 1)
        if isinstance(o, list):
            collected = []
            for it in o:
                collected.append(_step(it, idx))
            # gộp phẳng các None
            flat = []
            for v in collected:
                if v is None:
                    continue
                if isinstance(v, list):
                    flat.extend(v)
                else:
                    flat.append(v)
            return flat
        return None
    return _step(obj, 0)


# --------- B. Các hàm chính ---------

def extractChunks(
    reranked: List[Dict[str, Any]],
    segmentDict: List[Dict[str, Any]],
    nChunks: Optional[int] = None,
    dropFields: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    - Lấy chunk theo thứ tự từ reranked.
    - Giới hạn số lượng chunk gốc trả về bằng nChunks (nếu có).
    - Áp dụng bỏ trường theo dropFields (toàn bộ cấu trúc).
    - Kết quả: [{"chunk_id": int, "data": <json đã lọc>}]
    """
    if not reranked:
        return []

    orderedIds = _orderedUniqueChunkIDs(reranked)
    if nChunks is not None:
        orderedIds = orderedIds[:int(nChunks)]

    dropLower = set(x.lower() for x in (dropFields or []))

    out = []
    seen = set()
    for cid in orderedIds:
        if cid in seen:
            continue
        seen.add(cid)
        if 1 <= cid <= len(segmentDict):
            data = segmentDict[cid - 1]
            filtered = _filterFieldsRecursive(data, dropLower) if dropLower else data
            out.append({"chunk_id": cid, "data": filtered})
    return out


def collectChunkText(chunks: List[Dict[str, Any]]) -> str:
    """Biến toàn bộ danh sách chunk thành text (bỏ key, split dòng)."""
    if not chunks:
        return "(Không có chunk nào)"

    lines: List[str] = []
    for ch in chunks:
        for line in _iterValuesNoKeys(ch["data"]):
            lines.append(line)
        lines.append("")
    return "\n".join(lines).strip()


def extractFields(
    chunks: List[Dict[str, Any]],
    fields: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    - Với mỗi chunk gốc, lấy những TRƯỜNG được truyền vào (hỗ trợ path 'A.B.C').
    - Nếu fields=None → lấy TẤT CẢ top-level fields còn lại trong chunk['data'].
    - Trả về list theo từng chunk: {"chunk_id": ..., "fields": {...}}
    """
    results = []
    for ch in chunks:
        data = ch["data"]
        if not isinstance(data, dict):
            results.append({"chunk_id": ch["chunk_id"], "fields": data})
            continue

        if fields is None:
            payload = {k: v for k, v in data.items()}
        else:
            payload = {}
            for f in fields:
                payload[f] = _getByPath(data, f)
        results.append({"chunk_id": ch["chunk_id"], "fields": payload})
    return results


def processChunksPipeline(
    reranked: List[Dict[str, Any]],
    segmentDict: List[Dict[str, Any]],
    dropFields: Optional[List[str]] = None,     # Trường bị bỏ qua (áp dụng toàn bộ)
    fields: Optional[List[str]] = None,          # Trường muốn trích xuất (None → tất cả top-level)
    nChunks: Optional[int] = None               # Số lượng chunk gốc & text (nếu None → tất cả)
) -> Dict[str, Any]:
    """
    Trả về:
      - chunksJson: đúng số lượng chunk gốc (đã dropFields)
      - chunksText: text từ cùng số lượng chunk (bỏ key, split dòng)
      - extractedFields: các trường được chỉ định cho mỗi chunk
    """
    # 1️⃣ Lấy chunk gốc (JSON)
    chunksJson = extractChunks(
        reranked=reranked,
        segmentDict=segmentDict,
        nChunks=nChunks,
        dropFields=dropFields,
    )

    # 2️⃣ Biến thành text (cùng số lượng chunk)
    chunksText = collectChunkText(chunksJson)

    # 3️⃣ Lấy các trường cụ thể
    extractedFields = extractFields(chunksJson, fields=fields)

    return {
        "chunksJson": chunksJson,          # JSON chuẩn
        "chunksText": chunksText,          # text của cùng số lượng chunk
        "extractedFields": extractedFields # field được chọn
    }

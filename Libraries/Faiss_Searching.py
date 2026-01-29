import faiss
import numpy as np

from typing import Dict, List, Any, Optional
from sentence_transformers import SentenceTransformer, CrossEncoder


class SemanticSearchEngine:

    def __init__(
        self,
        indexer: SentenceTransformer,
        reranker: Optional[CrossEncoder] = None,
        device: str = "cuda",
        normalize: bool = True,
        topK: int = 20,
        rerankK: int = 10,
        rerankBatchSize: int = 16,
    ):
        self.device = device
        self.normalize = normalize
        self.topK = int(topK)
        self.rerankK = int(rerankK)
        self.rerankBatchSize = int(rerankBatchSize)

        if not isinstance(indexer, SentenceTransformer):
            raise TypeError("indexer phải là SentenceTransformer đã load sẵn.")
        self._indexer = indexer

        if reranker and not isinstance(reranker, CrossEncoder):
            raise TypeError("reranker phải là CrossEncoder hoặc None.")
        self.reranker = reranker

    # ---------------------------
    # Tiện ích nội bộ
    # ---------------------------
    @staticmethod
    def _l2Normalize(x: np.ndarray, axis: int = 1, eps: float = 1e-12) -> np.ndarray:
        denom = np.linalg.norm(x, axis=axis, keepdims=True)
        denom = np.maximum(denom, eps)
        return x / denom

    @staticmethod
    def _buildIdxMaps(mapping: Dict[str, Any], mapData: Dict[str, Any]):
        """Tạo ánh xạ index→text và index→key"""
        items = mapData.get("items", [])
        idx2text = {int(item["index"]): item.get("text", None) for item in items}
        rawI2k = mapping.get("index_to_key", {})
        idx2key = {int(i): k for i, k in rawI2k.items()}
        return idx2text, idx2key

    # ---------------------------
    # 1️⃣ SEARCH: FAISS vector search
    # ---------------------------
    def search(
        self,
        query: str,
        faissIndex: "faiss.Index",  # type: ignore
        mapping: Dict[str, Any],
        mapData: Dict[str, Any],
        mapChunk: Optional[Dict[str, Any]] = None,
        topK: Optional[int] = None,
        queryEmbedding: Optional[np.ndarray] = None,
    ) -> List[Dict[str, Any]]:
        """
        Trả về:
            [{"index":..., "key":..., "text":..., "faissScore":...}, ...]
        """
        k = int(topK or self.topK)

        if queryEmbedding is None:
            q = self._indexer.encode(
                [query], convert_to_tensor=True, device=str(self.device)
            )
            q = q.detach().cpu().numpy().astype("float32")
        else:
            q = np.asarray(queryEmbedding, dtype="float32")
            if q.ndim == 1:
                q = q[None, :]

        if self.normalize:
            q = self._l2Normalize(q)

        scores, ids = faissIndex.search(q, k)
        idx2text, idx2key = self._buildIdxMaps(mapping, mapData)

        chunkMap = mapChunk.get("index_to_chunk", {}) if mapChunk else {}
        results = []
        for score, idx in zip(scores[0].tolist(), ids[0].tolist()):
            chunkIDs = chunkMap.get(str(idx), [])
            results.append({
                "index": int(idx),
                "key": idx2key.get(int(idx)),
                "text": idx2text.get(int(idx)),
                "faissScore": float(score),
                "chunkIDs": chunkIDs,
            })
        return results

    # ---------------------------
    # 2️⃣ RERANK: CrossEncoder rerank
    # ---------------------------
    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        topK: Optional[int] = None,
        showProgress: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Xếp hạng lại kết quả bằng CrossEncoder (nếu có).
        Trả về danh sách topK kết quả đã rerank.
        """
        if not results:
            return []
        if self.reranker is None:
            raise ValueError("⚠️ Không có reranker được cung cấp khi khởi tạo.")

        k = int(topK or self.rerankK)

        pairs = []
        validIndices = []
        for i, r in enumerate(results):
            text = r.get("text")
            if isinstance(text, str) and text.strip():
                pairs.append([query, text])
                validIndices.append(i)

        if not pairs:
            return []

        scores = self.reranker.predict(
            pairs, batch_size=self.rerankBatchSize, show_progress_bar=showProgress
        )

        for i, s in zip(validIndices, scores):
            results[i]["rerankScore"] = float(s)

        reranked = [r for r in results if "rerankScore" in r]
        reranked.sort(key=lambda x: x["rerankScore"], reverse=True)
        return reranked[:k]

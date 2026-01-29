import re
import numpy as np

from underthesea import sent_tokenize

class ChunkUndertheseaBuilder:
    """
    Bộ tách văn bản tiếng Việt thông minh:
    1 Lọc trước (Extractive): chỉ giữ các câu có ý chính
    2 Gộp sau (Semantic): nhóm các câu trọng tâm theo ngữ nghĩa
    """

    def __init__(self,
                 embedder,
                 device: str = "cpu",
                 minWords: int = 256,
                 maxWords: int = 768,
                 simThreshold: float = 0.7,
                 keySentRatio: float = 0.4):
        if embedder is None:
            raise ValueError("❌ Cần truyền mô hình embedder đã load sẵn.")
        self.embedder = embedder
        self.device = device
        self.minWords = minWords
        self.maxWords = maxWords
        self.simThreshold = simThreshold
        self.keySentRatio = keySentRatio

    # ============================================================
    # 1️⃣ Tách câu
    # ============================================================
    def _splitSentences(self, text: str):
        """Tách câu tiếng Việt (fallback nếu underthesea lỗi)."""
        text = re.sub(r"[\x00-\x1f]+", " ", text)
        try:
            sents = sent_tokenize(text)
        except Exception:
            sents = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sents if len(s.strip()) > 2]

    # ============================================================
    # 2️⃣ Encode an toàn (GPU/CPU fallback)
    # ============================================================
    def _encode(self, sentences):
        try:
            return self.embedder.encode(
                sentences,
                convert_to_numpy=True,
                show_progress_bar=False,
                device=str(self.device)
            )
        except TypeError:
            return self.embedder.encode(sentences, convert_to_numpy=True, show_progress_bar=False)
        except RuntimeError as e:
            if "CUDA" in str(e):
                print("⚠️ GPU OOM, fallback sang CPU.")
                return self.embedder.encode(
                    sentences, convert_to_numpy=True, show_progress_bar=False, device="cpu"
                )
            raise e

    # ============================================================
    # 3️⃣ Lọc ý chính trước (EXTRACTIVE)
    # ============================================================
    def _extractiveFilter(self, sentences):
        """Chọn ra top-k câu đại diện nội dung nhất."""
        if len(sentences) <= 3:
            return sentences

        embeddings = self._encode(sentences)
        meanVec = np.mean(embeddings, axis=0)
        sims = np.dot(embeddings, meanVec) / (
            np.linalg.norm(embeddings, axis=1) * np.linalg.norm(meanVec)
        )

        k = max(1, int(len(sentences) * self.keySentRatio))
        idx = np.argsort(-sims)[:k]
        idx.sort()
        selected = [sentences[i] for i in idx]
        return selected

    # ============================================================
    # 4️⃣ Gộp các câu trọng tâm theo ngữ nghĩa
    # ============================================================
    def _semanticGroup(self, sentences):
        """Gộp các câu đã lọc theo mức tương đồng ngữ nghĩa."""
        if not sentences:
            return []

        embeddings = self._encode(sentences)
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

        chunks, curChunk, curLen = [], [], 0
        for i, sent in enumerate(sentences):
            wc = len(sent.split())
            if not curChunk:
                curChunk.append(sent)
                curLen = wc
                continue

            sim = np.dot(embeddings[i - 1], embeddings[i])
            tooLong = curLen + wc > self.maxWords
            tooShort = curLen < self.minWords
            topicChanged = sim < self.simThreshold

            if tooLong or (not tooShort and topicChanged):
                chunks.append(" ".join(curChunk))
                curChunk = [sent]
                curLen = wc
            else:
                curChunk.append(sent)
                curLen += wc

        if curChunk:
            chunks.append(" ".join(curChunk))
        return chunks

    # ============================================================
    # 5️⃣ Hàm chính build()
    # ============================================================
    def build(self, fullText: str):
        """
        Trả về list chứa {Index, Content} cho từng chunk.
        Quy trình:
            - Lọc câu trọng tâm trước
            - Gộp các câu đã lọc theo ngữ nghĩa
        """
        allSentences = self._splitSentences(fullText)
        print(f"📄 Tổng số câu: {len(allSentences)}")

        filtered = self._extractiveFilter(allSentences)
        print(f"✨ Giữ lại {len(filtered)} câu (~{len(filtered)/len(allSentences):.0%}) sau extractive filter")

        chunks = self._semanticGroup(filtered)
        results = [{"Index": i, "Content": chunk} for i, chunk in enumerate(chunks, start=1)]

        print(f"🔹 Tạo {len(results)} chunk ngữ nghĩa từ {len(filtered)} câu trọng tâm.")
        return results

# ============================================================
# Config/ModelLoader.py  —  Official, unified, complete
# - Manage Encoder/Chunker (SentenceTransformer) and Summarizer (Seq2Seq)
# - Auto-download to local cache when missing
# - GPU/CPU selection with CUDA checks
# - Consistent class-based API
# ============================================================

import os
import torch
from typing import List, Tuple, Optional, Dict, Any

from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM


class ModelLoader:
    """
    Unified model manager:
      - Encoder (SentenceTransformer)
      - Chunker (SentenceTransformer)
      - Summarizer (Seq2Seq: T5/BART/vit5)
    Provides:
      - load_encoder(name, cache)
      - load_chunker(name, cache)
      - load_summarizer(name, cache)
      - summarize(text, max_len, min_len)
      - summarize_batch(texts, max_len, min_len)
      - print_devices()
    """

    # -----------------------------
    # Construction / State
    # -----------------------------
    def __init__(self, preferCuda: bool = True) -> None:
        self.models: Dict[str, Any] = {}
        self.tokenizers: Dict[str, Any] = {}
        self.devices: Dict[str, torch.device] = {}
        self.preferCuda = preferCuda

    # -----------------------------
    # Device helpers
    # -----------------------------
    @staticmethod
    def _cudaCheck() -> None:
        print("CUDA supported:", torch.cuda.is_available())
        print("Number of GPUs:", torch.cuda.device_count())
        if torch.cuda.is_available():
            print("Current GPU:", torch.cuda.get_device_name(0))
            print("Capability:", torch.cuda.get_device_capability(0))
            print("CUDA version (PyTorch):", torch.version.cuda)
            print("cuDNN version:", torch.backends.cudnn.version())
        else:
            print("⚠️ CUDA not available, using CPU.")

    def _getDevice(self) -> torch.device:
        if self.preferCuda and torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")

    @staticmethod
    def _ensureDir(path: Optional[str]) -> None:
        if path:
            os.makedirs(path, exist_ok=True)

    # -----------------------------
    # SentenceTransformer (Encoder/Chunker)
    # -----------------------------
    @staticmethod
    def _ensureCachedSentenceModel(modelName: str, cachePath: str) -> str:
        """
        Ensure SentenceTransformer exists under cachePath.
        Rebuild structure if config missing.
        """
        if not os.path.exists(cachePath):
            print(f"📥 Downloading SentenceTransformer to: {cachePath}")
            model = SentenceTransformer(modelName)
            model.save(cachePath)
            print("✅ Cached SentenceTransformer successfully.")
        else:
            cfg = os.path.join(cachePath, "config_sentence_transformers.json")
            if not os.path.exists(cfg):
                print("⚙️ Rebuilding SentenceTransformer cache structure...")
                tmp = SentenceTransformer(modelName)
                tmp.save(cachePath)
        return cachePath

    def _loadSentenceModel(self, modelName: str, cachePath: Optional[str]) -> Tuple[SentenceTransformer, torch.device]:
        device = self._getDevice()
        print(f"\n🔍 Loading SentenceTransformer ({modelName}) on {device} ...")
        self._cudaCheck()

        if cachePath:
            self._ensureDir(cachePath)
            self._ensureCachedSentenceModel(modelName, cachePath)
            model = SentenceTransformer(cachePath, device=str(device))
            print(f"📂 Loaded from cache: {cachePath}")
        else:
            model = SentenceTransformer(modelName, device=str(device))

        print("✅ SentenceTransformer ready.")
        return model, device

    # Public APIs for SentenceTransformer
    def loadEncoder(self, name: str, cache: Optional[str] = None) -> Tuple[SentenceTransformer, torch.device]:
        model, device = self._loadSentenceModel(name, cache)
        self.models["encoder"] = model
        self.devices["encoder"] = device
        return model, device

    def loadChunker(self, name: str, cache: Optional[str] = None) -> Tuple[SentenceTransformer, torch.device]:
        model, device = self._loadSentenceModel(name, cache)
        self.models["chunker"] = model
        self.devices["chunker"] = device
        return model, device

    # -----------------------------
    # Summarizer (Seq2Seq: T5/BART/vit5)
    # -----------------------------
    @staticmethod
    def _hasHfConfig(cacheDir: str) -> bool:
        return os.path.exists(os.path.join(cacheDir, "config.json"))

    @staticmethod
    def _downloadAndCacheSummarizer(modelName: str, cacheDir: str) -> None:
        """
        Download HF model + tokenizer and save_pretrained to cacheDir.
        """
        print("⚙️ Cache missing — downloading model from Hugging Face...")
        tokenizer = AutoTokenizer.from_pretrained(modelName)
        model = AutoModelForSeq2SeqLM.from_pretrained(modelName)
        os.makedirs(cacheDir, exist_ok=True)
        tokenizer.save_pretrained(cacheDir)
        model.save_pretrained(cacheDir)
        print(f"✅ Summarizer cached at: {cacheDir}")

    def _loadSummarizerCore(self, modelOrDir: str, device: torch.device) -> Tuple[AutoTokenizer, AutoModelForSeq2SeqLM]:
        tokenizer = AutoTokenizer.from_pretrained(modelOrDir)
        model = AutoModelForSeq2SeqLM.from_pretrained(modelOrDir).to(device)
        return tokenizer, model

    def loadSummarizer(self, name: str, cache: Optional[str] = None) -> Tuple[AutoTokenizer, AutoModelForSeq2SeqLM, torch.device]:
        """
        Load Seq2Seq model; auto-download if cache dir missing or invalid.
        """
        device = self._getDevice()
        print(f"\n🔍 Initializing summarizer ({name}) on {device} ...")
        self._cudaCheck()

        if cache:
            self._ensureDir(cache)
            if not self._hasHfConfig(cache):
                self._downloadAndCacheSummarizer(name, cache)
            print("📂 Loading summarizer from local cache...")
            tok, mdl = self._loadSummarizerCore(cache, device)
        else:
            print("🌐 Loading summarizer directly from Hugging Face (no cache dir provided)...")
            tok, mdl = self._loadSummarizerCore(name, device)

        self.tokenizers["summarizer"] = tok
        self.models["summarizer"] = mdl
        self.devices["summarizer"] = device

        print(f"✅ Summarizer ready on {device}")
        return tok, mdl, device

    # -----------------------------
    # Summarization helpers
    # -----------------------------
    @staticmethod
    def _applyVietnamPrefix(text: str, prefix: str, suffix: str) -> str:
        """
        For VietAI/vit5-vietnews: prefix 'vietnews: ' and suffix ' </s>'
        Safe for general T5-family; harmless for BART-family.
        """
        t = (text or "").strip()
        if not t:
            return ""
        return f"{prefix}{t}{suffix}"

    def summarize(self,
                  text: str,
                  maxLen: int = 256,
                  minLen: int = 64,
                  prefix: str = "vietnews: ",
                  suffix: str = " </s>") -> str:
        """
        Summarize a single text with loaded summarizer.
        Raises RuntimeError if summarizer not loaded.
        """
        if "summarizer" not in self.models or "summarizer" not in self.tokenizers:
            raise RuntimeError("❌ Summarizer not loaded. Call loadSummarizer() first.")

        model: AutoModelForSeq2SeqLM = self.models["summarizer"]
        tokenizer: AutoTokenizer = self.tokenizers["summarizer"]
        device: torch.device = self.devices["summarizer"]

        prepared = self._applyVietnamPrefix(text, prefix, suffix)
        if not prepared:
            return ""

        encoding = tokenizer(
            prepared,
            return_tensors="pt",
            truncation=True,
            maxLength=1024
        ).to(device)

        with torch.no_grad():
            outputs = model.generate(
                **encoding,
                maxLength=maxLen,
                minLength=minLen,
                numBeams=4,
                noRepeatNgramSize=3,
                earlyStopping=True
            )

        summary = tokenizer.decode(
            outputs[0],
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True
        )
        return summary

    def summarizeBatch(self,
                        texts: List[str],
                        maxLen: int = 256,
                        minLen: int = 64,
                        prefix: str = "vietnews: ",
                        suffix: str = " </s>") -> List[str]:
        """
        Batch summarization. Processes in a single forward pass when possible.
        """
        if "summarizer" not in self.models or "summarizer" not in self.tokenizers:
            raise RuntimeError("❌ Summarizer not loaded. Call loadSummarizer() first.")

        model: AutoModelForSeq2SeqLM = self.models["summarizer"]
        tokenizer: AutoTokenizer = self.tokenizers["summarizer"]
        device: torch.device = self.devices["summarizer"]

        batch = [self._applyVietnamPrefix(t, prefix, suffix) for t in texts]
        batch = [b for b in batch if b]  # drop empties
        if not batch:
            return []

        encoding = tokenizer(
            batch,
            return_tensors="pt",
            truncation=True,
            maxLength=1024,
            padding=True
        ).to(device)

        summaries: List[str] = []
        with torch.no_grad():
            outputs = model.generate(
                **encoding,
                maxLength=maxLen,
                minLength=minLen,
                numBeams=4,
                noRepeatNgramSize=3,
                earlyStopping=True
            )
        for i in range(outputs.shape[0]):
            dec = tokenizer.decode(
                outputs[i],
                skip_special_tokens=True,
                clean_up_tokenization_spaces=True
            )
            summaries.append(dec)
        return summaries

    # -----------------------------
    # Diagnostics
    # -----------------------------
    def printDevices(self) -> None:
        print("\n📊 Device summary:")
        for key, dev in self.devices.items():
            print(f"  - {key}: {dev}")

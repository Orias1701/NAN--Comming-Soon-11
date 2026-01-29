"""
FastAPI gateway cho appFinal.py.
"""

import os
import time
from typing import Optional, List

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# -------------------------
# 🔒 Bearer token (optional)
# -------------------------

API_SECRET = os.getenv("API_SECRET", "").strip() 

def requireBearer(authorization: Optional[str] = Header(None)):
    """Kiểm tra Bearer token nếu bật API_SECRET."""
    if not API_SECRET:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if token != API_SECRET:
        raise HTTPException(status_code=403, detail="Invalid token")

# -------------------------
# 🧩 Import project modules
# -------------------------
try:
    print("Đang tải appFinal (models, indexes...). Vui lòng chờ...")
    import appFinal as appCalled
    print("✅ Đã load appFinal.")
except Exception as e:
    appCalled = None
    print(f"⚠️ CRITICAL: Không thể import appFinal: {e}")
    raise e

# -------------------------
# 🚀 Init FastAPI
# -------------------------
app = FastAPI(
    title="Document AI API (FastAPI)",
    version="2.0.0",
    description="API xử lý PDF: trích xuất, tóm tắt, tìm kiếm, phân loại.",
)

# Cho phép gọi API từ web client (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # All
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# 🏠 Root endpoint
# -------------------------
@app.get("/")
def root():
    """Trang chào mừng / kiểm tra trạng thái."""
    return {
        "message": "📘 Document AI API đang chạy.",
        "status": "ok",
        "docs": "/docs",
        "appFinal_loaded": bool(appCalled),
    }

# -------------------------
# 🩺 /health
# -------------------------
@app.get("/health")
def health(_=Depends(requireBearer)):
    """Kiểm tra trạng thái hoạt động."""
    appOk = bool(appCalled)
    return {
        "status": "ok",
        "time": time.time(),
        "appFinal_loaded": appOk,
        "main_index_loaded": bool(appCalled.gFaissIndex) if appOk else False,
        "service_index_loaded": bool(appCalled.gServiceFaissIndex) if appOk else False,
    }

# -------------------------
# 📘 /process_pdf
# -------------------------
@app.post("/process_pdf")
async def processPdf(file: UploadFile = File(...), _=Depends(requireBearer)):
    """Nhận file PDF -> chạy processPdfPipeline -> trả về summary + category."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận file PDF.")

    pdfBytes = await file.read()

    if not appCalled or not hasattr(appCalled, "processPdfPipeline"):
        raise HTTPException(status_code=500, detail="Không tìm thấy appFinal.processPdfPipeline().")

    try:
        result = appCalled.processPdfPipeline(pdfBytes)
        return {
            "status": "success",
            "checkstatus": result.get("checkstatus"),
            "summary": result.get("summary"),
            "category": result.get("category"),
        }
    except Exception as e:
        print(f"Lỗi /process_pdf: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý PDF: {str(e)}")

# -------------------------
# 🔍 /search
# -------------------------
class SearchIn(BaseModel):
    query: str
    k: int = 1

@app.post("/search", response_model=List[dict])
def search(body: SearchIn, _=Depends(requireBearer)):
    """Tìm kiếm bằng pipeline searchPipeline (FAISS + Rerank)."""
    q = (body.query or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="query không được để trống")

    if not appCalled or not hasattr(appCalled, "searchPipeline"):
        raise HTTPException(status_code=500, detail="Không tìm thấy appFinal.searchPipeline().")

    try:
        # Gọi hàm pipeline (hàm này giờ trả về List[dict])
        results = appCalled.searchPipeline(q, k=body.k)
        return results # Trả về list các đối tượng chunk
    except Exception as e:
        print(f"Lỗi /search: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi tìm kiếm: {str(e)}")

# -------------------------
# 🧠 /summarize
# -------------------------
class SummIn(BaseModel):
    text: str
    minInput: int = 256
    maxInput: int = 1024
    minLength: int = 100
    maxLength: int = 200

@app.post("/summarize")
def summarizeText(body: SummIn, _=Depends(requireBearer)):
    """Tóm tắt văn bản (dùng cho text bất kỳ)."""
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text không được để trống")

    # Lưu ý: tên biến là summaryEngine (không phải summarizer_engine)
    if not appCalled or not hasattr(appCalled, "summaryEngine"):
        raise HTTPException(status_code=500, detail="Không tìm thấy appFinal.summaryEngine.")

    try:
        # Gọi thẳng vào đối tượng summaryEngine
        summarized = appCalled.summaryEngine.summarize(
            text, 
            minInput=body.minInput, 
            maxInput=body.maxInput,
            minLength=body.minLength,
            maxLength=body.maxLength
        )
        return {"status": "success", "summary": summarized.get("summaryText", "")}
    except Exception as e:
        print(f"Lỗi /summarize: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi tóm tắt: {str(e)}")
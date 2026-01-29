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

def require_bearer(authorization: Optional[str] = Header(None)):
    """Kiểm tra Bearer token nếu bật API_SECRET."""
    if not API_SECRET:
        return  # Không bật xác thực
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if token != API_SECRET:
        raise HTTPException(status_code=403, detail="Invalid token")

# -------------------------
# 🧩 Import project modules
# -------------------------
try:
    # Import file chính của bạn
    print("Đang tải appFinal (models, indexes...). Vui lòng chờ...")
    import appFinal as APP_CALLED
    print("✅ Đã load appFinal.")
except Exception as e:
    APP_CALLED = None
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
        "appFinal_loaded": bool(APP_CALLED),
    }

# -------------------------
# 🩺 /health
# -------------------------
@app.get("/health")
def health(_=Depends(require_bearer)):
    """Kiểm tra trạng thái hoạt động."""
    app_ok = bool(APP_CALLED)
    return {
        "status": "ok",
        "time": time.time(),
        "appFinal_loaded": app_ok,
        "main_index_loaded": bool(APP_CALLED.g_FaissIndex) if app_ok else False,
        "service_index_loaded": bool(APP_CALLED.g_serviceFaissIndex) if app_ok else False,
    }

# -------------------------
# 📘 /process_pdf
# -------------------------
@app.post("/process_pdf")
async def process_pdf(file: UploadFile = File(...), _=Depends(require_bearer)):
    """Nhận file PDF -> chạy process_pdf_pipeline -> trả về summary + category."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận file PDF.")

    pdf_bytes = await file.read()

    if not APP_CALLED or not hasattr(APP_CALLED, "process_pdf_pipeline"):
        raise HTTPException(status_code=500, detail="Không tìm thấy appFinal.process_pdf_pipeline().")

    try:
        # Gọi hàm pipeline chúng ta đã tạo
        result = APP_CALLED.process_pdf_pipeline(pdf_bytes)
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
def search(body: SearchIn, _=Depends(require_bearer)):
    """Tìm kiếm bằng pipeline search_pipeline (FAISS + Rerank)."""
    q = (body.query or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="query không được để trống")

    if not APP_CALLED or not hasattr(APP_CALLED, "search_pipeline"):
        raise HTTPException(status_code=500, detail="Không tìm thấy appFinal.search_pipeline().")

    try:
        # Gọi hàm pipeline (hàm này giờ trả về List[dict])
        results = APP_CALLED.search_pipeline(q, k=body.k)
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
def summarize_text(body: SummIn, _=Depends(require_bearer)):
    """Tóm tắt văn bản (dùng cho text bất kỳ)."""
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text không được để trống")

    # Lưu ý: tên biến là summaryEngine (không phải summarizer_engine)
    if not APP_CALLED or not hasattr(APP_CALLED, "summaryEngine"):
        raise HTTPException(status_code=500, detail="Không tìm thấy appFinal.summaryEngine.")

    try:
        # Gọi thẳng vào đối tượng summaryEngine
        summarized = APP_CALLED.summaryEngine.summarize(
            text, 
            minInput=body.minInput, 
            maxInput=body.maxInput,
            min_length=body.minLength,
            max_length=body.maxLength
        )
        return {"status": "success", "summary": summarized.get("summary_text", "")}
    except Exception as e:
        print(f"Lỗi /summarize: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi tóm tắt: {str(e)}")
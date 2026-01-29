# Cấu trúc thư mục dự án AI (gợi ý)

Cấu trúc này phù hợp cho dự án AI (xử lý tài liệu, RAG, LLM, embedding) và dễ mở rộng.

---

## Cấu trúc tổng quan

```
project_root/
├── .env.example              # Mẫu biến môi trường (không commit secret)
├── .gitignore
├── README.md
├── STRUCTURE.md
├── requirements.txt          # Hoặc requirements_cuda*.yml
├── Dockerfile
├── docker-compose.yml        # (tùy chọn) Orchestrate services
│
├── config/                   # Cấu hình ứng dụng
│   ├── __init__.py
│   ├── config.py             # Load env, constants
│   └── config.json           # Hoặc YAML
│
├── src/                      # Mã nguồn chính (hoặc tên package chính)
│   ├── __init__.py
│   ├── api/                  # API / Web layer
│   │   ├── __init__.py
│   │   ├── routes/
│   │   └── middleware/
│   ├── services/             # Business logic, orchestration
│   │   ├── __init__.py
│   │   └── ...
│   ├── models/               # AI/ML models (loaders, runners)
│   │   ├── __init__.py
│   │   ├── llm/              # LLM load & inference
│   │   ├── embedding/        # Embedding models
│   │   └── summarizer/       # Summarization
│   ├── libraries/            # Core libs: PDF, RAG, FAISS, JSON...
│   │   ├── __init__.py
│   │   ├── rag/
│   │   ├── pdf/
│   │   └── text/
│   └── utils/                # Helpers dùng chung
│       ├── __init__.py
│       └── ...
│
├── data/                     # Dữ liệu (có thể .gitignore hoặc DVC)
│   ├── raw/                  # Dữ liệu thô (PDF, Excel...)
│   ├── processed/            # Đã xử lý (chunks, schema)
│   ├── embeddings/           # Index FAISS, mapping
│   └── datasets/             # Dataset cho train/eval (QA, labeled)
│
├── models_artifacts/         # Trọng số mô hình (GGUF, HuggingFace cache)
│   ├── llm/
│   └── summarizer/
│
├── scripts/                  # Scripts one-off: train, eval, import
│   ├── train.py
│   ├── eval.py
│   └── import_data.py
│
├── notebooks/                # Jupyter: thử nghiệm, EDA, pipeline
│   └── ...
│
├── tests/                    # Unit / integration tests
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   └── integration/
│
├── demo/                     # Frontend demo (HTML/JS) hoặc Streamlit
│   └── ...
│
├── environment/              # Conda/venv specs
│   └── master.yml
│
└── docs/                     # Tài liệu (tùy chọn)
    └── ...
```

---

## Giải thích từng phần

| Thư mục / File | Mục đích |
|----------------|----------|
| **config/** | Cấu hình central: env, đường dẫn, hyperparams. Tách biệt code và config. |
| **src/** | Toàn bộ mã nguồn. `api` = HTTP/entry, `services` = logic nghiệp vụ, `models` = load/inference AI, `libraries` = PDF/RAG/FAISS/JSON. |
| **data/** | Raw, processed, embeddings, datasets. Dễ dùng DVC hoặc .gitignore cho file lớn. |
| **models_artifacts/** | File mô hình (GGUF, HF cache). Thường không commit, chỉ đường dẫn hoặc script tải. |
| **scripts/** | Script chạy tay: train, eval, import. Tách khỏi ứng dụng chính. |
| **notebooks/** | Thử nghiệm, EDA, pipeline từng bước. |
| **tests/** | Unit/integration. Giữ chất lượng khi refactor. |
| **demo/** | Giao diện demo (web/Streamlit) tách khỏi core. |
| **environment/** | Spec môi trường (Conda/venv) để reproduce. |

---

## Ánh xạ nhanh với cấu trúc hiện tại

| Hiện tại | Gợi ý trong STRUCTURE |
|----------|------------------------|
| `Config/` | `config/` |
| `Models/` (LLMS, Summarizer, Utils) | `src/models/` + `models_artifacts/` |
| `Libraries/` | `src/libraries/` |
| `Services/` | `src/services/` |
| `Database/` (HNMU, JSON...) | `data/processed/`, `data/embeddings/`, `data/datasets/` |
| `api.py`, `appFinal.py`, ... | `src/api/` hoặc `scripts/` (tùy vai trò) |
| `Demo/` | `demo/` |
| `Environment/` | `environment/` |
| Notebooks ở root | `notebooks/` |

---

## Ghi chú

- **Single entry point**: Nên có một điểm vào chính (vd: `src/main.py` hoặc `app.py`) gọi API hoặc CLI.
- **Secrets**: Chỉ dùng biến môi trường hoặc vault, không hardcode trong repo.
- **Data & models**: Dùng `.gitignore` hoặc DVC cho `data/`, `models_artifacts/` để repo nhẹ.
- **Python path**: Nếu dùng `src/`, có thể cài package ở chế độ editable: `pip install -e .` (cần `setup.py` hoặc `pyproject.toml`).

Bạn có thể áp dụng từng bước (vd: tạo `src/`, gom `Libraries` vào `src/libraries/`) mà không cần đổi hết một lúc.

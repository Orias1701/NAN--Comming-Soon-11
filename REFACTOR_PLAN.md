# Kế hoạch refactor dự án về cấu trúc mới

Mục đích: **tăng bảo mật**, **dễ đọc**, **dễ bảo trì**, **giữ nguyên toàn bộ tính năng** hiện tại.

Tham chiếu cấu trúc: [STRUCTURE.md](./STRUCTURE.md).

---

## Nguyên tắc thực hiện

1. **Làm từng bước nhỏ**: Mỗi phase có thể commit riêng, chạy lại app và test trước khi sang phase tiếp theo.
2. **Giữ tương thích tạm thời**: Có thể giữ alias/import cũ trong giai đoạn chuyển tiếp (sau đó dọn dẹp).
3. **Bảo mật trước**: Tách secret ra env, không hardcode API key / token / đường dẫn nhạy cảm.
4. **Một entry point**: Cuối cùng chỉ còn một cách chạy app chính (vd: `python -m src` hoặc `uvicorn src.api.app:app`).

---

## Tổng quan các phase

| Phase | Nội dung chính | Rủi ro |
|-------|----------------|--------|
| 0 | Chuẩn bị: .env.example, pyproject.toml, tests skeleton | Thấp |
| 1 | Config: chuyển Config → config, load từ env + file | Trung bình |
| 2 | Data: tạo data/, chuyển đường dẫn Database/Services/Documents/Assets | Trung bình |
| 3 | Models artifacts: tách code (Models/Utils) và artifacts (models_artifacts/) | Trung bình |
| 4 | Tạo src/: libraries, models (loaders/utils), services, api | Cao |
| 5 | Gộp entry: appCalled + appFinal → services, api.py → src.api | Cao |
| 6 | Scripts & notebooks: start, appModel, notebooks | Thấp |
| 7 | Dọn dẹp: xóa code cũ, cập nhật Docker/README | Trung bình |

---

## Phase 0: Chuẩn bị (không đụng logic)

**Mục tiêu**: Có .env.example, pyproject.toml (hoặc setup.py), và khung tests để sau này refactor an toàn.

### Bước 0.1 – `.env.example`

- Tạo file `.env.example` với các biến **không chứa giá trị thật**:
  - `API_SECRET=` (mô tả: secret cho Bearer token)
  - `HOST=0.0.0.0`
  - `PORT=8000`
  - (Sau Phase 1 có thể thêm) `CONFIG_PATH=`, `DATA_ROOT=`, v.v.
- Đảm bảo `.gitignore` đã ignore `.env` (hiện đã có `**/.env*`).

### Bước 0.2 – `pyproject.toml` (hoặc `setup.py`)

- Thêm `pyproject.toml` với:
  - `[project]`: name, version, dependencies (đọc từ requirements.txt).
  - `[build-system]`: setuptools hoặc hatch.
  - (Khi đã có `src/`) `[tool.setuptools.packages.find]` với `where = ["src"]`.
- Mục đích: sau này chạy `pip install -e .` để import package từ `src/` ổn định.

### Bước 0.3 – Skeleton `tests/`

- Tạo `tests/__init__.py`, `tests/conftest.py` (pytest).
- Thêm 1 test đơn giản (vd: test health endpoint hoặc test import config) để CI/checkpoint chạy được.

### Bước 0.4 – Sửa `start.sh` (Docker)

- Hiện `start.sh` gọi `uvicorn app:app`; trong repo đang dùng `api:app`. Đổi thành `api:app` (và đúng port nếu cần) để Docker chạy đúng ứng dụng hiện tại. Sau refactor sẽ đổi lại thành module mới (vd: `src.api.app:app`).

**Checkpoint Phase 0**: `pytest tests/` chạy qua; `uvicorn api:app` và Docker vẫn hoạt động như cũ.

---

## Phase 1: Config tập trung và bảo mật

**Mục tiêu**: Một nơi đọc cấu hình; secret và đường dẫn nhạy cảm từ env; dễ đổi môi trường.

### Bước 1.1 – Đổi tên thư mục `Config` → `config`

- Đổi `Config/` thành `config/` (chữ thường, chuẩn Python).
- Cập nhật mọi import: `from Config import ...` → `from config import ...` (hoặc dùng alias tạm `import config as Config` nếu muốn đổi từ từ).

### Bước 1.2 – Tách nội dung cấu hình

- **config/config.py** (hoặc tên tương đương):
  - Đọc biến môi trường: `API_SECRET`, `DATA_ROOT` (optional), `CONFIG_PATH` (optional).
  - Hàm `get_config()` (hoặc `ConfigValues()`) chỉ trả về dict từ file (Config.json hoặc config.json) + override bằng env.
  - Không hardcode secret; không ghi path tuyệt đối máy cá nhân.
- **config/config.json** (hoặc Config.json):
  - Chỉ chứa cấu hình không nhạy cảm: tên model, cấu trúc thư mục tương đối, default port.
  - Đường dẫn gốc data/models có thể đọc từ env (vd: `DATA_ROOT`, `MODELS_DIR`).

### Bước 1.3 – Configs.py → config module

- Chuyển logic trong `Config/Configs.py` vào `config/config.py`:
  - Base path lấy từ env (vd: `os.getenv("DATA_ROOT", ".")`) rồi nối với `Database`, `Services`, `Documents`, `Assets`.
  - Model names (EMBEDD_MODEL, RERANK_MODEL, …) đọc từ config file hoặc env.
- Giữ key trả về tương thích với hiện tại (pdfPath, faissPath, …) để appCalled/appFinal không vỡ.

### Bước 1.4 – ModelLoader và config.json (appModel)

- `appModel.py` đang đọc `Config/config.json`. Chuyển sang đọc từ `config/config.json` và base path từ env (vd: `BASE_PATH` hoặc `MODELS_DIR`).
- Đường dẫn Docker Desktop (appModel) nên đọc từ env (vd: `DOCKER_DESKTOP_PATH`) thay vì hardcode `C:\...`.

**Checkpoint Phase 1**: Gọi `ConfigValues()` (hoặc get_config()) trả về đúng đường dẫn; API_SECRET lấy từ env; app chạy bình thường với config mới.

---

## Phase 2: Thư mục Data thống nhất

**Mục tiêu**: Dữ liệu nằm dưới `data/` (raw, processed, embeddings, datasets); code chỉ tham chiếu qua config.

### Bước 2.1 – Tạo cấu trúc `data/`

- Tạo:
  - `data/raw/` (tương đương Documents, file PDF gốc).
  - `data/processed/` (chunks, schema, segment – tương đương Database/HNMU, Database/HNMU_Merged, Services/Categories).
  - `data/embeddings/` (index FAISS, mapping, mapData, mapChunk – có thể gộp với processed nếu bạn muốn đơn giản).
  - `data/datasets/` (dataset QA, labeled – tương đương Database/HNMU/dataset_qa.json, v.v.).
- Có thể gộp `processed` và `embeddings` thành một thư mục nếu cấu trúc hiện tại đang gộp.

### Bước 2.2 – Ánh xạ đường dẫn trong config

- Trong `config/config.py`, base path = `os.getenv("DATA_ROOT", "./data")`.
  - `pdfPath` → `{DATA_ROOT}/raw/{pdfname}.pdf`
  - Các path Database/HNMU → `{DATA_ROOT}/processed/HNMU/...` (hoặc `data/processed/...` theo cấu trúc bạn chọn).
  - Services/Categories → `{DATA_ROOT}/processed/Categories/...` hoặc tương đương.
- Assets (exceptions, markers, status): có thể `data/assets/` hoặc `config/assets/` và đọc từ config.

### Bước 2.3 – Di chuyển file (tùy chọn từ từ)

- Copy (không xóa ngay) nội dung từ `Database/`, `Services/` (phần JSON/FAISS), `Documents/`, `Assets/` vào `data/` theo cấu trúc mới.
- Trong config, tạm thời trỏ vào thư mục mới; nếu ổn định thì xóa bản cũ hoặc bỏ qua bản cũ trong .gitignore.

### Bước 2.4 – .gitignore

- Đảm bảo `data/` (hoặc từng con) có thể ignore nếu không muốn commit dữ liệu lớn; có thể dùng `data/**/*.faiss`, `data/**/*.json` (tùy nhu cầu).

**Checkpoint Phase 2**: Config trỏ đúng `data/`; app load được index và segment; search & process_pdf vẫn hoạt động.

---

## Phase 3: Tách code Models và artifacts

**Mục tiêu**: Code load model (Utils) nằm trong package; file mô hình (GGUF, HuggingFace cache) nằm trong `models_artifacts/`.

### Bước 3.1 – Tạo `models_artifacts/`

- Tạo `models_artifacts/llm/`, `models_artifacts/summarizer/`, `models_artifacts/embedding/` (hoặc gộp nếu bạn muốn).
- Trong config, thêm (hoặc dùng env) `MODELS_ARTIFACTS_DIR` mặc định `./models_artifacts`.

### Bước 3.2 – Cập nhật config và ModelLoader

- Đường dẫn cache SentenceTransformer / Summarizer / LLM đọc từ config, base = `MODELS_ARTIFACTS_DIR` (hoặc giữ tên `Models/` nhưng nằm ngoài repo bằng .gitignore).
- `Config/ModelLoader.py` (sẽ nằm trong `config/` hoặc `src/models/`) chỉ nhận path qua tham số hoặc config, không hardcode `Models/`.

### Bước 3.3 – Di chuyển code trong `Models/`

- Chỉ **code** (Utils): `Models/Utils/` → sẽ chuyển vào `src/models/utils/` ở Phase 4.
- **Artifacts** (file .gguf, thư mục summarizer, sentence_transformers): di chuyển vật lý vào `models_artifacts/` hoặc trỏ config vào đó; .gitignore đã ignore `**/Models/*`, cần thêm rule cho `models_artifacts/` nếu không commit file nặng.

**Checkpoint Phase 3**: ModelLoader load được encoder/summarizer từ đường dẫn mới; appModel (Docker LLM) vẫn chạy với đường dẫn GGUF mới.

---

## Phase 4: Tạo package `src/`

**Mục tiêu**: Toàn bộ mã nguồn nằm trong `src/` với cấu trúc rõ ràng: api, services, models, libraries, utils.

### Bước 4.1 – Tạo cây thư mục `src/`

- Tạo:
  - `src/__init__.py`
  - `src/api/__init__.py`
  - `src/services/__init__.py`
  - `src/models/__init__.py`, `src/models/llm/`, `src/models/embedding/`, `src/models/summarizer/` (nếu cần tách), `src/models/utils/`
  - `src/libraries/__init__.py`, và các subpackage: `src/libraries/rag/`, `src/libraries/pdf/`, `src/libraries/text/` (hoặc giữ tên file giống hiện tại: faiss, json, common, summarizer).
  - `src/utils/__init__.py`

### Bước 4.2 – Chuyển `Libraries/` → `src/libraries/`

- Copy (hoặc move) từng file trong `Libraries/` vào `src/libraries/`.
  - Đổi import nội bộ: `from . import Common_MyUtils` giữ nguyên; import từ Config → `from config import ...` hoặc relative.
  - Trong các file dùng `from . import X`, kiểm tra lại path.
- Trong `src/libraries/__init__.py`, re-export các module cần dùng bên ngoài (hoặc để từng chỗ import trực tiếp `from src.libraries import ...`).

### Bước 4.3 – Chuyển `Models/Utils/` → `src/models/utils/`

- Copy `Common_ModelLoader.py`, `Common_DockerRun.py` vào `src/models/utils/`.
- Cập nhật import: từ `Libraries` → `from src.libraries import ...` (hoặc `from ..libraries` nếu cùng package).

### Bước 4.4 – Chuyển `Config/` (đã là config) và ModelLoader

- `config/` giữ ở root (chuẩn nhiều dự án) hoặc copy vào `src/config/` nếu muốn mọi thứ trong src. Khuyến nghị: **giữ config ở root** để env và path ít phụ thuộc package.
- `Config/ModelLoader.py` đã nằm trong config (Phase 1); nếu muốn gom vào src thì đặt thành `src/models/loader.py` và dùng config chỉ để lấy path.

### Bước 4.5 – Cài package và import

- Chạy `pip install -e .` (pyproject.toml đã cấu hình).
- Thay mọi `from Libraries import ...` bằng `from src.libraries import ...` (hoặc tên tương ứng).
- Thay `from Config import Configs` bằng `from config import config` (hoặc tên bạn chọn).
- Thay `from Models.Utils import ...` bằng `from src.models.utils import ...`.

**Checkpoint Phase 4**: Import từ `src.*` thành công; có thể tạm thời giữ song song file cũ (Libraries, Config, Models/Utils) và import từ src trong api/appFinal/appCalled để test; khi ổn thì xóa code cũ.

---

## Phase 5: Gộp entry và tách lớp API / Services

**Mục tiêu**: Một ứng dụng FastAPI trong `src/api/`; logic nghiệp vụ (pipeline) trong `src/services/`; không còn import trực tiếp appFinal/appCalled từ root.

### Bước 5.1 – Tạo `src/services/document_service.py` (hoặc tên tương ứng)

- Chuyển toàn bộ logic từ `appCalled.py` vào service:
  - Load config một lần (từ config module).
  - Khởi tạo model (ModelLoader), FAISS, reranker, summarizer, v.v.
  - Các hàm: `read_data`, `pre_read_pdf`, `run_search`, `run_rerank`, `chunk_map`, `merge_by_text`, `summary_run`, `process_pdf_pipeline`, `search_pipeline`, `summarize_pipeline`.
- Trả về kết quả dạng dict/list rõ ràng; không phụ thuộc biến global ngoài service.

### Bước 5.2 – Tạo `src/services/pipeline.py` (hoặc gộp vào document_service)

- Logic hiện tại trong `appFinal.py`: `classifyDocument`, load hai index (main + Categories), gọi `processPdfPipeline`, `searchPipeline`, `summarizePipeline`.
- Service nhận dependency (document_service) và config; expose các hàm pipeline cho API gọi.

### Bước 5.3 – Tạo `src/api/app.py`

- Chuyển nội dung `api.py` vào `src/api/app.py`:
  - Import từ `src.services` thay vì `import appFinal`.
  - FastAPI app, CORS, requireBearer (API_SECRET từ env), các route: `/`, `/health`, `/process_pdf`, `/search`, `/summarize`.
  - Khởi tạo service (lazy hoặc tại startup) và gọi `processPdfPipeline`, `searchPipeline`, `summarizePipeline` từ service.

### Bước 5.4 – Entry point chính

- Ở root: `main.py` hoặc `run.py` chỉ chứa:
  - `uvicorn.run("src.api.app:app", host=..., port=...)`
- Hoặc trong `pyproject.toml`: `[project.scripts]` với một entry point gọi uvicorn.
- `start.py` đổi thành gọi entry point mới (và vẫn mở browser nếu cần).

### Bước 5.5 – Cập nhật health và dependency

- `/health` lấy trạng thái từ service (index đã load chưa) thay vì `appFinal.gFaissIndex`.
- Kiểm tra Bearer token và CORS vẫn hoạt động; không lộ API_SECRET trong log hay response.

**Checkpoint Phase 5**: Chạy `uvicorn src.api.app:app` (hoặc qua main.py); Demo gọi API bình thường; process_pdf, search, summarize trả đúng kết quả.

---

## Phase 6: Scripts và notebooks

**Mục tiêu**: Script one-off và notebook tách khỏi core; dễ tìm và chạy.

### Bước 6.1 – Scripts

- `appModel.py` (khởi động Docker LLM): chuyển vào `scripts/start_llm_server.py` (hoặc tên tương ứng). Đọc config từ `config/` và env (DOCKER_DESKTOP_PATH, v.v.).
- `start.py`: có thể giữ ở root hoặc chuyển thành `scripts/run_web.py`; nội dung gọi uvicorn với module mới.

### Bước 6.2 – Notebooks

- Di chuyển `_PDFProcess.ipynb`, `_SumTrainer.ipynb`, `Database/JsonProcess.ipynb`, `Database/HNMU/gen.ipynb` vào `notebooks/`.
- Cập nhật đường dẫn trong notebook (data/, config/) để chạy đúng sau refactor.

### Bước 6.3 – Demo

- Giữ `demo/` ở root (hoặc đổi tên thành `Demo` → `demo` cho nhất quán). Cập nhật URL API nếu đổi port hoặc path.

**Checkpoint Phase 6**: Scripts chạy từ `scripts/`; notebooks chạy được với đường dẫn mới; demo gọi API thành công.

---

## Phase 7: Dọn dẹp và bảo mật cuối

**Mục tiêu**: Xóa code/ file cũ; cập nhật Docker và tài liệu; kiểm tra bảo mật.

### Bước 7.1 – Xóa code cũ

- Xóa (sau khi đã chắc chắn không dùng):
  - `appCalled.py`, `appFinal.py`, `api.py` ở root (đã chuyển vào src).
  - Thư mục `Libraries/`, `Config/` (đã chuyển config + src), `Models/Utils/` (đã chuyển vào src).
- Giữ `Models/` chỉ nếu vẫn trỏ tới artifacts; nếu đã chuyển hết sang `models_artifacts/` thì có thể xóa hoặc để trống và .gitignore.

### Bước 7.2 – Cập nhật Docker và start

- Dockerfile: COPY và CMD trỏ tới code mới (vd: `CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "7860"]`).
- start.sh: dùng module mới và đúng app (đã sửa ở Phase 0).
- Biến env trong Docker: API_SECRET, DATA_ROOT, CONFIG_PATH (nếu có) qua env hoặc Secrets, không ghi trong Dockerfile.

### Bước 7.3 – README và STRUCTURE

- README: hướng dẫn cài (`pip install -e .`), biến env (.env.example), cách chạy (entry point, scripts), Docker.
- STRUCTURE.md: cập nhật nếu có thay đổi so với bản đầu.

### Bước 7.4 – Kiểm tra bảo mật

- Không còn secret trong repo (grep API_SECRET, token, password).
- API_SECRET bắt buộc từ env khi bật bảo vệ; CORS cấu hình rõ (tránh allow_origins=["*"] ở production nếu có thể).
- File cấu hình không chứa path tuyệt đối máy cá nhân hoặc token.

**Checkpoint Phase 7**: Repo sạch; Docker build và chạy đúng; README đủ để người mới clone và chạy; pytest (và manual test) pass.

---

## Bảng theo dõi nhanh

| Phase | Trạng thái | Ghi chú |
|-------|------------|--------|
| 0 | ⬜ Chưa làm | Chuẩn bị env, pyproject, tests, sửa start.sh |
| 1 | ⬜ Chưa làm | Config → config, env, bảo mật |
| 2 | ⬜ Chưa làm | data/, đường dẫn |
| 3 | ⬜ Chưa làm | models_artifacts, tách code/artifacts |
| 4 | ⬜ Chưa làm | src/, libraries, models/utils |
| 5 | ⬜ Chưa làm | services, api, entry point |
| 6 | ⬜ Chưa làm | scripts, notebooks, demo |
| 7 | ⬜ Chưa làm | Dọn dẹp, Docker, README, bảo mật |

---

## Rủi ro và cách xử lý

- **Import vỡ sau khi đổi thư mục**: Mỗi phase xong chạy full flow (load app → gọi vài API). Có thể giữ file cũ và import từ cả hai nơi tạm thời.
- **Đường dẫn sai (data/models)**: Dùng config + env; log ra path khi khởi động để dễ debug.
- **Docker khác môi trường local**: Kiểm tra CMD và env trong Dockerfile; test build và chạy container trước khi đóng phase 7.
- **Bảo mật**: Mỗi phase kiểm tra không thêm secret vào file commit; dùng .env.example làm checklist.

Khi hoàn thành từng phase, cập nhật bảng trạng thái và checkpoint để dễ rollback hoặc tạm dừng giữa chừng.

import sys, os
import time
import subprocess

from pathlib import Path

from Libraries import Common_MyUtils as MU
from Models.Utils import Common_ModelLoader as ML, Common_DockerRun as DR

DOCKER_PATH = r"C:\Program Files\Docker\Docker\Docker Desktop.exe"

BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
CONFIG = BASE/"Config"/"config.json"
cfg = MU.readJson(CONFIG)

model_dir = cfg['paths']['local_model_dir']
model_typ = cfg['paths']['local_model_typ']
publisher = cfg['models']['responding_model']['publisher']
model_name = cfg['models']['responding_model']['model_name']
model_file = cfg['models']['responding_model']['model_file']

LLMS_LOCAT = f"{model_dir}/{model_typ}"
MODEL_REPO = f"{publisher}/{model_name}"
MODEL_FILE = f"{model_file}"
LLMS_DIR = Path(BASE/LLMS_LOCAT/MODEL_REPO)
LLMS_DIR.mkdir(parents=True, exist_ok=True)
LLMS_PATH = LLMS_DIR / MODEL_FILE

PORT = "8080"
IMAGE = "ghcr.io/ggerganov/llama.cpp:server-cuda"
SERVER_URL = f"http://localhost:{PORT}"
CONTAINER = "local-llama-gpu"

ML.modelLoad(LLMS_PATH, MODEL_REPO, MODEL_FILE, LLMS_DIR)
DR.dockerEnsure(DOCKER_PATH)

os.system(f"docker rm -f {CONTAINER} >nul 2>&1")

cmd = (
    f'docker run --gpus all --name {CONTAINER} -p {PORT}:8080 '
    f'-e GGML_CUDA=1 -e GGML_CUDA_FORCE_MMQ=1 -e GGML_CUDA_SCRATCH_SIZE_MB=4096 '
    f'-v "{LLMS_DIR}:/models" {IMAGE} '
    f'--model /models/{MODEL_FILE} --n-gpu-layers 999 --ctx-size 4096'
)

sc_msg = f"""
✅ Llama server started!
URL: http://localhost:{PORT}
Model: {MODEL_FILE}
Press Ctrl+C to stop!
"""

print("🚀 Starting Llama server...")
subprocess.Popen(cmd, shell=True)
time.sleep(3)

print(sc_msg)
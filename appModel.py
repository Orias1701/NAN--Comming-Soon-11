import sys, os
import time
import subprocess

from pathlib import Path

from Libraries import Common_MyUtils as MU
from Models.Utils import Common_ModelLoader as ML, Common_DockerRun as DR

dockerPath = r"C:\Program Files\Docker\Docker\Docker Desktop.exe"

base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
config = base/"Config"/"config.json"
cfg = MU.readJson(config)

modelDir = cfg['paths']['local_model_dir']
modelTyp = cfg['paths']['local_model_typ']
publisher = cfg['models']['responding_model']['publisher']
modelName = cfg['models']['responding_model']['model_name']
modelFile = cfg['models']['responding_model']['model_file']

llmsLocat = f"{modelDir}/{modelTyp}"
modelRepo = f"{publisher}/{modelName}"
modelFile = f"{modelFile}"
llmsDir = Path(base/llmsLocat/modelRepo)
llmsDir.mkdir(parents=True, exist_ok=True)
llmsPath = llmsDir / modelFile

port = "8080"
image = "ghcr.io/ggerganov/llama.cpp:server-cuda"
serverUrl = f"http://localhost:{port}"
container = "local-llama-gpu"

ML.modelLoad(llmsPath, modelRepo, modelFile, llmsDir)
DR.dockerEnsure(dockerPath)

os.system(f"docker rm -f {container} >nul 2>&1")

cmd = (
    f'docker run --gpus all --name {container} -p {port}:8080 '
    f'-e GGML_CUDA=1 -e GGML_CUDA_FORCE_MMQ=1 -e GGML_CUDA_SCRATCH_SIZE_MB=4096 '
    f'-v "{llmsDir}:/models" {image} '
    f'--model /models/{modelFile} --n-gpu-layers 999 --ctx-size 4096'
)

scMsg = f"""
✅ Llama server started!
URL: http://localhost:{port}
Model: {modelFile}
Press Ctrl+C to stop!
"""

print("🚀 Starting Llama server...")
subprocess.Popen(cmd, shell=True)
time.sleep(3)

print(scMsg)
import os
import tempfile
import logging

from fastapi import FastAPI, UploadFile, File, HTTPException
from markitdown import MarkItDown
from openai import OpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("markitdown-svc")

app = FastAPI(title="markitdown-svc")

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://ollama.ollama.svc.cluster.local:11434/v1")
OLLAMA_VISION_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")
OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY", "ollama")  # value is ignored by Ollama, required by the SDK
ENABLE_PLUGINS = os.environ.get("ENABLE_PLUGINS", "true").lower() == "true"
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "100"))

llm_client = OpenAI(base_url=OLLAMA_BASE_URL, api_key=OLLAMA_API_KEY)

md = MarkItDown(
    enable_plugins=ENABLE_PLUGINS,
    llm_client=llm_client,
    llm_model=OLLAMA_VISION_MODEL,
)

logger.info(
    "markitdown-svc starting | ollama_base_url=%s vision_model=%s plugins=%s",
    OLLAMA_BASE_URL, OLLAMA_VISION_MODEL, ENABLE_PLUGINS,
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/convert")
async def convert(file: UploadFile = File(...)):
    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_MB:
        raise HTTPException(status_code=413, detail=f"File exceeds {MAX_UPLOAD_MB}MB limit")

    suffix = os.path.splitext(file.filename or "")[1]
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        result = md.convert(tmp_path)
        return {
            "filename": file.filename,
            "markdown": result.text_content,
        }
    except Exception as exc:
        logger.exception("conversion failed for %s", file.filename)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

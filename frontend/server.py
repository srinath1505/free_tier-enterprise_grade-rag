import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse

app = FastAPI()

STATIC_DIR = Path(__file__).parent / "static"

_base = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
BACKEND_URL = _base if _base.endswith("/api/v1") else f"{_base}/api/v1"


@app.get("/api/config")
def get_config():
    return {"backend_url": BACKEND_URL}


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    candidate = STATIC_DIR / full_path
    if candidate.is_file():
        return FileResponse(str(candidate))
    return FileResponse(str(STATIC_DIR / "index.html"))
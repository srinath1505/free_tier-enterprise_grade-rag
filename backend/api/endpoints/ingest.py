import os
import shutil
from pathlib import Path
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request, status
from pydantic import BaseModel
from backend.core.config import settings
from backend.core.limiter import limiter
from backend.security.auth import get_current_admin_user
from ingestion.ingest import ingest_data_directory
from ingestion.loaders.pdf import PDFLoader
from ingestion.loaders.docx import DOCXLoader
from ingestion.loaders.txt import TXTLoader
from ingestion.chunker import SemanticChunker

router = APIRouter()

DATA_DIR = os.path.join(settings.BASE_DIR, "data")
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}
LOADER_MAP = {".pdf": PDFLoader, ".docx": DOCXLoader, ".txt": TXTLoader}


def _safe_filename(filename: str) -> str:
    """Strip path components and return just the base filename."""
    return Path(filename).name


def _validate_upload(filename: str, content_type: str, size_bytes: int) -> None:
    """Raise HTTPException for any invalid upload before it touches disk."""
    safe_name = _safe_filename(filename)
    if not safe_name:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    ext = Path(safe_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported content type '{content_type}'.",
        )

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if size_bytes > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size_bytes / 1024 / 1024:.1f} MB). Maximum allowed size is {settings.MAX_UPLOAD_SIZE_MB} MB.",
        )


class FileInfo(BaseModel):
    filename: str
    size: float  # KB


@router.get("/files", response_model=List[FileInfo])
async def list_files(current_user: dict = Depends(get_current_admin_user)):
    if not os.path.exists(DATA_DIR):
        return []
    files = []
    for f in os.listdir(DATA_DIR):
        file_path = os.path.join(DATA_DIR, f)
        if os.path.isfile(file_path):
            files.append(FileInfo(filename=f, size=round(os.path.getsize(file_path) / 1024, 2)))
    return files


@router.post("/upload")
@limiter.limit(f"{settings.RATE_LIMIT_UPLOAD_PER_MIN}/minute")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_admin_user),
):
    # Read content into memory first so we can validate before touching disk
    content = await file.read()

    _validate_upload(file.filename, file.content_type, len(content))

    safe_name = _safe_filename(file.filename)
    os.makedirs(DATA_DIR, exist_ok=True)
    file_path = os.path.join(DATA_DIR, safe_name)

    with open(file_path, "wb") as f:
        f.write(content)

    ext = Path(safe_name).suffix.lower()
    try:
        loader = LOADER_MAP[ext](file_path)
        raw_docs = loader.load()

        chunker = SemanticChunker()
        chunked_docs = chunker.chunk(raw_docs)

        if chunked_docs:
            from backend.api.endpoints.rag import get_vector_store, get_retriever
            vs = get_vector_store()
            texts = [d["content"] for d in chunked_docs]
            metadatas = [{**d["metadata"], "content": d["content"]} for d in chunked_docs]
            vs.add_documents(texts, metadatas)
            get_retriever()._rebuild_bm25()

        return {
            "message": "File uploaded and ingested successfully",
            "filename": safe_name,
            "chunks": len(chunked_docs),
        }
    except HTTPException:
        raise
    except Exception as e:
        # File was saved but ingestion failed — remove it to avoid orphaned files
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed: {str(e)}. File has been removed.",
        )


@router.delete("/files/{filename}")
async def delete_file(filename: str, current_user: dict = Depends(get_current_admin_user)):
    safe_name = _safe_filename(filename)
    file_path = os.path.join(DATA_DIR, safe_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    os.remove(file_path)
    return {"message": f"File '{safe_name}' deleted. Rebuild the index to purge its vectors."}


@router.post("/rebuild")
async def rebuild_index(current_user: dict = Depends(get_current_admin_user)):
    if os.path.exists(settings.VECTOR_STORE_PATH):
        shutil.rmtree(settings.VECTOR_STORE_PATH)
        os.makedirs(settings.VECTOR_STORE_PATH)
    ingest_data_directory(DATA_DIR)
    # Reload the in-process singletons so queries immediately reflect the new index
    from backend.api.endpoints.rag import get_retriever
    get_retriever().reload()
    return {"message": "Index rebuilt successfully"}

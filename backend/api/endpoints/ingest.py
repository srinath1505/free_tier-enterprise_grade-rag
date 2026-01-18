import os
import shutil
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, status
from pydantic import BaseModel
from backend.core.config import settings
from backend.security.auth import get_current_admin_user
from ingestion.ingest import ingest_data_directory
# We might want to expose a specific file ingest function later, for now we re-ingest or add to existing
from ingestion.loaders.pdf import PDFLoader
from ingestion.loaders.docx import DOCXLoader
from ingestion.loaders.txt import TXTLoader
from ingestion.chunker import SemanticChunker
from backend.engine.vector_store import VectorStore

router = APIRouter()

DATA_DIR = os.path.join(settings.BASE_DIR, "data")

class FileInfo(BaseModel):
    filename: str
    size: float # KB

@router.get("/files", response_model=List[FileInfo])
async def list_files(current_user: dict = Depends(get_current_admin_user)):
    """List all files in the data directory."""
    if not os.path.exists(DATA_DIR):
        return []
    
    files = []
    for f in os.listdir(DATA_DIR):
        file_path = os.path.join(DATA_DIR, f)
        if os.path.isfile(file_path):
            size_kb = os.path.getsize(file_path) / 1024
            files.append(FileInfo(filename=f, size=round(size_kb, 2)))
    return files

@router.post("/upload")
async def upload_file(file: UploadFile = File(...), current_user: dict = Depends(get_current_admin_user)):
    """Upload a file and ingest it immediately."""
    file_path = os.path.join(DATA_DIR, file.filename)
    
    # Save file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Trigger Single File Ingestion (Optimization: Don't re-ingest everything)
    try:
        # 1. Load
        ext = os.path.splitext(file_path)[1].lower()
        loader_cls = None
        if ext == '.pdf': loader_cls = PDFLoader
        elif ext == '.docx': loader_cls = DOCXLoader
        elif ext == '.txt': loader_cls = TXTLoader
        
        if not loader_cls:
            return {"message": f"File saved, but extension {ext} not supported for ingestion.", "filename": file.filename}

        loader = loader_cls(file_path)
        raw_docs = loader.load()
        
        # 2. Chunk
        chunker = SemanticChunker()
        chunked_docs = chunker.chunk(raw_docs)
        
        # 3. Embed & Add
        if chunked_docs:
            vector_store = VectorStore()
            texts = [d['content'] for d in chunked_docs]
            metadatas = []
            for d in chunked_docs:
                meta = d['metadata'].copy()
                meta['content'] = d['content']
                metadatas.append(meta)
            vector_store.add_documents(texts, metadatas)
            
        return {"message": "File uploaded and ingested successfully", "filename": file.filename, "chunks": len(chunked_docs)}
        
    except Exception as e:
        # Fallback: file is saved, but ingestion failed
        return {"message": f"File saved, but ingestion failed: {str(e)}", "filename": file.filename}

@router.delete("/files/{filename}")
async def delete_file(filename: str, current_user: dict = Depends(get_current_admin_user)):
    """Delete a file from disk. Note: vectors remain until rebuild."""
    file_path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    os.remove(file_path)
    return {"message": f"File {filename} deleted. Please rebuild index to purge vectors."}

@router.post("/rebuild")
async def rebuild_index(current_user: dict = Depends(get_current_admin_user)):
    """Wipes the Vector Store and re-ingests all files in data/."""
    # 1. Delete existing index
    if os.path.exists(settings.VECTOR_STORE_PATH):
        import shutil
        shutil.rmtree(settings.VECTOR_STORE_PATH)
        os.makedirs(settings.VECTOR_STORE_PATH)
        
    # 2. Re-run Ingestion
    ingest_data_directory(DATA_DIR)
    
    return {"message": "Index rebuilt successfully"}

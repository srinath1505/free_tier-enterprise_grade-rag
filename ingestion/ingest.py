import os
import sys
import glob
from typing import List

# Ensure project root in path to allow imports from backend and ingestion
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.loaders.pdf import PDFLoader
from ingestion.loaders.docx import DOCXLoader
from ingestion.loaders.txt import TXTLoader
from ingestion.chunker import SemanticChunker
from backend.engine.vector_store import VectorStore
from backend.core.config import settings

# Map extensions to loaders
LOADERS = {
    '.pdf': PDFLoader,
    '.docx': DOCXLoader,
    '.txt': TXTLoader
}

def ingest_data_directory(data_dir: str = "data"):
    print(f"Starting ingestion from: {data_dir}")
    
    # 1. Gather files
    files = []
    for ext in LOADERS.keys():
        found = glob.glob(os.path.join(data_dir, f"*{ext}"))
        files.extend(found)
    
    if not files:
        print("No compatible files found in data/ directory.")
        return

    print(f"Found {len(files)} files.")
    
    # 2. Load Documents
    raw_docs = []
    for file_path in files:
        ext = os.path.splitext(file_path)[1].lower()
        loader_cls = LOADERS.get(ext)
        if loader_cls:
            print(f"Loading {os.path.basename(file_path)}...")
            loader = loader_cls(file_path)
            raw_docs.extend(loader.load())

    print(f"Loaded {len(raw_docs)} source documents.")
    
    # 3. Chunk Documents
    print("Chunking documents...")
    chunker = SemanticChunker()
    chunked_docs = chunker.chunk(raw_docs)
    print(f"Created {len(chunked_docs)} chunks.")
    
    if not chunked_docs:
        print("No content to ingest.")
        return

    # 4. Embed and Store
    print("Embedding and Storing in Vector Store...")
    vector_store = VectorStore()
    
    texts = [d['content'] for d in chunked_docs]
    metadatas = []
    for d in chunked_docs:
        meta = d['metadata'].copy()
        meta['content'] = d['content'] # STORE CONTENT IN METADATA FOR RETRIEVAL
        metadatas.append(meta)
    
    # Batch add if needed, FAISS wrapper handles arrays
    # Add a unique ID to metadata if not present (simple hash)
    # for i, m in enumerate(metadatas):
    #     m['chunk_id'] = i
        
    vector_store.add_documents(texts, metadatas)
    print("Ingestion Complete!")

if __name__ == "__main__":
    # Ensure project root in path if run directly
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ingest_data_directory()

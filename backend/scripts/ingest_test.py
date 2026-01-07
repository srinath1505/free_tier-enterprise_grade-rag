import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.engine.vector_store import VectorStore
from backend.core.config import settings

def main():
    print("Initializing Vector Store...")
    vector_store = VectorStore()
    
    # Dummy data
    texts = [
        "The Enterprise RAG Platform is designed to run on free-tier resources.",
        "It uses a hybrid retrieval approach combining FAISS and BM25.",
        "For LLM orchestration, it supports local Ollama instances or Hugging Face Inference API.",
        "Security features include RBAC, JWT authentication, and input sanitization.",
        "The system aims to keep memory usage under 512MB for Render.com compatibility."
    ]
    
    metadatas = [
        {"id": "doc1", "content": texts[0], "source": "manual"},
        {"id": "doc2", "content": texts[1], "source": "manual"},
        {"id": "doc3", "content": texts[2], "source": "manual"},
        {"id": "doc4", "content": texts[3], "source": "manual"},
        {"id": "doc5", "content": texts[4], "source": "manual"},
    ]
    
    print(f"Adding {len(texts)} documents...")
    vector_store.add_documents(texts, metadatas)
    print("Done! Vector store saved.")

if __name__ == "__main__":
    main()

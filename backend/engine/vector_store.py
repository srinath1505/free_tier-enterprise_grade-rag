import os
import json
import pickle
import faiss
import numpy as np
from typing import List, Dict, Any
from langchain_community.embeddings import HuggingFaceEmbeddings
from backend.core.config import settings

class VectorStore:
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(
            model_name=settings.EMBEDDING_MODEL_NAME,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        self.index = None
        self.metadata: List[Dict[str, Any]] = []
        
        # Determine dimension from model (384 for all-MiniLM-L6-v2)
        # We'll initialize lazily or load from disk
        self._load_or_initialize()

    def _load_or_initialize(self):
        os.makedirs(settings.VECTOR_STORE_PATH, exist_ok=True)

        index_path = os.path.join(settings.VECTOR_STORE_PATH, "index.faiss")
        meta_json = os.path.join(settings.VECTOR_STORE_PATH, "metadata.json")
        meta_pkl  = os.path.join(settings.VECTOR_STORE_PATH, "metadata.pkl")

        if os.path.exists(index_path) and (os.path.exists(meta_json) or os.path.exists(meta_pkl)):
            self.index = faiss.read_index(index_path)
            if os.path.exists(meta_json):
                with open(meta_json, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
            else:
                # One-time migration from legacy pickle format
                with open(meta_pkl, "rb") as f:
                    self.metadata = pickle.load(f)
                self.save()          # write JSON
                os.remove(meta_pkl)  # drop the pickle file
        else:
            self.index = faiss.IndexFlatIP(384)
            self.metadata = []

    def add_documents(self, texts: List[str], metadatas: List[Dict[str, Any]]):
        embeddings = self.embeddings.embed_documents(texts)
        embeddings_np = np.array(embeddings).astype("float32")
        
        if self.index is None:
             self.index = faiss.IndexFlatIP(len(embeddings[0]))
             
        self.index.add(embeddings_np)
        self.metadata.extend(metadatas)
        self.save()

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        if self.index is None or self.index.ntotal == 0:
            return []
            
        query_embedding = self.embeddings.embed_query(query)
        query_np = np.array([query_embedding]).astype("float32")
        
        # D: distances, I: indices
        D, I = self.index.search(query_np, k)
        
        results = []
        for i, idx in enumerate(I[0]):
            if idx != -1 and idx < len(self.metadata):
                item = self.metadata[idx].copy()
                item['score'] = float(D[0][i])
                results.append(item)
        
        return results

    def reload(self):
        """Reload the FAISS index and metadata from disk (called after external writes)."""
        self._load_or_initialize()

    def save(self):
        os.makedirs(settings.VECTOR_STORE_PATH, exist_ok=True)

        if self.index:
            faiss.write_index(self.index, os.path.join(settings.VECTOR_STORE_PATH, "index.faiss"))

        with open(os.path.join(settings.VECTOR_STORE_PATH, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(self.metadata, f)

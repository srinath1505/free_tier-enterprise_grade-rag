import os
from typing import List
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl

class Settings(BaseSettings):
    PROJECT_NAME: str = "Enterprise RAG Platform"
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = "YOUR_SUPER_SECRET_KEY_CHANGE_IN_PROD"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    # Paths
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    VECTOR_STORE_PATH: str = os.path.join(BASE_DIR, "vector_store")
    
    # LLM Settings
    # Supports 'local' (Ollama) or 'hf' (Hugging Face Inference API)
    LLM_PROVIDER: str = "local" 
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "phi3:mini"
    
    # Hugging Face (Fallback)
    HF_INFERENCE_API_URL: str = "microsoft/Phi-3-mini-4k-instruct" # Using Model ID now
    HF_TOKEN: str = ""

    # Retrieval Settings
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    RERANKER_MODEL_NAME: str = "cross-encoder/ms-marco-TinyBERT-L-2-v2"
    TOP_K_RETRIEVAL: int = 5
    
    # Constraints
    MAX_MEMORY_MB: int = 512

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()

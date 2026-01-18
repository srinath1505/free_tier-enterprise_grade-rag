from fastapi import APIRouter
from backend.api.endpoints import rag, auth, ingest

api_router = APIRouter()
api_router.include_router(auth.router, tags=["authentication"])
api_router.include_router(rag.router, prefix="/rag", tags=["rag"])
api_router.include_router(ingest.router, prefix="/ingest", tags=["ingestion"])

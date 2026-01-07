from fastapi import APIRouter
from backend.api.endpoints import rag, auth

api_router = APIRouter()
api_router.include_router(auth.router, tags=["authentication"])
api_router.include_router(rag.router, prefix="/rag", tags=["rag"])

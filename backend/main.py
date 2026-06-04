import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from backend.core.config import settings
from backend.core.logging import setup_logging
from backend.core.observability import setup_langsmith
from backend.core.limiter import limiter
from backend.api.api import api_router
from backend.database import init_db, AsyncSessionLocal
from backend.security.user_store import init_default_admin

setup_logging()
setup_langsmith()

logger = logging.getLogger(__name__)

_DEFAULT_SECRET = "YOUR_SUPER_SECRET_KEY_CHANGE_IN_PROD"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.SECRET_KEY == _DEFAULT_SECRET:
        logger.warning(
            "SECURITY: SECRET_KEY is the default value — set a strong random key in .env before deploying."
        )
    await init_db()
    async with AsyncSessionLocal() as db:
        await init_default_admin(db)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def root():
    return {"message": "Welcome to Enterprise RAG Platform API"}


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.PROJECT_NAME}

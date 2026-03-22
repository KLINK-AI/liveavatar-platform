"""LiveAvatar White-Label Platform — Main Application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from config import get_settings
from database import init_db
from api.routes import sessions, conversations, tenants, knowledge, admin, tenant_admin

settings = get_settings()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("Starting LiveAvatar Platform", env=settings.app_env)
    await init_db()
    logger.info("Database initialized")

    # Pre-warm OpenAI embedding connection to avoid cold-start latency (~5s)
    # Uses the singleton so the warmed connection is reused by all RAG pipelines.
    try:
        from services.rag.vector_store import get_vector_store
        vs = get_vector_store()
        await vs.warmup()
        logger.info("OpenAI embedding connection pre-warmed")
    except Exception as e:
        logger.warning("Embedding warmup failed (non-critical)", error=str(e))

    yield
    logger.info("Shutting down LiveAvatar Platform")


app = FastAPI(
    title=settings.app_name,
    description="White-Label Plattform für LiveAvatar LITE Mode mit eigenem LLM, RAG, TTS und STT",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins so the widget.js can be embedded on any customer website.
# Note: allow_credentials must be False when using wildcard origins (browser spec).
# The API uses Bearer tokens (not cookies), so credentials are not needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["Sessions"])
app.include_router(conversations.router, prefix="/api/v1/conversations", tags=["Conversations"])
app.include_router(tenants.router, prefix="/api/v1/tenants", tags=["Tenants"])
app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["Knowledge Base"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(tenant_admin.router, prefix="/api/v1/tenant-admin", tags=["Tenant Admin"])


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": "1.0.0",
    }


@app.get("/")
async def root():
    return {
        "message": "LiveAvatar White-Label Platform API",
        "docs": "/docs",
        "health": "/health",
    }

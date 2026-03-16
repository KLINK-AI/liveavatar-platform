"""LiveAvatar White-Label Platform — Main Application."""

import socket
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from config import get_settings
from database import init_db
from api.routes import sessions, conversations, tenants, knowledge, admin

settings = get_settings()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("Starting LiveAvatar Platform", env=settings.app_env)
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down LiveAvatar Platform")


app = FastAPI(
    title=settings.app_name,
    description="White-Label Plattform für LiveAvatar LITE Mode mit eigenem LLM, RAG, TTS und STT",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["Sessions"])
app.include_router(conversations.router, prefix="/api/v1/conversations", tags=["Conversations"])
app.include_router(tenants.router, prefix="/api/v1/tenants", tags=["Tenants"])
app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["Knowledge Base"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])


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


@app.get("/debug/network")
async def debug_network():
    """
    Diagnose network connectivity from inside the Docker container.
    Tests DNS resolution, HTTP connectivity, and LiveAvatar API reachability.
    """
    results = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dns": {},
        "http_tests": {},
        "env": {
            "liveavatar_api_base": settings.liveavatar_api_base,
            "has_api_key": bool(settings.liveavatar_api_key),
        },
    }

    # Test 1: DNS Resolution
    for host in ["api.liveavatar.com", "api.heygen.com", "google.com"]:
        try:
            t0 = time.monotonic()
            ips = socket.getaddrinfo(host, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
            t1 = time.monotonic()
            results["dns"][host] = {
                "resolved": True,
                "ips": list(set(addr[4][0] for addr in ips)),
                "ms": round((t1 - t0) * 1000),
            }
        except Exception as e:
            results["dns"][host] = {"resolved": False, "error": str(e)}

    # Test 2: HTTP GET to various endpoints
    test_urls = [
        ("google", "https://www.google.com", {}),
        ("liveavatar_root", f"{settings.liveavatar_api_base}/", {}),
        (
            "liveavatar_avatars",
            f"{settings.liveavatar_api_base}/v1/avatars/public",
            {"X-API-KEY": settings.liveavatar_api_key},
        ),
    ]

    for name, url, extra_headers in test_urls:
        try:
            t0 = time.monotonic()
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {"Accept": "application/json"}
                headers.update(extra_headers)
                resp = await client.get(url, headers=headers)
            t1 = time.monotonic()
            body_preview = resp.text[:300] if resp.text else ""
            results["http_tests"][name] = {
                "url": url,
                "status_code": resp.status_code,
                "ms": round((t1 - t0) * 1000),
                "body_preview": body_preview,
            }
        except Exception as e:
            results["http_tests"][name] = {
                "url": url,
                "error": type(e).__name__,
                "detail": str(e),
            }

    # Test 3: POST to /v1/sessions/token (the actual failing call)
    try:
        t0 = time.monotonic()
        async with httpx.AsyncClient(
            base_url=settings.liveavatar_api_base,
            headers={
                "X-API-KEY": settings.liveavatar_api_key,
                "Content-Type": "application/json",
            },
            timeout=15.0,
        ) as client:
            resp = await client.post(
                "/v1/sessions/token",
                json={
                    "mode": "LITE",
                    "avatar_id": "9b116530-ab51-48ec-9fc6-e5c01d4d3568",
                    "is_sandbox": True,
                },
            )
        t1 = time.monotonic()
        results["http_tests"]["liveavatar_token"] = {
            "url": f"{settings.liveavatar_api_base}/v1/sessions/token",
            "status_code": resp.status_code,
            "ms": round((t1 - t0) * 1000),
            "body_preview": resp.text[:500] if resp.text else "",
        }
    except Exception as e:
        t1 = time.monotonic()
        results["http_tests"]["liveavatar_token"] = {
            "url": f"{settings.liveavatar_api_base}/v1/sessions/token",
            "error": type(e).__name__,
            "detail": str(e),
            "ms": round((t1 - t0) * 1000),
        }

    return results

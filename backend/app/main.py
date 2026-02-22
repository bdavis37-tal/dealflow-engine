"""
FastAPI application entry point for the dealflow engine.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .api.ai_routes import router as ai_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load .env file if present (development convenience)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    from .services.ai_service import is_ai_available
    ai_status = "enabled" if is_ai_available() else "disabled (no ANTHROPIC_API_KEY)"
    logger.info("Dealflow Engine API starting up... AI features: %s", ai_status)
    yield
    logger.info("Dealflow Engine API shutting down.")


app = FastAPI(
    title="Dealflow Engine API",
    description=(
        "Open-source M&A financial modeling engine. "
        "TurboTax meets Goldman Sachs — guided deal analysis for everyone."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — origins configured from CORS_ORIGINS env var (comma-separated).
# Falls back to safe localhost-only defaults for development.
# In production, set CORS_ORIGINS to your actual frontend origin(s).
_default_origins = [
    "http://localhost:5173",   # Vite dev server
    "http://localhost:3000",   # Alternative dev port
    "http://localhost:80",     # Docker production
    "http://frontend:80",      # Docker compose internal
]
_env_origins = os.environ.get("CORS_ORIGINS", "")
allowed_origins = (
    [o.strip() for o in _env_origins.split(",") if o.strip()]
    if _env_origins
    else _default_origins
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(ai_router)


@app.get("/")
async def root():
    return {
        "name": "Dealflow Engine",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }

"""
SchoolChat — FastAPI application entry point.
"""

import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routers import auth, channels, users
from app.websocket.handler import router as ws_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger("schoolchat")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.server_name}")
    yield
    logger.info(f"Shutting down {settings.server_name}")


app = FastAPI(
    title=settings.server_name,
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
origins = settings.allowed_origins.split(",") if settings.allowed_origins != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routers
app.include_router(auth.router)
app.include_router(channels.router)
app.include_router(users.router)

# WebSocket router
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.server_name}


# ── Web UI for testing ──
STATIC_DIR = Path(__file__).parent / "static"


@app.get("/")
async def web_ui():
    """Serve the built-in testing web UI."""
    return FileResponse(STATIC_DIR / "index.html")

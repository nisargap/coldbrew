import os
import sys
import logging

from dotenv import load_dotenv
load_dotenv()  # Load .env from backend/ directory

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Ensure the backend directory is on the path
sys.path.insert(0, os.path.dirname(__file__))

from database import create_tables
from routers import feeds, events, notifications, personas, status
from services.telegram import start_bot, stop_bot

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# App
app = FastAPI(
    title="ColdBrew API",
    description="Warehouse video intelligence platform",
    version="0.1.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(feeds.router)
app.include_router(events.router)
app.include_router(notifications.router)
app.include_router(personas.router)
app.include_router(status.router)

# Serve uploaded files (thumbnails etc.)
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.on_event("startup")
async def on_startup():
    create_tables()
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    try:
        await start_bot()
    except Exception as e:
        logger.warning(f"Telegram bot failed to start (non-fatal): {e}")
    logger.info("ColdBrew API started. Database initialized.")


@app.on_event("shutdown")
async def on_shutdown():
    await stop_bot()


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "coldbrew"}

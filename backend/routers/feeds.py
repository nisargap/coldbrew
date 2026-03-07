import uuid
import os
import json
import shutil
import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, UploadFile, File, Form, Depends, BackgroundTasks, HTTPException
from starlette.responses import StreamingResponse
import sqlite3

from database import get_db
from models import FeedUploadResponse, FeedResponse
from services.analysis import analyze_video
from services.event_bus import subscribe, unsubscribe

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/feeds", tags=["feeds"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")


@router.post("/upload", response_model=FeedUploadResponse, status_code=201)
async def upload_feed(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    feed_name: str = Form(...),
    db: sqlite3.Connection = Depends(get_db),
):
    # Validate file type
    if file.content_type not in ("video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"):
        raise HTTPException(status_code=400, detail="Unsupported file type. Upload MP4, MOV, AVI, or WEBM.")

    feed_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Save file to disk
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "video.mp4")[1] or ".mp4"
    file_path = os.path.join(UPLOAD_DIR, f"{feed_id}{ext}")

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Create feed record
    db.execute(
        "INSERT INTO feeds (id, feed_name, file_path, status, created_at, event_count) VALUES (?, ?, ?, ?, ?, ?)",
        (feed_id, feed_name, file_path, "processing", now, 0),
    )
    db.commit()

    logger.info(f"Feed {feed_id} created: {feed_name} -> {file_path}")

    # Kick off analysis in background
    background_tasks.add_task(analyze_video, file_path, feed_id, feed_name)

    return FeedUploadResponse(feed_id=feed_id, status="processing")


@router.get("", response_model=list[FeedResponse])
def list_feeds(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        "SELECT id, feed_name, status, error_message, created_at, event_count FROM feeds ORDER BY created_at DESC"
    ).fetchall()
    return [
        FeedResponse(
            feed_id=row["id"],
            feed_name=row["feed_name"],
            status=row["status"],
            error_message=row["error_message"] if "error_message" in row.keys() else None,
            created_at=row["created_at"],
            event_count=row["event_count"],
        )
        for row in rows
    ]


@router.get("/stream")
async def stream_feed_updates():
    """SSE endpoint — streams real-time feed status changes to the browser."""
    queue = await subscribe()

    async def event_generator():
        try:
            while True:
                try:
                    # Wait up to 30s for a message, then send keepalive
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(data)}\n\n"
                except asyncio.TimeoutError:
                    # SSE keepalive comment to prevent proxy/browser timeout
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            await unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering if present
        },
    )

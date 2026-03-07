import uuid
import os
import json
import shutil
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, Depends, BackgroundTasks, HTTPException
from starlette.responses import StreamingResponse
import sqlite3

from database import get_db
from models import FeedUploadResponse, FeedResponse
from services.analysis import analyze_video
from services.event_bus import subscribe, unsubscribe, publish as publish_sse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/feeds", tags=["feeds"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")

VALID_MODES = {"standard", "agent"}


def _row_to_feed(row: sqlite3.Row) -> FeedResponse:
    return FeedResponse(
        feed_id=row["id"],
        feed_name=row["feed_name"],
        status=row["status"],
        error_message=row["error_message"] if "error_message" in row.keys() else None,
        analysis_mode=row["analysis_mode"] if "analysis_mode" in row.keys() else "standard",
        created_at=row["created_at"],
        event_count=row["event_count"],
    )


@router.post("/upload", response_model=FeedUploadResponse, status_code=201)
async def upload_feed(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    feed_name: str = Form(...),
    analysis_mode: str = Form("standard"),
    db: sqlite3.Connection = Depends(get_db),
):
    # Validate file type
    if file.content_type not in ("video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"):
        raise HTTPException(status_code=400, detail="Unsupported file type. Upload MP4, MOV, AVI, or WEBM.")

    if analysis_mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid analysis mode. Must be one of: {VALID_MODES}")

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
        "INSERT INTO feeds (id, feed_name, file_path, status, analysis_mode, created_at, event_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (feed_id, feed_name, file_path, "processing", analysis_mode, now, 0),
    )
    db.commit()

    logger.info(f"Feed {feed_id} created: {feed_name} (mode={analysis_mode}) -> {file_path}")

    # Kick off analysis in background
    background_tasks.add_task(analyze_video, file_path, feed_id, feed_name, analysis_mode)

    return FeedUploadResponse(feed_id=feed_id, status="processing", analysis_mode=analysis_mode)


@router.get("", response_model=list[FeedResponse])
def list_feeds(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        "SELECT id, feed_name, status, error_message, analysis_mode, created_at, event_count FROM feeds ORDER BY created_at DESC"
    ).fetchall()
    return [_row_to_feed(row) for row in rows]


# SSE must be registered BEFORE /{feed_id} to avoid being captured as a path param
@router.get("/stream")
async def stream_feed_updates():
    """SSE endpoint — streams real-time feed status changes to the browser."""
    queue = await subscribe()

    async def event_generator():
        try:
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(data)}\n\n"
                except asyncio.TimeoutError:
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
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{feed_id}/reanalyze", response_model=FeedUploadResponse)
def reanalyze_feed(
    feed_id: str,
    background_tasks: BackgroundTasks,
    analysis_mode: str = "agent",
    db: sqlite3.Connection = Depends(get_db),
):
    """Re-analyze an existing feed with a different analysis mode."""
    if analysis_mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid analysis mode. Must be one of: {VALID_MODES}")

    row = db.execute("SELECT id, feed_name, file_path, status FROM feeds WHERE id = ?", (feed_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Feed not found")

    if row["status"] == "processing":
        raise HTTPException(status_code=409, detail="Feed is already being analyzed")

    # Reset feed to processing state
    db.execute(
        "UPDATE feeds SET status = ?, error_message = NULL, analysis_mode = ?, event_count = 0 WHERE id = ?",
        ("processing", analysis_mode, feed_id),
    )
    db.commit()

    logger.info(f"Feed {feed_id} re-analysis started (mode={analysis_mode})")

    # Publish SSE so frontend updates immediately
    publish_sse({
        "type": "feed_update",
        "feed_id": feed_id,
        "status": "processing",
        "feed_name": row["feed_name"],
        "analysis_mode": analysis_mode,
    })

    # Kick off analysis in background
    background_tasks.add_task(analyze_video, row["file_path"], feed_id, row["feed_name"], analysis_mode)

    return FeedUploadResponse(feed_id=feed_id, status="processing", analysis_mode=analysis_mode)


@router.get("/{feed_id}", response_model=FeedResponse)
def get_feed(feed_id: str, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute(
        "SELECT id, feed_name, status, error_message, analysis_mode, created_at, event_count FROM feeds WHERE id = ?",
        (feed_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Feed not found")
    return _row_to_feed(row)

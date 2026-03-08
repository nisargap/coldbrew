import uuid
import os
import json
import shutil
import asyncio
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, Depends, BackgroundTasks, HTTPException
from pydantic import BaseModel
from starlette.responses import StreamingResponse
import sqlite3

from database import get_db, DB_PATH
from models import FeedUploadResponse, FeedResponse
from services.analysis import analyze_video, parse_nomadic_events, classify_category, classify_severity
from services.event_bus import subscribe, unsubscribe, publish as publish_sse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/feeds", tags=["feeds"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")

VALID_MODES = {"standard", "agent"}

# Track active livestream monitors: feed_id -> { stop_event, stream_id, session_id }
_active_streams: dict[str, dict] = {}


class LivestreamRequest(BaseModel):
    url: str
    feed_name: str
    analysis_mode: str = "standard"
    query: str = ""  # natural-language query for rapid review event detection


def _video_url_from_path(file_path: str) -> str | None:
    """Convert local file path to a URL served by the /uploads mount."""
    if not file_path:
        return None
    basename = os.path.basename(file_path)
    return f"/uploads/{basename}"


def _row_to_feed(row: sqlite3.Row) -> FeedResponse:
    file_path = row["file_path"] if "file_path" in row.keys() else None
    nomadic_stream_id = row["nomadic_stream_id"] if "nomadic_stream_id" in row.keys() else None
    session_id = row["session_id"] if "session_id" in row.keys() else None

    # Build viewer URL from stream_id and session_id
    viewer_url = None
    if nomadic_stream_id and session_id:
        viewer_url = f"https://app.nomadicml.com/events/{nomadic_stream_id}/{session_id}"

    return FeedResponse(
        feed_id=row["id"],
        feed_name=row["feed_name"],
        status=row["status"],
        error_message=row["error_message"] if "error_message" in row.keys() else None,
        analysis_mode=row["analysis_mode"] if "analysis_mode" in row.keys() else "standard",
        confidence_level=row["confidence_level"] if "confidence_level" in row.keys() else "low",
        video_url=_video_url_from_path(file_path),
        stream_url=row["stream_url"] if "stream_url" in row.keys() else None,
        nomadic_stream_id=nomadic_stream_id,
        session_id=session_id,
        viewer_url=viewer_url,
        created_at=row["created_at"],
        event_count=row["event_count"],
    )


VALID_CONFIDENCE_LEVELS = {"low", "high"}


@router.post("/upload", response_model=FeedUploadResponse, status_code=201)
async def upload_feed(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    feed_name: str = Form(...),
    analysis_mode: str = Form("standard"),
    confidence_level: str = Form("low"),
    db: sqlite3.Connection = Depends(get_db),
):
    # Validate file type
    if file.content_type not in ("video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. Accepted formats: MP4, MOV, AVI, WEBM."
        )

    if analysis_mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid analysis mode '{analysis_mode}'. Must be one of: {sorted(VALID_MODES)}")

    if confidence_level not in VALID_CONFIDENCE_LEVELS:
        raise HTTPException(status_code=400, detail=f"Invalid confidence level '{confidence_level}'. Must be one of: {sorted(VALID_CONFIDENCE_LEVELS)}")

    if not feed_name.strip():
        raise HTTPException(status_code=400, detail="Feed name is required and cannot be empty.")

    feed_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Save file to disk
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "video.mp4")[1] or ".mp4"
    file_path = os.path.join(UPLOAD_DIR, f"{feed_id}{ext}")

    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file to disk: {str(e)[:200]}")

    # Create feed record
    try:
        db.execute(
            "INSERT INTO feeds (id, feed_name, file_path, status, analysis_mode, confidence_level, created_at, event_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (feed_id, feed_name, file_path, "processing", analysis_mode, confidence_level, now, 0),
        )
        db.commit()
    except Exception as e:
        logger.error(f"Database error creating feed record: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: Failed to create feed record. {str(e)[:200]}")

    logger.info(f"Feed {feed_id} created: {feed_name} (mode={analysis_mode}, confidence={confidence_level}) -> {file_path}")

    # Kick off analysis in background
    background_tasks.add_task(analyze_video, file_path, feed_id, feed_name, analysis_mode, confidence_level)

    return FeedUploadResponse(feed_id=feed_id, status="processing", analysis_mode=analysis_mode, confidence_level=confidence_level)


@router.post("/livestream", response_model=FeedUploadResponse, status_code=201)
async def start_livestream(
    req: LivestreamRequest,
    background_tasks: BackgroundTasks,
    db: sqlite3.Connection = Depends(get_db),
):
    """Start livestream monitoring using NomadicML SDK native livestream API."""
    if req.analysis_mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid analysis mode. Must be one of: {VALID_MODES}")

    if not req.url.strip():
        raise HTTPException(status_code=400, detail="URL is required")

    feed_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Create feed record with "monitoring" status
    db.execute(
        "INSERT INTO feeds (id, feed_name, file_path, status, analysis_mode, created_at, event_count, stream_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (feed_id, req.feed_name.strip(), "", "monitoring", req.analysis_mode, now, 0, req.url.strip()),
    )
    db.commit()

    logger.info(f"Feed {feed_id} livestream started: {req.feed_name} (url={req.url}, mode={req.analysis_mode})")

    # Create stop event for this stream
    stop_event = threading.Event()
    _active_streams[feed_id] = {
        "stop_event": stop_event,
        "stream_id": None,
        "session_id": None,
    }

    # Publish SSE so frontend shows monitoring status immediately
    publish_sse({
        "type": "feed_update",
        "feed_id": feed_id,
        "status": "monitoring",
        "feed_name": req.feed_name.strip(),
        "analysis_mode": req.analysis_mode,
    })

    # Start monitoring in background thread using NomadicML SDK
    background_tasks.add_task(
        _livestream_monitor, req.url, feed_id, req.feed_name.strip(), req.analysis_mode, req.query.strip(), stop_event
    )

    return FeedUploadResponse(feed_id=feed_id, status="monitoring", analysis_mode=req.analysis_mode)


@router.delete("/livestream/all")
def stop_all_livestreams(db: sqlite3.Connection = Depends(get_db)):
    """Stop all running livestream monitors (in-memory + DB orphans)."""
    stopped = []

    # 1. Stop all in-memory active streams
    feed_ids = list(_active_streams.keys())
    for fid in feed_ids:
        stream_info = _active_streams.get(fid)
        if not stream_info:
            continue
        stream_info["stop_event"].set()

        stream_id = stream_info.get("stream_id")
        session_id = stream_info.get("session_id")
        if stream_id and session_id:
            try:
                from nomadicml import NomadicML
                api_key = os.environ.get("NOMADIC_SDK_API_KEY")
                if api_key:
                    client = NomadicML(api_key=api_key)
                    client.livestream.end_session(stream_id, session_id)
            except Exception as e:
                logger.warning(f"[Livestream] Failed to end NomadicML session for {fid}: {e}")

        _active_streams.pop(fid, None)
        stopped.append(fid)

    # 2. Also catch DB orphans (feeds stuck as "monitoring" after server restart)
    rows = db.execute("SELECT id FROM feeds WHERE status = 'monitoring'").fetchall()
    for row in rows:
        fid = row[0]
        if fid not in stopped:
            stopped.append(fid)

    # 3. Bulk update all monitoring feeds to completed
    if stopped:
        db.execute("UPDATE feeds SET status = 'completed' WHERE status = 'monitoring'")
        db.commit()
        for fid in stopped:
            publish_sse({
                "type": "feed_update",
                "feed_id": fid,
                "status": "completed",
            })

    logger.info(f"Stopped all livestreams: {stopped}")
    return {"status": "stopped", "stopped_count": len(stopped), "feed_ids": stopped}


@router.delete("/{feed_id}/livestream")
def stop_livestream(feed_id: str, db: sqlite3.Connection = Depends(get_db)):
    """Stop a running livestream monitor (in-memory or DB orphan)."""
    stream_info = _active_streams.get(feed_id)

    if stream_info:
        # Signal the background thread to stop
        stream_info["stop_event"].set()

        # Also end the session on NomadicML side
        stream_id = stream_info.get("stream_id")
        session_id = stream_info.get("session_id")
        if stream_id and session_id:
            try:
                from nomadicml import NomadicML
                api_key = os.environ.get("NOMADIC_SDK_API_KEY")
                if api_key:
                    client = NomadicML(api_key=api_key)
                    client.livestream.end_session(stream_id, session_id)
                    logger.info(f"[Livestream] Ended NomadicML session {session_id} for feed {feed_id}")
            except Exception as e:
                logger.warning(f"[Livestream] Failed to end NomadicML session: {e}")

        _active_streams.pop(feed_id, None)
    else:
        # No in-memory entry — check if it's a DB orphan (server restarted)
        row = db.execute("SELECT status FROM feeds WHERE id = ?", (feed_id,)).fetchone()
        if not row or row[0] != "monitoring":
            raise HTTPException(status_code=404, detail="No active livestream for this feed")
        logger.info(f"[Livestream] Cleaning up DB-orphaned monitoring feed {feed_id}")

    # Update feed status
    db.execute("UPDATE feeds SET status = ? WHERE id = ?", ("completed", feed_id))
    db.commit()

    publish_sse({
        "type": "feed_update",
        "feed_id": feed_id,
        "status": "completed",
    })

    logger.info(f"Feed {feed_id} livestream stopped by user")
    return {"status": "stopped", "feed_id": feed_id}


def _livestream_monitor(url: str, feed_id: str, feed_name: str, analysis_mode: str, query: str, stop_event: threading.Event):
    """Background thread: continuously monitor a livestream using NomadicML SDK.

    The SDK's start_session captures a short segment of the live stream and
    analyzes it.  To provide continuous monitoring, we loop — starting a new
    session each cycle, collecting events via iter_events, then immediately
    starting another session until stop_event is set.
    """
    conn = None
    total_events = 0
    stream_id = None
    session_id = None
    cycle = 0

    try:
        from nomadicml import NomadicML

        api_key = os.environ.get("NOMADIC_SDK_API_KEY")
        if not api_key:
            raise ValueError("NOMADIC_SDK_API_KEY environment variable is not set")

        client = NomadicML(api_key=api_key)

        # Use warehouse prompt as rapid_review_query if no custom query provided
        rapid_review_query = query if query else (
            "Detect any notable events in this warehouse or facility footage: "
            "safety violations (missing PPE, restricted zones), equipment issues (conveyor jams, forklift malfunctions), "
            "shipment activity (truck arrivals, loading/unloading, damaged cargo), "
            "operational issues (blocked aisles, idle zones), "
            "environmental hazards (spills, smoke, leaks)."
        )

        # ---- Continuous monitoring loop ----
        while not stop_event.is_set():
            cycle += 1
            logger.info(f"[Livestream] Feed {feed_id} cycle {cycle}: starting NomadicML session for {url}")

            publish_sse({
                "type": "livestream_cycle",
                "feed_id": feed_id,
                "cycle": cycle,
                "status": "capturing",
            })

            # Start a new session
            try:
                session_result = client.livestream.start_session(
                    source_url=url,
                    name=f"{feed_name} (cycle {cycle})",
                    rapid_review_query=rapid_review_query,
                    stream_id=stream_id,  # reuse stream_id from first cycle if available
                )
            except Exception as e:
                logger.error(f"[Livestream] Feed {feed_id} cycle {cycle}: start_session failed: {e}")
                # Brief pause before retrying
                if stop_event.wait(5):
                    break
                continue

            stream_id = session_result.get("stream_id") or stream_id
            session_id = session_result.get("session_id")

            logger.info(f"[Livestream] Feed {feed_id} cycle {cycle}: session started — stream_id={stream_id}, session_id={session_id}")

            # Store stream_id and session_id for stop endpoint
            if feed_id in _active_streams:
                _active_streams[feed_id]["stream_id"] = stream_id
                _active_streams[feed_id]["session_id"] = session_id

            # Update feed record with session info
            try:
                conn = sqlite3.connect(DB_PATH)
                conn.execute(
                    "UPDATE feeds SET nomadic_stream_id = ?, session_id = ? WHERE id = ?",
                    (stream_id, session_id, feed_id),
                )
                conn.commit()
                conn.close()
                conn = None
            except Exception:
                if conn:
                    conn.close()
                    conn = None

            # Build viewer URL
            viewer_url = None
            if stream_id and session_id:
                viewer_url = f"https://app.nomadicml.com/events/{stream_id}/{session_id}"

            publish_sse({
                "type": "livestream_cycle",
                "feed_id": feed_id,
                "cycle": cycle,
                "status": "analyzing",
                "viewer_url": viewer_url,
                "stream_id": stream_id,
                "session_id": session_id,
            })

            # Poll for events from this session
            session_events = 0
            try:
                for sdk_event in client.livestream.iter_events(
                    stream_id=stream_id,
                    session_id=session_id,
                    poll_interval=3.0,
                    timeout=120,  # safety timeout per session
                ):
                    if stop_event.is_set():
                        break

                    session_events += 1
                    total_events += 1
                    logger.info(f"[Livestream] Feed {feed_id} cycle {cycle}: event #{total_events}: {sdk_event.get('description', 'N/A')[:100]}")

                    # Convert SDK event to our local event format and store
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        local_event = _sdk_event_to_local(sdk_event, feed_id, feed_name)

                        conn.execute(
                            """INSERT OR IGNORE INTO events (id, feed_id, timestamp, category, severity, title, description,
                               source_feed, thumbnail_url, confidence, status, created_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (
                                local_event["id"], local_event["feed_id"], local_event["timestamp"],
                                local_event["category"], local_event["severity"], local_event["title"],
                                local_event["description"], local_event["source_feed"], local_event["thumbnail_url"],
                                local_event["confidence"], local_event["status"], local_event["created_at"],
                            ),
                        )

                        # Update event count on feed
                        row = conn.execute("SELECT COUNT(*) FROM events WHERE feed_id = ?", (feed_id,)).fetchone()
                        db_total = row[0] if row else 0
                        conn.execute("UPDATE feeds SET event_count = ? WHERE id = ?", (db_total, feed_id))
                        conn.commit()
                        conn.close()
                        conn = None

                        # Publish SSE for this new event
                        publish_sse({
                            "type": "livestream_cycle",
                            "feed_id": feed_id,
                            "cycle": cycle,
                            "status": "done",
                            "event_count": db_total,
                        })

                    except Exception as e:
                        logger.error(f"[Livestream] Feed {feed_id}: failed to store event: {e}")
                        if conn:
                            conn.close()
                            conn = None

            except Exception as e:
                logger.error(f"[Livestream] Feed {feed_id} cycle {cycle}: iter_events error: {e}")

            logger.info(f"[Livestream] Feed {feed_id} cycle {cycle} done. {session_events} events this cycle, {total_events} total")

            # Brief pause between cycles to avoid hammering the API
            if not stop_event.is_set():
                publish_sse({
                    "type": "livestream_cycle",
                    "feed_id": feed_id,
                    "cycle": cycle,
                    "status": "waiting",
                    "event_count": total_events,
                })
                # Wait 2 seconds between cycles (or stop if signaled)
                if stop_event.wait(2):
                    break

        logger.info(f"[Livestream] Feed {feed_id}: monitoring loop ended after {cycle} cycles. Total events: {total_events}")

    except Exception as e:
        logger.error(f"[Livestream] Feed {feed_id} failed: {e}", exc_info=True)
        publish_sse({
            "type": "livestream_cycle",
            "feed_id": feed_id,
            "cycle": cycle,
            "status": "error",
            "error": str(e)[:200],
        })

        # Update feed with error
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("UPDATE feeds SET status = ?, error_message = ? WHERE id = ?", ("error", str(e)[:500], feed_id))
            conn.commit()
            conn.close()
            conn = None
        except Exception:
            pass
    finally:
        if conn:
            conn.close()

    # Clean up when done
    _active_streams.pop(feed_id, None)

    # End the last session on NomadicML side if still active
    if stream_id and session_id and not stop_event.is_set():
        try:
            from nomadicml import NomadicML
            api_key = os.environ.get("NOMADIC_SDK_API_KEY")
            if api_key:
                client = NomadicML(api_key=api_key)
                client.livestream.end_session(stream_id, session_id)
        except Exception:
            pass

    # Update feed status to completed
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE feeds SET status = ? WHERE id = ?", ("completed", feed_id))
        conn.commit()
        conn.close()
    except Exception:
        pass

    publish_sse({
        "type": "feed_update",
        "feed_id": feed_id,
        "status": "completed",
        "event_count": total_events,
        "feed_name": feed_name,
    })
    logger.info(f"[Livestream] Feed {feed_id} monitor stopped. Total events: {total_events}")


def _sdk_event_to_local(sdk_event: dict, feed_id: str, feed_name: str) -> dict:
    """Convert a NomadicML SDK livestream event to our local event format."""
    description = (
        sdk_event.get("aiAnalysis")
        or sdk_event.get("ai_analysis")
        or sdk_event.get("description")
        or sdk_event.get("label")
        or "No description available"
    )

    label = sdk_event.get("label") or sdk_event.get("description") or ""
    title_text = label if label else description
    if len(title_text) > 60:
        title_text = title_text[:57] + "..."

    event_type = sdk_event.get("category") or sdk_event.get("type") or ""
    full_text = f"{label} {description} {event_type}"

    valid_categories = {"Safety", "Equipment", "Shipment", "Operational", "Environmental"}
    category = event_type.strip().title() if event_type.strip().title() in valid_categories else classify_category(full_text, description)

    valid_severities = {"Critical", "High", "Medium", "Low"}
    severity_raw = (sdk_event.get("severity") or "").strip().title()
    severity = severity_raw if severity_raw in valid_severities else classify_severity(full_text, description)

    confidence = sdk_event.get("confidence") or 0.8
    if isinstance(confidence, (int, float)) and confidence > 1:
        confidence = confidence / 100.0

    t_start = sdk_event.get("t_start") or sdk_event.get("start_time") or "00:00"
    t_end = sdk_event.get("t_end") or sdk_event.get("end_time") or "00:00"
    stream_time = sdk_event.get("stream_time") or sdk_event.get("capture_time") or 0

    return {
        "id": str(uuid.uuid4()),
        "feed_id": feed_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "category": category,
        "severity": severity,
        "title": title_text,
        "description": description,
        "source_feed": feed_name,
        "video_time": f"{t_start}-{t_end}",
        "thumbnail_url": sdk_event.get("thumbnail_url") or sdk_event.get("thumbnail") or None,
        "confidence": confidence,
        "status": "new",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("", response_model=list[FeedResponse])
def list_feeds(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        "SELECT id, feed_name, file_path, status, error_message, analysis_mode, confidence_level, created_at, event_count, stream_url, nomadic_stream_id, session_id FROM feeds ORDER BY created_at DESC"
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
    confidence_level: str = "low",
    db: sqlite3.Connection = Depends(get_db),
):
    """Re-analyze an existing feed with a different analysis mode."""
    if analysis_mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid analysis mode '{analysis_mode}'. Must be one of: {sorted(VALID_MODES)}")

    if confidence_level not in VALID_CONFIDENCE_LEVELS:
        raise HTTPException(status_code=400, detail=f"Invalid confidence level '{confidence_level}'. Must be one of: {sorted(VALID_CONFIDENCE_LEVELS)}")

    row = db.execute("SELECT id, feed_name, file_path, status FROM feeds WHERE id = ?", (feed_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Feed '{feed_id}' not found.")

    if row["status"] == "processing":
        raise HTTPException(status_code=409, detail=f"Feed '{row['feed_name']}' is already being analyzed. Wait for the current analysis to complete.")

    # Reset feed to processing state
    db.execute(
        "UPDATE feeds SET status = ?, error_message = NULL, analysis_mode = ?, confidence_level = ?, event_count = 0 WHERE id = ?",
        ("processing", analysis_mode, confidence_level, feed_id),
    )
    db.commit()

    logger.info(f"Feed {feed_id} re-analysis started (mode={analysis_mode}, confidence={confidence_level})")

    # Publish SSE so frontend updates immediately
    publish_sse({
        "type": "feed_update",
        "feed_id": feed_id,
        "status": "processing",
        "feed_name": row["feed_name"],
        "analysis_mode": analysis_mode,
    })

    # Kick off analysis in background
    background_tasks.add_task(analyze_video, row["file_path"], feed_id, row["feed_name"], analysis_mode, confidence_level)

    return FeedUploadResponse(feed_id=feed_id, status="processing", analysis_mode=analysis_mode, confidence_level=confidence_level)


@router.get("/{feed_id}", response_model=FeedResponse)
def get_feed(feed_id: str, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute(
        "SELECT id, feed_name, file_path, status, error_message, analysis_mode, confidence_level, created_at, event_count, stream_url, nomadic_stream_id, session_id FROM feeds WHERE id = ?",
        (feed_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Feed '{feed_id}' not found. It may have been deleted.")
    return _row_to_feed(row)

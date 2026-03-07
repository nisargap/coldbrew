import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
import sqlite3

from database import get_db
from models import EventResponse, EventStatusUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/events", tags=["events"])

VALID_STATUSES = {"acknowledged", "dismissed"}


def row_to_event(row: sqlite3.Row) -> EventResponse:
    return EventResponse(
        id=row["id"],
        feed_id=row["feed_id"],
        timestamp=row["timestamp"],
        category=row["category"],
        severity=row["severity"],
        title=row["title"],
        description=row["description"],
        source_feed=row["source_feed"],
        thumbnail_url=row["thumbnail_url"],
        confidence=row["confidence"],
        status=row["status"],
    )


@router.get("", response_model=list[EventResponse])
def list_events(
    category: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    feed_id: Optional[str] = Query(None),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    db: sqlite3.Connection = Depends(get_db),
):
    query = "SELECT * FROM events WHERE 1=1"
    params: list = []

    if category:
        query += " AND category = ?"
        params.append(category)
    if severity:
        query += " AND severity = ?"
        params.append(severity)
    if feed_id:
        query += " AND feed_id = ?"
        params.append(feed_id)
    if min_confidence is not None:
        query += " AND confidence >= ?"
        params.append(min_confidence)

    query += " ORDER BY created_at DESC"
    rows = db.execute(query, params).fetchall()

    return [row_to_event(row) for row in rows]


@router.get("/{event_id}", response_model=EventResponse)
def get_event(event_id: str, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Event not found")
    return row_to_event(row)


@router.patch("/{event_id}")
def update_event_status(
    event_id: str,
    body: EventStatusUpdate,
    db: sqlite3.Connection = Depends(get_db),
):
    if body.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {VALID_STATUSES}")

    row = db.execute("SELECT id FROM events WHERE id = ?", (event_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Event not found")

    db.execute("UPDATE events SET status = ? WHERE id = ?", (body.status, event_id))
    db.commit()

    return {"id": event_id, "status": body.status}

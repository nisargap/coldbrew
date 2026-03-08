import uuid
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
import sqlite3

from database import get_db
from models import (
    NotificationSendRequest,
    NotificationSendResponse,
    NotificationResponse,
    PersonaResponse,
    EventSummary,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _get_persona(db: sqlite3.Connection, persona_id: str) -> dict | None:
    """Look up a persona from the database."""
    row = db.execute("SELECT id, name, role FROM personas WHERE id = ?", (persona_id,)).fetchone()
    if row:
        return {"id": row["id"], "name": row["name"], "role": row["role"]}
    return None


@router.post("/send", response_model=NotificationSendResponse, status_code=201)
def send_notification(
    body: NotificationSendRequest,
    db: sqlite3.Connection = Depends(get_db),
):
    if not body.event_ids:
        raise HTTPException(status_code=400, detail="No events selected")
    if not body.persona_ids:
        raise HTTPException(status_code=400, detail="No personas selected")
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Resolve personas from the database
    sent_to = []
    for pid in body.persona_ids:
        persona = _get_persona(db, pid)
        if persona:
            sent_to.append(persona)

    if not sent_to:
        raise HTTPException(status_code=400, detail="No valid personas found")

    notification_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    db.execute(
        "INSERT INTO notifications (id, message, sent_to, event_ids, created_at) VALUES (?, ?, ?, ?, ?)",
        (
            notification_id,
            body.message,
            json.dumps(sent_to),
            json.dumps(body.event_ids),
            now,
        ),
    )
    db.commit()

    logger.info(f"Notification {notification_id} sent to {[p['name'] for p in sent_to]} for {len(body.event_ids)} events")

    return NotificationSendResponse(
        notification_id=notification_id,
        sent_to=[PersonaResponse(**p) for p in sent_to],
        event_count=len(body.event_ids),
    )


@router.get("", response_model=list[NotificationResponse])
def list_notifications(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        "SELECT * FROM notifications ORDER BY created_at DESC"
    ).fetchall()

    results = []
    for row in rows:
        sent_to = json.loads(row["sent_to"])
        event_ids = json.loads(row["event_ids"])

        # Enrich with event summaries
        event_summaries = []
        if event_ids:
            placeholders = ",".join("?" for _ in event_ids)
            event_rows = db.execute(
                f"SELECT id, title, category, severity FROM events WHERE id IN ({placeholders})",
                event_ids,
            ).fetchall()
            event_summaries = [
                EventSummary(
                    id=er["id"],
                    title=er["title"],
                    category=er["category"],
                    severity=er["severity"],
                )
                for er in event_rows
            ]

        results.append(
            NotificationResponse(
                id=row["id"],
                message=row["message"],
                sent_to=[PersonaResponse(**p) for p in sent_to],
                event_ids=event_ids,
                events=event_summaries,
                created_at=row["created_at"],
            )
        )
    return results

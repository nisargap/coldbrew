import uuid
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
import sqlite3

from database import get_db
from models import (
    PERSONAS,
    NotificationSendRequest,
    NotificationSendResponse,
    NotificationResponse,
    PersonaResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/notifications", tags=["notifications"])


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

    # Resolve personas
    sent_to = []
    for pid in body.persona_ids:
        persona = PERSONAS.get(pid)
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
        results.append(
            NotificationResponse(
                id=row["id"],
                message=row["message"],
                sent_to=[PersonaResponse(**p) for p in sent_to],
                event_ids=event_ids,
                created_at=row["created_at"],
            )
        )
    return results

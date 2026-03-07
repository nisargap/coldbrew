from pydantic import BaseModel
from typing import Optional


# --- Personas (hardcoded) ---

PERSONAS = {
    "alex-rivera": {"id": "alex-rivera", "name": "Alex Rivera", "role": "Warehouse Manager"},
    "sam-okafor": {"id": "sam-okafor", "name": "Sam Okafor", "role": "Maintenance Technician"},
    "jordan-lin": {"id": "jordan-lin", "name": "Jordan Lin", "role": "Dock Supervisor"},
    "priya-desai": {"id": "priya-desai", "name": "Priya Desai", "role": "Safety Officer"},
}


# --- Request / Response models ---

class FeedUploadResponse(BaseModel):
    feed_id: str
    status: str
    analysis_mode: str


class FeedResponse(BaseModel):
    feed_id: str
    feed_name: str
    status: str
    error_message: Optional[str] = None
    analysis_mode: str = "standard"
    created_at: str
    event_count: int


class EventResponse(BaseModel):
    id: str
    feed_id: str
    timestamp: str
    category: str
    severity: str
    title: str
    description: str
    source_feed: str
    thumbnail_url: Optional[str]
    confidence: float
    status: str


class EventSummary(BaseModel):
    id: str
    title: str
    category: str
    severity: str


class EventStatusUpdate(BaseModel):
    status: str


class NotificationSendRequest(BaseModel):
    event_ids: list[str]
    persona_ids: list[str]
    message: str


class PersonaResponse(BaseModel):
    id: str
    name: str
    role: str


class NotificationSendResponse(BaseModel):
    notification_id: str
    sent_to: list[PersonaResponse]
    event_count: int


class NotificationResponse(BaseModel):
    id: str
    message: str
    sent_to: list[PersonaResponse]
    event_ids: list[str]
    events: list[EventSummary] = []
    created_at: str

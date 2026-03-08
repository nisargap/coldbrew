import logging

from fastapi import APIRouter, Depends
import sqlite3

from database import get_db
from models import PersonaResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/personas", tags=["personas"])


@router.get("", response_model=list[PersonaResponse])
def list_personas(db: sqlite3.Connection = Depends(get_db)):
    """List all personas from the database."""
    rows = db.execute("SELECT id, name, role, category FROM personas ORDER BY name").fetchall()
    return [
        PersonaResponse(id=row["id"], name=row["name"], role=row["role"], category=row["category"])
        for row in rows
    ]

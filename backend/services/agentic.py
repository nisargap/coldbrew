"""
Automated agentic analysis — Claude enrichment of NomadicML-detected events.

After NomadicML analysis completes, this service:
1. Batches all events from a feed into a single Claude call
2. Receives structured enrichment (root cause, actions, risk score, voice script)
3. Stores enrichments in the event_enrichments table
4. Triggers ElevenLabs voice alerts for high-risk events (risk_score >= 7)
5. Publishes SSE events for real-time UI updates
"""

import json
import os
import uuid
import sqlite3
import logging
from datetime import datetime, timezone

from services.event_bus import publish as publish_sse

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "coldbrew.db")

SYSTEM_PROMPT = """You are a warehouse safety and operations analyst. You are given a list of events detected by a computer vision system analyzing warehouse CCTV footage.

For each event, produce a structured analysis. Respond ONLY with a JSON array (no wrapping object, no markdown).

Each element must have these fields:
- "event_index": integer matching the event's position in the input array (0-based)
- "root_cause": string, what likely caused this event (1-2 sentences)
- "recommended_actions": array of strings, specific actions to take (2-4 items)
- "urgency_reasoning": string, why this severity level is appropriate
- "suggested_personas": array of objects like {"role": "Safety Officer", "reason": "..."}. Use roles from: Warehouse Manager, Maintenance Technician, Dock Supervisor, Safety Officer
- "risk_score": integer 1-10 (10 = immediate danger to life/property)
- "correlation_notes": string or null, any connections to other events in this batch
- "voice_alert_script": string or null. If risk_score >= 7, provide a concise spoken alert (1-3 sentences) suitable for a warehouse PA system. Include the location, what happened, and what to do. If risk_score < 7, set to null.

Example response for 1 event:
[{"event_index":0,"root_cause":"...","recommended_actions":["..."],"urgency_reasoning":"...","suggested_personas":[{"role":"Safety Officer","reason":"..."}],"risk_score":8,"correlation_notes":null,"voice_alert_script":"Attention all personnel..."}]

Be specific to warehouse operations. Reference OSHA/NFPA where applicable. Respond ONLY with the JSON array."""


def enrich_events(feed_id: str, feed_name: str, events: list[dict], analysis_mode: str = "standard"):
    """
    Post-analysis Claude enrichment. Called after NomadicML events are stored.

    - Batches all events from a feed into a single Claude call
    - Parses structured JSON response
    - Stores enrichments in event_enrichments table
    - Triggers ElevenLabs TTS for high-risk events
    - Publishes SSE events on completion
    """
    conn = None
    try:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.info(f"[Agentic] ANTHROPIC_API_KEY not set — skipping enrichment for feed {feed_id}")
            _update_agentic_status(feed_id, "skipped")
            return

        _update_agentic_status(feed_id, "processing")

        # Publish SSE: enrichment started
        publish_sse({
            "type": "feed_update",
            "feed_id": feed_id,
            "status": "enriching",
            "feed_name": feed_name,
        })

        # Build the user message with all events
        user_payload = {
            "feed_name": feed_name,
            "analysis_mode": analysis_mode,
            "events": [
                {
                    "event_index": i,
                    "title": e.get("title", "Unknown"),
                    "description": e.get("description", ""),
                    "category": e.get("category", "Operational"),
                    "severity": e.get("severity", "Low"),
                    "confidence": e.get("confidence", 0.5),
                    "video_time": e.get("video_time", "00:00-00:00"),
                }
                for i, e in enumerate(events)
            ],
        }

        logger.info(f"[Agentic] Calling Claude for {len(events)} events from feed {feed_id}")

        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")

        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": json.dumps(user_payload, indent=2)},
            ],
        )

        # Extract text content from response
        response_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                response_text += block.text

        logger.info(f"[Agentic] Claude response received ({len(response_text)} chars)")

        # Parse JSON response
        enrichments_data = _parse_claude_response(response_text, len(events))

        if not enrichments_data:
            logger.warning(f"[Agentic] No enrichments parsed from Claude response")
            _update_agentic_status(feed_id, "error")
            return

        # Store enrichments in DB
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        now = datetime.now(timezone.utc).isoformat()

        stored_enrichments = []
        for enrichment in enrichments_data:
            event_index = enrichment.get("event_index", 0)
            if event_index >= len(events):
                continue

            event = events[event_index]
            event_id = event.get("id")
            if not event_id:
                continue

            enrichment_id = str(uuid.uuid4())

            recommended_actions = json.dumps(enrichment.get("recommended_actions", []))
            suggested_personas = json.dumps(enrichment.get("suggested_personas", []))
            voice_alert_script = enrichment.get("voice_alert_script")
            risk_score = min(max(int(enrichment.get("risk_score", 1)), 1), 10)

            try:
                conn.execute(
                    """INSERT OR REPLACE INTO event_enrichments
                    (id, event_id, feed_id, root_cause, recommended_actions, urgency_reasoning,
                     suggested_personas, risk_score, correlation_notes, voice_alert_script,
                     model_used, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        enrichment_id, event_id, feed_id,
                        enrichment.get("root_cause", "No root cause determined."),
                        recommended_actions,
                        enrichment.get("urgency_reasoning", ""),
                        suggested_personas,
                        risk_score,
                        enrichment.get("correlation_notes"),
                        voice_alert_script,
                        model,
                        now,
                    ),
                )

                stored_enrichments.append({
                    "id": enrichment_id,
                    "event_id": event_id,
                    "risk_score": risk_score,
                    "voice_alert_script": voice_alert_script,
                })
            except Exception as e:
                logger.error(f"[Agentic] Failed to store enrichment for event {event_id}: {e}")

        conn.commit()
        logger.info(f"[Agentic] Stored {len(stored_enrichments)} enrichments for feed {feed_id}")

        # --- Voice alerts for high-risk events ---
        _generate_voice_alerts(conn, stored_enrichments, feed_id, feed_name)

        conn.close()
        conn = None

        # Update feed agentic_status
        _update_agentic_status(feed_id, "completed")

        # Compute average risk score
        risk_scores = [e["risk_score"] for e in stored_enrichments]
        avg_risk = round(sum(risk_scores) / len(risk_scores), 1) if risk_scores else 0

        # Publish SSE: enrichment complete
        publish_sse({
            "type": "agentic_complete",
            "feed_id": feed_id,
            "enriched_count": len(stored_enrichments),
            "avg_risk_score": avg_risk,
            "feed_name": feed_name,
        })

        logger.info(f"[Agentic] Enrichment complete for feed {feed_id}. {len(stored_enrichments)} enriched, avg risk: {avg_risk}")

    except Exception as e:
        logger.error(f"[Agentic] Enrichment failed for feed {feed_id}: {e}", exc_info=True)
        _update_agentic_status(feed_id, "error")
    finally:
        if conn:
            conn.close()


def _parse_claude_response(text: str, expected_count: int) -> list[dict]:
    """Parse Claude's JSON response into a list of enrichments."""
    # Strip markdown code fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first and last lines (```json and ```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"[Agentic] JSON parse error: {e}")
        logger.error(f"[Agentic] Raw text (first 1000 chars): {cleaned[:1000]}")
        return []

    # Handle multiple response formats from Claude:
    #   { "enrichments": [...] }
    #   { "events": [...] }
    #   { "analyses": [...] }
    #   { "event_analyses": [...] }
    #   bare [...]
    if isinstance(parsed, dict):
        logger.info(f"[Agentic] Parsed dict keys: {list(parsed.keys())}")
        # Try common wrapper keys
        enrichments = (
            parsed.get("enrichments")
            or parsed.get("events")
            or parsed.get("analyses")
            or parsed.get("event_analyses")
            or parsed.get("results")
        )
        if enrichments is None:
            # Maybe the dict IS a single enrichment (only 1 event)
            if "root_cause" in parsed or "risk_score" in parsed:
                enrichments = [parsed]
            else:
                # Try the first list-valued key
                for k, v in parsed.items():
                    if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                        logger.info(f"[Agentic] Using key '{k}' as enrichments list")
                        enrichments = v
                        break
                if enrichments is None:
                    logger.error(f"[Agentic] Could not find enrichments list in dict keys: {list(parsed.keys())}")
                    enrichments = []
    elif isinstance(parsed, list):
        enrichments = parsed
    else:
        logger.error(f"[Agentic] Unexpected response type: {type(parsed)}")
        return []

    logger.info(f"[Agentic] Parsed {len(enrichments)} enrichment(s) from Claude response")
    return enrichments


def _generate_voice_alerts(conn: sqlite3.Connection, enrichments: list[dict], feed_id: str, feed_name: str):
    """Generate ElevenLabs voice alerts for high-risk enrichments (risk_score >= 7)."""
    elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY")

    for enrichment in enrichments:
        script = enrichment.get("voice_alert_script")
        if not script or enrichment["risk_score"] < 7:
            continue

        if not elevenlabs_key:
            # Mark as skipped
            conn.execute(
                "UPDATE event_enrichments SET voice_alert_status = 'skipped' WHERE id = ?",
                (enrichment["id"],),
            )
            conn.commit()
            continue

        try:
            from services.voice import generate_voice_alert

            url = generate_voice_alert(
                enrichment["id"],
                enrichment["event_id"],
                script,
            )
            conn.execute(
                "UPDATE event_enrichments SET voice_alert_url = ?, voice_alert_status = 'completed' WHERE id = ?",
                (url, enrichment["id"]),
            )
            conn.commit()

            # Publish SSE for voice alert
            publish_sse({
                "type": "voice_alert_ready",
                "feed_id": feed_id,
                "event_id": enrichment["event_id"],
                "voice_alert_url": url,
                "risk_score": enrichment["risk_score"],
                "feed_name": feed_name,
            })

            logger.info(f"[Voice] Generated alert for event {enrichment['event_id']}: {url}")

        except Exception as e:
            logger.warning(f"[Voice] TTS failed for event {enrichment['event_id']}: {e}")
            conn.execute(
                "UPDATE event_enrichments SET voice_alert_status = 'error' WHERE id = ?",
                (enrichment["id"],),
            )
            conn.commit()


def _update_agentic_status(feed_id: str, status: str):
    """Update the agentic_status column on the feeds table."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE feeds SET agentic_status = ? WHERE id = ?", (status, feed_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"[Agentic] Failed to update agentic_status for {feed_id}: {e}")


def get_enrichment_for_event(event_id: str) -> dict | None:
    """Retrieve the enrichment for a single event."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM event_enrichments WHERE event_id = ?", (event_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return _row_to_enrichment(row)


def get_enrichments_for_feed(feed_id: str) -> list[dict]:
    """Retrieve all enrichments for a feed."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM event_enrichments WHERE feed_id = ? ORDER BY created_at", (feed_id,)).fetchall()
    conn.close()
    return [_row_to_enrichment(row) for row in rows]


def _row_to_enrichment(row: sqlite3.Row) -> dict:
    """Convert a DB row to an enrichment dict."""
    return {
        "id": row["id"],
        "event_id": row["event_id"],
        "feed_id": row["feed_id"],
        "root_cause": row["root_cause"],
        "recommended_actions": json.loads(row["recommended_actions"]) if row["recommended_actions"] else [],
        "urgency_reasoning": row["urgency_reasoning"],
        "suggested_personas": json.loads(row["suggested_personas"]) if row["suggested_personas"] else [],
        "risk_score": row["risk_score"],
        "correlation_notes": row["correlation_notes"],
        "voice_alert_script": row["voice_alert_script"],
        "voice_alert_url": row["voice_alert_url"],
        "voice_alert_status": row["voice_alert_status"],
        "model_used": row["model_used"],
        "created_at": row["created_at"],
    }

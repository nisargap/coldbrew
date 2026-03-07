"""
NomadicML SDK integration for video analysis.

This service handles:
1. Uploading videos to NomadicML
2. Running analysis with the warehouse prompt
3. Parsing results into Event records
4. Storing events in the database
"""

import uuid
import os
import json
import sqlite3
import logging
from datetime import datetime, timezone

from services.event_bus import publish as publish_sse

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "coldbrew.db")

WAREHOUSE_PROMPT = (
    "Analyze this warehouse or facility footage for notable events. "
    "Detect and describe any of the following:\n"
    "- SAFETY: Workers without PPE (hard hats, vests, safety glasses), "
    "people in restricted zones, forklift near-misses, blocked emergency exits, "
    "unsafe lifting or climbing\n"
    "- EQUIPMENT: Conveyor belt jams or stops, forklift malfunctions, "
    "dock door failures, broken lighting, machinery operating abnormally\n"
    "- SHIPMENT: Truck arrivals at loading docks, truck departures, "
    "loading/unloading activity, damaged or fallen cargo, "
    "empty docks with no expected activity\n"
    "- OPERATIONAL: Aisles blocked by misplaced pallets or equipment, "
    "unusual crowd density, zones with no activity for extended periods, "
    "disorganized staging areas\n"
    "- ENVIRONMENTAL: Liquid spills on floor, smoke or haze, "
    "water leaks, debris accumulation, visible temperature issues\n\n"
    "For each event found, provide: a short title, "
    "which category it falls under (Safety/Equipment/Shipment/Operational/Environmental), "
    "an estimated severity (Critical/High/Medium/Low), "
    "and a one-sentence description of what is happening."
)


def classify_category(event_type: str, description: str) -> str:
    text = f"{event_type} {description}".lower()
    if any(kw in text for kw in ["ppe", "hard hat", "vest", "safety", "near-miss", "restricted", "exit", "violation"]):
        return "Safety"
    elif any(kw in text for kw in ["conveyor", "forklift", "malfunction", "broken", "jam", "machinery", "equipment"]):
        return "Equipment"
    elif any(kw in text for kw in ["truck", "shipment", "loading", "dock", "cargo", "delivery", "arrival", "departure"]):
        return "Shipment"
    elif any(kw in text for kw in ["blocked", "aisle", "pallet", "idle", "crowd", "staging", "operational"]):
        return "Operational"
    elif any(kw in text for kw in ["spill", "smoke", "leak", "water", "debris", "temperature", "environmental"]):
        return "Environmental"
    return "Operational"


def classify_severity(event_type: str, description: str) -> str:
    text = f"{event_type} {description}".lower()
    if any(kw in text for kw in ["fire", "smoke", "collision", "injury", "critical", "emergency", "trapped"]):
        return "Critical"
    elif any(kw in text for kw in ["near-miss", "malfunction", "no ppe", "hard hat", "blocked exit", "high", "danger"]):
        return "High"
    elif any(kw in text for kw in ["spill", "jam", "stopped", "blocked", "damaged", "medium"]):
        return "Medium"
    return "Low"


def extract_title(description: str) -> str:
    if not description:
        return "Unnamed Event"
    first_sentence = description.split(".")[0].strip()
    if len(first_sentence) > 60:
        return first_sentence[:57] + "..."
    return first_sentence


def parse_nomadic_events(analysis_response: dict, feed_id: str, feed_name: str) -> list[dict]:
    events = []

    # Log the full response for debugging
    logger.info(f"[Parser] Full response keys: {list(analysis_response.keys())}")
    logger.info(f"[Parser] Summary: {analysis_response.get('summary', 'N/A')}")

    raw_events = analysis_response.get("events", [])
    logger.info(f"[Parser] Number of raw events: {len(raw_events)}")

    for i, raw in enumerate(raw_events):
        logger.info(f"[Parser] Raw event {i}: {json.dumps(raw, default=str)}")

        # Extract fields from NomadicML SDK response
        # Actual SDK format: aiAnalysis, label, category, severity (lowercase), t_start, t_end, confidence
        description = (
            raw.get("aiAnalysis")
            or raw.get("ai_analysis")
            or raw.get("description")
            or raw.get("summary")
            or raw.get("text")
            or "No description available"
        )

        title = (
            raw.get("label")
            or raw.get("title")
            or raw.get("event_title")
            or raw.get("name")
            or extract_title(description)
        )

        event_type = (
            raw.get("category")
            or raw.get("type")
            or raw.get("event_type")
            or ""
        )

        confidence = raw.get("confidence") or raw.get("similarity_score") or raw.get("score") or 0.8

        # Handle confidence as percentage vs decimal
        if isinstance(confidence, (int, float)) and confidence > 1:
            confidence = confidence / 100.0

        # Severity from SDK is lowercase — normalize to title case
        severity_raw = (raw.get("severity") or raw.get("severity_level") or "").strip().title()

        # Category from SDK matches our schema
        category_raw = (raw.get("category") or raw.get("event_category") or "").strip()

        event = {
            "id": str(uuid.uuid4()),
            "feed_id": feed_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "category": category_raw if category_raw in ("Safety", "Equipment", "Shipment", "Operational", "Environmental") else classify_category(event_type, description),
            "severity": severity_raw if severity_raw in ("Critical", "High", "Medium", "Low") else classify_severity(event_type, description),
            "title": title,
            "description": description,
            "source_feed": feed_name,
            "video_time": f"{raw.get('t_start', '00:00')}-{raw.get('t_end', '00:00')}",
            "thumbnail_url": raw.get("thumbnail_url") or raw.get("thumbnail") or raw.get("frame_url") or None,
            "confidence": confidence,
            "status": "new",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"[Parser] Parsed event {i}: title={event['title']}, cat={event['category']}, sev={event['severity']}")
        events.append(event)

    # Also parse the summary as an event if no individual events were extracted well
    summary = analysis_response.get("summary", "")
    if summary and all(e["description"] == "No description available" for e in events):
        logger.info(f"[Parser] Events had no descriptions, using summary as fallback")
        # Replace event descriptions with the summary
        if len(events) == 1:
            events[0]["description"] = summary
            events[0]["title"] = extract_title(summary)
            events[0]["category"] = classify_category("", summary)
            events[0]["severity"] = classify_severity("", summary)

    return events


def analyze_video(file_path: str, feed_id: str, feed_name: str):
    """
    Background task: upload video to NomadicML, analyze, store events.
    """
    conn = None
    try:
        logger.info(f"[Analysis] Starting for feed {feed_id}: {file_path}")

        # Import NomadicML SDK
        from nomadicml import NomadicML
        from nomadicml.video import AnalysisType, CustomCategory

        api_key = os.environ.get("NOMADIC_SDK_API_KEY")
        if not api_key:
            raise ValueError("NOMADIC_SDK_API_KEY environment variable is not set")

        client = NomadicML(api_key=api_key)

        # Step 1: Upload video to NomadicML (with retry)
        logger.info(f"[Analysis] Uploading video to NomadicML...")
        upload_response = None
        for attempt in range(3):
            try:
                upload_response = client.upload(file_path)
                break
            except Exception as upload_err:
                if attempt == 2:
                    raise
                wait = 2 ** attempt
                logger.warning(f"[Analysis] Upload attempt {attempt + 1} failed: {upload_err}. Retrying in {wait}s...")
                import time
                time.sleep(wait)
        video_id = upload_response["video_id"]
        logger.info(f"[Analysis] Upload complete. video_id={video_id}")

        # Step 2: Run analysis
        logger.info(f"[Analysis] Running analysis...")
        analysis = client.analyze(
            video_id,
            analysis_type=AnalysisType.ASK,
            custom_event=WAREHOUSE_PROMPT,
            custom_category=CustomCategory.DRIVING,
        )
        logger.info(f"[Analysis] Analysis complete. Raw response keys: {list(analysis.keys()) if isinstance(analysis, dict) else type(analysis)}")

        # Step 3: Parse events
        if isinstance(analysis, dict):
            events = parse_nomadic_events(analysis, feed_id, feed_name)
        else:
            logger.warning(f"[Analysis] Unexpected response type: {type(analysis)}")
            events = []

        # Filter by confidence
        events = [e for e in events if e.get("confidence", 0) >= 0.7]
        logger.info(f"[Analysis] {len(events)} events after confidence filtering")

        # Step 4: Store events in database
        conn = sqlite3.connect(DB_PATH)
        for event in events:
            conn.execute(
                """INSERT INTO events (id, feed_id, timestamp, category, severity, title, description,
                   source_feed, thumbnail_url, confidence, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event["id"], event["feed_id"], event["timestamp"],
                    event["category"], event["severity"], event["title"],
                    event["description"], event["source_feed"], event["thumbnail_url"],
                    event["confidence"], event["status"], event["created_at"],
                ),
            )

        # Step 5: Update feed status
        conn.execute(
            "UPDATE feeds SET status = ?, event_count = ? WHERE id = ?",
            ("completed", len(events), feed_id),
        )
        conn.commit()
        logger.info(f"[Analysis] Feed {feed_id} complete. {len(events)} events stored.")

        # Publish real-time update via SSE
        publish_sse({
            "type": "feed_update",
            "feed_id": feed_id,
            "status": "completed",
            "event_count": len(events),
            "feed_name": feed_name,
        })

    except Exception as e:
        logger.error(f"[Analysis] Failed for feed {feed_id}: {e}", exc_info=True)
        error_msg = str(e)[:500]
        try:
            if conn is None:
                conn = sqlite3.connect(DB_PATH)
            conn.execute("UPDATE feeds SET status = ?, error_message = ? WHERE id = ?", ("error", error_msg, feed_id))
            conn.commit()
        except Exception as db_err:
            logger.error(f"[Analysis] Failed to update feed status to error: {db_err}")

        # Publish error update via SSE
        publish_sse({
            "type": "feed_update",
            "feed_id": feed_id,
            "status": "error",
            "error_message": error_msg,
            "feed_name": feed_name,
        })
    finally:
        if conn:
            conn.close()

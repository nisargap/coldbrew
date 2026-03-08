"""
NomadicML SDK integration for video analysis.

Supports two analysis modes:
1. Standard (ASK) — Custom event detection with warehouse prompt
2. Agent (GENERAL_AGENT) — NomadicML Agent with Robotic Action Segmentation (ROBOTICS category)
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

# --- Prompts ---

WAREHOUSE_PROMPT_STANDARD = (
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

WAREHOUSE_PROMPT_AGENT = (
    "You are a warehouse safety and operations monitoring agent. "
    "Segment and analyze all actions and events in this warehouse or industrial facility footage.\n\n"
    "For every action or event you detect, classify it into EXACTLY ONE of these warehouse incident categories:\n"
    "- Safety: PPE violations, near-misses, unsafe behavior, restricted zone entries, blocked exits\n"
    "- Equipment: Machinery malfunctions, conveyor issues, forklift problems, broken infrastructure\n"
    "- Shipment: Truck arrivals/departures, loading/unloading, damaged cargo, dock activity\n"
    "- Operational: Blocked aisles, misplaced inventory, idle zones, workflow disruptions\n"
    "- Environmental: Spills, leaks, smoke, debris, temperature hazards\n\n"
    "For each detected action segment, provide:\n"
    "1. A clear, specific title describing the action\n"
    "2. The category (Safety/Equipment/Shipment/Operational/Environmental)\n"
    "3. Severity (Critical/High/Medium/Low) based on risk to people and operations\n"
    "4. A detailed description of what is happening and why it matters\n\n"
    "Be thorough — identify every distinct action, worker movement, "
    "equipment operation, and environmental change in the footage."
)


# --- Classification helpers ---

def classify_category(event_type: str, description: str) -> str:
    text = f"{event_type} {description}".lower()
    if any(kw in text for kw in ["ppe", "hard hat", "vest", "safety", "near-miss", "restricted", "exit", "violation", "worker", "injury"]):
        return "Safety"
    elif any(kw in text for kw in ["conveyor", "forklift", "malfunction", "broken", "jam", "machinery", "equipment", "motor", "belt"]):
        return "Equipment"
    elif any(kw in text for kw in ["truck", "shipment", "loading", "dock", "cargo", "delivery", "arrival", "departure", "unloading"]):
        return "Shipment"
    elif any(kw in text for kw in ["blocked", "aisle", "pallet", "idle", "crowd", "staging", "operational", "workflow", "inventory"]):
        return "Operational"
    elif any(kw in text for kw in ["spill", "smoke", "leak", "water", "debris", "temperature", "environmental", "flood", "fire", "haze", "overflow", "liquid", "hazard", "chemical", "gas", "toxic"]):
        return "Environmental"
    return "Operational"


def classify_severity(event_type: str, description: str) -> str:
    text = f"{event_type} {description}".lower()
    if any(kw in text for kw in ["fire", "smoke", "collision", "injury", "critical", "emergency", "trapped", "explosion", "death"]):
        return "Critical"
    elif any(kw in text for kw in ["near-miss", "malfunction", "no ppe", "hard hat", "blocked exit", "high", "danger", "burst", "flood", "overflow", "hazard", "toxic"]):
        return "High"
    elif any(kw in text for kw in ["spill", "jam", "stopped", "blocked", "damaged", "medium", "leak", "liquid", "distraction"]):
        return "Medium"
    return "Low"


def extract_title(description: str) -> str:
    if not description:
        return "Unnamed Event"
    first_sentence = description.split(".")[0].strip()
    if len(first_sentence) > 60:
        return first_sentence[:57] + "..."
    return first_sentence


# --- Response parser ---

def parse_nomadic_events(analysis_response: dict, feed_id: str, feed_name: str) -> list[dict]:
    events = []

    logger.info(f"[Parser] Full response keys: {list(analysis_response.keys())}")
    logger.info(f"[Parser] Summary: {analysis_response.get('summary', 'N/A')}")

    raw_events = analysis_response.get("events", [])
    logger.info(f"[Parser] Number of raw events: {len(raw_events)}")

    for i, raw in enumerate(raw_events):
        logger.info(f"[Parser] Raw event {i}: {json.dumps(raw, default=str)}")

        # --- Build description from all available text fields ---
        # Agent mode only has "label"; ASK mode has "aiAnalysis", "description", etc.
        label = raw.get("label") or ""
        ai_analysis = (
            raw.get("aiAnalysis")
            or raw.get("ai_analysis")
            or raw.get("description")
            or raw.get("summary")
            or raw.get("text")
            or ""
        )

        # Use the richest text as description; label as fallback
        if ai_analysis:
            description = ai_analysis
        elif label:
            # Agent mode: label IS the description
            # Strip prefix tags like "[Detection]" for a cleaner description
            description = label
        else:
            description = "No description available"

        # Title: use label if available, otherwise extract from description
        if label:
            # Clean up prefix tags like "[Detection]" for the title
            clean_label = label
            if clean_label.startswith("[") and "]" in clean_label:
                clean_label = clean_label[clean_label.index("]") + 1:].strip()
            title = extract_title(clean_label)
        else:
            title = (
                raw.get("title")
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
        if isinstance(confidence, (int, float)) and confidence > 1:
            confidence = confidence / 100.0

        # Severity: normalize to title case
        severity_raw = (raw.get("severity") or raw.get("severity_level") or "").strip().title()

        # Category: from SDK or classify locally
        category_raw = (raw.get("category") or raw.get("event_category") or "").strip()

        # Classify using the FULL text (label + description) for accurate matching
        full_text = f"{label} {description} {event_type}"

        # Validate category against our taxonomy
        valid_categories = {"Safety", "Equipment", "Shipment", "Operational", "Environmental"}
        if category_raw not in valid_categories:
            category_raw = classify_category(full_text, description)

        valid_severities = {"Critical", "High", "Medium", "Low"}
        if severity_raw not in valid_severities:
            severity_raw = classify_severity(full_text, description)

        # Video time: handle both "t_start"/"t_end" (ASK) and "start_time"/"end_time" (Agent)
        t_start = raw.get("t_start") or raw.get("start_time") or "00:00"
        t_end = raw.get("t_end") or raw.get("end_time") or "00:00"

        event = {
            "id": str(uuid.uuid4()),
            "feed_id": feed_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "category": category_raw,
            "severity": severity_raw,
            "title": title,
            "description": description,
            "source_feed": feed_name,
            "video_time": f"{t_start}-{t_end}",
            "thumbnail_url": raw.get("thumbnail_url") or raw.get("thumbnail") or raw.get("frame_url") or None,
            "confidence": confidence,
            "status": "new",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"[Parser] Parsed event {i}: title={event['title']}, cat={event['category']}, sev={event['severity']}")
        events.append(event)

    # Fallback: if events had no descriptions, use summary
    summary = analysis_response.get("summary", "")
    if summary and all(e["description"] == "No description available" for e in events):
        logger.info(f"[Parser] Events had no descriptions, using summary as fallback")
        if len(events) == 1:
            events[0]["description"] = summary
            events[0]["title"] = extract_title(summary)
            events[0]["category"] = classify_category("", summary)
            events[0]["severity"] = classify_severity("", summary)

    return events


# --- Main analysis function ---

def analyze_video(file_path: str, feed_id: str, feed_name: str, analysis_mode: str = "standard", confidence_level: str = "low"):
    """
    Background task: upload video to NomadicML, analyze, store events.

    analysis_mode:
      - "standard": AnalysisType.ASK + CustomCategory.ROBOTICS
      - "agent":    AnalysisType.GENERAL_AGENT

    confidence_level:
      - "low":  returns more events including lower-confidence detections
      - "high": returns only high-confidence detections
    """
    conn = None
    try:
        logger.info(f"[Analysis] Starting for feed {feed_id} (mode={analysis_mode}, confidence={confidence_level}): {file_path}")

        from nomadicml import NomadicML
        from nomadicml.video import AnalysisType, CustomCategory

        api_key = os.environ.get("NOMADIC_SDK_API_KEY")
        if not api_key:
            raise ValueError("NOMADIC_SDK_API_KEY environment variable is not set")

        client = NomadicML(api_key=api_key)

        # Step 1: Upload video (with retry)
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

        # Step 2: Run analysis based on mode
        logger.info(f"[Analysis] Running analysis (mode={analysis_mode})...")

        if analysis_mode == "agent":
            # NomadicML Agent — no custom_event or custom_category allowed
            analysis = client.analyze(
                video_id,
                analysis_type=AnalysisType.GENERAL_AGENT,
                confidence=confidence_level,
            )
        else:
            # Standard ASK mode — supports custom_event for warehouse-specific prompting
            analysis = client.analyze(
                video_id,
                analysis_type=AnalysisType.ASK,
                custom_event=WAREHOUSE_PROMPT_STANDARD,
                custom_category=CustomCategory.ROBOTICS,
                confidence=confidence_level,
            )

        logger.info(f"[Analysis] Analysis complete. Raw response keys: {list(analysis.keys()) if isinstance(analysis, dict) else type(analysis)}")

        # Step 3: Parse events
        if isinstance(analysis, dict):
            events = parse_nomadic_events(analysis, feed_id, feed_name)
        else:
            logger.warning(f"[Analysis] Unexpected response type: {type(analysis)}")
            events = []

        logger.info(f"[Analysis] {len(events)} events parsed (confidence_level={confidence_level})")

        # Step 4: Store events in database
        conn = sqlite3.connect(DB_PATH)

        # If re-analyzing, clear old events for this feed first
        conn.execute("DELETE FROM events WHERE feed_id = ?", (feed_id,))

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
        # Check if feed is in "monitoring" mode (livestream) — don't overwrite status
        current_row = conn.execute("SELECT status FROM feeds WHERE id = ?", (feed_id,)).fetchone()
        current_status = current_row[0] if current_row else None

        if current_status == "monitoring":
            # Livestream feed: only update event_count, keep "monitoring" status
            total_events = conn.execute("SELECT COUNT(*) FROM events WHERE feed_id = ?", (feed_id,)).fetchone()[0]
            conn.execute(
                "UPDATE feeds SET event_count = ?, analysis_mode = ? WHERE id = ?",
                (total_events, analysis_mode, feed_id),
            )
            conn.commit()
            logger.info(f"[Analysis] Feed {feed_id} cycle complete ({analysis_mode}). {len(events)} new events, {total_events} total.")
        else:
            conn.execute(
                "UPDATE feeds SET status = ?, event_count = ?, analysis_mode = ? WHERE id = ?",
                ("completed", len(events), analysis_mode, feed_id),
            )
            conn.commit()
            logger.info(f"[Analysis] Feed {feed_id} complete ({analysis_mode}). {len(events)} events stored.")

            # Publish real-time update via SSE (only for non-monitoring feeds)
            publish_sse({
                "type": "feed_update",
                "feed_id": feed_id,
                "status": "completed",
                "event_count": len(events),
                "feed_name": feed_name,
                "analysis_mode": analysis_mode,
            })

    except Exception as e:
        logger.error(f"[Analysis] Failed for feed {feed_id}: {e}", exc_info=True)
        error_msg = str(e)[:500]
        try:
            if conn is None:
                conn = sqlite3.connect(DB_PATH)
            # Don't overwrite "monitoring" status — the livestream loop handles retries
            current_row = conn.execute("SELECT status FROM feeds WHERE id = ?", (feed_id,)).fetchone()
            if current_row and current_row[0] == "monitoring":
                logger.info(f"[Analysis] Feed {feed_id} cycle failed but feed is monitoring — skipping status update")
            else:
                conn.execute("UPDATE feeds SET status = ?, error_message = ? WHERE id = ?", ("error", error_msg, feed_id))
                conn.commit()
        except Exception as db_err:
            logger.error(f"[Analysis] Failed to update feed status to error: {db_err}")

        # Don't publish error SSE for monitoring feeds (cycle errors handled by monitor)
        current_status_check = None
        try:
            tmp_conn = sqlite3.connect(DB_PATH)
            r = tmp_conn.execute("SELECT status FROM feeds WHERE id = ?", (feed_id,)).fetchone()
            current_status_check = r[0] if r else None
            tmp_conn.close()
        except Exception:
            pass

        if current_status_check != "monitoring":
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

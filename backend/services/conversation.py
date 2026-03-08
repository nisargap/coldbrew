"""
ElevenLabs Conversational AI — Dynamic voice agent for warehouse analysis debrief.

After agentic enrichment completes, this service:
1. Creates an ElevenLabs Conversational AI agent configured with the feed's analysis context
2. Returns a signed WebSocket URL so the frontend can connect directly
3. Cleans up agents when conversations end

The agent narrates findings, then offers to discuss specific events in detail.
"""

import os
import json
import logging
import sqlite3
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "coldbrew.db")

ELEVENLABS_API = "https://api.elevenlabs.io/v1"


def _api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise ValueError("ELEVENLABS_API_KEY not set — conversational AI unavailable")
    return key


def _build_system_prompt(feed_name: str, events: list[dict], enrichments: list[dict]) -> str:
    """Build a dynamic system prompt with the full analysis context."""

    # Map enrichments by event_id for easy lookup
    enrichment_map = {e["event_id"]: e for e in enrichments}

    event_summaries = []
    for i, ev in enumerate(events):
        enr = enrichment_map.get(ev["id"])
        summary = (
            f"Event {i + 1}: \"{ev.get('title', 'Unknown')}\"\n"
            f"  Category: {ev.get('category', 'Unknown')} | Severity: {ev.get('severity', 'Unknown')} | "
            f"Confidence: {ev.get('confidence', 0):.0%}\n"
            f"  Description: {ev.get('description', 'N/A')}\n"
        )
        if enr:
            actions = enr.get("recommended_actions", [])
            if isinstance(actions, str):
                try:
                    actions = json.loads(actions)
                except Exception:
                    actions = [actions]
            personas = enr.get("suggested_personas", [])
            if isinstance(personas, str):
                try:
                    personas = json.loads(personas)
                except Exception:
                    personas = []

            persona_names = [
                p["role"] if isinstance(p, dict) else str(p) for p in personas
            ]

            summary += (
                f"  Root Cause: {enr.get('root_cause', 'N/A')}\n"
                f"  Risk Score: {enr.get('risk_score', 'N/A')}/10\n"
                f"  Recommended Actions: {'; '.join(actions) if actions else 'N/A'}\n"
                f"  Urgency: {enr.get('urgency_reasoning', 'N/A')}\n"
                f"  Suggested Personnel: {', '.join(persona_names) if persona_names else 'N/A'}\n"
                f"  Correlations: {enr.get('correlation_notes', 'None')}\n"
            )
        event_summaries.append(summary)

    events_text = "\n".join(event_summaries) if event_summaries else "No events detected."

    avg_risk = 0
    if enrichments:
        scores = [e.get("risk_score", 0) for e in enrichments if isinstance(e.get("risk_score"), (int, float))]
        avg_risk = sum(scores) / len(scores) if scores else 0

    critical_count = sum(1 for e in events if e.get("severity") in ("Critical", "High"))

    return f"""You are the ColdBrew Warehouse Intelligence Analyst — a professional, knowledgeable voice agent for warehouse safety and operations.

You have just completed an analysis of a warehouse CCTV feed called "{feed_name}".

== ANALYSIS SUMMARY ==
Total Events Detected: {len(events)}
Critical/High Severity Events: {critical_count}
Average Risk Score: {avg_risk:.1f}/10

== DETAILED FINDINGS ==
{events_text}

== YOUR ROLE ==
1. START by giving a clear, concise narration of what was found in this feed. Mention the key findings — especially critical and high severity events. Be specific about what happened, where, and why it matters.

2. After your narration, ASK the user if they'd like to:
   - Dig deeper into any specific event
   - Understand the recommended actions for a particular issue
   - Know which personnel should be notified
   - Get clarification on risk scores or root causes
   - Discuss correlations between events

3. RESPOND to follow-up questions with specific, actionable detail drawn from the analysis data above.

== STYLE ==
- Be professional but conversational — like a senior safety officer briefing the team
- Use specific details from the analysis (risk scores, categories, recommended actions)
- Reference OSHA/NFPA standards when relevant
- Keep initial narration to 30-60 seconds (avoid droning on)
- When asked about a specific event, provide the full detail available
- If asked about something not in the analysis, say so honestly"""


def _build_first_message(feed_name: str, event_count: int, critical_count: int) -> str:
    """Build the agent's opening narration hook."""
    if event_count == 0:
        return f"I've completed the analysis of your feed \"{feed_name}\". Good news — no significant events were detected. Would you like me to explain what I looked for?"

    severity_note = ""
    if critical_count > 0:
        severity_note = f", including {critical_count} critical or high severity {'issue' if critical_count == 1 else 'issues'} that need your attention"

    return (
        f"I've just finished analyzing the warehouse feed \"{feed_name}\". "
        f"I detected {event_count} {'event' if event_count == 1 else 'events'}{severity_note}. "
        f"Let me walk you through what I found."
    )


def create_conversation_agent(feed_id: str) -> dict:
    """
    Create an ElevenLabs Conversational AI agent configured with this feed's analysis context.

    Returns: { "agent_id": str, "signed_url": str }
    """
    api_key = _api_key()

    # Fetch feed info
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        feed_row = conn.execute("SELECT feed_name FROM feeds WHERE id = ?", (feed_id,)).fetchone()
        if not feed_row:
            raise ValueError(f"Feed '{feed_id}' not found")
        feed_name = feed_row["feed_name"]

        # Fetch events
        event_rows = conn.execute(
            "SELECT id, title, description, category, severity, confidence, timestamp FROM events WHERE feed_id = ? ORDER BY created_at",
            (feed_id,),
        ).fetchall()
        events = [dict(r) for r in event_rows]

        # Fetch enrichments
        enrichment_rows = conn.execute(
            "SELECT * FROM event_enrichments WHERE feed_id = ?",
            (feed_id,),
        ).fetchall()
        enrichments = [dict(r) for r in enrichment_rows]
    finally:
        conn.close()

    critical_count = sum(1 for e in events if e.get("severity") in ("Critical", "High"))

    system_prompt = _build_system_prompt(feed_name, events, enrichments)
    first_message = _build_first_message(feed_name, len(events), critical_count)

    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

    # Create the agent via ElevenLabs API
    payload = json.dumps({
        "name": f"ColdBrew — {feed_name[:40]}",
        "conversation_config": {
            "agent": {
                "prompt": {
                    "prompt": system_prompt,
                },
                "first_message": first_message,
                "language": "en",
            },
            "tts": {
                "voice_id": voice_id,
            },
        },
    }).encode()

    req = urllib.request.Request(
        f"{ELEVENLABS_API}/convai/agents/create",
        data=payload,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
        },
    )

    try:
        resp = urllib.request.urlopen(req, timeout=15)
        agent_data = json.loads(resp.read())
        agent_id = agent_data["agent_id"]
        logger.info(f"[ConvAI] Created agent {agent_id} for feed {feed_id} ({feed_name})")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        logger.error(f"[ConvAI] Agent creation failed: HTTP {e.code}: {body[:300]}")
        raise RuntimeError(f"ElevenLabs agent creation failed (HTTP {e.code}): {body[:200]}")
    except Exception as e:
        logger.error(f"[ConvAI] Agent creation error: {e}")
        raise

    # Get a signed WebSocket URL for the frontend
    signed_url = _get_signed_url(api_key, agent_id)

    return {
        "agent_id": agent_id,
        "signed_url": signed_url,
        "feed_name": feed_name,
        "event_count": len(events),
        "critical_count": critical_count,
    }


def _get_signed_url(api_key: str, agent_id: str) -> str:
    """Get a signed WebSocket URL for a conversational AI session."""
    req = urllib.request.Request(
        f"{ELEVENLABS_API}/convai/conversation/get-signed-url?agent_id={agent_id}",
        headers={"xi-api-key": api_key},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        return data["signed_url"]
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        logger.error(f"[ConvAI] Signed URL failed: HTTP {e.code}: {body[:300]}")
        raise RuntimeError(f"Failed to get conversation URL (HTTP {e.code})")
    except Exception as e:
        logger.error(f"[ConvAI] Signed URL error: {e}")
        raise


def delete_conversation_agent(agent_id: str) -> bool:
    """Clean up an ElevenLabs Conversational AI agent."""
    try:
        api_key = _api_key()
    except ValueError:
        return False

    req = urllib.request.Request(
        f"{ELEVENLABS_API}/convai/agents/{agent_id}",
        headers={"xi-api-key": api_key},
        method="DELETE",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        logger.info(f"[ConvAI] Deleted agent {agent_id}")
        return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            logger.info(f"[ConvAI] Agent {agent_id} already deleted (404)")
            return True
        logger.warning(f"[ConvAI] Failed to delete agent {agent_id}: HTTP {e.code}")
        return False
    except Exception as e:
        logger.warning(f"[ConvAI] Failed to delete agent {agent_id}: {e}")
        return False

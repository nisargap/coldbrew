# ColdBrew — Feature PRD: Agentic Post-Analysis, Voice Alerts & Daily Reports

**Track:** Robotics · **Event:** NomadicML 12-Hour Hackathon

---

## Overview

Three tightly coupled features that turn raw NomadicML detections into actionable, multi-modal intelligence:

1. **Automated Agentic Analysis** — After NomadicML returns detected events, Claude automatically enriches each event with root-cause reasoning, recommended actions, urgency scoring, and smart persona routing.
2. **Voice Alert Generation (ElevenLabs)** — Critical and high-severity events get an auto-generated voice alert powered by ElevenLabs TTS, spoken as if a warehouse PA system is delivering urgent notifications. Plugs directly into the Claude enrichment output.
3. **Daily Report Generation** — On-demand single-day summary reports aggregating all events, agentic insights, notification activity, and operational recommendations. Includes an optional audio narration of the executive summary.

The full pipeline: **Upload → NomadicML Analyze → _Claude Enrichment_ → _ElevenLabs Voice Alerts_ → Dashboard → Notify → _Report (with audio)_**.

---

## Problem Statement

NomadicML's vision analysis excels at _detecting what happened_ — a forklift near-miss, a spill, a missing shipment. But warehouse operators need more than detection:

- **"Why does this matter?"** — Context about severity, potential consequences, and regulatory implications.
- **"What should I do?"** — Concrete recommended actions tied to the specific event.
- **"Who needs to know?"** — Automatic routing suggestions based on event semantics, not just category.
- **"What happened today?"** — A shift-end summary that captures the full picture without scrolling through dozens of individual events.

The gap between _detection_ and _decision_ is where these features live.

Additionally, warehouse floors are **noisy, hands-busy environments**. Workers can't always stop to read a screen. Voice alerts bridge that last mile — a spoken alert over a PA system or a worker's earpiece is faster and harder to ignore than a push notification.

---

## Feature 1: Automated Agentic Analysis

### Concept

After `analyze_video()` finishes and events are stored in the database, a second-pass **Claude agentic analysis** automatically runs. For each event (or batch of events), Claude receives the NomadicML detection data and produces structured enrichment.

### Data Flow

```
NomadicML Analysis Complete
        │
        ▼
┌─────────────────────────┐
│  Claude Agentic Pass    │
│                         │
│  Input:                 │
│  - Event title          │
│  - Event description    │
│  - Category / Severity  │
│  - Video timestamp      │
│  - Feed name / context  │
│  - Other events from    │
│    same feed (batch)    │
│                         │
│  Output (per event):    │
│  - Root cause analysis  │
│  - Recommended actions  │
│  - Urgency reasoning    │
│  - Suggested personas   │
│  - Risk score (1-10)    │
│  - Correlation notes    │
│  - Voice alert script   │
└─────────────────────────┘
        │
        ▼
  Store enrichment in DB
        │
        ├───────────────────────────┐
        │                           ▼
        │              ┌────────────────────────┐
        │              │  ElevenLabs TTS         │
        │              │  (Critical/High only)   │
        │              │                         │
        │              │  Input:                 │
        │              │  - Voice alert script   │
        │              │    from Claude           │
        │              │                         │
        │              │  Output:                │
        │              │  - MP3 audio file        │
        │              │  - Stored in /uploads    │
        │              │  - URL saved to DB       │
        │              └────────────────────────┘
        │                           │
        ▼                           ▼
  Publish SSE update       Audio playable on
  ("agentic_complete")     Dashboard & Notify page
        │
        ▼
  Dashboard shows enriched events (with audio player)
```

### Claude Prompt Design

The agentic pass sends a **single batch request** per feed (all events from one analysis), not per-event. This is cheaper and allows Claude to correlate across events.

**System prompt:**
```
You are a warehouse safety and operations analyst. You are given a list of
events detected by a computer vision system analyzing warehouse CCTV footage.

For each event, produce a structured analysis with:
1. root_cause: What likely caused this event (1-2 sentences)
2. recommended_actions: Array of specific actions to take (2-4 items)
3. urgency_reasoning: Why this severity level is appropriate, or suggest adjustment
4. suggested_personas: Which roles should be notified, with reasoning
5. risk_score: 1-10 integer (10 = immediate danger to life/property)
6. correlation_notes: Any connections to other events in this batch
7. voice_alert_script: A concise spoken alert (1-3 sentences) suitable for a
   warehouse PA system or earpiece. Use clear, direct language. Include the
   location/feed name, what happened, and what to do. Only generate this for
   events with risk_score >= 7.

Respond in JSON. Be specific to warehouse operations. Reference industry
standards (OSHA, NFPA) where applicable.
```

**User message includes:**
```json
{
  "feed_name": "Dock Cam 2",
  "analysis_mode": "standard",
  "events": [
    {
      "title": "Forklift operating in pedestrian zone",
      "description": "A forklift was observed...",
      "category": "Safety",
      "severity": "High",
      "confidence": 0.87,
      "video_time": "01:23-01:45"
    }
  ]
}
```

**Expected response:**
```json
{
  "enrichments": [
    {
      "event_index": 0,
      "root_cause": "Forklift operator likely took a shortcut through the pedestrian walkway, possibly due to a blocked primary route or time pressure during shift change.",
      "recommended_actions": [
        "Immediately restrict forklift access to the pedestrian zone — add temporary barriers",
        "Review and re-mark floor zones with high-visibility tape",
        "Conduct a brief safety stand-down with forklift operators on shift",
        "Check if the primary forklift route was obstructed"
      ],
      "urgency_reasoning": "High severity is appropriate — pedestrian-forklift interactions are the #1 cause of warehouse fatalities per OSHA. Upgrade to Critical if repeated within the same shift.",
      "suggested_personas": [
        { "role": "Safety Officer", "reason": "Primary — OSHA compliance and zone enforcement" },
        { "role": "Warehouse Manager", "reason": "Secondary — may need to adjust shift routing" }
      ],
      "risk_score": 8,
      "correlation_notes": "No correlated events in this batch. If pedestrian detection events appear in the same zone, escalate to Critical.",
      "voice_alert_script": "Attention Dock Cam 2 area. A forklift has been detected operating in the pedestrian walkway. All foot traffic, clear the zone immediately. Safety Officer, please respond to Dock 2 for zone enforcement."
    }
  ]
}
```

### Database Schema Changes

New table: `event_enrichments`

```sql
CREATE TABLE IF NOT EXISTS event_enrichments (
    id                  TEXT PRIMARY KEY,
    event_id            TEXT NOT NULL REFERENCES events(id),
    feed_id             TEXT NOT NULL REFERENCES feeds(id),
    root_cause          TEXT NOT NULL,
    recommended_actions TEXT NOT NULL,       -- JSON array
    urgency_reasoning   TEXT NOT NULL,
    suggested_personas  TEXT NOT NULL,       -- JSON array of {role, reason}
    risk_score          INTEGER NOT NULL,
    correlation_notes   TEXT,
    voice_alert_script  TEXT,               -- Claude-generated spoken alert text (risk_score >= 7)
    voice_alert_url     TEXT,               -- Path to ElevenLabs-generated MP3 file
    voice_alert_status  TEXT DEFAULT NULL,   -- NULL, 'generating', 'completed', 'error', 'skipped'
    model_used          TEXT NOT NULL DEFAULT 'claude-sonnet-4-20250514',
    created_at          TEXT NOT NULL,
    UNIQUE(event_id)    -- One enrichment per event
);
```

Add column to `feeds`:
```sql
ALTER TABLE feeds ADD COLUMN agentic_status TEXT DEFAULT NULL;
-- Values: NULL (not started), 'processing', 'completed', 'error', 'skipped'
```

### Backend Implementation

**New service:** `backend/services/agentic.py`

```python
def enrich_events(feed_id: str, feed_name: str, events: list[dict]):
    """
    Post-analysis Claude enrichment. Called after NomadicML events are stored.
    
    - Batches all events from a feed into a single Claude call
    - Parses structured JSON response
    - Stores enrichments in event_enrichments table
    - For events with voice_alert_script (risk_score >= 7), triggers ElevenLabs TTS
    - Publishes SSE event on completion
    """
```

**New service:** `backend/services/voice.py`

```python
def generate_voice_alert(enrichment_id: str, event_id: str, script: str) -> str:
    """
    Generate a voice alert MP3 using ElevenLabs TTS.
    
    - Uses a professional, authoritative voice suitable for PA announcements
    - Saves the MP3 to uploads/voice/{event_id}.mp3
    - Updates event_enrichments with voice_alert_url and status
    - Returns the URL path to the generated audio
    """
```

**Integration point:** At the end of `analyze_video()` in `analysis.py`, after events are stored:

```python
# Step 6: Agentic enrichment + voice alerts (non-blocking)
if events and os.environ.get("ANTHROPIC_API_KEY"):
    try:
        from services.agentic import enrich_events
        enrich_events(feed_id, feed_name, events)
        # Voice alerts are triggered inside enrich_events for risk_score >= 7
    except Exception as e:
        logger.warning(f"[Agentic] Enrichment failed (non-fatal): {e}")
        # Update agentic_status to 'error' but don't fail the feed
```

**New API endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/events/{id}/enrichment` | Get agentic enrichment for a specific event |
| `GET` | `/api/feeds/{id}/enrichments` | Get all enrichments for a feed |
| `POST` | `/api/feeds/{id}/enrich` | Manually trigger agentic enrichment for a feed |

### Frontend Changes

**Event detail expansion (Dashboard & Feed Detail page):**
- Existing event cards get an expandable "AI Analysis" section.
- Shows: root cause, recommended actions (as a checklist), risk score (visual gauge), suggested personas with reasoning.
- A subtle "AI" badge indicates the event has been enriched.

**Feed detail page:**
- New status indicator: "Analyzing → Enriching → Complete"
- If agentic enrichment is processing, show a secondary progress state.

**Quick-notify upgrade:**
- When sending a notification for an enriched event, pre-populate the message with the root cause and recommended actions.
- Pre-select suggested personas from the enrichment.

### SSE Events

```json
{
  "type": "feed_update",
  "feed_id": "abc-123",
  "status": "enriching",
  "feed_name": "Dock Cam 2"
}
```
```json
{
  "type": "agentic_complete",
  "feed_id": "abc-123",
  "enriched_count": 5,
  "avg_risk_score": 6.2,
  "feed_name": "Dock Cam 2"
}
```

### Error Handling

- If `ANTHROPIC_API_KEY` is not set, skip enrichment silently. Set `agentic_status = 'skipped'`.
- If Claude returns malformed JSON, retry once with a stricter prompt. On second failure, set `agentic_status = 'error'` and store error message.
- Enrichment failure **never** blocks the main analysis pipeline. The feed status remains `completed` regardless.
- Rate limit: Max 1 concurrent enrichment call per feed. Use a simple lock or queue.

### Cost Considerations

- Batch all events per feed into a single Claude call (not per-event).
- Use `claude-sonnet` (not opus) for cost efficiency.
- Estimated token usage: ~500 input + ~400 output per event (increased slightly for `voice_alert_script`) → ~$0.005/event.
- A typical 10-event feed costs ~$0.05 to enrich.

---

## Feature 2: Voice Alert Generation (ElevenLabs)

### Concept

When Claude's agentic enrichment identifies a high-risk event (risk_score ≥ 7), it generates a concise `voice_alert_script` — a PA-style spoken message. ColdBrew then sends this script to the **ElevenLabs Text-to-Speech API** to produce an MP3 audio file. The audio is stored on disk and playable directly from the dashboard, feed detail page, and notification flow.

This turns ColdBrew from a visual dashboard into a **multi-modal alerting system** — warehouse workers can hear alerts through PA speakers, headsets, or the web UI without stopping to read.

### Data Flow

```
Claude Enrichment Complete
        │
        ▼
  For each enrichment with voice_alert_script:
        │
        ▼
┌────────────────────────────┐
│  ElevenLabs TTS API        │
│                            │
│  Input:                    │
│  - voice_alert_script text │
│  - Voice ID (configurable) │
│  - Model: eleven_turbo_v2  │
│                            │
│  Output:                   │
│  - MP3 audio stream        │
│  - Saved to disk           │
│  - ~2-5 seconds of audio   │
└────────────────────────────┘
        │
        ▼
  Store MP3 at /uploads/voice/{event_id}.mp3
        │
        ▼
  Update event_enrichments:
    voice_alert_url = "/uploads/voice/{event_id}.mp3"
    voice_alert_status = "completed"
        │
        ▼
  Publish SSE: "voice_alert_ready"
```

### ElevenLabs Integration

**SDK:** `elevenlabs` Python package.

**Voice selection:**
- Use a professional, authoritative voice suitable for warehouse PA announcements.
- Recommended: `"Rachel"` (clear, professional female voice) or `"Adam"` (authoritative male voice).
- Configurable via `ELEVENLABS_VOICE_ID` env var with a sensible default.

**Implementation in `backend/services/voice.py`:**

```python
import os
from elevenlabs import ElevenLabs

def generate_voice_alert(enrichment_id: str, event_id: str, script: str) -> str:
    """Generate an MP3 voice alert from a text script using ElevenLabs."""
    
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY not set")
    
    client = ElevenLabs(api_key=api_key)
    
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "Rachel")
    
    # Generate speech
    audio_generator = client.text_to_speech.convert(
        text=script,
        voice_id=voice_id,
        model_id="eleven_turbo_v2_5",  # Low-latency model
        output_format="mp3_44100_128",
    )
    
    # Save to disk
    voice_dir = os.path.join(os.path.dirname(__file__), "..", "uploads", "voice")
    os.makedirs(voice_dir, exist_ok=True)
    file_path = os.path.join(voice_dir, f"{event_id}.mp3")
    
    with open(file_path, "wb") as f:
        for chunk in audio_generator:
            f.write(chunk)
    
    return f"/uploads/voice/{event_id}.mp3"
```

**Trigger logic (inside `enrich_events()` in `agentic.py`):**

```python
# After storing enrichments, generate voice alerts for high-risk events
if os.environ.get("ELEVENLABS_API_KEY"):
    for enrichment in enrichments:
        if enrichment.get("voice_alert_script") and enrichment["risk_score"] >= 7:
            try:
                from services.voice import generate_voice_alert
                url = generate_voice_alert(
                    enrichment["id"],
                    enrichment["event_id"],
                    enrichment["voice_alert_script"],
                )
                # Update DB with audio URL
                conn.execute(
                    "UPDATE event_enrichments SET voice_alert_url = ?, voice_alert_status = 'completed' WHERE id = ?",
                    (url, enrichment["id"]),
                )
                conn.commit()
            except Exception as e:
                logger.warning(f"[Voice] TTS failed for event {enrichment['event_id']}: {e}")
                conn.execute(
                    "UPDATE event_enrichments SET voice_alert_status = 'error' WHERE id = ?",
                    (enrichment["id"],),
                )
                conn.commit()
else:
    # Mark all as skipped
    for enrichment in enrichments:
        if enrichment.get("voice_alert_script"):
            conn.execute(
                "UPDATE event_enrichments SET voice_alert_status = 'skipped' WHERE id = ?",
                (enrichment["id"],),
            )
    conn.commit()
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/events/{id}/voice` | Get voice alert audio URL for an event |
| `POST` | `/api/events/{id}/voice/regenerate` | Regenerate voice alert for an event |

The `/uploads/voice/` directory is already served as static files via FastAPI's `StaticFiles` mount.

### Frontend Changes

**Audio player on event cards:**
- Events with a `voice_alert_url` show a small speaker icon / play button.
- Clicking it plays the MP3 inline using an HTML5 `<audio>` element.
- Visual indicator: pulsing speaker icon for Critical events, static icon for High.

**Dashboard:**
- A "🔊 Play Alert" button appears next to the "Quick Notify" button on high-risk events.
- Auto-play option (off by default): When a new voice alert arrives via SSE, play it automatically. Controlled by a toggle in the dashboard header.

**Feed detail page:**
- Voice alerts appear in the enrichment expansion panel alongside root cause and actions.
- Full audio player with waveform visualization (optional stretch goal).

**Notification flow:**
- When sending a notification for an event with a voice alert, include a link to the audio.
- Telegram notifications can include the MP3 as an audio file attachment.

### SSE Events

```json
{
  "type": "voice_alert_ready",
  "feed_id": "abc-123",
  "event_id": "evt-456",
  "voice_alert_url": "/uploads/voice/evt-456.mp3",
  "risk_score": 8,
  "feed_name": "Dock Cam 2"
}
```

### Error Handling

- If `ELEVENLABS_API_KEY` is not set, skip voice generation silently. Set `voice_alert_status = 'skipped'`. Voice alerts are a non-blocking enhancement.
- If ElevenLabs API fails (rate limit, network), set `voice_alert_status = 'error'` and allow manual retry via the regenerate endpoint.
- If Claude didn't generate a `voice_alert_script` (risk_score < 7), no voice generation is attempted.
- Voice generation failure **never** blocks enrichment or the main pipeline.

### Cost Considerations

- ElevenLabs pricing: ~$0.30 per 1,000 characters (Starter tier).
- Typical voice alert script: ~150-300 characters → ~$0.05-0.09 per alert.
- Only triggered for risk_score ≥ 7 events (Critical/High) — estimated 20-30% of all events.
- A typical 10-event feed with 3 high-risk events costs ~$0.15-0.27 for voice alerts.
- Use `eleven_turbo_v2_5` model for lowest latency (~500ms generation time).

---

## Feature 3: Daily Report Generation

### Concept

A user can generate a single-day operational report that summarizes all events, notifications sent, agentic insights, and provides high-level recommendations. The report is generated by Claude using all event data from the selected date. Optionally, the executive summary can be narrated as audio using ElevenLabs — useful for managers who want a quick audio debrief at shift handoff.

### User Flow

```
Dashboard or Reports Page
        │
        ▼
  Select date (defaults to today)
        │
        ▼
  Click "Generate Report"
  (optional: check "Include audio summary")
        │
        ▼
  Backend gathers all events for that date
        │
        ▼
  Claude generates structured report
        │
        ├────────────────────────────┐
        │                            ▼
        │               ┌──────────────────────┐
        │               │  ElevenLabs TTS       │
        │               │  (if audio requested) │
        │               │                       │
        │               │  Narrates executive   │
        │               │  summary section      │
        │               └──────────────────────┘
        │                            │
        ▼                            ▼
  Report displayed in-app    Audio player at top
  (and downloadable)         of report
```

### Report Structure

The generated report includes these sections:

1. **Executive Summary** — 2-3 sentence overview of the day.
2. **Key Metrics**
   - Total events detected
   - Breakdown by category (Safety: 5, Equipment: 3, ...)
   - Breakdown by severity (Critical: 1, High: 4, ...)
   - Average risk score (from agentic enrichments, if available)
   - Total notifications sent
   - Feeds analyzed
3. **Critical & High Severity Incidents** — Detailed write-up of each critical/high event with root cause and actions taken (from enrichments).
4. **Event Timeline** — Chronological list of all events with timestamps, categories, and one-line summaries.
5. **Notification Log** — Who was notified about what, and when.
6. **Operational Recommendations** — Claude's synthesis of patterns, repeated issues, and suggested process improvements.
7. **Unresolved Items** — Events still in `new` or `acknowledged` status that need attention.

### Claude Prompt Design

**System prompt:**
```
You are a warehouse operations analyst generating a daily shift report.
Write in a professional, concise style suitable for warehouse management.
Use specific numbers and reference specific events by title.
Structure the report using the provided section headers.
Flag any patterns that suggest systemic issues (e.g., repeated safety events
in the same zone, equipment failures on the same line).
```

**User message includes:**
```json
{
  "report_date": "2026-03-07",
  "feeds": [
    { "feed_name": "Dock Cam 2", "event_count": 4, "analysis_mode": "agent" }
  ],
  "events": [ ... all events for the date ... ],
  "enrichments": [ ... all enrichments for those events ... ],
  "notifications": [ ... all notifications sent that day ... ],
  "metrics": {
    "total_events": 12,
    "by_category": { "Safety": 5, "Equipment": 3, "Shipment": 2, "Operational": 2 },
    "by_severity": { "Critical": 1, "High": 4, "Medium": 5, "Low": 2 }
  }
}
```

### Database Schema

New table: `reports`

```sql
CREATE TABLE IF NOT EXISTS reports (
    id              TEXT PRIMARY KEY,
    report_date     TEXT NOT NULL,           -- YYYY-MM-DD
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,           -- Full markdown report
    metrics         TEXT NOT NULL,           -- JSON blob of key metrics
    audio_url       TEXT,                    -- ElevenLabs narration of executive summary
    audio_status    TEXT DEFAULT NULL,       -- NULL, 'generating', 'completed', 'error', 'skipped'
    model_used      TEXT NOT NULL DEFAULT 'claude-sonnet-4-20250514',
    status          TEXT NOT NULL DEFAULT 'generating',  -- generating, completed, error
    error_message   TEXT,
    created_at      TEXT NOT NULL,
    UNIQUE(report_date)                     -- One report per date
);
```

### Backend Implementation

**New service:** `backend/services/reports.py`

```python
def generate_daily_report(report_date: str) -> str:
    """
    Gather all events, enrichments, and notifications for the given date.
    Send to Claude for report generation.
    Store the result in the reports table.
    Returns the report_id.
    """
```

**New API endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/reports` | List all generated reports |
| `GET` | `/api/reports/{id}` | Get a specific report |
| `POST` | `/api/reports/generate` | Generate a report for a given date |
| `DELETE` | `/api/reports/{id}` | Delete a report |

**`POST /api/reports/generate` request body:**
```json
{
  "report_date": "2026-03-07",
  "include_audio": true
}
```

**`GET /api/reports/{id}` response:**
```json
{
  "id": "rpt-abc123",
  "report_date": "2026-03-07",
  "title": "Daily Operations Report — March 7, 2026",
  "content": "## Executive Summary\n\nA total of 12 events were detected across 3 feeds...",
  "metrics": {
    "total_events": 12,
    "by_category": { "Safety": 5, "Equipment": 3, "Shipment": 2, "Operational": 2 },
    "by_severity": { "Critical": 1, "High": 4, "Medium": 5, "Low": 2 },
    "notifications_sent": 6,
    "feeds_analyzed": 3,
    "avg_risk_score": 5.8
  },
  "audio_url": "/uploads/reports/rpt-abc123.mp3",
  "audio_status": "completed",
  "status": "completed",
  "created_at": "2026-03-07T23:45:00Z"
}
```

### Frontend Implementation

**New page:** `/reports`

- **Date picker** — Calendar input defaulting to today.
- **Generate button** — Triggers report generation. Shows loading state while Claude processes.
- **"Include audio summary" checkbox** — Opt-in to ElevenLabs narration of the executive summary.
- **Report list** — Cards showing previous reports with date, event count, status, and a 🔊 icon if audio is available.
- **Report view** — Full rendered markdown report with:
  - Audio player at the top if `audio_url` is present — plays the narrated executive summary.
  - Sticky metrics bar (event count, severity breakdown as colored pills).
  - Sections rendered as collapsible cards.
  - "Download as PDF" button (using browser print or a lightweight library).
  - "Share" button (copies a link or the raw text).

**Sidebar update:**
- Add "Reports" link between "Notifications" and "Status" in the sidebar navigation.

**Dashboard integration:**
- Add a "Generate Report" button in the dashboard header when viewing a specific day's events.

### Error Handling

- If no events exist for the selected date, return a lightweight "No events" report with zero metrics.
- If `ANTHROPIC_API_KEY` is not set, return an error: "Claude API key not configured. Set ANTHROPIC_API_KEY in backend/.env."
- If report generation fails, store the error and allow retry.
- Duplicate date: If a report for that date already exists, prompt the user to regenerate (replaces the old one).

### Cost Considerations

- One Claude call per report, regardless of event count.
- Estimated: ~2,000 input tokens + ~1,500 output tokens → ~$0.015/report.
- Reports are cached in the database — regeneration is explicit, not automatic.

---

## Shared Technical Details

### Environment Variables

| Variable | Required By | Purpose |
|----------|-------------|---------|
| `NOMADIC_SDK_API_KEY` | Feature 1 | Video analysis (existing) |
| `ANTHROPIC_API_KEY` | Feature 1 & 3 | Claude agentic enrichment and report generation |
| `CLAUDE_MODEL` | Optional | Override default model (default: `claude-sonnet-4-20250514`) |
| `ELEVENLABS_API_KEY` | Feature 2 & 3 | ElevenLabs TTS for voice alerts and report narration |
| `ELEVENLABS_VOICE_ID` | Optional | Override default voice (default: `Rachel`) |

### Dependencies

Already installed:
- `anthropic` — Claude SDK (used by Telegram bot)

New package required:
- `elevenlabs` — ElevenLabs Python SDK for text-to-speech

Add to `backend/requirements.txt`:
```
elevenlabs
```

### Status Page Integration

The existing `/status` page already checks Claude and Telegram connectivity. Add an **ElevenLabs** health check:

```python
def _check_elevenlabs() -> dict:
    """Check ElevenLabs API key and connectivity."""
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key:
        return {
            "name": "ElevenLabs",
            "status": "disabled",
            "message": "ELEVENLABS_API_KEY not set. Voice alerts disabled.",
            "latency_ms": None,
        }
    try:
        start = time.time()
        from elevenlabs import ElevenLabs
        client = ElevenLabs(api_key=api_key)
        voices = client.voices.get_all()
        latency = round((time.time() - start) * 1000)
        return {
            "name": "ElevenLabs",
            "status": "connected",
            "message": f"Authenticated. {len(voices.voices)} voices available.",
            "latency_ms": latency,
        }
    except Exception as e:
        latency = round((time.time() - start) * 1000)
        return {
            "name": "ElevenLabs",
            "status": "error",
            "message": str(e)[:200],
            "latency_ms": latency,
        }
```

All features (agentic enrichment, voice alerts, report generation) should gracefully degrade when their respective API keys are missing — the core NomadicML analysis pipeline always works independently.

---

## Build Order

### Phase 1: Agentic Enrichment (Backend)
1. Add `event_enrichments` table and `agentic_status` column to `feeds`.
2. Create `backend/services/agentic.py` with the enrichment logic (including `voice_alert_script` in Claude prompt).
3. Wire into `analyze_video()` as a post-processing step.
4. Add API endpoints for retrieving enrichments.
5. Add SSE events for enrichment status.

### Phase 2: Voice Alerts (Backend)
6. Install `elevenlabs` package.
7. Create `backend/services/voice.py` with TTS generation.
8. Wire voice generation into `enrich_events()` for events with risk_score ≥ 7.
9. Add ElevenLabs health check to `/api/status`.
10. Serve `/uploads/voice/` as static files.

### Phase 3: Agentic Enrichment + Voice (Frontend)
11. Update event cards with expandable "AI Analysis" section.
12. Add inline audio player for events with `voice_alert_url`.
13. Update feed detail page with enrichment status indicator.
14. Pre-populate notification form with enrichment data.
15. Add auto-play toggle for voice alerts on dashboard.

### Phase 4: Daily Reports (Backend)
16. Add `reports` table (with `audio_url` and `audio_status` columns).
17. Create `backend/services/reports.py` with report generation logic.
18. Add optional ElevenLabs narration of executive summary.
19. Add report API endpoints.

### Phase 5: Daily Reports (Frontend)
20. Create `/reports` page with date picker, audio checkbox, and report viewer.
21. Add audio player at top of report view.
22. Add "Reports" to sidebar.
23. Add markdown renderer for report content.

### Phase 6: Polish
24. Test full pipeline end-to-end: Upload → NomadicML → Claude → ElevenLabs → Dashboard.
25. Verify graceful degradation when Claude or ElevenLabs is unavailable.
26. Validate SSE updates flow correctly for the multi-step pipeline.
27. Load-test voice generation with concurrent enrichments.

---

## Success Criteria

### Agentic Enrichment
- [ ] After a NomadicML analysis completes, Claude enrichment runs automatically within 10 seconds.
- [ ] Each enriched event shows root cause, recommended actions, risk score, and suggested personas.
- [ ] Enrichment failure does not break the main analysis pipeline.
- [ ] Total added latency for agentic enrichment: < 15 seconds for a typical 10-event feed.

### Voice Alerts (ElevenLabs)
- [ ] Events with risk_score ≥ 7 automatically get a generated voice alert MP3.
- [ ] Voice alerts are playable inline on the dashboard and feed detail pages.
- [ ] Voice generation completes within 3 seconds per alert.
- [ ] Voice alerts degrade gracefully when `ELEVENLABS_API_KEY` is not set (marked as "skipped").
- [ ] ElevenLabs appears on the `/status` page with correct connectivity state.

### Daily Reports
- [ ] User can generate a daily report for any date with events.
- [ ] Report includes all 7 sections with accurate metrics.
- [ ] Reports are cached — viewing a previously generated report is instant.
- [ ] Optional audio narration of the executive summary is playable at the top of the report.

### Shared
- [ ] All three features degrade gracefully when their respective API keys are missing.
- [ ] No single dependency failure blocks the core NomadicML → Dashboard pipeline.
- [ ] `/status` page shows health of all 4 dependencies: NomadicML, Claude, Telegram, ElevenLabs.

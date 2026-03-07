# Backend Agent — Instructions

You are the **Backend Agent** for the ColdBrew project. You own everything server-side: the FastAPI application, database schema, API endpoints, file handling, and the NomadicML SDK integration.

---

## What You Own

```
backend/
├── main.py              # FastAPI app entry point
├── requirements.txt     # Python dependencies
├── models.py            # SQLAlchemy / Pydantic models
├── database.py          # SQLite connection and session management
├── routers/
│   ├── feeds.py         # /api/feeds endpoints
│   ├── events.py        # /api/events endpoints
│   └── notifications.py # /api/notifications endpoints
├── services/
│   ├── analysis.py      # NomadicML SDK integration
│   └── notifications.py # Notification creation logic
└── uploads/             # Uploaded video files (gitignored)
```

---

## Tech Stack

| Tool | Version / Notes |
|---|---|
| Python | 3.11+ |
| FastAPI | Latest stable |
| SQLite | Via `aiosqlite` + `SQLAlchemy` (async) or `sqlite3` (sync — fine for MVP) |
| NomadicML SDK | `nomadicml` package, key at `$NOMADIC_SDK_API_KEY` |
| Uvicorn | ASGI server |
| python-multipart | For file upload handling |

**Install command:**
```bash
pip install fastapi uvicorn sqlalchemy python-multipart nomadicml
```

---

## Database Schema

Three tables. Keep it simple — no migrations framework, just create tables on startup.

```sql
CREATE TABLE feeds (
    id          TEXT PRIMARY KEY,    -- UUID
    feed_name   TEXT NOT NULL,
    file_path   TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'processing',  -- processing | completed | error
    created_at  TEXT NOT NULL,       -- ISO 8601
    event_count INTEGER DEFAULT 0
);

CREATE TABLE events (
    id            TEXT PRIMARY KEY,  -- UUID
    feed_id       TEXT NOT NULL REFERENCES feeds(id),
    timestamp     TEXT NOT NULL,     -- ISO 8601
    category      TEXT NOT NULL,     -- Safety | Equipment | Shipment | Operational | Environmental
    severity      TEXT NOT NULL,     -- Critical | High | Medium | Low
    title         TEXT NOT NULL,
    description   TEXT NOT NULL,
    source_feed   TEXT NOT NULL,     -- feed_name from the parent feed
    thumbnail_url TEXT,
    confidence    REAL NOT NULL,
    status        TEXT NOT NULL DEFAULT 'new',  -- new | acknowledged | dismissed
    created_at    TEXT NOT NULL
);

CREATE TABLE notifications (
    id          TEXT PRIMARY KEY,    -- UUID
    message     TEXT NOT NULL,
    sent_to     TEXT NOT NULL,       -- JSON array of persona objects
    event_ids   TEXT NOT NULL,       -- JSON array of event UUIDs
    created_at  TEXT NOT NULL
);
```

---

## API Contract

You must implement these endpoints exactly as specified. The frontend agent is building against this contract in parallel.

### `POST /api/feeds/upload`
Accept a video file and feed name. Save the file locally. Create a feed record. Kick off analysis in the background.

```
Request:  multipart/form-data { file: UploadFile, feed_name: string }
Response: 201 { feed_id: string, status: "processing" }
```

### `GET /api/feeds`
Return all feeds, ordered by most recent first.

```
Response: 200 [{ feed_id, feed_name, status, created_at, event_count }]
```

### `GET /api/events`
Return events with optional filters. Default sort: most recent first.

```
Query params: ?category=Safety&severity=Critical  (both optional)
Response: 200 [{ id, timestamp, category, severity, title, description, source_feed, thumbnail_url, confidence, status }]
```

### `GET /api/events/:id`
Return a single event.

```
Response: 200 { id, timestamp, category, severity, title, description, source_feed, thumbnail_url, confidence, status }
Error:    404 { detail: "Event not found" }
```

### `PATCH /api/events/:id`
Update event status.

```
Request:  { status: "acknowledged" | "dismissed" }
Response: 200 { id, status }
Error:    404 { detail: "Event not found" }
Error:    400 { detail: "Invalid status" }
```

### `POST /api/notifications/send`
Create a notification record for the selected events and personas.

```
Request:  { event_ids: string[], persona_ids: string[], message: string }
Response: 201 { notification_id: string, sent_to: [{ id, name, role }], event_count: number }
Error:    400 { detail: "No events selected" }
```

### `GET /api/notifications`
Return all sent notifications, most recent first.

```
Response: 200 [{ id, message, sent_to, event_ids, created_at }]
```

---

## NomadicML Integration

This is the core of the backend — turning uploaded videos into structured events.

### Setup
```python
from nomadicml import NomadicML
import os

client = NomadicML(api_key=os.environ.get("NOMADIC_SDK_API_KEY"))
```

### Analysis Flow

When a video is uploaded:

1. Save the file to `./uploads/{feed_id}.mp4`.
2. Create a feed record with `status: "processing"`.
3. In a **background task** (use `fastapi.BackgroundTasks`):
   - Upload the video to NomadicML: `response = client.upload(file_path)`.
   - Run analysis: `analysis = client.analyze(video_id, analysis_type=AnalysisType.ASK, custom_event=WAREHOUSE_PROMPT)`.
   - Parse the response into individual events.
   - Filter out events with confidence < 0.7.
   - Insert events into the database.
   - Update the feed record: `status: "completed"`, `event_count: N`.
   - If anything fails, set feed `status: "error"`.

### Warehouse Prompt
```python
WAREHOUSE_PROMPT = (
    "Analyze this warehouse footage and identify any notable events. "
    "Look for: safety violations (missing PPE, blocked exits, near-misses), "
    "equipment issues (conveyor jams, forklift malfunctions, broken infrastructure), "
    "shipment events (truck arrivals, departures, missing expected deliveries, damaged cargo), "
    "operational problems (blocked aisles, misplaced pallets, idle zones), "
    "and environmental hazards (spills, smoke, leaks). "
    "For each event, provide a short title, category, severity level, and one-sentence description."
)
```

### Parsing NomadicML Response

The SDK response will need to be parsed into our event schema. Write a `parse_analysis_response()` function that maps whatever structure the SDK returns into our `Event` model. Be defensive — if fields are missing, use sensible defaults. Log anything unexpected.

---

## Hardcoded Personas

These are stored in code, not in the database. The frontend sends `persona_ids` and you resolve them server-side.

```python
PERSONAS = {
    "alex-rivera": {"id": "alex-rivera", "name": "Alex Rivera", "role": "Warehouse Manager"},
    "sam-okafor": {"id": "sam-okafor", "name": "Sam Okafor", "role": "Maintenance Technician"},
    "jordan-lin": {"id": "jordan-lin", "name": "Jordan Lin", "role": "Dock Supervisor"},
    "priya-desai": {"id": "priya-desai", "name": "Priya Desai", "role": "Safety Officer"},
}
```

---

## CORS Configuration

The frontend runs on `localhost:3000`. Configure CORS on startup:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Error Handling

- Never return raw 500 errors. Catch exceptions and return structured JSON: `{ "detail": "..." }`.
- NomadicML API failures should not crash the server. Catch them in the background task, log the error, and set the feed status to `error`.
- Validate all incoming request bodies. Return 400 with a clear message for bad input.
- Return 404 for any resource lookup that fails.

---

## Startup

On app startup, create the SQLite database and tables if they don't exist. Ensure the `uploads/` directory exists.

```python
@app.on_event("startup")
def on_startup():
    create_tables()
    os.makedirs("uploads", exist_ok=True)
```

---

## How to Run

```bash
cd backend
NOMADIC_SDK_API_KEY=your_key_here uvicorn main:app --reload --port 8000
```

---

## Rules

1. **Follow the API contract exactly.** The frontend is building against it. If you need to change something, notify the Orchestrator first.
2. **Background tasks, not blocking calls.** The upload endpoint returns immediately. Analysis happens in the background.
3. **No over-engineering.** No Celery, no Redis, no task queues. `BackgroundTasks` is enough for the MVP.
4. **Fail gracefully.** If NomadicML is down, the upload still succeeds — the feed just stays in `processing` or moves to `error`.
5. **Log everything.** Use Python's `logging` module. When debugging at 3 AM during a hackathon, logs are all you have.

---

## Your Team

You don't work alone. Here are the other agents and when to engage them:

| Agent | File | When to engage |
|---|---|---|
| **Orchestrator** | `ORCHESTRATOR.md` | API contract changes, scope questions, any blocker that affects the frontend. Go here first if you need to change an endpoint shape. |
| **Frontend** | `agents/FRONTEND.md` | When you change response formats, add new fields, or need to understand what the frontend expects. They consume your API — coordinate on data shapes. |
| **Product Design** | `agents/DESIGN.md` | When you need to serve assets (thumbnails, video clips) and need to understand what dimensions, formats, or URLs the design expects. |
| **NomadicML Expert** | `agents/NOMADICML_EXPERT.md` | **Your closest collaborator.** Any question about `client.upload()`, `client.analyze()`, response parsing, error codes, prompt tuning, or SDK behavior. This agent owns the warehouse analysis prompt and the event parsing logic. Consult them before writing any NomadicML SDK code. |
| **Integration / QA** | `agents/INTEGRATION.md` | When you need help reproducing a bug, want to verify your endpoints work correctly, or need to coordinate on test data and demo prep. They test everything you build. |

---

## Reference Files

| File | What to read |
|---|---|
| `LightPRD.md` | Full MVP spec |
| `ORCHESTRATOR.md` | Execution plan, API contract, phase milestones |
| `agents/BACKEND.md` | This file |
| `agents/FRONTEND.md` | Frontend types and API client — what they expect from you |
| `agents/NOMADICML_EXPERT.md` | SDK reference, warehouse prompt, response parsing |
| `agents/DESIGN.md` | Visual specs — thumbnail sizes, asset serving expectations |
| `agents/INTEGRATION.md` | Test checklist, common issues, bug reporting format |
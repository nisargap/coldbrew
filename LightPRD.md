# ColdBrew MVP — Light PRD

**Track:** Robotics · **Event:** NomadicML 12-Hour Hackathon

---

## What We're Building

A web app where a user uploads a warehouse video, the system analyzes it for notable events using a vision model, and surfaces those events on a dashboard with the ability to send notifications to the right people.

That's it. No live streams, no routing engine, no report PDFs. Upload → Analyze → See Events → Notify.

---

## User Flow

```
Upload video → System chunks & analyzes → Events appear on dashboard
                                                  │
                                          User reviews events
                                                  │
                                    Select events → Send notification
```

---

## Features

### 1. Video Upload
- Single page with a drop zone to upload an MP4/MOV file.
- User tags the upload with a feed name (e.g., "Dock Cam 2", "Aisle 5").
- Upload gets queued for processing; progress indicator shown.

### 2. Video Analysis (NomadicML SDK)
- Backend uploads the video to NomadicML via their SDK (`client.upload()`).
- Runs analysis using `client.analyze()` with a custom event prompt targeting warehouse incidents:
  - Safety violations, equipment failures, shipment anomalies, operational issues, environmental hazards.
- The SDK handles all frame extraction, chunking, and vision model inference — we don't need to manage that ourselves.
- For each detected event, we extract: title, category (Safety / Equipment / Shipment / Operational / Environmental), severity (Critical / High / Medium / Low), description.
- Events with confidence ≥ 0.7 are saved to the database.

**SDK usage:**
```python
from nomadicml import NomadicML
import os

client = NomadicML(api_key=os.environ.get("NOMADIC_SDK_API_KEY"))

# Upload
response = client.upload("path/to/video.mp4")
video_id = response["video_id"]

# Analyze
analysis = client.analyze(
    video_id,
    analysis_type=AnalysisType.ASK,
    custom_event="Find safety incidents, equipment failures, shipment anomalies, operational issues, and environmental hazards in this warehouse footage",
)
```

### 3. Event Dashboard
- Reverse-chronological list of all detected events.
- Each event card shows:
  - Thumbnail (extracted frame)
  - Title and description
  - Severity badge (color-coded: red / orange / yellow / blue)
  - Category tag
  - Timestamp
  - Source feed name
- Filter by: category, severity.
- Click an event to see the full description and a larger thumbnail.

### 4. Notifications
- Checkbox selection on event cards.
- "Notify" button opens a simple form:
  - **To:** pick from a predefined persona list (Warehouse Manager, Maintenance Tech, Dock Supervisor, Safety Officer).
  - **Message:** auto-generated summary of selected events, editable by the user.
  - **Send** — for MVP this logs the notification and shows a success toast. Email integration is a stretch goal.
- Notification history visible in a sidebar or tab.

---

## Personas (Hardcoded for MVP)

| Name | Role |
|---|---|
| Alex Rivera | Warehouse Manager |
| Sam Okafor | Maintenance Technician |
| Jordan Lin | Dock Supervisor |
| Priya Desai | Safety Officer |

No auth, no user accounts. These are just names in a dropdown.

---

## Event Schema

```
Event {
  id            string
  timestamp     datetime
  category      string      // Safety | Equipment | Shipment | Operational | Environmental
  severity      string      // Critical | High | Medium | Low
  title         string
  description   string
  source_feed   string
  thumbnail_url string
  confidence    float
  status        string      // New | Acknowledged | Dismissed
}
```

---

## API Endpoints

| Method | Endpoint | What it does |
|---|---|---|
| `POST` | `/api/feeds/upload` | Upload a video file with a feed name |
| `GET` | `/api/feeds` | List uploaded feeds and their processing status |
| `GET` | `/api/events` | List events (filterable by category, severity) |
| `GET` | `/api/events/:id` | Single event detail |
| `PATCH` | `/api/events/:id` | Update status (acknowledge / dismiss) |
| `POST` | `/api/notifications/send` | Send notification for selected events to chosen persona(s) |
| `GET` | `/api/notifications` | List sent notifications |

---

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js + Tailwind + shadcn/ui |
| Backend | Python + FastAPI |
| Database | SQLite |
| Video Processing | Handled by NomadicML SDK (ffmpeg for local thumbnail extraction if needed) |
| Vision AI | NomadicML SDK (`$NOMADIC_SDK_API_KEY`) |
| File Storage | Local filesystem (./uploads) |

---

## Pages

1. **Upload** — drag-and-drop video upload with feed name input.
2. **Dashboard** — event list with filters and bulk-select notifications.
3. **Notification History** — log of sent notifications.

Three pages. No settings, no config, no admin panel.

---

## What's Explicitly Out of Scope

- Live / RTSP camera streams
- Configurable routing rules
- Email / SMS delivery (notifications are in-app only)
- Report generation / PDF export
- Escalation logic
- User auth / roles
- Multi-warehouse / tenancy
- Mobile layout

---

## Build Order

1. **Backend skeleton** — FastAPI app, SQLite models, file upload endpoint.
2. **NomadicML integration** — Wire up SDK client, upload video, run analysis, parse events into DB.
3. **Frontend shell** — Next.js app with three pages, basic layout.
4. **Event dashboard** — Fetch and display events, filters, severity badges.
5. **Upload page** — Drop zone, progress bar, feed name input.
6. **Notification flow** — Select events, pick persona, send, show toast.
7. **Polish** — Dark theme, visual cleanup, loading states.

---

*This is the hackathon MVP. Everything else lives in the full PRD.md.*

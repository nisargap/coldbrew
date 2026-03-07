# ColdBrew — Warehouse Intelligence Platform

### Product Requirements Document

**Team:** ColdBrew · **Track:** Robotics · **Event:** NomadicML 12-Hour Hackathon

---

## 1 · Problem Statement

Modern warehouses generate thousands of hours of CCTV footage daily, yet almost none of it is watched in real time. Incidents — spills, equipment malfunctions, missed shipments, safety violations — go unnoticed until a human stumbles upon them or damage has already been done. The gap between *something happening* and *the right person knowing about it* is where losses pile up.

ColdBrew closes that gap. It watches every feed, detects meaningful events, and routes alerts to the exact person who can act on them — automatically, in seconds.

---

## 2 · Product Overview

ColdBrew is a real-time warehouse video intelligence platform that:

1. **Ingests** live and recorded video feeds (CCTV, dock cameras, facility sensors).
2. **Analyzes** each frame/clip using vision models to detect predefined event categories.
3. **Routes** detected events to the correct persona via configurable notification channels.
4. **Displays** everything on a clean, operator-grade dashboard with manual override controls and reporting.

---

## 3 · Target Users & Personas

| Persona | Role | What They Care About |
|---|---|---|
| **Warehouse Manager** | Oversees daily operations | Throughput, staffing issues, overall incident counts, shift reports |
| **Maintenance Technician** | Repairs equipment & infrastructure | Equipment faults, spills, blocked aisles, temperature anomalies |
| **Dock Supervisor** | Manages inbound/outbound shipments | Shipment arrivals, missed deliveries, trailer door status, loading delays |
| **Safety Officer** | Enforces compliance & safety protocols | PPE violations, forklift near-misses, fire hazards, blocked exits |
| **Floor Worker** (notification recipient) | Executes tasks on the floor | Direct task alerts ("clean spill in Aisle 7") |

---

## 4 · Event Taxonomy

Events are the core data primitive. Every detected occurrence produces an **Event** record.

### 4.1 Event Categories

| Category | Example Events | Default Routing |
|---|---|---|
| **Safety** | PPE violation, blocked emergency exit, forklift near-miss, person in restricted zone | Safety Officer, Warehouse Manager |
| **Equipment** | Conveyor belt jam, forklift malfunction, dock door stuck, lighting failure | Maintenance Technician |
| **Shipment** | Truck arrival, truck departure, no-show shipment (expected but not arrived), damaged cargo visible | Dock Supervisor |
| **Operational** | Aisle blocked by misplaced pallets, unusual crowd density, idle zone (no movement for extended period) | Warehouse Manager |
| **Environmental** | Spill detected, smoke/haze, water leak, unusual temperature reading (if thermal cam) | Maintenance Technician, Safety Officer |

### 4.2 Event Schema

```
Event {
  id              string       // UUID
  timestamp       datetime     // When the event was detected
  category        enum         // Safety | Equipment | Shipment | Operational | Environmental
  severity        enum         // Critical | High | Medium | Low
  title           string       // Short human-readable label, e.g. "Forklift near-miss in Zone B"
  description     string       // LLM-generated summary of what happened
  source_feed     string       // Camera/feed identifier
  thumbnail_url   string       // Snapshot frame from the moment of detection
  clip_url        string       // Short video clip surrounding the event
  status          enum         // New | Acknowledged | In Progress | Resolved | Dismissed
  assigned_to     string[]     // Persona(s) notified
  confidence      float        // Model confidence score (0–1)
  metadata        json         // Flexible bag for extra attributes
}
```

---

## 5 · Core Features

### 5.1 Video Feed Ingestion

- Accept video input via file upload (MP4, AVI, MOV) for the hackathon demo.
- Support simulated "live" playback of uploaded warehouse footage to mimic real-time CCTV.
- Each feed is tagged with a **location label** (e.g., "Dock Camera 3", "Aisle 12 North").
- Future: RTSP stream support for real camera integration.

### 5.2 AI Video Analysis Pipeline (NomadicML SDK)

- Upload video to NomadicML via `client.upload()`.
- Run analysis using `client.analyze()` with custom event prompts tailored to each event category (safety, equipment, shipment, operational, environmental).
- NomadicML handles all video segmentation, frame extraction, and vision model inference internally — we consume structured results.
- For each detected event, the SDK returns classification, severity, and a natural-language description.
- Confidence threshold filtering: only surface events above a configurable threshold (default ≥ 0.7).
- Deduplication: suppress repeated alerts for the same ongoing event within a cooldown window.

**SDK initialization:**
```python
from nomadicml import NomadicML
import os

client = NomadicML(api_key=os.environ.get("NOMADIC_SDK_API_KEY"))
```

**Analysis flow:**
```python
# Upload video
response = client.upload("path/to/video.mp4")
video_id = response["video_id"]

# Analyze for warehouse events
analysis = client.analyze(
    video_id,
    analysis_type=AnalysisType.ASK,
    custom_event="Detect safety violations, equipment failures, shipment anomalies, operational issues, and environmental hazards",
)

# Batch analysis for multiple feeds
video_ids = [v["video_id"] for v in uploads]
batch = client.analyze(video_ids, analysis_type=AnalysisType.ASK, ...)
```

### 5.3 Event Routing Engine

- Rule-based routing: map `(category, severity)` → persona(s).
- Configurable routing rules via the dashboard (stretch goal).
- Notification channels:
  - **In-app** — real-time event cards on the dashboard (primary for demo).
  - **Email** — summary digests or critical-only instant alerts.
  - **SMS / Push** — critical events only (stretch goal).
- Escalation logic: if an event is not acknowledged within N minutes, escalate to the next persona up the chain.

### 5.4 Dashboard

The dashboard is the primary interface. It must feel like a purpose-built operations tool — not a generic admin panel.

#### 5.4.1 Live Feed View
- Grid of active camera feeds with overlaid event badges.
- Click any feed to expand to full view with timeline scrubber.

#### 5.4.2 Event Stream
- Reverse-chronological feed of detected events.
- Filterable by: category, severity, status, camera source, time range.
- Each event card shows: thumbnail, title, severity badge, timestamp, assigned persona, status.
- Click to expand: full description, video clip playback, action buttons (Acknowledge / Assign / Resolve / Dismiss).

#### 5.4.3 Mass Notification Panel
- Select multiple events (checkbox or lasso select).
- "Notify" action opens a compose pane:
  - Pre-populated recipient list based on event routing rules.
  - Editable message body (auto-generated summary of selected events).
  - Channel selection (in-app, email).
  - Send immediately or schedule.

#### 5.4.4 Analytics & Reports
- **Summary cards**: total events today, breakdown by category, avg. response time, unresolved count.
- **Trend chart**: events over time (hourly/daily) with category breakdown.
- **Report generator**:
  - Select date range + filters.
  - Generate a downloadable PDF/CSV report.
  - Report includes: event log, response times, top recurring event types, severity distribution.
- **Shift report**: one-click summary of all events during the current/previous shift.

#### 5.4.5 Design Principles
- Dark mode by default (operators work in dim environments).
- High information density without clutter — inspired by Bloomberg Terminal and Figma's density.
- Status colors: red (critical), orange (high), yellow (medium), blue (low), green (resolved).
- No unnecessary animations. Transitions should be fast and functional.
- Typography: monospaced for data, sans-serif for labels. Clear hierarchy.
- No gradients, no drop shadows, no rounded-everything. Flat, precise, industrial.

---

## 6 · Technical Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Frontend (Next.js)                 │
│  Dashboard · Event Stream · Notifications · Reports     │
└────────────────────────┬────────────────────────────────┘
                         │  REST + WebSocket
┌────────────────────────┴────────────────────────────────┐
│                    Backend (FastAPI)                     │
│                                                         │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Video    │  │ Analysis     │  │ Routing &        │  │
│  │ Ingestion│──│ Pipeline     │──│ Notification     │  │
│  │ Service  │  │ (NomadicML)  │  │ Engine           │  │
│  └──────────┘  └──────────────┘  └──────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │              Data Layer (SQLite/PostgreSQL)       │   │
│  │  Events · Feeds · Routing Rules · Notifications  │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Stack

| Layer | Technology | Rationale |
|---|---|---|
| Frontend | Next.js 14 + Tailwind CSS + shadcn/ui | Fast to build, great component library, SSR for initial load |
| Backend | Python + FastAPI | Best ecosystem for video processing and ML model calls |
| Database | SQLite (dev) / PostgreSQL (prod) | Simple for hackathon, scales later |
| Video Processing | Handled by NomadicML SDK (ffmpeg for local thumbnails) | SDK manages segmentation and frame extraction |
| AI / Vision | NomadicML SDK (`$NOMADIC_SDK_API_KEY`) | Purpose-built video understanding API for physical-world analysis |
| Real-time | WebSockets (FastAPI → Next.js) | Push events to dashboard instantly |
| Notifications | In-app + Email (Resend or SMTP) | Lightweight, reliable |

---

## 7 · Data Flow

```
1. Video uploaded or streamed
        │
2. Video uploaded to NomadicML via client.upload()
        │
3. Analysis triggered via client.analyze() with custom event prompts
        │
4. NomadicML processes video (segmentation, frame extraction, vision model)
        │
5. SDK returns: { event_detected, category, severity, description }
        │
6. If event_detected and confidence ≥ threshold:
   ├── Create Event record in DB
   ├── Push to dashboard via WebSocket
   └── Trigger routing engine
              │
7. Routing engine resolves personas from (category, severity) rules
              │
8. Notifications dispatched to matched personas
              │
9. Persona acknowledges / resolves via dashboard
```

---

## 8 · API Surface (Key Endpoints)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/feeds` | Register a new video feed (upload or URL) |
| `GET` | `/api/feeds` | List all registered feeds |
| `GET` | `/api/events` | List events (with filters: category, severity, status, time range) |
| `GET` | `/api/events/:id` | Get single event detail |
| `PATCH` | `/api/events/:id` | Update event status (acknowledge, resolve, dismiss) |
| `POST` | `/api/events/:id/assign` | Assign event to a persona |
| `POST` | `/api/notifications/send` | Mass notify — send alerts for selected events |
| `GET` | `/api/reports/generate` | Generate report (params: date range, filters, format) |
| `GET` | `/api/analytics/summary` | Dashboard summary stats |
| `WS` | `/ws/events` | Real-time event stream |

---

## 9 · Scope & Prioritization

### Must Have (Hackathon Demo)
- [ ] Video upload and processing pipeline
- [ ] Vision LLM integration for event detection
- [ ] Event storage and retrieval API
- [ ] Dashboard with live event stream
- [ ] Event detail view with thumbnail and description
- [ ] Severity-based color coding and filtering
- [ ] Mass notification UI (in-app)
- [ ] Basic analytics summary cards
- [ ] Report generation (CSV export)

### Should Have (If Time Permits)
- [ ] Simulated live feed playback with real-time event popping
- [ ] Routing rules configuration UI
- [ ] Email notifications via Resend
- [ ] Trend charts (events over time)
- [ ] Escalation logic for unacknowledged events

### Nice to Have (Post-Hackathon)
- [ ] RTSP live camera stream support
- [ ] SMS / push notifications
- [ ] Custom event category definitions
- [ ] Multi-warehouse support
- [ ] Role-based access control
- [ ] Mobile-responsive layout
- [ ] Audit trail for all actions

---

## 10 · Demo Scenario

For the hackathon presentation, the following scripted walkthrough:

1. **Upload** two warehouse videos: one general floor feed, one dock camera.
2. System processes videos → **events appear** on the dashboard in real time.
3. Show a **safety event** (e.g., person without hard hat) → routed to Safety Officer.
4. Show a **shipment event** (e.g., expected truck never arrived) → routed to Dock Supervisor.
5. Show an **equipment event** (e.g., conveyor jam) → routed to Maintenance.
6. **Acknowledge** one event, **dismiss** another, **resolve** a third — demonstrating the lifecycle.
7. Select 3 events → **mass notify** the Warehouse Manager with a combined summary.
8. Open **Reports** → generate a shift report covering all detected events.

---

## 11 · Success Metrics (Post-Hackathon Vision)

| Metric | Target |
|---|---|
| Mean time from event occurrence to alert | < 30 seconds |
| Event detection accuracy (precision) | ≥ 85% |
| False positive rate | ≤ 15% |
| Dashboard load time | < 2 seconds |
| Report generation time | < 5 seconds |

---

## 12 · Open Questions

1. **Video sourcing**: Do we use publicly available warehouse footage for the demo, or record our own?
2. **Notification persistence**: Should notifications be stored as first-class entities or derived from events?
3. **Multi-tenancy**: Is warehouse-level isolation needed for the demo, or single-tenant is fine?

---

*Last updated: March 7, 2026*

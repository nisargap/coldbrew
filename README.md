# ColdBrew

Warehouse video intelligence platform. Upload CCTV footage, detect events automatically, and notify the right people.

Built for the **NomadicML 12-Hour Hackathon** — Robotics Track.

---

## What It Does

1. **Upload** warehouse video feeds (CCTV, dock cameras, facility footage).
2. **Analyze** footage using the NomadicML vision API to detect safety violations, equipment failures, shipment anomalies, and more.
3. **Surface** detected events on a real-time dashboard with severity levels and category filters.
4. **Notify** the right warehouse persona (manager, maintenance tech, dock supervisor, safety officer) with one click.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, Tailwind CSS, shadcn/ui |
| Backend | Python, FastAPI, SQLite |
| Vision AI | NomadicML SDK |

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- NomadicML API key (set as `NOMADIC_SDK_API_KEY` environment variable)

---

## Getting Started

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

NOMADIC_SDK_API_KEY=your_key_here uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## Project Structure

```
coldbrew/
├── backend/               # FastAPI application
│   ├── main.py
│   ├── models.py
│   ├── database.py
│   ├── routers/
│   │   ├── feeds.py
│   │   ├── events.py
│   │   └── notifications.py
│   ├── services/
│   │   ├── analysis.py
│   │   └── notifications.py
│   └── uploads/
├── frontend/              # Next.js application
│   ├── app/
│   │   ├── upload/
│   │   ├── dashboard/
│   │   └── notifications/
│   ├── components/
│   └── lib/
├── agents/                # Agent instruction files
│   ├── BACKEND.md
│   ├── FRONTEND.md
│   ├── DESIGN.md
│   └── INTEGRATION.md
├── PRD.md                 # Full product requirements
├── LightPRD.md            # MVP scope
├── ORCHESTRATOR.md        # Orchestrator agent instructions
└── README.md
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/feeds/upload` | Upload a video file |
| `GET` | `/api/feeds` | List all feeds |
| `GET` | `/api/events` | List events (filterable) |
| `GET` | `/api/events/:id` | Get event detail |
| `PATCH` | `/api/events/:id` | Update event status |
| `POST` | `/api/notifications/send` | Send notification |
| `GET` | `/api/notifications` | List notifications |

---

## Event Categories

| Category | Examples |
|---|---|
| Safety | PPE violations, blocked exits, near-misses |
| Equipment | Conveyor jams, forklift malfunctions |
| Shipment | Truck arrivals, missing deliveries, damaged cargo |
| Operational | Blocked aisles, misplaced pallets |
| Environmental | Spills, smoke, leaks |

---

## Team

Built by the ColdBrew team at NomadicML Hackathon 2026.

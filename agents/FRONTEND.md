# Frontend Agent — Instructions

You are the **Frontend Agent** for the ColdBrew project. You own the entire Next.js application — layout, pages, components, API integration, and visual design implementation.

---

## What You Own

```
frontend/
├── app/
│   ├── layout.tsx          # Root layout: dark theme, sidebar nav
│   ├── page.tsx            # Redirect to /dashboard
│   ├── upload/
│   │   └── page.tsx        # Video upload page
│   ├── dashboard/
│   │   └── page.tsx        # Event dashboard
│   └── notifications/
│       └── page.tsx        # Notification history
├── components/
│   ├── layout/
│   │   ├── sidebar.tsx     # Sidebar navigation
│   │   └── header.tsx      # Top bar (page title, actions)
│   ├── events/
│   │   ├── event-card.tsx  # Individual event card
│   │   ├── event-list.tsx  # Scrollable event list with filters
│   │   ├── event-detail.tsx# Expanded event view
│   │   └── severity-badge.tsx
│   ├── upload/
│   │   ├── drop-zone.tsx   # Drag-and-drop file input
│   │   └── upload-status.tsx
│   └── notifications/
│       ├── notify-modal.tsx   # Mass notification composer
│       └── notification-card.tsx
├── lib/
│   ├── api.ts              # API client (fetch wrappers)
│   └── types.ts            # TypeScript types matching API contract
├── tailwind.config.ts
├── next.config.js
└── package.json
```

---

## Tech Stack

| Tool | Notes |
|---|---|
| Next.js 14 | App Router |
| Tailwind CSS | Utility-first styling |
| shadcn/ui | Component primitives (Button, Dialog, Select, Toast, Checkbox, Card, Badge) |
| TypeScript | Strict mode |
| Lucide React | Icons |

**Setup commands:**
```bash
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir=false --import-alias="@/*"
cd frontend
npx shadcn@latest init
npx shadcn@latest add button card checkbox dialog select toast badge input textarea separator scroll-area
npm install lucide-react
```

---

## API Client

All API calls go through a single `lib/api.ts` file. The backend runs on `localhost:8000`.

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function uploadFeed(file: File, feedName: string) {
  const form = new FormData();
  form.append("file", file);
  form.append("feed_name", feedName);
  const res = await fetch(`${API_URL}/api/feeds/upload`, { method: "POST", body: form });
  return res.json();
}

export async function getFeeds() {
  const res = await fetch(`${API_URL}/api/feeds`);
  return res.json();
}

export async function getEvents(params?: { category?: string; severity?: string }) {
  const query = new URLSearchParams(params as Record<string, string>).toString();
  const res = await fetch(`${API_URL}/api/events${query ? `?${query}` : ""}`);
  return res.json();
}

export async function getEvent(id: string) {
  const res = await fetch(`${API_URL}/api/events/${id}`);
  return res.json();
}

export async function updateEventStatus(id: string, status: "acknowledged" | "dismissed") {
  const res = await fetch(`${API_URL}/api/events/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  return res.json();
}

export async function sendNotification(eventIds: string[], personaIds: string[], message: string) {
  const res = await fetch(`${API_URL}/api/notifications/send`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event_ids: eventIds, persona_ids: personaIds, message }),
  });
  return res.json();
}

export async function getNotifications() {
  const res = await fetch(`${API_URL}/api/notifications`);
  return res.json();
}
```

---

## TypeScript Types

Match the API contract exactly:

```typescript
export interface Feed {
  feed_id: string;
  feed_name: string;
  status: "processing" | "completed" | "error";
  created_at: string;
  event_count: number;
}

export interface Event {
  id: string;
  timestamp: string;
  category: "Safety" | "Equipment" | "Shipment" | "Operational" | "Environmental";
  severity: "Critical" | "High" | "Medium" | "Low";
  title: string;
  description: string;
  source_feed: string;
  thumbnail_url: string | null;
  confidence: number;
  status: "new" | "acknowledged" | "dismissed";
}

export interface Persona {
  id: string;
  name: string;
  role: string;
}

export interface Notification {
  id: string;
  message: string;
  sent_to: Persona[];
  event_ids: string[];
  created_at: string;
}
```

---

## Personas (Hardcoded)

```typescript
export const PERSONAS: Persona[] = [
  { id: "alex-rivera", name: "Alex Rivera", role: "Warehouse Manager" },
  { id: "sam-okafor", name: "Sam Okafor", role: "Maintenance Technician" },
  { id: "jordan-lin", name: "Jordan Lin", role: "Dock Supervisor" },
  { id: "priya-desai", name: "Priya Desai", role: "Safety Officer" },
];
```

---

## Pages

### 1. Upload (`/upload`)

**Layout:**
- Centered content area.
- Large drag-and-drop zone (dashed border, icon, "Drop a video file here or click to browse").
- Text input below for feed name.
- Upload button (disabled until file + name are provided).
- Below the upload zone: list of recent uploads with status badges (processing / completed / error).

**Behavior:**
- On file drop or select: show file name and size.
- On submit: call `uploadFeed()`, show uploading state with progress.
- After upload: card appears in the recent uploads list with "Processing..." badge.
- Poll `getFeeds()` every 3 seconds to update status. Stop polling when status is `completed` or `error`.

**Accepted files:** `.mp4`, `.mov`

### 2. Dashboard (`/dashboard`)

**Layout:**
- Top bar: page title "Events", filter controls on the right.
- Filter row: category dropdown (All / Safety / Equipment / Shipment / Operational / Environmental), severity dropdown (All / Critical / High / Medium / Low).
- Below filters: scrollable grid/list of event cards.
- Floating action bar at bottom when ≥ 1 event is selected: shows count of selected events + "Notify" button.

**Event Card:**
- Thumbnail on the left (or placeholder icon if no thumbnail).
- Title (bold), description (truncated to 2 lines).
- Severity badge: colored pill.
  - Critical: `bg-red-500/15 text-red-400 border-red-500/30`
  - High: `bg-orange-500/15 text-orange-400 border-orange-500/30`
  - Medium: `bg-yellow-500/15 text-yellow-400 border-yellow-500/30`
  - Low: `bg-blue-500/15 text-blue-400 border-blue-500/30`
- Category tag: muted pill.
- Timestamp: relative ("2 min ago") or absolute.
- Source feed name: small text.
- Status badge if acknowledged/dismissed.
- Checkbox in top-right corner for selection.
- Click card → expand inline or open detail panel with full description, larger thumbnail, Acknowledge/Dismiss buttons.

**Notify Modal** (opens when "Notify" clicked):
- Header: "Send Notification" with count of selected events.
- Persona multi-select: checkboxes with name + role.
- Message textarea: pre-populated with auto-generated summary of selected events. User can edit.
- Cancel / Send buttons.
- On send: call `sendNotification()`, show success toast, clear selection.

### 3. Notification History (`/notifications`)

**Layout:**
- Page title: "Notification History".
- List of notification cards, most recent first.

**Notification Card:**
- Timestamp.
- "Sent to" — list of persona names with role tags.
- Event count badge ("3 events").
- Message content (full text, or truncated with expand).

**Empty state:** "No notifications sent yet."

---

## Visual Design Specs

Follow the Product Design Agent's direction (`agents/DESIGN.md`), but these are the non-negotiable defaults:

### Theme
- Background: `#09090B` (zinc-950).
- Card/surface: `#18181B` (zinc-900).
- Border: `#27272A` (zinc-800).
- Primary text: `#FAFAFA` (zinc-50).
- Secondary text: `#A1A1AA` (zinc-400).
- Accent: `#3B82F6` (blue-500).

### Typography
- Headings: Inter or system sans-serif, semibold.
- Body: Inter or system sans-serif, regular.
- Data/timestamps: JetBrains Mono or system monospace.

### Severity Colors
| Level | Background | Text | Border |
|---|---|---|---|
| Critical | `#EF4444/15%` | `#EF4444` | `#EF4444/30%` |
| High | `#F97316/15%` | `#F97316` | `#F97316/30%` |
| Medium | `#EAB308/15%` | `#EAB308` | `#EAB308/30%` |
| Low | `#3B82F6/15%` | `#3B82F6` | `#3B82F6/30%` |

### Category Colors
All categories use the same muted style: `bg-zinc-800 text-zinc-300 border-zinc-700`.

### Spacing
- Page padding: `p-6`.
- Card padding: `p-4`.
- Gap between cards: `gap-3`.
- Sidebar width: `w-56`.

---

## States to Handle

Every page needs these:

| State | What to show |
|---|---|
| **Loading** | Skeleton cards (pulsing gray rectangles matching card layout) |
| **Empty** | Centered icon + message + call-to-action |
| **Error** | Red banner with retry button |
| **Populated** | Normal content |

Empty state messages:
- Dashboard: "No events detected yet. Upload a video to get started." + link to Upload page.
- Notifications: "No notifications sent yet."
- Upload (no recent feeds): "Upload your first warehouse video."

---

## Component Patterns

- Use `"use client"` on any component that needs state, effects, or event handlers.
- Use shadcn/ui `<Card>`, `<Badge>`, `<Button>`, `<Dialog>`, `<Select>`, `<Checkbox>`, `<Textarea>`, `<Input>` as base components.
- Toast notifications via shadcn/ui `useToast()`.
- No global state management library. Use React state + prop drilling. The app is small enough.
- Fetch data with `useEffect` + `useState`. No React Query or SWR — keep dependencies minimal.

---

## How to Run

```bash
cd frontend
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

---

## Rules

1. **Match the API contract.** The types in `lib/types.ts` must mirror the backend response shapes exactly. If something doesn't match, flag it to the Orchestrator.
2. **Dark theme only.** No light mode toggle. No light mode styles. One theme.
3. **No placeholder data in production code.** Mock data is fine during development while the backend isn't ready, but it must be clearly labeled and easy to remove.
4. **Responsive is out of scope.** Build for desktop only (1280px+ viewport). Don't spend time on mobile breakpoints.
5. **No external fonts CDN.** Use system font stacks or bundle fonts locally. The demo shouldn't depend on network for fonts.
6. **Follow the Design Agent.** If the Design Agent (`agents/DESIGN.md`) provides specific component specs, colors, or layout decisions, follow them over the defaults in this file.

---

## Your Team

You don't work alone. Here are the other agents and when to engage them:

| Agent | File | When to engage |
|---|---|---|
| **Orchestrator** | `ORCHESTRATOR.md` | When you need to change an API contract (e.g., you need a new field from the backend), or when you're blocked waiting on another agent. All contract changes go through the Orchestrator. |
| **Backend** | `agents/BACKEND.md` | When API responses don't match the contract, when you need a new endpoint or field, or when you're debugging a data issue. They serve the data you display — coordinate on shapes and edge cases. |
| **Product Design** | `agents/DESIGN.md` | **Your closest collaborator.** Follow their specs for colors, typography, spacing, component design, and layout. If you're unsure how something should look, ask them. If their spec conflicts with implementation feasibility, negotiate with them. |
| **NomadicML Expert** | `agents/NOMADICML_EXPERT.md` | When you need to understand what data the analysis pipeline produces (event structure, confidence scores, categories) so you can display it correctly. Also consult them if you need to show analysis status or progress to the user. |
| **Integration / QA** | `agents/INTEGRATION.md` | When you need to verify that your pages work end-to-end with the real backend. They will test every interaction on your pages and report bugs. Coordinate with them on expected behavior for edge cases (empty states, errors, loading). |

---

## Reference Files

| File | What to read |
|---|---|
| `LightPRD.md` | Full MVP spec |
| `ORCHESTRATOR.md` | Execution plan, API contract, phase milestones |
| `agents/FRONTEND.md` | This file |
| `agents/BACKEND.md` | API endpoint details — what you're calling |
| `agents/DESIGN.md` | Visual design system — colors, layout, component specs |
| `agents/NOMADICML_EXPERT.md` | SDK response shapes — what data to expect from analysis |
| `agents/INTEGRATION.md` | Test checklist — what QA will verify on your pages |
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function uploadFeed(file: File, feedName: string, analysisMode: string = "standard") {
  const form = new FormData();
  form.append("file", file);
  form.append("feed_name", feedName);
  form.append("analysis_mode", analysisMode);
  const res = await fetch(`${API_URL}/api/feeds/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(err.detail || "Upload failed");
  }
  return res.json();
}

export async function reanalyzeFeed(feedId: string, analysisMode: string = "agent") {
  const res = await fetch(`${API_URL}/api/feeds/${feedId}/reanalyze?analysis_mode=${analysisMode}`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Re-analysis failed" }));
    throw new Error(err.detail || "Re-analysis failed");
  }
  return res.json();
}

export async function getFeeds() {
  const res = await fetch(`${API_URL}/api/feeds`);
  if (!res.ok) throw new Error("Failed to fetch feeds");
  return res.json();
}

export async function getFeed(feedId: string) {
  const res = await fetch(`${API_URL}/api/feeds/${feedId}`);
  if (!res.ok) throw new Error("Feed not found");
  return res.json();
}

export async function getEvents(params?: { category?: string; severity?: string; feed_id?: string }) {
  const filtered: Record<string, string> = {};
  if (params?.category) filtered.category = params.category;
  if (params?.severity) filtered.severity = params.severity;
  if (params?.feed_id) filtered.feed_id = params.feed_id;
  const query = new URLSearchParams(filtered).toString();
  const res = await fetch(`${API_URL}/api/events${query ? `?${query}` : ""}`);
  if (!res.ok) throw new Error("Failed to fetch events");
  return res.json();
}

export async function getEvent(id: string) {
  const res = await fetch(`${API_URL}/api/events/${id}`);
  if (!res.ok) throw new Error("Event not found");
  return res.json();
}

export async function updateEventStatus(id: string, status: "acknowledged" | "dismissed") {
  const res = await fetch(`${API_URL}/api/events/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error("Failed to update event");
  return res.json();
}

export async function sendNotification(eventIds: string[], personaIds: string[], message: string) {
  const res = await fetch(`${API_URL}/api/notifications/send`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event_ids: eventIds, persona_ids: personaIds, message }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Failed to send" }));
    throw new Error(err.detail || "Failed to send notification");
  }
  return res.json();
}

export async function getNotifications() {
  const res = await fetch(`${API_URL}/api/notifications`);
  if (!res.ok) throw new Error("Failed to fetch notifications");
  return res.json();
}

/**
 * Subscribe to real-time feed status updates via SSE.
 * Returns an unsubscribe function.
 */
export function subscribeFeedUpdates(onUpdate: (data: FeedSSEEvent) => void): () => void {
  const url = `${API_URL}/api/feeds/stream`;
  const eventSource = new EventSource(url);

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as FeedSSEEvent;
      onUpdate(data);
    } catch {
      // Ignore malformed messages
    }
  };

  eventSource.onerror = () => {
    // EventSource auto-reconnects — nothing to do
  };

  return () => eventSource.close();
}

export interface FeedSSEEvent {
  type: "feed_update";
  feed_id: string;
  status: "completed" | "error";
  event_count?: number;
  error_message?: string;
  feed_name?: string;
}

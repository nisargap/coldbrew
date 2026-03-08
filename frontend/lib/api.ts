const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function uploadFeed(file: File, feedName: string, analysisMode: string = "standard", confidenceLevel: string = "low") {
  const form = new FormData();
  form.append("file", file);
  form.append("feed_name", feedName);
  form.append("analysis_mode", analysisMode);
  form.append("confidence_level", confidenceLevel);
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

export async function startLivestream(url: string, feedName: string, analysisMode: string = "standard", query: string = "") {
  const res = await fetch(`${API_URL}/api/feeds/livestream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, feed_name: feedName, analysis_mode: analysisMode, query }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Livestream failed" }));
    throw new Error(err.detail || "Livestream failed");
  }
  return res.json();
}

export async function stopLivestream(feedId: string) {
  const res = await fetch(`${API_URL}/api/feeds/${feedId}/livestream`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Failed to stop" }));
    throw new Error(err.detail || "Failed to stop livestream");
  }
  return res.json();
}

export async function updateLivestreamQuery(feedId: string, query: string) {
  const res = await fetch(`${API_URL}/api/feeds/${feedId}/livestream/query`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Failed to update query" }));
    throw new Error(err.detail || "Failed to update livestream query");
  }
  return res.json();
}

export async function stopAllLivestreams() {
  const res = await fetch(`${API_URL}/api/feeds/livestream/all`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Failed to stop all" }));
    throw new Error(err.detail || "Failed to stop all livestreams");
  }
  return res.json();
}

export async function reanalyzeFeed(feedId: string, analysisMode: string = "agent", confidenceLevel: string = "low") {
  const params = new URLSearchParams({ analysis_mode: analysisMode, confidence_level: confidenceLevel });
  const res = await fetch(`${API_URL}/api/feeds/${feedId}/reanalyze?${params}`, {
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
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `Failed to fetch feeds (HTTP ${res.status})` }));
    throw new Error(err.detail || `Failed to fetch feeds (HTTP ${res.status})`);
  }
  return res.json();
}

export async function getFeed(feedId: string) {
  const res = await fetch(`${API_URL}/api/feeds/${feedId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `Feed not found (HTTP ${res.status})` }));
    throw new Error(err.detail || `Feed not found (HTTP ${res.status})`);
  }
  return res.json();
}

export async function getEvents(params?: { category?: string; severity?: string; feed_id?: string; min_confidence?: number }) {
  const filtered: Record<string, string> = {};
  if (params?.category) filtered.category = params.category;
  if (params?.severity) filtered.severity = params.severity;
  if (params?.feed_id) filtered.feed_id = params.feed_id;
  if (params?.min_confidence !== undefined) filtered.min_confidence = String(params.min_confidence);
  const query = new URLSearchParams(filtered).toString();
  const res = await fetch(`${API_URL}/api/events${query ? `?${query}` : ""}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `Failed to fetch events (HTTP ${res.status})` }));
    throw new Error(err.detail || `Failed to fetch events (HTTP ${res.status})`);
  }
  return res.json();
}

export async function getEvent(id: string) {
  const res = await fetch(`${API_URL}/api/events/${id}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `Event not found (HTTP ${res.status})` }));
    throw new Error(err.detail || `Event not found (HTTP ${res.status})`);
  }
  return res.json();
}

export async function updateEventStatus(id: string, status: "acknowledged" | "dismissed") {
  const res = await fetch(`${API_URL}/api/events/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `Failed to update event (HTTP ${res.status})` }));
    throw new Error(err.detail || `Failed to update event (HTTP ${res.status})`);
  }
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
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `Failed to fetch notifications (HTTP ${res.status})` }));
    throw new Error(err.detail || `Failed to fetch notifications (HTTP ${res.status})`);
  }
  return res.json();
}

export async function getPersonas() {
  const res = await fetch(`${API_URL}/api/personas`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `Failed to fetch personas (HTTP ${res.status})` }));
    throw new Error(err.detail || `Failed to fetch personas (HTTP ${res.status})`);
  }
  return res.json();
}

export async function getEventEnrichment(eventId: string) {
  const res = await fetch(`${API_URL}/api/events/${eventId}/enrichment`);
  if (res.status === 404) return null; // Not enriched yet
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `Failed to fetch enrichment (HTTP ${res.status})` }));
    throw new Error(err.detail || `Failed to fetch enrichment (HTTP ${res.status})`);
  }
  return res.json();
}

export async function getFeedEnrichments(feedId: string) {
  const res = await fetch(`${API_URL}/api/feeds/${feedId}/enrichments`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `Failed to fetch enrichments (HTTP ${res.status})` }));
    throw new Error(err.detail || `Failed to fetch enrichments (HTTP ${res.status})`);
  }
  return res.json();
}

export async function triggerEnrichment(feedId: string) {
  const res = await fetch(`${API_URL}/api/feeds/${feedId}/enrich`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Failed to trigger enrichment" }));
    throw new Error(err.detail || "Failed to trigger enrichment");
  }
  return res.json();
}

export async function startConversation(feedId: string): Promise<{
  agent_id: string;
  signed_url: string;
  feed_name: string;
  event_count: number;
  critical_count: number;
}> {
  const res = await fetch(`${API_URL}/api/feeds/${feedId}/conversation`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Failed to start conversation" }));
    throw new Error(err.detail || "Failed to start conversation");
  }
  return res.json();
}

export async function endConversation(feedId: string, agentId: string) {
  const res = await fetch(`${API_URL}/api/feeds/${feedId}/conversation/${agentId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Failed to end conversation" }));
    throw new Error(err.detail || "Failed to end conversation");
  }
  return res.json();
}

export async function getDependencyStatus() {
  const res = await fetch(`${API_URL}/api/status`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `Failed to check status (HTTP ${res.status})` }));
    throw new Error(err.detail || `Failed to check status (HTTP ${res.status})`);
  }
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
  type: "feed_update" | "livestream_cycle" | "agentic_complete" | "voice_alert_ready";
  feed_id: string;
  status?: "completed" | "error" | "monitoring" | "capturing" | "analyzing" | "enriching" | "done";
  event_count?: number;
  error_message?: string;
  error?: string;
  feed_name?: string;
  analysis_mode?: string;
  cycle?: number;
  viewer_url?: string;
  stream_id?: string;
  session_id?: string;
  // Agentic enrichment fields
  enriched_count?: number;
  avg_risk_score?: number;
  agentic_status?: string;
  // Voice alert fields
  event_id?: string;
  voice_alert_url?: string;
  risk_score?: number;
}

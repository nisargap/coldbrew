"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Filter, Bell, Check, X, ChevronDown, ExternalLink } from "lucide-react";
import { getEvents, updateEventStatus, sendNotification, getPersonas } from "@/lib/api";
import type { Event, Persona } from "@/lib/types";
import { SEVERITY_COLORS } from "@/lib/types";

const CATEGORIES = ["All", "Safety", "Equipment", "Shipment", "Operational", "Environmental"];
const SEVERITIES = ["All", "Critical", "High", "Medium", "Low"];

export default function DashboardPage() {
  const router = useRouter();
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState("All");
  const [severityFilter, setSeverityFilter] = useState("All");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showNotifyModal, setShowNotifyModal] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const fetchEvents = useCallback(async () => {
    try {
      const params: { category?: string; severity?: string } = {};
      if (categoryFilter !== "All") params.category = categoryFilter;
      if (severityFilter !== "All") params.severity = severityFilter;
      const data = await getEvents(params);
      setEvents(data);
    } catch {
      // Silently fail
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, severityFilter]);

  useEffect(() => {
    setLoading(true);
    fetchEvents();
  }, [fetchEvents]);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 4000);
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleStatusUpdate = async (id: string, status: "acknowledged" | "dismissed") => {
    try {
      await updateEventStatus(id, status);
      showToast(status === "acknowledged" ? "Event acknowledged." : "Event dismissed.");
      fetchEvents();
    } catch {
      showToast("Something went wrong. Try again.");
    }
  };

  const handleQuickNotify = (event: Event) => {
    setSelectedIds(new Set([event.id]));
    setShowNotifyModal(true);
  };

  const formatTime = (iso: string) => {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  };

  const criticalCount = events.filter(
    (e) => (e.severity === "Critical" || e.severity === "High") && e.status === "new"
  ).length;

  return (
    <div className="p-6">
      {/* Header + Filters */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-4">
          <h2 className="text-xl font-semibold text-zinc-50">Events</h2>
          {criticalCount > 0 && (
            <span className="flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-medium text-red-400 bg-red-500/[0.08] border border-red-500/25 rounded-full animate-pulse">
              <AlertTriangle size={11} />
              {criticalCount} critical
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Filter size={14} className="text-zinc-500" />
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="bg-[#27272A] border border-[#27272A] rounded-md px-2.5 py-1.5 text-xs text-zinc-300 focus:outline-none focus:border-blue-500"
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="bg-[#27272A] border border-[#27272A] rounded-md px-2.5 py-1.5 text-xs text-zinc-300 focus:outline-none focus:border-blue-500"
          >
            {SEVERITIES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="space-y-2">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-[72px] bg-[#18181B] rounded-md animate-pulse" />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && events.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <AlertTriangle size={32} className="text-zinc-600 mb-3" />
          <p className="text-sm text-zinc-400">No events detected yet.</p>
          <a href="/upload" className="text-sm text-blue-400 hover:underline mt-1">
            Upload a video to get started.
          </a>
        </div>
      )}

      {/* Event list */}
      {!loading && events.length > 0 && (
        <div className="border border-[#27272A] rounded-lg overflow-hidden">
          {events.map((event) => {
            const isSelected = selectedIds.has(event.id);
            const isExpanded = expandedId === event.id;
            const sev = SEVERITY_COLORS[event.severity] || SEVERITY_COLORS.Low;
            const isCritical = event.severity === "Critical" || event.severity === "High";

            return (
              <div key={event.id}>
                <div
                  className={`flex items-center gap-3 px-3 py-3 border-b border-[#27272A] hover:bg-[#27272A]/50 transition-colors duration-100 cursor-pointer ${
                    isSelected ? "border-l-2 border-l-blue-500" : "border-l-2 border-l-transparent"
                  }`}
                  onClick={() => setExpandedId(isExpanded ? null : event.id)}
                >
                  {/* Checkbox */}
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={(e) => {
                      e.stopPropagation();
                      toggleSelect(event.id);
                    }}
                    onClick={(e) => e.stopPropagation()}
                    className="w-3.5 h-3.5 rounded border-zinc-600 bg-transparent accent-blue-500 cursor-pointer flex-shrink-0"
                  />

                  {/* Thumbnail placeholder */}
                  <div className={`w-12 h-12 rounded-md flex items-center justify-center flex-shrink-0 ${
                    isCritical ? "bg-red-500/[0.08] border border-red-500/20" : "bg-[#27272A]"
                  }`}>
                    <AlertTriangle size={16} className={isCritical ? "text-red-400" : "text-zinc-600"} />
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-[15px] font-medium text-zinc-100 truncate">
                        {event.title}
                      </p>
                      {event.status !== "new" && (
                        <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
                          event.status === "acknowledged"
                            ? "bg-green-500/10 text-green-400"
                            : "bg-zinc-700 text-zinc-500"
                        }`}>
                          {event.status}
                        </span>
                      )}
                    </div>
                    <p className="text-[13px] text-zinc-400 truncate mt-0.5">
                      {event.description}
                    </p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-[11px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">
                        {event.category}
                      </span>
                      <span className={`text-[11px] px-1.5 py-0.5 rounded-full border ${sev.bg} ${sev.text} ${sev.border}`}>
                        {event.severity}
                      </span>
                      <span className="text-[11px] text-zinc-600">·</span>
                      <button
                        onClick={(e) => { e.stopPropagation(); router.push(`/feeds/${event.feed_id}`); }}
                        className="text-[11px] text-blue-400 hover:underline flex items-center gap-0.5"
                      >
                        {event.source_feed}
                        <ExternalLink size={9} />
                      </button>
                      <span className="text-[11px] text-zinc-600">·</span>
                      <span className={`text-[11px] font-mono ${
                        event.confidence >= 0.7 ? "text-zinc-500" : "text-amber-500/70"
                      }`}>
                        {(event.confidence * 100).toFixed(0)}%
                      </span>
                      <span className="text-[11px] text-zinc-600">·</span>
                      <span className="text-xs text-zinc-600 font-mono">
                        {formatTime(event.timestamp)}
                      </span>
                    </div>
                  </div>

                  {/* Quick notify for critical/high severity events */}
                  {isCritical && event.status === "new" && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleQuickNotify(event);
                      }}
                      className="flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-medium text-red-400 border border-red-500/25 bg-red-500/[0.08] rounded-md hover:bg-red-500/[0.15] transition-colors flex-shrink-0"
                      title="Send alert for this event"
                    >
                      <Bell size={11} />
                      Alert
                    </button>
                  )}

                  <ChevronDown
                    size={14}
                    className={`text-zinc-600 transition-transform flex-shrink-0 ${isExpanded ? "rotate-180" : ""}`}
                  />
                </div>

                {/* Expanded detail */}
                {isExpanded && (
                  <div className="px-6 py-4 bg-[#18181B] border-b border-[#27272A]">
                    <p className="text-sm text-zinc-300 mb-3">{event.description}</p>
                    <div className="flex items-center gap-4 text-xs text-zinc-500 mb-4">
                      <span>Confidence: {(event.confidence * 100).toFixed(0)}%</span>
                      <button
                        onClick={() => router.push(`/feeds/${event.feed_id}`)}
                        className="text-blue-400 hover:underline flex items-center gap-1"
                      >
                        View feed: {event.source_feed}
                        <ExternalLink size={10} />
                      </button>
                      <span>ID: {event.id.slice(0, 8)}</span>
                    </div>
                    {event.status === "new" && (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={(e) => { e.stopPropagation(); handleStatusUpdate(event.id, "acknowledged"); }}
                          className="flex items-center gap-1.5 px-3 py-1.5 text-[13px] text-zinc-300 border border-[#27272A] rounded-md hover:bg-[#27272A] transition-colors"
                        >
                          <Check size={13} />
                          Acknowledge
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleStatusUpdate(event.id, "dismissed"); }}
                          className="flex items-center gap-1.5 px-3 py-1.5 text-[13px] text-zinc-300 border border-[#27272A] rounded-md hover:bg-[#27272A] transition-colors"
                        >
                          <X size={13} />
                          Dismiss
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleQuickNotify(event); }}
                          className="flex items-center gap-1.5 px-3 py-1.5 text-[13px] text-red-400 border border-red-500/25 bg-red-500/[0.08] rounded-md hover:bg-red-500/[0.15] transition-colors"
                        >
                          <Bell size={13} />
                          Send Alert
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Floating action bar */}
      {selectedIds.size > 0 && (
        <div className="fixed bottom-0 left-56 right-0 bg-[#18181B] border-t border-[#27272A] px-6 py-3 flex items-center justify-between z-40">
          <span className="text-sm text-zinc-300">
            {selectedIds.size} event{selectedIds.size !== 1 ? "s" : ""} selected
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSelectedIds(new Set())}
              className="px-3 py-1.5 text-[13px] text-zinc-400 border border-[#27272A] rounded-md hover:bg-[#27272A] transition-colors"
            >
              Clear
            </button>
            <button
              onClick={() => setShowNotifyModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white text-[13px] font-medium rounded-md hover:bg-blue-600 transition-colors"
            >
              <Bell size={14} />
              Notify
            </button>
          </div>
        </div>
      )}

      {/* Notify Modal */}
      {showNotifyModal && (
        <NotifyModal
          selectedEvents={events.filter((e) => selectedIds.has(e.id))}
          onClose={() => setShowNotifyModal(false)}
          onSent={() => {
            setSelectedIds(new Set());
            setShowNotifyModal(false);
            showToast("Notification sent.");
            fetchEvents();
          }}
        />
      )}

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 right-6 bg-[#18181B] border border-[#27272A] text-zinc-200 text-sm px-4 py-3 rounded-lg shadow-xl z-50 animate-[fadeIn_150ms_ease-in]">
          {toast}
        </div>
      )}
    </div>
  );
}

function NotifyModal({
  selectedEvents,
  onClose,
  onSent,
}: {
  selectedEvents: Event[];
  onClose: () => void;
  onSent: () => void;
}) {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [selectedPersonas, setSelectedPersonas] = useState<Set<string>>(new Set());

  useEffect(() => {
    getPersonas()
      .then((data: Persona[]) => {
        setPersonas(data);
        // Smart auto-select: match personas to event categories
        const autoSelect = new Set<string>();
        const categoryMap: Record<string, string> = {};
        for (const p of data) {
          if (p.category) categoryMap[p.category] = p.id;
        }
        for (const e of selectedEvents) {
          if (e.severity === "Critical" || e.severity === "High") {
            // Select first persona (manager) for critical/high
            if (data.length > 0) autoSelect.add(data[0].id);
          }
          if (categoryMap[e.category]) autoSelect.add(categoryMap[e.category]);
        }
        if (autoSelect.size === 0 && data.length > 0) autoSelect.add(data[0].id);
        setSelectedPersonas(autoSelect);
      })
      .catch(() => {});
  }, []);

  const [message, setMessage] = useState(() => {
    const lines = selectedEvents.map(
      (e) => `• [${e.severity}] ${e.title} (${e.category})`
    );
    return `Alert: ${selectedEvents.length} event${selectedEvents.length !== 1 ? "s" : ""} detected in warehouse monitoring.\n\n${lines.join("\n")}`;
  });
  const [sending, setSending] = useState(false);

  const togglePersona = (id: string) => {
    setSelectedPersonas((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSend = async () => {
    if (selectedPersonas.size === 0 || !message.trim()) return;
    setSending(true);
    try {
      await sendNotification(
        selectedEvents.map((e) => e.id),
        Array.from(selectedPersonas),
        message
      );
      onSent();
    } catch {
      // Error
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-[#18181B] border border-[#27272A] rounded-lg w-full max-w-lg mx-4 p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-[15px] font-semibold text-zinc-100">Send Notification</h3>
        <p className="text-xs text-zinc-500 mt-1">
          {selectedEvents.length} event{selectedEvents.length !== 1 ? "s" : ""} selected
        </p>

        {/* Event summary */}
        <div className="mt-3 space-y-1 max-h-24 overflow-y-auto">
          {selectedEvents.map((e) => {
            const sev = SEVERITY_COLORS[e.severity] || SEVERITY_COLORS.Low;
            return (
              <div key={e.id} className="flex items-center gap-2 text-[12px]">
                <span className={`px-1.5 py-0.5 rounded-full border ${sev.bg} ${sev.text} ${sev.border}`}>
                  {e.severity}
                </span>
                <span className="text-zinc-300 truncate">{e.title}</span>
              </div>
            );
          })}
        </div>

        {/* Persona selection */}
        <div className="mt-4">
          <label className="text-xs font-medium text-zinc-500 uppercase tracking-wider">
            Recipients
          </label>
          <div className="mt-2 space-y-1.5">
            {personas.length === 0 ? (
              <p className="text-xs text-zinc-500">Loading recipients...</p>
            ) : personas.map((p: Persona) => (
              <label
                key={p.id}
                className="flex items-center gap-2.5 px-3 py-2 rounded-md hover:bg-[#27272A]/50 cursor-pointer transition-colors"
              >
                <input
                  type="checkbox"
                  checked={selectedPersonas.has(p.id)}
                  onChange={() => togglePersona(p.id)}
                  className="w-3.5 h-3.5 rounded border-zinc-600 bg-transparent accent-blue-500"
                />
                <span className="text-[13px] text-zinc-200">{p.name}</span>
                <span className="text-[11px] text-zinc-500">{p.role}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Message */}
        <div className="mt-4">
          <label className="text-xs font-medium text-zinc-500 uppercase tracking-wider">
            Message
          </label>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={5}
            className="mt-2 w-full bg-[#27272A] border border-[#27272A] rounded-md px-3 py-2.5 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-blue-500 resize-none"
          />
        </div>

        {/* Actions */}
        <div className="mt-4 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-[13px] text-zinc-400 border border-[#27272A] rounded-md hover:bg-[#27272A] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSend}
            disabled={selectedPersonas.size === 0 || !message.trim() || sending}
            className="px-4 py-2 bg-blue-500 text-white text-[13px] font-medium rounded-md hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {sending ? "Sending..." : "Send Notification"}
          </button>
        </div>
      </div>
    </div>
  );
}

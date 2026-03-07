"use client";

import { useState, useEffect } from "react";
import { Bell, Users, ChevronDown, ChevronUp, AlertTriangle } from "lucide-react";
import { getNotifications } from "@/lib/api";
import type { Notification, EventSummary } from "@/lib/types";
import { SEVERITY_COLORS } from "@/lib/types";

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    getNotifications()
      .then(setNotifications)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return d.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  };

  return (
    <div className="p-6 max-w-3xl">
      <h2 className="text-xl font-semibold text-zinc-50 mb-6">
        Notification History
      </h2>

      {/* Loading */}
      {loading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-32 bg-[#18181B] rounded-lg animate-pulse" />
          ))}
        </div>
      )}

      {/* Empty */}
      {!loading && notifications.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <Bell size={32} className="text-zinc-600 mb-3" />
          <p className="text-sm text-zinc-400">No notifications have been sent.</p>
          <a href="/dashboard" className="text-sm text-blue-400 hover:underline mt-1">
            Go to dashboard to review events.
          </a>
        </div>
      )}

      {/* List */}
      {!loading && notifications.length > 0 && (
        <div className="space-y-3">
          {notifications.map((n) => {
            const isExpanded = expandedId === n.id;
            const criticalEvents = n.events.filter(
              (e) => e.severity === "Critical" || e.severity === "High"
            );
            const hasCritical = criticalEvents.length > 0;

            return (
              <div
                key={n.id}
                className={`bg-[#18181B] border rounded-lg overflow-hidden ${
                  hasCritical ? "border-red-500/20" : "border-[#27272A]"
                }`}
              >
                {/* Header */}
                <div className="p-4">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-md flex items-center justify-center flex-shrink-0 ${
                        hasCritical ? "bg-red-500/[0.08]" : "bg-blue-500/[0.08]"
                      }`}>
                        {hasCritical ? (
                          <AlertTriangle size={14} className="text-red-400" />
                        ) : (
                          <Bell size={14} className="text-blue-400" />
                        )}
                      </div>
                      <div>
                        <p className="text-[13px] text-zinc-200 font-medium">
                          Alert sent to {n.sent_to.length} recipient{n.sent_to.length !== 1 ? "s" : ""}
                        </p>
                        <p className="text-xs text-zinc-600 font-mono mt-0.5">{formatTime(n.created_at)}</p>
                      </div>
                    </div>
                    <span className={`text-[11px] px-2 py-0.5 rounded font-medium ${
                      hasCritical
                        ? "bg-red-500/[0.12] text-red-400 border border-red-500/25"
                        : "bg-zinc-800 text-zinc-400"
                    }`}>
                      {n.event_ids.length} event{n.event_ids.length !== 1 ? "s" : ""}
                    </span>
                  </div>

                  {/* Routing: who was notified */}
                  <div className="flex flex-wrap gap-1.5 mb-3">
                    {n.sent_to.map((p) => (
                      <span
                        key={p.id}
                        className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20"
                      >
                        <Users size={9} />
                        {p.name} · {p.role}
                      </span>
                    ))}
                  </div>

                  {/* Event severity summary */}
                  {n.events.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mb-3">
                      {n.events.map((ev: EventSummary) => {
                        const sev = SEVERITY_COLORS[ev.severity] || SEVERITY_COLORS.Low;
                        return (
                          <span
                            key={ev.id}
                            className={`text-[11px] px-1.5 py-0.5 rounded-full border ${sev.bg} ${sev.text} ${sev.border}`}
                          >
                            {ev.severity}: {ev.title.length > 30 ? ev.title.slice(0, 30) + "…" : ev.title}
                          </span>
                        );
                      })}
                    </div>
                  )}

                  {/* Expand/collapse message */}
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : n.id)}
                    className="flex items-center gap-1 text-[12px] text-zinc-500 hover:text-zinc-300 transition-colors"
                  >
                    {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                    {isExpanded ? "Hide message" : "View message"}
                  </button>
                </div>

                {/* Expanded: full message */}
                {isExpanded && (
                  <div className="px-4 pb-4 pt-0">
                    <div className="bg-[#27272A]/50 rounded-md p-3">
                      <p className="text-[13px] text-zinc-300 whitespace-pre-wrap leading-relaxed font-mono">
                        {n.message}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

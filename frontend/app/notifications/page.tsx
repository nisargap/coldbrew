"use client";

import { useState, useEffect } from "react";
import { Bell, Users, FileText } from "lucide-react";
import { getNotifications } from "@/lib/api";
import type { Notification } from "@/lib/types";

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getNotifications()
      .then(setNotifications)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const formatTime = (iso: string) => {
    const d = new Date(iso);
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
            <div key={i} className="h-24 bg-[#18181B] rounded-lg animate-pulse" />
          ))}
        </div>
      )}

      {/* Empty */}
      {!loading && notifications.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <Bell size={32} className="text-zinc-600 mb-3" />
          <p className="text-sm text-zinc-400">No notifications have been sent.</p>
        </div>
      )}

      {/* List */}
      {!loading && notifications.length > 0 && (
        <div className="space-y-3">
          {notifications.map((n) => (
            <div
              key={n.id}
              className="bg-[#18181B] border border-[#27272A] rounded-lg p-4"
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Users size={14} className="text-zinc-500" />
                  <span className="text-[13px] text-zinc-300">
                    Sent to{" "}
                    {n.sent_to
                      .map((p) => p.name)
                      .join(", ")}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">
                    <FileText size={10} className="inline mr-1" />
                    {n.event_ids.length} event{n.event_ids.length !== 1 ? "s" : ""}
                  </span>
                  <span className="text-xs text-zinc-600 font-mono">
                    {formatTime(n.created_at)}
                  </span>
                </div>
              </div>
              <div className="flex flex-wrap gap-1.5 mb-2">
                {n.sent_to.map((p) => (
                  <span
                    key={p.id}
                    className="text-[11px] px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20"
                  >
                    {p.name} · {p.role}
                  </span>
                ))}
              </div>
              <p className="text-sm text-zinc-400 whitespace-pre-wrap leading-relaxed">
                {n.message}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

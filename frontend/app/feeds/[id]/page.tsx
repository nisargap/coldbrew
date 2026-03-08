"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  AlertTriangle,
  Bell,
  Check,
  X,
  Play,
  ChevronDown,
  FileVideo,
  CheckCircle2,
  Loader2,
  AlertCircle,
  Bot,
  RefreshCw,
  Zap,
  Radio,
  StopCircle,
} from "lucide-react";
import {
  getFeed,
  getEvents,
  updateEventStatus,
  sendNotification,
  reanalyzeFeed,
  stopLivestream,
  subscribeFeedUpdates,
  getPersonas,
} from "@/lib/api";
import type { Event, Feed, Persona, AnalysisMode, ConfidenceLevel } from "@/lib/types";
import { SEVERITY_COLORS, ANALYSIS_MODES, CONFIDENCE_LEVELS } from "@/lib/types";
import HlsPlayer from "@/components/hls-player";

export default function FeedDetailPage() {
  const params = useParams();
  const router = useRouter();
  const feedId = params.id as string;

  const [feed, setFeed] = useState<Feed | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [showNotifyModal, setShowNotifyModal] = useState(false);
  const [showReanalyzeConfirm, setShowReanalyzeConfirm] = useState(false);
  const [reanalyzeMode, setReanalyzeMode] = useState<AnalysisMode>("agent");
  const [reanalyzeConfidence, setReanalyzeConfidence] = useState<ConfidenceLevel>("low");
  const [reanalyzing, setReanalyzing] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [monitoringCycle, setMonitoringCycle] = useState(0);
  const [monitoringStatus, setMonitoringStatus] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);

  const [loadError, setLoadError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setLoadError(null);
      const [feedData, eventsData] = await Promise.all([
        getFeed(feedId),
        getEvents({ feed_id: feedId }),
      ]);
      setFeed(feedData);
      setEvents(eventsData);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to load feed data.";
      setLoadError(msg);
    } finally {
      setLoading(false);
    }
  }, [feedId]);

  useEffect(() => {
    fetchData();

    // SSE for real-time updates
    const unsub = subscribeFeedUpdates((event) => {
      if (event.feed_id === feedId) {
        // Handle livestream cycle events
        if (event.type === "livestream_cycle") {
          setMonitoringCycle(event.cycle ?? 0);
          setMonitoringStatus(event.status ?? null);
          // Refresh data when a new event is detected
          if (event.status === "done") {
            fetchData();
          }
          // Refresh feed data when we get session info (viewer_url)
          if (event.viewer_url || event.session_id) {
            fetchData();
          }
        } else {
          fetchData();
        }
      }
    });

    return () => unsub();
  }, [fetchData, feedId]);

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

  const selectAllCritical = () => {
    const criticalIds = events
      .filter((e) => e.severity === "Critical" || e.severity === "High")
      .map((e) => e.id);
    setSelectedIds(new Set(criticalIds));
  };

  const handleStatusUpdate = async (id: string, status: "acknowledged" | "dismissed") => {
    try {
      await updateEventStatus(id, status);
      showToast(status === "acknowledged" ? "Event acknowledged." : "Event dismissed.");
      fetchData();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to update event status.";
      showToast(`Error: ${msg}`);
    }
  };

  const handleQuickNotify = (event: Event) => {
    setSelectedIds(new Set([event.id]));
    setShowNotifyModal(true);
  };

  const handleReanalyze = async () => {
    setReanalyzing(true);
    setShowReanalyzeConfirm(false);
    try {
      await reanalyzeFeed(feedId, reanalyzeMode, reanalyzeConfidence);
      showToast(`Re-analysis started with ${reanalyzeMode === "agent" ? "Agent" : "Standard"} mode (${reanalyzeConfidence} confidence).`);
      fetchData();
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : "Re-analysis failed");
    } finally {
      setReanalyzing(false);
    }
  };

  const handleStopMonitoring = async () => {
    setStopping(true);
    try {
      await stopLivestream(feedId);
      showToast("Livestream monitoring stopped.");
      fetchData();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to stop monitoring.";
      showToast(`Error: ${msg}`);
    } finally {
      setStopping(false);
    }
  };

  const getYouTubeVideoId = (url: string): string | null => {
    const m = url.match(
      /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/live\/)([a-zA-Z0-9_-]{11})/
    );
    return m ? m[1] : null;
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
    (e) => e.severity === "Critical" || e.severity === "High"
  ).length;

  if (loading) {
    return (
      <div className="p-6">
        <div className="h-8 w-48 bg-[#18181B] rounded animate-pulse mb-6" />
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-[72px] bg-[#18181B] rounded-md animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (!feed) {
    return (
      <div className="p-6">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-1.5 text-sm text-zinc-400 hover:text-zinc-200 mb-4 transition-colors"
        >
          <ArrowLeft size={14} /> Back
        </button>
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <AlertCircle size={28} className="text-red-400 mb-3" />
          <p className="text-sm text-red-400 font-medium mb-1">Feed not found</p>
          {loadError && <p className="text-xs text-zinc-500 max-w-md">{loadError}</p>}
          <button
            onClick={() => { setLoading(true); fetchData(); }}
            className="mt-3 px-3 py-1.5 text-[13px] text-zinc-300 border border-[#27272A] rounded-md hover:bg-[#27272A] transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-1">
        <button
          onClick={() => router.back()}
          className="p-1.5 rounded-md hover:bg-[#27272A] transition-colors text-zinc-400 hover:text-zinc-200"
        >
          <ArrowLeft size={16} />
        </button>
        <FileVideo size={18} className="text-zinc-500" />
        <h2 className="text-xl font-semibold text-zinc-50">{feed.feed_name}</h2>
        <StatusBadge status={feed.status} />
        <ModeBadge mode={feed.analysis_mode} />
      </div>

      <div className="flex items-center gap-4 ml-[52px] mb-6">
        <span className="text-xs text-zinc-500">
          {feed.event_count} event{feed.event_count !== 1 ? "s" : ""} detected
        </span>
        <span className="text-xs text-zinc-600 font-mono">{formatTime(feed.created_at)}</span>
      </div>

      {/* Livestream monitoring panel */}
      {feed.stream_url && (
        <div className="mb-5">
          {feed.status === "monitoring" && (
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                <span className="text-xs font-medium text-red-400 uppercase tracking-wider">Live Monitoring</span>
                {monitoringCycle > 0 && (
                  <span className="text-[11px] text-zinc-500">
                    — {monitoringCycle} event{monitoringCycle !== 1 ? "s" : ""} detected
                    {monitoringStatus === "capturing"
                      ? " · Starting session..."
                      : monitoringStatus === "analyzing"
                      ? " · Analyzing stream..."
                      : monitoringStatus === "done"
                      ? " · New event!"
                      : monitoringStatus === "error"
                      ? " · Error (retrying)"
                      : ""}
                  </span>
                )}
              </div>
              <button
                onClick={handleStopMonitoring}
                disabled={stopping}
                className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-medium text-red-400 border border-red-500/25 bg-red-500/[0.08] rounded-md hover:bg-red-500/[0.15] transition-colors disabled:opacity-50"
              >
                {stopping ? (
                  <Loader2 size={12} className="animate-spin" />
                ) : (
                  <StopCircle size={12} />
                )}
                Stop Monitoring
              </button>
            </div>
          )}

          {/* Stream info card */}
          <div className="rounded-lg border border-[#27272A] bg-[#18181B] overflow-hidden">
            <div className="p-4 space-y-3">
              {/* Stream source */}
              <div className="flex items-center gap-2 text-sm text-zinc-400">
                <Radio size={14} className="text-red-400" />
                <span className="text-zinc-300 font-mono text-[13px] truncate">{feed.stream_url}</span>
              </div>

              {/* NomadicML Viewer link */}
              {feed.viewer_url && (
                <a
                  href={feed.viewer_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 px-3 py-2 rounded-md bg-blue-500/[0.08] border border-blue-500/25 text-blue-400 text-[13px] font-medium hover:bg-blue-500/[0.15] transition-colors w-fit"
                >
                  <Play size={14} />
                  Open in NomadicML Viewer ↗
                </a>
              )}

              {/* Stream player — YouTube embed or HLS player */}
              {(() => {
                const url = feed.stream_url ?? "";
                const videoId = getYouTubeVideoId(url);
                if (videoId) {
                  return (
                    <div className="rounded-lg overflow-hidden border border-[#27272A] bg-black">
                      <div className="aspect-video w-full">
                        <iframe
                          src={`https://www.youtube.com/embed/${videoId}?autoplay=1&mute=1`}
                          className="w-full h-full"
                          allow="autoplay; encrypted-media"
                          allowFullScreen
                          title="Live Stream"
                        />
                      </div>
                    </div>
                  );
                }
                // HLS / M3U8 or direct stream URL
                if (url && (url.includes(".m3u8") || url.startsWith("http"))) {
                  return (
                    <HlsPlayer
                      src={url}
                      autoPlay
                      muted
                      className="border border-[#27272A]"
                    />
                  );
                }
                return null;
              })()}
            </div>

            {/* Live event feed — directly below the player */}
            <div className="border-t border-[#27272A]">
              <div className="flex items-center justify-between px-4 py-2.5 bg-[#111113]">
                <div className="flex items-center gap-2">
                  <Zap size={13} className="text-yellow-400" />
                  <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
                    Live Events
                  </span>
                  {events.length > 0 && (
                    <span className="text-[11px] font-medium text-zinc-500">
                      ({events.length})
                    </span>
                  )}
                </div>
                {feed.status === "monitoring" && (
                  <div className="flex items-center gap-1.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                    <span className="text-[11px] text-green-400/80">
                      {monitoringStatus === "capturing"
                        ? "Starting session..."
                        : monitoringStatus === "analyzing"
                        ? "Analyzing stream..."
                        : monitoringStatus === "waiting"
                        ? "Waiting for next cycle..."
                        : monitoringStatus === "done"
                        ? "New event detected"
                        : "Listening..."}
                    </span>
                  </div>
                )}
              </div>

              {/* Events appear here in real-time */}
              {events.length === 0 && feed.status === "monitoring" && (
                <div className="flex items-center justify-center py-8 px-4">
                  <Loader2 size={16} className="text-zinc-600 animate-spin mr-2" />
                  <span className="text-sm text-zinc-500">
                    Waiting for events... The SDK is analyzing the stream in real-time.
                  </span>
                </div>
              )}

              {events.length === 0 && feed.status === "completed" && (
                <div className="flex items-center justify-center py-8 px-4">
                  <span className="text-sm text-zinc-500">No events were detected in this stream.</span>
                </div>
              )}

              {events.length > 0 && (
                <div className="max-h-[480px] overflow-y-auto divide-y divide-[#27272A]">
                  {events.map((event, index) => {
                    const sev = SEVERITY_COLORS[event.severity] || SEVERITY_COLORS.Low;
                    const isCritical = event.severity === "Critical" || event.severity === "High";
                    const isSelected = selectedIds.has(event.id);
                    const isExpanded = expandedId === event.id;
                    const isNew = index === 0 && feed.status === "monitoring";

                    return (
                      <div
                        key={event.id}
                        className={`transition-all duration-300 ${isNew ? "bg-yellow-500/[0.03]" : ""}`}
                      >
                        <div
                          className={`flex items-center gap-3 px-4 py-3 hover:bg-[#1a1a1d] transition-colors cursor-pointer ${
                            isSelected ? "border-l-2 border-l-blue-500" : "border-l-2 border-l-transparent"
                          }`}
                          onClick={() => setExpandedId(isExpanded ? null : event.id)}
                        >
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={(e) => { e.stopPropagation(); toggleSelect(event.id); }}
                            onClick={(e) => e.stopPropagation()}
                            className="w-3.5 h-3.5 rounded border-zinc-600 bg-transparent accent-blue-500 cursor-pointer flex-shrink-0"
                          />

                          <div className={`w-8 h-8 rounded-md flex items-center justify-center flex-shrink-0 ${isCritical ? "bg-red-500/10" : "bg-[#27272A]"}`}>
                            <AlertTriangle size={13} className={isCritical ? "text-red-400" : "text-zinc-600"} />
                          </div>

                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <p className="text-[13px] font-medium text-zinc-100 truncate">{event.title}</p>
                              {event.status !== "new" && (
                                <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
                                  event.status === "acknowledged" ? "bg-green-500/10 text-green-400" : "bg-zinc-700 text-zinc-500"
                                }`}>
                                  {event.status}
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-2 mt-0.5">
                              <span className="text-[11px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">{event.category}</span>
                              <span className={`text-[11px] px-1.5 py-0.5 rounded-full border ${sev.bg} ${sev.text} ${sev.border}`}>{event.severity}</span>
                              <span className="text-[11px] text-zinc-600 font-mono">{formatTime(event.timestamp)}</span>
                            </div>
                          </div>

                          {isCritical && event.status === "new" && (
                            <button
                              onClick={(e) => { e.stopPropagation(); handleQuickNotify(event); }}
                              className="flex items-center gap-1 px-2 py-1 text-[11px] font-medium text-red-400 border border-red-500/25 bg-red-500/[0.08] rounded-md hover:bg-red-500/[0.15] transition-colors flex-shrink-0"
                              title="Quick alert"
                            >
                              <Bell size={10} /> Alert
                            </button>
                          )}

                          <ChevronDown
                            size={13}
                            className={`text-zinc-600 transition-transform flex-shrink-0 ${isExpanded ? "rotate-180" : ""}`}
                          />
                        </div>

                        {isExpanded && (
                          <div className="px-14 py-3 bg-[#111113]">
                            <p className="text-[13px] text-zinc-300 leading-relaxed mb-2">{event.description}</p>
                            <div className="flex items-center gap-4 text-[11px] text-zinc-600 mb-3">
                              <span>Confidence: {(event.confidence * 100).toFixed(0)}%</span>
                              <span>Feed: {event.source_feed}</span>
                              <span>ID: {event.id.slice(0, 8)}</span>
                            </div>
                            {event.status === "new" && (
                              <div className="flex items-center gap-2">
                                <button
                                  onClick={(e) => { e.stopPropagation(); handleStatusUpdate(event.id, "acknowledged"); }}
                                  className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] text-zinc-300 border border-[#27272A] rounded-md hover:bg-[#27272A] transition-colors"
                                >
                                  <Check size={12} /> Acknowledge
                                </button>
                                <button
                                  onClick={(e) => { e.stopPropagation(); handleStatusUpdate(event.id, "dismissed"); }}
                                  className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] text-zinc-300 border border-[#27272A] rounded-md hover:bg-[#27272A] transition-colors"
                                >
                                  <X size={12} /> Dismiss
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
            </div>
          </div>
        </div>
      )}

      {/* Video player (for uploaded files, not livestreams) */}
      {feed.video_url && !feed.stream_url && (
        <VideoPlayer videoUrl={feed.video_url} feedName={feed.feed_name} />
      )}

      {/* Action bar */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        {/* Re-analyze button */}
        {feed.status !== "processing" && feed.status !== "monitoring" && (
          <button
            onClick={() => setShowReanalyzeConfirm(true)}
            disabled={reanalyzing}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-medium text-purple-400 border border-purple-500/25 bg-purple-500/[0.08] rounded-md hover:bg-purple-500/[0.15] transition-colors disabled:opacity-50"
          >
            {reanalyzing ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <Bot size={12} />
            )}
            {feed.analysis_mode === "agent" ? "Re-analyze (Standard)" : "Analyze with Agent"}
          </button>
        )}

        {criticalCount > 0 && (
          <button
            onClick={selectAllCritical}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-medium text-red-400 border border-red-500/25 bg-red-500/[0.08] rounded-md hover:bg-red-500/[0.15] transition-colors"
          >
            <AlertTriangle size={12} />
            Select {criticalCount} Critical/High
          </button>
        )}
        {selectedIds.size > 0 && (
          <button
            onClick={() => setShowNotifyModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-medium text-white bg-blue-500 rounded-md hover:bg-blue-600 transition-colors"
          >
            <Bell size={12} />
            Notify ({selectedIds.size})
          </button>
        )}
      </div>

      {/* Processing state */}
      {feed.status === "processing" && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <Loader2 size={28} className="text-yellow-400 animate-spin mb-3" />
          <p className="text-sm text-zinc-400">
            {feed.analysis_mode === "agent"
              ? "Analyzing with NomadicML Agent (Robotic Action Segmentation)..."
              : "Analyzing video..."}
          </p>
        </div>
      )}

      {/* No events (non-stream feeds) */}
      {!feed.stream_url && events.length === 0 && feed.status === "completed" && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <AlertTriangle size={28} className="text-zinc-600 mb-3" />
          <p className="text-sm text-zinc-400">No events detected in this video.</p>
          <button
            onClick={() => {
              setReanalyzeMode(feed.analysis_mode === "agent" ? "standard" : "agent");
              setShowReanalyzeConfirm(true);
            }}
            className="mt-4 text-[13px] text-purple-400 hover:text-purple-300 underline underline-offset-2"
          >
            Try analyzing with {feed.analysis_mode === "agent" ? "Standard" : "Agent"} mode
          </button>
        </div>
      )}

      {/* Events list (for uploaded video feeds only — livestream events shown inline above) */}
      {events.length > 0 && !feed.stream_url && (
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

                  <div className="w-12 h-12 bg-[#27272A] rounded-md flex items-center justify-center flex-shrink-0">
                    <AlertTriangle size={16} className={isCritical ? "text-red-400" : "text-zinc-600"} />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-[15px] font-medium text-zinc-100 truncate">{event.title}</p>
                      {event.status !== "new" && (
                        <span
                          className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
                            event.status === "acknowledged"
                              ? "bg-green-500/10 text-green-400"
                              : "bg-zinc-700 text-zinc-500"
                          }`}
                        >
                          {event.status}
                        </span>
                      )}
                    </div>
                    <p className="text-[13px] text-zinc-400 truncate mt-0.5">{event.description}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-[11px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">
                        {event.category}
                      </span>
                      <span
                        className={`text-[11px] px-1.5 py-0.5 rounded-full border ${sev.bg} ${sev.text} ${sev.border}`}
                      >
                        {event.severity}
                      </span>
                      <span className="text-xs text-zinc-600 font-mono">
                        {formatTime(event.timestamp)}
                      </span>
                    </div>
                  </div>

                  {/* Quick notify for critical */}
                  {isCritical && event.status === "new" && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleQuickNotify(event);
                      }}
                      className="flex items-center gap-1 px-2 py-1 text-[11px] font-medium text-red-400 border border-red-500/25 bg-red-500/[0.08] rounded-md hover:bg-red-500/[0.15] transition-colors flex-shrink-0"
                      title="Quick alert"
                    >
                      <Bell size={11} />
                      Alert
                    </button>
                  )}

                  <ChevronDown
                    size={14}
                    className={`text-zinc-600 transition-transform flex-shrink-0 ${
                      isExpanded ? "rotate-180" : ""
                    }`}
                  />
                </div>

                {isExpanded && (
                  <div className="px-6 py-4 bg-[#18181B] border-b border-[#27272A]">
                    <p className="text-sm text-zinc-300 mb-3">{event.description}</p>
                    <div className="flex items-center gap-4 text-xs text-zinc-500 mb-4">
                      <span>Confidence: {(event.confidence * 100).toFixed(0)}%</span>
                      <span>Feed: {event.source_feed}</span>
                      <span>ID: {event.id.slice(0, 8)}</span>
                    </div>
                    {event.status === "new" && (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleStatusUpdate(event.id, "acknowledged");
                          }}
                          className="flex items-center gap-1.5 px-3 py-1.5 text-[13px] text-zinc-300 border border-[#27272A] rounded-md hover:bg-[#27272A] transition-colors"
                        >
                          <Check size={13} /> Acknowledge
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleStatusUpdate(event.id, "dismissed");
                          }}
                          className="flex items-center gap-1.5 px-3 py-1.5 text-[13px] text-zinc-300 border border-[#27272A] rounded-md hover:bg-[#27272A] transition-colors"
                        >
                          <X size={13} /> Dismiss
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

      {/* Re-analyze confirmation modal */}
      {showReanalyzeConfirm && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
          onClick={() => setShowReanalyzeConfirm(false)}
        >
          <div
            className="bg-[#18181B] border border-[#27272A] rounded-lg w-full max-w-md mx-4 p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 mb-3">
              <RefreshCw size={16} className="text-purple-400" />
              <h3 className="text-[15px] font-semibold text-zinc-100">Re-analyze Feed</h3>
            </div>

            <p className="text-sm text-zinc-400 mb-4">
              This will re-analyze <strong className="text-zinc-200">{feed.feed_name}</strong> with
              a different analysis mode. Existing events will be replaced.
            </p>

            <div className="space-y-2 mb-4">
              <label className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Analysis Mode</label>
              <div className="mt-1 space-y-2">
                {ANALYSIS_MODES.map((mode) => (
                  <button
                    key={mode.value}
                    onClick={() => setReanalyzeMode(mode.value)}
                    className={`w-full flex items-start gap-3 p-3 rounded-lg border text-left transition-all ${
                      reanalyzeMode === mode.value
                        ? mode.value === "agent"
                          ? "border-purple-500/50 bg-purple-500/5 ring-1 ring-purple-500/20"
                          : "border-blue-500/50 bg-blue-500/5 ring-1 ring-blue-500/20"
                        : "border-[#27272A] hover:border-zinc-600"
                    }`}
                  >
                    <div className="mt-0.5">
                      {mode.value === "agent" ? (
                        <Bot
                          size={16}
                          className={reanalyzeMode === mode.value ? "text-purple-400" : "text-zinc-500"}
                        />
                      ) : (
                        <Zap
                          size={16}
                          className={reanalyzeMode === mode.value ? "text-blue-400" : "text-zinc-500"}
                        />
                      )}
                    </div>
                    <div>
                      <p
                        className={`text-[13px] font-medium ${
                          reanalyzeMode === mode.value ? "text-zinc-100" : "text-zinc-400"
                        }`}
                      >
                        {mode.label}
                      </p>
                      <p className="text-[11px] text-zinc-600 mt-0.5">{mode.description}</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2 mb-4">
              <label className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Confidence Level</label>
              <div className="mt-1 grid grid-cols-2 gap-2">
                {CONFIDENCE_LEVELS.map((level) => (
                  <button
                    key={level.value}
                    onClick={() => setReanalyzeConfidence(level.value)}
                    className={`flex items-center gap-2 p-2.5 rounded-lg border text-left transition-all ${
                      reanalyzeConfidence === level.value
                        ? level.value === "high"
                          ? "border-emerald-500/50 bg-emerald-500/5 ring-1 ring-emerald-500/20"
                          : "border-amber-500/50 bg-amber-500/5 ring-1 ring-amber-500/20"
                        : "border-[#27272A] hover:border-zinc-600"
                    }`}
                  >
                    <div>
                      <p className={`text-[12px] font-medium ${
                        reanalyzeConfidence === level.value ? "text-zinc-100" : "text-zinc-400"
                      }`}>{level.label}</p>
                      <p className="text-[10px] text-zinc-600 mt-0.5">{level.description}</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowReanalyzeConfirm(false)}
                className="px-4 py-2 text-[13px] text-zinc-400 border border-[#27272A] rounded-md hover:bg-[#27272A] transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleReanalyze}
                className="px-4 py-2 bg-purple-600 text-white text-[13px] font-medium rounded-md hover:bg-purple-700 transition-colors flex items-center gap-1.5"
              >
                <Bot size={13} />
                Re-analyze
              </button>
            </div>
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
            fetchData();
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

const VIDEO_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function VideoPlayer({ videoUrl, feedName }: { videoUrl: string; feedName: string }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const fullUrl = `${VIDEO_BASE}${videoUrl}`;

  return (
    <div className="mb-5">
      <button
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="flex items-center gap-2 text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2 hover:text-zinc-300 transition-colors"
      >
        <Play size={12} className={isCollapsed ? "" : "text-blue-400"} />
        {isCollapsed ? "Show Video" : "Video Feed"}
      </button>
      {!isCollapsed && (
        <div className="rounded-lg overflow-hidden border border-[#27272A] bg-black">
          <video
            ref={videoRef}
            src={fullUrl}
            controls
            className="w-full max-h-[400px] object-contain bg-black"
            preload="metadata"
          >
            Your browser does not support video playback.
          </video>
        </div>
      )}
    </div>
  );
}

function ModeBadge({ mode }: { mode: string }) {
  if (mode === "agent") {
    return (
      <span className="flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">
        <Bot size={10} />
        Agent
      </span>
    );
  }
  return (
    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-500 border border-zinc-700">
      Standard
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  if (status === "completed") {
    return (
      <span className="flex items-center gap-1 text-[11px] font-medium text-green-400">
        <CheckCircle2 size={12} /> Completed
      </span>
    );
  }
  if (status === "error") {
    return (
      <span className="flex items-center gap-1 text-[11px] font-medium text-red-400">
        <AlertCircle size={12} /> Error
      </span>
    );
  }
  if (status === "monitoring") {
    return (
      <span className="flex items-center gap-1 text-[11px] font-medium text-red-400 animate-pulse">
        <Radio size={12} /> Live
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1 text-[11px] font-medium text-yellow-400 animate-pulse">
      <Loader2 size={12} className="animate-spin" /> Analyzing
    </span>
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
        const autoSelect = new Set<string>();
        const categoryMap: Record<string, string> = {};
        for (const p of data) {
          if (p.category) categoryMap[p.category] = p.id;
        }
        for (const e of selectedEvents) {
          if (e.severity === "Critical" || e.severity === "High") {
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
    const lines = selectedEvents.map((e) => `• [${e.severity}] ${e.title} (${e.category})`);
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
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to send notification. Check backend logs.");
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

        <div className="mt-4">
          <label className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Recipients</label>
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

        <div className="mt-4">
          <label className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Message</label>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={6}
            className="mt-2 w-full bg-[#27272A] border border-[#27272A] rounded-md px-3 py-2.5 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-blue-500 resize-none"
          />
        </div>

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

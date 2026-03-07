"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  Upload as UploadIcon,
  FileVideo,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ChevronRight,
  Bot,
  Zap,
} from "lucide-react";
import { uploadFeed, getFeeds, subscribeFeedUpdates } from "@/lib/api";
import type { Feed, AnalysisMode } from "@/lib/types";
import { ANALYSIS_MODES } from "@/lib/types";

export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [feedName, setFeedName] = useState("");
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode>("standard");
  const [uploading, setUploading] = useState(false);
  const [feeds, setFeeds] = useState<Feed[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchFeeds = useCallback(async () => {
    try {
      const data = await getFeeds();
      setFeeds(data);
    } catch {
      // Silently fail
    }
  }, []);

  // Initial load + SSE subscription for real-time updates
  useEffect(() => {
    fetchFeeds();

    const unsub = subscribeFeedUpdates(() => {
      fetchFeeds();
    });

    return () => unsub();
  }, [fetchFeeds]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped && (dropped.type === "video/mp4" || dropped.type === "video/quicktime")) {
      setFile(dropped);
      setError(null);
    } else {
      setError("Please upload an MP4 or MOV file.");
    }
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) {
      setFile(selected);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file || !feedName.trim()) return;
    setUploading(true);
    setError(null);
    try {
      await uploadFeed(file, feedName.trim(), analysisMode);
      setFile(null);
      setFeedName("");
      if (fileInputRef.current) fileInputRef.current.value = "";
      fetchFeeds();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const formatTime = (iso: string) => {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    return `${hrs}h ago`;
  };

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h2 className="text-xl font-semibold text-zinc-50 mb-6">Upload</h2>

      {/* Drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-colors duration-100 ${
          dragOver
            ? "border-blue-500 bg-blue-500/5"
            : "border-zinc-700 hover:border-zinc-600"
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="video/mp4,video/quicktime"
          onChange={handleFileSelect}
          className="hidden"
        />
        {file ? (
          <div className="flex flex-col items-center gap-2">
            <FileVideo size={32} className="text-blue-400" />
            <p className="text-sm text-zinc-200 font-medium">{file.name}</p>
            <p className="text-xs text-zinc-500">
              {(file.size / (1024 * 1024)).toFixed(1)} MB
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <UploadIcon size={32} className="text-zinc-500" />
            <p className="text-sm text-zinc-300">
              Drop a video file here, or click to browse
            </p>
            <p className="text-xs text-zinc-600">MP4 or MOV, up to 500 MB</p>
          </div>
        )}
      </div>

      {/* Analysis mode selector */}
      <div className="mt-4">
        <label className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2 block">
          Analysis Mode
        </label>
        <div className="grid grid-cols-2 gap-2">
          {ANALYSIS_MODES.map((mode) => (
            <button
              key={mode.value}
              onClick={() => setAnalysisMode(mode.value)}
              className={`flex items-start gap-3 p-3 rounded-lg border text-left transition-all ${
                analysisMode === mode.value
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
                    className={analysisMode === mode.value ? "text-purple-400" : "text-zinc-500"}
                  />
                ) : (
                  <Zap
                    size={16}
                    className={analysisMode === mode.value ? "text-blue-400" : "text-zinc-500"}
                  />
                )}
              </div>
              <div>
                <p
                  className={`text-[13px] font-medium ${
                    analysisMode === mode.value ? "text-zinc-100" : "text-zinc-400"
                  }`}
                >
                  {mode.label}
                </p>
                <p className="text-[11px] text-zinc-600 mt-0.5">
                  {mode.description}
                </p>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Feed name + upload button */}
      <div className="mt-4 flex gap-3">
        <input
          type="text"
          placeholder="Feed name (e.g., Dock Cam 2)"
          value={feedName}
          onChange={(e) => setFeedName(e.target.value)}
          className="flex-1 bg-[#27272A] border border-[#27272A] rounded-md px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-blue-500 transition-colors"
        />
        <button
          onClick={handleUpload}
          disabled={!file || !feedName.trim() || uploading}
          className={`px-4 py-2 text-white text-[13px] font-medium rounded-md disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2 ${
            analysisMode === "agent"
              ? "bg-purple-600 hover:bg-purple-700"
              : "bg-blue-500 hover:bg-blue-600"
          }`}
        >
          {uploading ? (
            <>
              <Loader2 size={14} className="animate-spin" />
              Uploading...
            </>
          ) : analysisMode === "agent" ? (
            <>
              <Bot size={14} />
              Analyze with Agent
            </>
          ) : (
            "Upload & Analyze"
          )}
        </button>
      </div>

      {error && (
        <p className="mt-3 text-sm text-red-400 flex items-center gap-1.5">
          <AlertCircle size={14} />
          {error}
        </p>
      )}

      {/* Recent uploads */}
      {feeds.length > 0 && (
        <div className="mt-8">
          <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">
            Recent Uploads
          </h3>
          <div className="space-y-1">
            {feeds.map((feed) => {
              const isClickable = feed.status === "completed";
              return (
                <div
                  key={feed.feed_id}
                  onClick={isClickable ? () => router.push(`/feeds/${feed.feed_id}`) : undefined}
                  className={`flex items-center justify-between py-2.5 px-3 rounded-md hover:bg-[#27272A]/50 transition-colors ${
                    isClickable ? "cursor-pointer" : ""
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <FileVideo size={16} className="text-zinc-500" />
                    <span className="text-[13px] text-zinc-200">{feed.feed_name}</span>
                    <ModeBadge mode={feed.analysis_mode} />
                  </div>
                  <div className="flex items-center gap-4">
                    {feed.status === "completed" && (
                      <span className="text-xs text-blue-400 hover:underline">
                        {feed.event_count} event{feed.event_count !== 1 ? "s" : ""}
                      </span>
                    )}
                    <StatusBadge status={feed.status} errorMessage={feed.error_message} />
                    <span className="text-xs text-zinc-600 font-mono">
                      {formatTime(feed.created_at)}
                    </span>
                    {isClickable && (
                      <ChevronRight size={14} className="text-zinc-600" />
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {feeds.length === 0 && !uploading && (
        <p className="mt-10 text-center text-sm text-zinc-600">
          Upload your first warehouse video to begin monitoring.
        </p>
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

function StatusBadge({ status, errorMessage }: { status: string; errorMessage?: string | null }) {
  if (status === "completed") {
    return (
      <span className="flex items-center gap-1 text-[11px] font-medium text-green-400">
        <CheckCircle2 size={12} />
        Completed
      </span>
    );
  }
  if (status === "error") {
    return (
      <span
        className="flex items-center gap-1 text-[11px] font-medium text-red-400"
        title={errorMessage || "Analysis failed"}
      >
        <AlertCircle size={12} />
        Error{errorMessage ? `: ${errorMessage.slice(0, 60)}` : ""}
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1 text-[11px] font-medium text-yellow-400 animate-pulse">
      <Loader2 size={12} className="animate-spin" />
      Analyzing...
    </span>
  );
}

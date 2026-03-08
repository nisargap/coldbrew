"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Activity,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Loader2,
  Zap,
  Bot,
  Send,
  Shield,
  Clock,
  Wifi,
  WifiOff,
  KeyRound,
  Power,
  Volume2,
} from "lucide-react";
import { getDependencyStatus } from "@/lib/api";

interface DependencyCheck {
  name: string;
  status: "connected" | "misconfigured" | "auth_error" | "unreachable" | "disabled" | "error";
  message: string;
  latency_ms: number | null;
  hint?: string;
}

interface StatusResponse {
  overall: "healthy" | "degraded" | "unhealthy";
  checked_at: string;
  dependencies: DependencyCheck[];
}

const STATUS_CONFIG: Record<
  string,
  { icon: typeof Activity; color: string; bg: string; border: string; label: string }
> = {
  connected: {
    icon: CheckCircle2,
    color: "text-green-400",
    bg: "bg-green-500/[0.08]",
    border: "border-green-500/20",
    label: "Connected",
  },
  misconfigured: {
    icon: KeyRound,
    color: "text-amber-400",
    bg: "bg-amber-500/[0.08]",
    border: "border-amber-500/20",
    label: "Not Configured",
  },
  auth_error: {
    icon: Shield,
    color: "text-red-400",
    bg: "bg-red-500/[0.08]",
    border: "border-red-500/20",
    label: "Auth Error",
  },
  unreachable: {
    icon: WifiOff,
    color: "text-red-400",
    bg: "bg-red-500/[0.08]",
    border: "border-red-500/20",
    label: "Unreachable",
  },
  disabled: {
    icon: Power,
    color: "text-zinc-500",
    bg: "bg-zinc-800/50",
    border: "border-zinc-700",
    label: "Disabled",
  },
  error: {
    icon: XCircle,
    color: "text-red-400",
    bg: "bg-red-500/[0.08]",
    border: "border-red-500/20",
    label: "Error",
  },
};

const SERVICE_ICONS: Record<string, typeof Activity> = {
  NomadicML: Zap,
  "Claude (Anthropic)": Bot,
  ElevenLabs: Volume2,
  "Telegram Bot": Send,
};

const OVERALL_CONFIG: Record<string, { color: string; bg: string; border: string; label: string; icon: typeof Activity }> = {
  healthy: {
    color: "text-green-400",
    bg: "bg-green-500/[0.06]",
    border: "border-green-500/20",
    label: "All Systems Operational",
    icon: CheckCircle2,
  },
  degraded: {
    color: "text-amber-400",
    bg: "bg-amber-500/[0.06]",
    border: "border-amber-500/20",
    label: "Degraded Performance",
    icon: AlertTriangle,
  },
  unhealthy: {
    color: "text-red-400",
    bg: "bg-red-500/[0.06]",
    border: "border-red-500/20",
    label: "Systems Down",
    icon: XCircle,
  },
};

export default function StatusPage() {
  const [data, setData] = useState<StatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<string | null>(null);

  const fetchStatus = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const result = await getDependencyStatus();
      setData(result);
      setLastChecked(new Date().toLocaleTimeString());
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to check dependency status. Is the backend running?"
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();

    // Auto-refresh every 30 seconds
    const interval = setInterval(() => fetchStatus(true), 30_000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const overall = data ? OVERALL_CONFIG[data.overall] || OVERALL_CONFIG.unhealthy : null;

  return (
    <div className="p-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold text-zinc-50">System Status</h2>
          <p className="text-[13px] text-zinc-500 mt-0.5">
            External dependency health checks
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastChecked && (
            <span className="text-[11px] text-zinc-600 font-mono flex items-center gap-1">
              <Clock size={10} />
              {lastChecked}
            </span>
          )}
          <button
            onClick={() => fetchStatus(true)}
            disabled={refreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-medium text-zinc-300 border border-[#27272A] rounded-md hover:bg-[#27272A] transition-colors disabled:opacity-50"
          >
            <RefreshCw
              size={12}
              className={refreshing ? "animate-spin" : ""}
            />
            {refreshing ? "Checking..." : "Refresh"}
          </button>
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex flex-col items-center justify-center py-20">
          <Loader2 size={24} className="text-zinc-500 animate-spin mb-3" />
          <p className="text-sm text-zinc-500">Checking dependencies...</p>
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <XCircle size={28} className="text-red-400 mb-3" />
          <p className="text-sm text-red-400 font-medium mb-1">
            Status check failed
          </p>
          <p className="text-xs text-zinc-500 max-w-md">{error}</p>
          <button
            onClick={() => fetchStatus()}
            className="mt-3 px-3 py-1.5 text-[13px] text-zinc-300 border border-[#27272A] rounded-md hover:bg-[#27272A] transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {/* Status data */}
      {!loading && data && (
        <>
          {/* Overall banner */}
          {overall && (
            <div
              className={`flex items-center gap-3 px-4 py-3.5 rounded-lg border mb-6 ${overall.bg} ${overall.border}`}
            >
              <overall.icon size={18} className={overall.color} />
              <div>
                <p className={`text-[14px] font-semibold ${overall.color}`}>
                  {overall.label}
                </p>
                <p className="text-[11px] text-zinc-500 mt-0.5">
                  {data.dependencies.filter((d) => d.status === "connected").length} of{" "}
                  {data.dependencies.filter((d) => d.status !== "disabled").length} active
                  services connected
                </p>
              </div>
            </div>
          )}

          {/* Dependency cards */}
          <div className="space-y-3">
            {data.dependencies.map((dep) => {
              const cfg =
                STATUS_CONFIG[dep.status] || STATUS_CONFIG.error;
              const ServiceIcon = SERVICE_ICONS[dep.name] || Activity;
              const StatusIcon = cfg.icon;

              return (
                <div
                  key={dep.name}
                  className={`border rounded-lg overflow-hidden transition-colors ${cfg.border}`}
                >
                  <div className="flex items-start gap-4 p-4">
                    {/* Service icon */}
                    <div
                      className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${cfg.bg}`}
                    >
                      <ServiceIcon size={18} className={cfg.color} />
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2.5 mb-1">
                        <h3 className="text-[14px] font-semibold text-zinc-100">
                          {dep.name}
                        </h3>
                        <span
                          className={`inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full border ${cfg.bg} ${cfg.color} ${cfg.border}`}
                        >
                          <StatusIcon size={10} />
                          {cfg.label}
                        </span>
                      </div>
                      <p className="text-[13px] text-zinc-400 leading-relaxed">
                        {dep.message}
                      </p>
                      {dep.hint && (
                        <p className="text-[11px] text-zinc-500 mt-1 italic">
                          💡 {dep.hint}
                        </p>
                      )}
                    </div>

                    {/* Latency */}
                    <div className="flex-shrink-0 text-right">
                      {dep.latency_ms !== null ? (
                        <div className="flex items-center gap-1.5">
                          <Wifi
                            size={11}
                            className={
                              dep.latency_ms < 500
                                ? "text-green-500"
                                : dep.latency_ms < 2000
                                ? "text-amber-500"
                                : "text-red-500"
                            }
                          />
                          <span
                            className={`text-[12px] font-mono ${
                              dep.latency_ms < 500
                                ? "text-green-400/80"
                                : dep.latency_ms < 2000
                                ? "text-amber-400/80"
                                : "text-red-400/80"
                            }`}
                          >
                            {dep.latency_ms}ms
                          </span>
                        </div>
                      ) : (
                        <span className="text-[11px] text-zinc-600 font-mono">
                          —
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Env var hint for misconfigured services */}
                  {dep.status === "misconfigured" && (
                    <div className="px-4 py-2.5 bg-amber-500/[0.03] border-t border-amber-500/10">
                      <p className="text-[11px] text-amber-400/80 font-mono">
                        {dep.name === "NomadicML" && "→ Set NOMADIC_SDK_API_KEY in backend/.env"}
                        {dep.name === "Claude (Anthropic)" && "→ Set ANTHROPIC_API_KEY in backend/.env"}
                        {dep.name === "Telegram Bot" && "→ Set TELEGRAM_BOT_TOKEN in backend/.env"}
                      </p>
                    </div>
                  )}

                  {dep.status === "auth_error" && (
                    <div className="px-4 py-2.5 bg-red-500/[0.03] border-t border-red-500/10">
                      <p className="text-[11px] text-red-400/80 font-mono">
                        → Check that your API key is valid and not expired.
                      </p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Footer */}
          <div className="mt-6 pt-4 border-t border-[#27272A]">
            <p className="text-[11px] text-zinc-600">
              Auto-refreshes every 30 seconds · Last checked:{" "}
              {new Date(data.checked_at).toLocaleString()}
            </p>
          </div>
        </>
      )}
    </div>
  );
}

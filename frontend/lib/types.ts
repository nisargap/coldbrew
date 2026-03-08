export type AnalysisMode = "standard" | "agent";
export type ConfidenceLevel = "low" | "high";

export interface Feed {
  feed_id: string;
  feed_name: string;
  status: "processing" | "completed" | "error" | "monitoring";
  error_message?: string | null;
  analysis_mode: AnalysisMode;
  confidence_level: ConfidenceLevel;
  agentic_status?: string | null; // null | "processing" | "completed" | "error" | "skipped"
  video_url?: string | null;
  stream_url?: string | null;
  stream_query?: string | null;
  nomadic_stream_id?: string | null;
  session_id?: string | null;
  viewer_url?: string | null;
  created_at: string;
  event_count: number;
}

export const ANALYSIS_MODES: { value: AnalysisMode; label: string; description: string }[] = [
  { value: "standard", label: "Standard", description: "Custom event detection (ASK)" },
  { value: "agent", label: "Agent — Robotic Action Segmentation", description: "NomadicML Agent with ROBOTICS category" },
];

export const CONFIDENCE_LEVELS: { value: ConfidenceLevel; label: string; description: string }[] = [
  { value: "high", label: "High Confidence", description: "Only confident detections" },
  { value: "low", label: "Low Confidence", description: "Include uncertain detections" },
];

export interface Event {
  id: string;
  feed_id: string;
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

export interface EventSummary {
  id: string;
  title: string;
  category: string;
  severity: string;
}

export interface Persona {
  id: string;
  name: string;
  role: string;
  category?: string | null;
}

export interface Notification {
  id: string;
  message: string;
  sent_to: Persona[];
  event_ids: string[];
  events: EventSummary[];
  created_at: string;
}

export const SEVERITY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  Critical: { bg: "bg-red-500/[0.12]", text: "text-red-400", border: "border-red-500/25" },
  High: { bg: "bg-orange-500/[0.12]", text: "text-orange-400", border: "border-orange-500/25" },
  Medium: { bg: "bg-yellow-500/[0.12]", text: "text-yellow-400", border: "border-yellow-500/25" },
  Low: { bg: "bg-blue-500/[0.12]", text: "text-blue-400", border: "border-blue-500/25" },
};

export const CATEGORY_ICONS: Record<string, string> = {
  Safety: "🦺",
  Equipment: "⚙️",
  Shipment: "🚛",
  Operational: "📦",
  Environmental: "🌡️",
};

export interface SuggestedPersona {
  role: string;
  reason: string;
}

export interface EventEnrichment {
  id: string;
  event_id: string;
  feed_id: string;
  root_cause: string;
  recommended_actions: string[];
  urgency_reasoning: string;
  suggested_personas: SuggestedPersona[];
  risk_score: number;
  correlation_notes: string | null;
  voice_alert_script: string | null;
  voice_alert_url: string | null;
  voice_alert_status: string | null;
  model_used: string;
  created_at: string;
}

export const RISK_COLORS: Record<number, string> = {
  10: "text-red-500",
  9: "text-red-400",
  8: "text-orange-400",
  7: "text-orange-300",
  6: "text-yellow-400",
  5: "text-yellow-300",
  4: "text-blue-400",
  3: "text-blue-300",
  2: "text-zinc-400",
  1: "text-zinc-500",
};

export function getRiskColor(score: number): string {
  if (score >= 9) return "text-red-400";
  if (score >= 7) return "text-orange-400";
  if (score >= 5) return "text-yellow-400";
  if (score >= 3) return "text-blue-400";
  return "text-zinc-400";
}

export function getRiskBg(score: number): string {
  if (score >= 9) return "bg-red-500/10 border-red-500/25";
  if (score >= 7) return "bg-orange-500/10 border-orange-500/25";
  if (score >= 5) return "bg-yellow-500/10 border-yellow-500/25";
  if (score >= 3) return "bg-blue-500/10 border-blue-500/25";
  return "bg-zinc-500/10 border-zinc-500/25";
}

export type AnalysisMode = "standard" | "agent";
export type ConfidenceLevel = "low" | "high";

export interface Feed {
  feed_id: string;
  feed_name: string;
  status: "processing" | "completed" | "error" | "monitoring";
  error_message?: string | null;
  analysis_mode: AnalysisMode;
  confidence_level: ConfidenceLevel;
  video_url?: string | null;
  stream_url?: string | null;
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

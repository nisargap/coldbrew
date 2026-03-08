"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useConversation } from "@11labs/react";
import {
  Mic,
  MicOff,
  Phone,
  PhoneOff,
  Volume2,
  VolumeX,
  Loader2,
  MessageCircle,
  X,
  Minimize2,
  Maximize2,
  Hand,
} from "lucide-react";
import { startConversation, endConversation } from "@/lib/api";

type MicMode = "open" | "ptt";

interface ConversationPanelProps {
  feedId: string;
  feedName: string;
  onClose: () => void;
  autoStart?: boolean;
}

export default function ConversationPanel({
  feedId,
  feedName,
  onClose,
  autoStart = false,
}: ConversationPanelProps) {
  const [agentId, setAgentId] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [minimized, setMinimized] = useState(false);
  const [micMode, setMicMode] = useState<MicMode>("open");
  const [micMuted, setMicMuted] = useState(false); // open-mic: unmuted by default
  const [agentMuted, setAgentMuted] = useState(false);
  const transcriptRef = useRef<HTMLDivElement>(null);
  const cleanupRef = useRef(false);
  const prevVolumeRef = useRef(1);

  const conversation = useConversation({
    onConnect: () => {
      setConnecting(false);
      setError(null);
    },
    onDisconnect: (details) => {
      if (details.reason === "error") {
        setError(`Connection lost: ${details.message}`);
      }
      if (agentId && !cleanupRef.current) {
        cleanupRef.current = true;
        endConversation(feedId, agentId).catch(() => {});
      }
    },
    onError: (message) => {
      console.error("[ConvAI] Error:", message);
      setError(typeof message === "string" ? message : "Conversation error");
    },
    onMessage: () => {},
    onAudio: () => {},
    onDebug: () => {},
    // Controlled mic mute state
    micMuted,
  });

  const handleStart = useCallback(async () => {
    setConnecting(true);
    setError(null);
    cleanupRef.current = false;

    try {
      const data = await startConversation(feedId);
      setAgentId(data.agent_id);

      await conversation.startSession({
        signedUrl: data.signed_url,
      });
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Failed to start conversation";
      setError(msg);
      setConnecting(false);
    }
  }, [feedId, conversation]);

  const handleEnd = useCallback(async () => {
    try {
      await conversation.endSession();
    } catch {
      // Ignore errors during cleanup
    }
    if (agentId && !cleanupRef.current) {
      cleanupRef.current = true;
      endConversation(feedId, agentId).catch(() => {});
    }
    setAgentId(null);
  }, [feedId, agentId, conversation]);

  const handleClose = useCallback(async () => {
    if (conversation.status === "connected") {
      await handleEnd();
    }
    onClose();
  }, [conversation.status, handleEnd, onClose]);

  // --- Mic Mode Logic ---

  // When switching to PTT, mute mic; when switching to open, unmute
  const toggleMicMode = useCallback(() => {
    setMicMode((prev) => {
      const next = prev === "open" ? "ptt" : "open";
      setMicMuted(next === "ptt"); // PTT starts muted, open starts unmuted
      return next;
    });
  }, []);

  // PTT handlers: unmute while held, mute on release
  const handlePttDown = useCallback(() => {
    if (micMode === "ptt") setMicMuted(false);
  }, [micMode]);

  const handlePttUp = useCallback(() => {
    if (micMode === "ptt") setMicMuted(true);
  }, [micMode]);

  // Open-mic toggle
  const toggleMicMuted = useCallback(() => {
    if (micMode === "open") setMicMuted((m) => !m);
  }, [micMode]);

  // --- Stop Agent Talking ---
  const handleStopTalking = useCallback(() => {
    if (agentMuted) {
      // Restore volume
      conversation.setVolume({ volume: prevVolumeRef.current });
      setAgentMuted(false);
    } else {
      // Mute agent output to interrupt
      prevVolumeRef.current = 1;
      conversation.setVolume({ volume: 0 });
      setAgentMuted(true);
    }
  }, [agentMuted, conversation]);

  // Auto-restore volume when agent stops speaking
  useEffect(() => {
    if (!conversation.isSpeaking && agentMuted) {
      conversation.setVolume({ volume: prevVolumeRef.current });
      setAgentMuted(false);
    }
  }, [conversation.isSpeaking, agentMuted, conversation]);

  // Auto-start if requested
  useEffect(() => {
    if (
      autoStart &&
      conversation.status === "disconnected" &&
      !connecting &&
      !error
    ) {
      handleStart();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoStart]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (agentId && !cleanupRef.current) {
        cleanupRef.current = true;
        endConversation(feedId, agentId).catch(() => {});
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agentId, feedId]);

  const isConnected = conversation.status === "connected";
  const isSpeaking = conversation.isSpeaking;

  // ---------- Minimized View ----------
  if (minimized) {
    return (
      <div className="fixed bottom-6 right-6 z-50">
        <button
          onClick={() => setMinimized(false)}
          className={`flex items-center gap-2 px-4 py-3 rounded-full shadow-2xl border transition-all ${
            isConnected
              ? isSpeaking
                ? "bg-emerald-600 border-emerald-500 animate-pulse"
                : "bg-[#18181B] border-emerald-500/50"
              : "bg-[#18181B] border-[#27272A]"
          }`}
        >
          <MessageCircle
            size={16}
            className={isConnected ? "text-emerald-400" : "text-zinc-400"}
          />
          <span className="text-sm text-zinc-200">
            {isConnected
              ? isSpeaking
                ? "Agent speaking…"
                : micMode === "ptt"
                ? "PTT mode"
                : "Listening…"
              : "Analyst"}
          </span>
          <Maximize2 size={12} className="text-zinc-500" />
        </button>
      </div>
    );
  }

  // ---------- Full View ----------
  return (
    <div className="fixed bottom-6 right-6 z-50 w-[380px] max-h-[560px] bg-[#0C0C0E] border border-[#27272A] rounded-2xl shadow-2xl flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#27272A] bg-[#18181B]/50">
        <div className="flex items-center gap-2.5">
          <div
            className={`w-2.5 h-2.5 rounded-full ${
              isConnected
                ? isSpeaking
                  ? "bg-emerald-400 animate-pulse"
                  : "bg-emerald-500"
                : connecting
                ? "bg-yellow-400 animate-pulse"
                : "bg-zinc-600"
            }`}
          />
          <div>
            <p className="text-[13px] font-medium text-zinc-200">
              Warehouse Analyst
            </p>
            <p className="text-[10px] text-zinc-500 truncate max-w-[200px]">
              {feedName}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {/* Mic mode toggle (only when connected) */}
          {isConnected && (
            <button
              onClick={toggleMicMode}
              className={`p-1.5 rounded transition-colors text-[10px] font-medium ${
                micMode === "ptt"
                  ? "bg-amber-500/15 text-amber-400 border border-amber-500/25"
                  : "text-zinc-500 hover:text-zinc-300"
              }`}
              title={
                micMode === "ptt"
                  ? "Push-to-Talk — click to switch to Open Mic"
                  : "Open Mic — click to switch to Push-to-Talk"
              }
            >
              {micMode === "ptt" ? (
                <span className="flex items-center gap-1">
                  <Hand size={11} />
                  PTT
                </span>
              ) : (
                <span className="flex items-center gap-1">
                  <Mic size={11} />
                  Open
                </span>
              )}
            </button>
          )}
          <button
            onClick={() => setMinimized(true)}
            className="p-1.5 text-zinc-500 hover:text-zinc-300 transition-colors"
            title="Minimize"
          >
            <Minimize2 size={13} />
          </button>
          <button
            onClick={handleClose}
            className="p-1.5 text-zinc-500 hover:text-red-400 transition-colors"
            title="Close"
          >
            <X size={13} />
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-4 py-4" ref={transcriptRef}>
        {/* Not connected yet */}
        {!isConnected && !connecting && !error && (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <div className="w-16 h-16 rounded-full bg-gradient-to-br from-emerald-600/20 to-blue-600/20 border border-emerald-500/20 flex items-center justify-center mb-4">
              <MessageCircle size={24} className="text-emerald-400" />
            </div>
            <p className="text-sm text-zinc-300 mb-1 font-medium">
              Talk to your Warehouse Analyst
            </p>
            <p className="text-xs text-zinc-500 mb-6 max-w-[260px] leading-relaxed">
              The AI analyst will narrate the findings from this feed and answer
              your questions about the detected events.
            </p>
            <button
              onClick={handleStart}
              className="flex items-center gap-2 px-5 py-2.5 bg-emerald-600 text-white text-[13px] font-medium rounded-full hover:bg-emerald-700 transition-colors shadow-lg shadow-emerald-600/20"
            >
              <Phone size={14} />
              Start Conversation
            </button>
          </div>
        )}

        {/* Connecting */}
        {connecting && (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Loader2
              size={28}
              className="text-emerald-400 animate-spin mb-4"
            />
            <p className="text-sm text-zinc-300">Connecting to analyst…</p>
            <p className="text-xs text-zinc-500 mt-1">
              Setting up voice channel
            </p>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <div className="w-12 h-12 rounded-full bg-red-500/10 border border-red-500/25 flex items-center justify-center mb-3">
              <PhoneOff size={20} className="text-red-400" />
            </div>
            <p className="text-sm text-red-400 mb-1">Connection Failed</p>
            <p className="text-xs text-zinc-500 mb-4 max-w-[260px]">{error}</p>
            <button
              onClick={handleStart}
              className="flex items-center gap-2 px-4 py-2 bg-[#27272A] text-zinc-300 text-[12px] rounded-md hover:bg-[#333] transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {/* Connected — voice visualization */}
        {isConnected && (
          <div className="flex flex-col items-center justify-center py-6">
            {/* Voice visualization orb */}
            <div className="relative mb-5">
              <div
                className={`w-24 h-24 rounded-full flex items-center justify-center transition-all duration-300 ${
                  isSpeaking && !agentMuted
                    ? "bg-gradient-to-br from-emerald-500/30 to-blue-500/30 scale-110"
                    : !micMuted && !isSpeaking
                    ? "bg-gradient-to-br from-blue-500/20 to-cyan-500/20 scale-105"
                    : "bg-gradient-to-br from-zinc-800 to-zinc-900 scale-100"
                }`}
              >
                <div
                  className={`w-16 h-16 rounded-full flex items-center justify-center transition-all duration-200 ${
                    isSpeaking && !agentMuted
                      ? "bg-gradient-to-br from-emerald-500/50 to-emerald-600/50"
                      : !micMuted && !isSpeaking
                      ? "bg-gradient-to-br from-blue-500/40 to-cyan-500/40"
                      : "bg-[#27272A]"
                  }`}
                >
                  {isSpeaking && !agentMuted ? (
                    <Volume2
                      size={24}
                      className="text-emerald-400 animate-pulse"
                    />
                  ) : agentMuted ? (
                    <VolumeX size={24} className="text-red-400" />
                  ) : !micMuted ? (
                    <Mic size={24} className="text-blue-400 animate-pulse" />
                  ) : (
                    <MicOff size={24} className="text-zinc-500" />
                  )}
                </div>
              </div>

              {/* Animated rings when speaking / transmitting */}
              {isSpeaking && !agentMuted && (
                <>
                  <div className="absolute inset-0 rounded-full border border-emerald-500/20 animate-ping" />
                  <div
                    className="absolute inset-[-8px] rounded-full border border-emerald-500/10 animate-ping"
                    style={{ animationDelay: "0.3s" }}
                  />
                </>
              )}
              {!micMuted && !isSpeaking && (
                <div className="absolute inset-0 rounded-full border border-blue-500/20 animate-ping" />
              )}
            </div>

            {/* Status text */}
            <p className="text-sm text-zinc-300 font-medium mb-0.5">
              {agentMuted
                ? "Agent silenced"
                : isSpeaking
                ? "Agent is speaking…"
                : !micMuted
                ? "Listening to you…"
                : micMode === "ptt"
                ? "Hold to talk"
                : "Microphone muted"}
            </p>
            <p className="text-[11px] text-zinc-500 mb-1">
              {agentMuted
                ? "Agent audio is muted — will resume when it finishes"
                : isSpeaking
                ? "Press Stop to silence the agent"
                : micMode === "ptt"
                ? micMuted
                  ? "Press and hold the mic button below to speak"
                  : "Release to stop transmitting"
                : micMuted
                ? "Click the mic button to unmute"
                : "Speak naturally — ask about any detected event"}
            </p>
          </div>
        )}
      </div>

      {/* Footer — controls when connected */}
      {isConnected && (
        <div className="border-t border-[#27272A] px-4 py-3 flex flex-col gap-2.5">
          {/* Main controls row */}
          <div className="flex items-center justify-center gap-2.5">
            {/* Mic control */}
            {micMode === "ptt" ? (
              /* Push-to-Talk button */
              <button
                onMouseDown={handlePttDown}
                onMouseUp={handlePttUp}
                onMouseLeave={handlePttUp}
                onTouchStart={handlePttDown}
                onTouchEnd={handlePttUp}
                onTouchCancel={handlePttUp}
                className={`flex items-center gap-2 px-5 py-2.5 text-[12px] font-medium rounded-full transition-all select-none ${
                  !micMuted
                    ? "bg-blue-600 text-white shadow-lg shadow-blue-600/30 scale-105"
                    : "bg-[#27272A] text-zinc-300 hover:bg-[#333] border border-zinc-700"
                }`}
              >
                {!micMuted ? (
                  <>
                    <Mic size={14} className="animate-pulse" />
                    Transmitting…
                  </>
                ) : (
                  <>
                    <Hand size={14} />
                    Hold to Talk
                  </>
                )}
              </button>
            ) : (
              /* Open-mic mute/unmute toggle */
              <button
                onClick={toggleMicMuted}
                className={`flex items-center gap-2 px-4 py-2 text-[12px] font-medium rounded-full transition-colors ${
                  micMuted
                    ? "bg-[#27272A] text-zinc-400 hover:bg-[#333] border border-zinc-700"
                    : "bg-blue-600/80 text-white hover:bg-blue-600"
                }`}
              >
                {micMuted ? (
                  <>
                    <MicOff size={13} />
                    Unmute
                  </>
                ) : (
                  <>
                    <Mic size={13} />
                    Mute
                  </>
                )}
              </button>
            )}

            {/* Stop agent talking — visible when agent is speaking */}
            {isSpeaking && (
              <button
                onClick={handleStopTalking}
                className={`flex items-center gap-2 px-4 py-2 text-[12px] font-medium rounded-full transition-colors ${
                  agentMuted
                    ? "bg-amber-600/80 text-white hover:bg-amber-600"
                    : "bg-red-600/20 text-red-400 hover:bg-red-600/30 border border-red-500/25"
                }`}
              >
                {agentMuted ? (
                  <>
                    <Volume2 size={13} />
                    Unmute Agent
                  </>
                ) : (
                  <>
                    <VolumeX size={13} />
                    Stop Talking
                  </>
                )}
              </button>
            )}

            {/* End conversation */}
            <button
              onClick={handleEnd}
              className="flex items-center gap-2 px-4 py-2 bg-red-600/80 text-white text-[12px] font-medium rounded-full hover:bg-red-600 transition-colors"
            >
              <PhoneOff size={13} />
              End
            </button>
          </div>

          {/* Hint text */}
          <p className="text-[10px] text-zinc-600 text-center">
            {micMode === "ptt"
              ? "Push-to-Talk mode — hold the button while speaking"
              : "Open Mic mode — your voice is always transmitted"}
          </p>
        </div>
      )}

      {/* Footer — when not connected and has error */}
      {!isConnected && !connecting && error && (
        <div className="border-t border-[#27272A] px-4 py-2.5">
          <p className="text-[10px] text-zinc-600 text-center">
            Powered by ElevenLabs Conversational AI
          </p>
        </div>
      )}
    </div>
  );
}

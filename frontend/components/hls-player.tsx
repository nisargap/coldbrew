"use client";

import { useEffect, useRef, useState } from "react";
import Hls from "hls.js";
import { AlertCircle, Loader2, Volume2, VolumeX } from "lucide-react";

interface HlsPlayerProps {
  src: string;
  autoPlay?: boolean;
  muted?: boolean;
  className?: string;
}

export default function HlsPlayer({
  src,
  autoPlay = true,
  muted = true,
  className = "",
}: HlsPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsRef = useRef<Hls | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [isMuted, setIsMuted] = useState(muted);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !src) return;

    setError(null);
    setLoading(true);

    // Clean up previous instance
    if (hlsRef.current) {
      hlsRef.current.destroy();
      hlsRef.current = null;
    }

    if (Hls.isSupported()) {
      const hls = new Hls({
        enableWorker: true,
        lowLatencyMode: true,
        liveSyncDurationCount: 3,
        liveMaxLatencyDurationCount: 6,
        liveDurationInfinity: true,
        // Retry config for flaky streams
        manifestLoadingMaxRetry: 6,
        manifestLoadingRetryDelay: 1000,
        levelLoadingMaxRetry: 6,
        fragLoadingMaxRetry: 6,
      });

      hlsRef.current = hls;

      hls.loadSource(src);
      hls.attachMedia(video);

      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        setLoading(false);
        if (autoPlay) {
          video.play().catch(() => {
            // Autoplay blocked — user needs to interact
          });
        }
      });

      hls.on(Hls.Events.ERROR, (_event, data) => {
        if (data.fatal) {
          switch (data.type) {
            case Hls.ErrorTypes.NETWORK_ERROR:
              setError("Network error — stream may be offline or unreachable.");
              hls.startLoad(); // Try to recover
              break;
            case Hls.ErrorTypes.MEDIA_ERROR:
              setError("Media error — attempting recovery...");
              hls.recoverMediaError();
              break;
            default:
              setError("Failed to load stream. It may be offline or the URL is invalid.");
              hls.destroy();
              break;
          }
        }
      });
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      // Safari native HLS support
      video.src = src;
      video.addEventListener("loadedmetadata", () => {
        setLoading(false);
        if (autoPlay) {
          video.play().catch(() => {});
        }
      });
      video.addEventListener("error", () => {
        setError("Failed to load HLS stream.");
      });
    } else {
      setError("Your browser does not support HLS playback.");
    }

    return () => {
      if (hlsRef.current) {
        hlsRef.current.destroy();
        hlsRef.current = null;
      }
    };
  }, [src, autoPlay]);

  const toggleMute = () => {
    if (videoRef.current) {
      videoRef.current.muted = !isMuted;
      setIsMuted(!isMuted);
    }
  };

  return (
    <div className={`relative rounded-lg overflow-hidden bg-black ${className}`}>
      <div className="aspect-video w-full">
        {loading && !error && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/60 z-10">
            <Loader2 size={28} className="text-zinc-400 animate-spin" />
          </div>
        )}

        {error && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/80 z-10 px-4">
            <AlertCircle size={24} className="text-red-400 mb-2" />
            <p className="text-sm text-zinc-400 text-center">{error}</p>
          </div>
        )}

        <video
          ref={videoRef}
          className="w-full h-full object-contain"
          muted={isMuted}
          playsInline
          controls={false}
        />
      </div>

      {/* Mute toggle overlay */}
      <button
        onClick={toggleMute}
        className="absolute bottom-3 right-3 p-1.5 rounded-md bg-black/50 backdrop-blur-sm border border-white/10 text-zinc-300 hover:text-white hover:bg-black/70 transition-colors z-20"
        title={isMuted ? "Unmute" : "Mute"}
      >
        {isMuted ? <VolumeX size={14} /> : <Volume2 size={14} />}
      </button>
    </div>
  );
}

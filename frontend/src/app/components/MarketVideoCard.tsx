"use client";
import { useState, useCallback, useEffect, useRef } from "react";
import {
  Brain, HeartPulse, Target, CalendarDays,
  Film, Play, Download, Loader2, AlertTriangle,
  Video, Volume2, RefreshCw
} from "lucide-react";

const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/api/v1";
const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const STORAGE_KEY = "alpha-hunter-portfolio";

type Category = "health" | "market" | "historical";

const TABS: { id: Category; label: string; icon: typeof HeartPulse; desc: string; color: string; gradient: string }[] = [
  { id: "health", label: "Portfolio Health", icon: HeartPulse, desc: "P&L, risk, diversification", color: "#10b981", gradient: "linear-gradient(135deg, rgba(16,185,129,0.15), rgba(16,185,129,0.03))" },
  { id: "market", label: "Market Analysis", icon: Target, desc: "Signals, patterns, momentum", color: "#60a5fa", gradient: "linear-gradient(135deg, rgba(96,165,250,0.15), rgba(96,165,250,0.03))" },
  { id: "historical", label: "Historical", icon: CalendarDays, desc: "Seasonality, volatility, backtests", color: "#fbbf24", gradient: "linear-gradient(135deg, rgba(251,191,36,0.15), rgba(251,191,36,0.03))" },
];

const CATEGORY_ENDPOINTS: Record<Category, string> = {
  health: "/intelligence/portfolio-health",
  market: "/intelligence/market-analysis",
  historical: "/intelligence/historical",
};

const STATUS_MESSAGES: Record<string, string> = {
  queued: "Queuing video generation...",
  building_scenes: "📊 Building visual scenes from your data...",
  rendering_frames: "🎨 Rendering chart frames with Pillow...",
  synthesizing_speech: "🎙️ Synthesizing speech with Amazon Polly...",
  composing_video: "🎬 Composing final video with MoviePy...",
};

export default function MarketVideoCard() {
  const [tab, setTab] = useState<Category>("health");
  const [holdings, setHoldings] = useState<any[]>([]);

  // Video state per category
  const [videoState, setVideoState] = useState<Record<Category, {
    status: "idle" | "fetching_report" | "generating" | "completed" | "failed";
    progress: number;
    statusMsg: string;
    videoUrl: string | null;
    error: string | null;
    jobId: string | null;
    elapsed: number | null;
  }>>({
    health: { status: "idle", progress: 0, statusMsg: "", videoUrl: null, error: null, jobId: null, elapsed: null },
    market: { status: "idle", progress: 0, statusMsg: "", videoUrl: null, error: null, jobId: null, elapsed: null },
    historical: { status: "idle", progress: 0, statusMsg: "", videoUrl: null, error: null, jobId: null, elapsed: null },
  });

  const pollRef = useRef<NodeJS.Timeout | null>(null);

  // Load holdings from localStorage
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setHoldings(JSON.parse(raw));
    } catch {}
  }, []);

  // Cleanup
  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  // Update video state for a specific category
  const updateCatState = useCallback((cat: Category, update: Partial<typeof videoState.health>) => {
    setVideoState(prev => ({ ...prev, [cat]: { ...prev[cat], ...update } }));
  }, []);

  // Poll video job status
  const startPolling = useCallback((cat: Category, jobId: string) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const resp = await fetch(`${API}/intelligence/video-status/${jobId}`);
        if (!resp.ok) return;
        const data = await resp.json();

        updateCatState(cat, {
          progress: data.progress_pct || 0,
          statusMsg: STATUS_MESSAGES[data.status] || "Processing...",
        });

        if (data.status === "completed" && data.video_url) {
          updateCatState(cat, {
            status: "completed",
            progress: 100,
            statusMsg: "✅ Video ready!",
            videoUrl: `${BASE_URL}${data.video_url}`,
            elapsed: data.elapsed_sec,
          });
          if (pollRef.current) clearInterval(pollRef.current);
        } else if (data.status === "failed") {
          updateCatState(cat, {
            status: "failed",
            progress: 0,
            error: data.error || "Video generation failed",
          });
          if (pollRef.current) clearInterval(pollRef.current);
        }
      } catch {}
    }, 2000);
  }, [updateCatState]);

  // Main action: fetch report → generate video
  const generateVideo = useCallback(async (cat: Category) => {
    if (!holdings.length) return;

    // Reset state
    updateCatState(cat, {
      status: "fetching_report",
      progress: 5,
      statusMsg: "📡 Fetching live market data & analyzing portfolio...",
      videoUrl: null,
      error: null,
      jobId: null,
      elapsed: null,
    });

    try {
      // Step 1: Fetch intelligence report
      const payload = {
        holdings: holdings.map((h: any) => ({
          symbol: h.symbol || h.ticker,
          qty: h.qty || h.quantity || 0,
          buy_price: h.buyPrice || h.buy_price || 0,
        })),
      };

      const reportResp = await fetch(`${API}${CATEGORY_ENDPOINTS[cat]}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!reportResp.ok) {
        const d = await reportResp.json().catch(() => null);
        throw new Error(d?.detail || `Report fetch failed (HTTP ${reportResp.status})`);
      }

      const reportData = await reportResp.json();

      // Step 2: Start video generation
      updateCatState(cat, {
        status: "generating",
        progress: 10,
        statusMsg: "📊 Building visual scenes from your data...",
      });

      const videoResp = await fetch(`${API}/intelligence/generate-video`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category: cat, report_data: reportData }),
      });

      if (!videoResp.ok) {
        const d = await videoResp.json().catch(() => null);
        throw new Error(d?.detail || d?.error || `Video generation failed (HTTP ${videoResp.status})`);
      }

      const videoData = await videoResp.json();
      updateCatState(cat, { jobId: videoData.job_id });

      // Step 3: Start polling
      startPolling(cat, videoData.job_id);

    } catch (e: any) {
      updateCatState(cat, {
        status: "failed",
        progress: 0,
        error: e.message || "An error occurred",
      });
    }
  }, [holdings, updateCatState, startPolling]);

  const current = videoState[tab];
  const isWorking = current.status === "fetching_report" || current.status === "generating";
  const tabMeta = TABS.find(t => t.id === tab)!;

  return (
    <div style={{
      background: "linear-gradient(135deg, rgba(15,23,42,0.95), rgba(30,41,59,0.9))",
      border: "1px solid rgba(100,116,139,0.25)",
      borderRadius: 16, overflow: "hidden",
      backdropFilter: "blur(12px)",
      boxShadow: "0 4px 24px rgba(0,0,0,0.3)",
      height: "100%",
      display: "flex",
      flexDirection: "column",
    }}>
      {/* Header */}
      <div style={{
        padding: "14px 18px", display: "flex", alignItems: "center", justifyContent: "space-between",
        borderBottom: "1px solid rgba(100,116,139,0.2)",
        background: "linear-gradient(90deg, rgba(245,158,11,0.08), rgba(139,92,246,0.05), transparent)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ padding: 6, background: "rgba(245,158,11,0.15)", borderRadius: 10 }}>
            <Film size={16} style={{ color: "#fbbf24" }} />
          </div>
          <div>
            <span style={{ fontSize: 14, fontWeight: 700, color: "#e2e8f0" }}>AI Video Intelligence </span>
            <span style={{ fontSize: 10, padding: "2px 6px", background: "linear-gradient(135deg,#f59e0b,#d97706)", borderRadius: 6, color: "#fff", fontWeight: 600, verticalAlign: "middle" }}>VIDEO</span>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <Volume2 size={10} style={{ color: "#64748b" }} />
          <span style={{ fontSize: 9, color: "#64748b" }}>Polly TTS • MoviePy</span>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, padding: "10px 12px", background: "rgba(15,23,42,0.5)" }}>
        {TABS.map((t) => {
          const Icon = t.icon;
          const isActive = tab === t.id;
          const catState = videoState[t.id];
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                flex: 1, padding: "8px 6px", borderRadius: 10, border: "1px solid",
                borderColor: isActive ? `${t.color}60` : "transparent",
                background: isActive ? t.gradient : "rgba(30,41,59,0.3)",
                cursor: "pointer", transition: "all 0.2s",
                display: "flex", flexDirection: "column" as const, alignItems: "center", gap: 3,
                position: "relative" as const,
              }}
            >
              <Icon size={14} style={{ color: isActive ? t.color : "#64748b" }} />
              <span style={{ fontSize: 10, fontWeight: 600, color: isActive ? "#e2e8f0" : "#64748b" }}>{t.label}</span>
              <span style={{ fontSize: 8, color: "#64748b" }}>{t.desc}</span>
              {/* Video ready indicator */}
              {catState.status === "completed" && (
                <span style={{
                  position: "absolute" as const, top: 4, right: 4,
                  width: 8, height: 8, borderRadius: "50%",
                  background: t.color,
                  boxShadow: `0 0 6px ${t.color}80`,
                }} />
              )}
              {(catState.status === "fetching_report" || catState.status === "generating") && (
                <span style={{
                  position: "absolute" as const, top: 4, right: 4,
                  width: 8, height: 8, borderRadius: "50%",
                  background: "#f59e0b",
                  animation: "pulse 1.5s infinite",
                }} />
              )}
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div style={{ padding: 16, minHeight: 280, flex: 1 }}>

        {/* No holdings state */}
        {!holdings.length && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, padding: "40px 0" }}>
            <div style={{ padding: 16, background: "rgba(245,158,11,0.08)", borderRadius: 16, border: "1px solid rgba(245,158,11,0.15)" }}>
              <Film size={32} style={{ color: "#64748b" }} />
            </div>
            <p style={{ fontSize: 13, color: "#94a3b8", fontWeight: 500 }}>Add stocks to your portfolio first</p>
            <p style={{ fontSize: 11, color: "#64748b", textAlign: "center", maxWidth: 300 }}>
              Go to Portfolio Manager and add your holdings to generate AI-narrated video reports.
            </p>
          </div>
        )}

        {/* Idle state — ready to generate */}
        {holdings.length > 0 && current.status === "idle" && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, padding: "30px 0" }}>
            <div style={{
              padding: 20, borderRadius: 20,
              background: `${tabMeta.color}10`,
              border: `1px solid ${tabMeta.color}20`,
            }}>
              <Video size={36} style={{ color: tabMeta.color }} />
            </div>
            <div style={{ textAlign: "center" }}>
              <p style={{ fontSize: 15, color: "#e2e8f0", fontWeight: 600, margin: 0 }}>{tabMeta.label} Video</p>
              <p style={{ fontSize: 11, color: "#64748b", maxWidth: 320, margin: "6px auto 0" }}>
                {tab === "health" && "Generate a narrated video analyzing your portfolio condition — P&L breakdown, risk assessment, and diversification insights."}
                {tab === "market" && "Generate a narrated video with technical signals — MACD divergences, RSI levels, candlestick patterns, and buy/sell signals."}
                {tab === "historical" && "Generate a narrated video covering historical patterns — seasonality, volatility regimes, day-of-week returns, and backtests."}
              </p>
            </div>
            <button
              onClick={() => generateVideo(tab)}
              style={{
                padding: "12px 32px", borderRadius: 12, border: "none",
                cursor: "pointer",
                background: `linear-gradient(135deg, ${tabMeta.color}, ${tabMeta.color}cc)`,
                color: "#fff", fontSize: 14, fontWeight: 700,
                display: "flex", alignItems: "center", gap: 10,
                boxShadow: `0 4px 20px ${tabMeta.color}40`,
                transition: "all 0.2s",
              }}
            >
              <Film size={16} />
              🎬 Generate {tabMeta.label} Video
            </button>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <Volume2 size={10} style={{ color: "#475569" }} />
              <span style={{ fontSize: 9, color: "#475569" }}>
                Audio: Amazon Polly (Neural) • Video: MoviePy + Pillow • {holdings.length} stocks
              </span>
            </div>
          </div>
        )}

        {/* Working state — fetching report or generating video */}
        {holdings.length > 0 && isWorking && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, padding: "30px 0" }}>
            {/* Animated icon */}
            <div style={{
              position: "relative", padding: 20, borderRadius: 20,
              background: "rgba(245,158,11,0.08)",
              border: "1px solid rgba(245,158,11,0.15)",
            }}>
              <Loader2 size={36} style={{ color: "#fbbf24", animation: "spin 1.5s linear infinite" }} />
              <span style={{
                position: "absolute", top: -4, right: -4,
                fontSize: 18,
              }}>
                {current.status === "fetching_report" ? "📡" : "🎬"}
              </span>
            </div>

            {/* Status message */}
            <div style={{ textAlign: "center" }}>
              <p style={{ fontSize: 13, color: "#fbbf24", fontWeight: 600, margin: 0 }}>
                {current.statusMsg}
              </p>
              <p style={{ fontSize: 10, color: "#64748b", margin: "4px 0 0" }}>
                This may take 1-2 minutes. Please wait...
              </p>
            </div>

            {/* Progress bar */}
            <div style={{ width: "100%", maxWidth: 400 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                <span style={{ fontSize: 10, color: "#94a3b8" }}>Progress</span>
                <span style={{ fontSize: 10, color: "#fbbf24", fontWeight: 600 }}>{current.progress}%</span>
              </div>
              <div style={{ height: 6, borderRadius: 6, background: "rgba(30,41,59,0.8)", overflow: "hidden" }}>
                <div style={{
                  height: "100%", borderRadius: 6,
                  background: "linear-gradient(90deg, #f59e0b, #d97706, #f59e0b)",
                  backgroundSize: "200% 100%",
                  animation: "shimmer 2s linear infinite",
                  width: `${Math.max(current.progress, 5)}%`,
                  transition: "width 0.5s ease",
                }} />
              </div>
            </div>

            {/* Pipeline stages */}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" as const, justifyContent: "center" }}>
              {["📡 Data", "📊 Scenes", "🎨 Frames", "🎙️ Polly TTS", "🎬 Compose"].map((stage, i) => {
                const stageProgress = [5, 25, 40, 60, 80];
                const isActive = current.progress >= stageProgress[i] && current.progress < (stageProgress[i + 1] || 101);
                const isDone = current.progress >= (stageProgress[i + 1] || 101);
                return (
                  <span key={i} style={{
                    fontSize: 9, padding: "3px 8px", borderRadius: 6,
                    background: isDone ? "rgba(16,185,129,0.1)" : isActive ? "rgba(245,158,11,0.15)" : "rgba(30,41,59,0.5)",
                    border: `1px solid ${isDone ? "rgba(16,185,129,0.3)" : isActive ? "rgba(245,158,11,0.3)" : "rgba(71,85,105,0.3)"}`,
                    color: isDone ? "#10b981" : isActive ? "#fbbf24" : "#475569",
                    fontWeight: isActive ? 700 : 400,
                  }}>
                    {isDone ? "✓ " : ""}{stage}
                  </span>
                );
              })}
            </div>
          </div>
        )}

        {/* Error state */}
        {current.status === "failed" && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14, padding: "30px 0" }}>
            <div style={{ padding: 16, background: "rgba(239,68,68,0.08)", borderRadius: 16, border: "1px solid rgba(239,68,68,0.15)" }}>
              <AlertTriangle size={32} style={{ color: "#f87171" }} />
            </div>
            <p style={{ fontSize: 12, color: "#fca5a5", textAlign: "center", maxWidth: 320 }}>{current.error}</p>
            <button
              onClick={() => { updateCatState(tab, { status: "idle", error: null }); }}
              style={{
                padding: "8px 20px", borderRadius: 10, border: "none",
                cursor: "pointer",
                background: "rgba(239,68,68,0.15)",
                color: "#f87171", fontSize: 12, fontWeight: 600,
                display: "flex", alignItems: "center", gap: 6,
              }}
            >
              <RefreshCw size={12} /> Try Again
            </button>
          </div>
        )}

        {/* Video Player — completed state */}
        {current.status === "completed" && current.videoUrl && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {/* Video player */}
            <div style={{ borderRadius: 12, overflow: "hidden", border: `1px solid ${tabMeta.color}30`, background: "rgba(15,23,42,0.8)" }}>
              <div style={{
                padding: "10px 14px",
                background: `${tabMeta.color}08`,
                display: "flex", alignItems: "center", justifyContent: "space-between",
                borderBottom: `1px solid ${tabMeta.color}15`,
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Play size={14} style={{ color: tabMeta.color }} />
                  <span style={{ fontSize: 12, fontWeight: 700, color: tabMeta.color }}>
                    {tabMeta.label} Video Report
                  </span>
                  {current.elapsed && (
                    <span style={{ fontSize: 9, color: "#64748b", fontStyle: "italic" }}>
                      ({current.elapsed.toFixed(0)}s render)
                    </span>
                  )}
                </div>
                <a
                  href={current.videoUrl}
                  download
                  style={{
                    display: "flex", alignItems: "center", gap: 4,
                    fontSize: 10, color: "#94a3b8", textDecoration: "none",
                    padding: "4px 10px", borderRadius: 6,
                    background: "rgba(100,116,139,0.1)",
                    border: "1px solid rgba(100,116,139,0.2)",
                  }}
                >
                  <Download size={10} /> Download MP4
                </a>
              </div>
              <video
                controls
                autoPlay
                style={{ width: "100%", display: "block", maxHeight: 400 }}
                src={current.videoUrl}
              />
            </div>

            {/* Regenerate button */}
            <div style={{ display: "flex", justifyContent: "center" }}>
              <button
                onClick={() => generateVideo(tab)}
                style={{
                  padding: "8px 20px", borderRadius: 10, border: "none",
                  cursor: "pointer",
                  background: `linear-gradient(135deg, ${tabMeta.color}20, ${tabMeta.color}05)`,
                  color: tabMeta.color, fontSize: 12, fontWeight: 600,
                  display: "flex", alignItems: "center", gap: 6,
                  border: `1px solid ${tabMeta.color}25`,
                }}
              >
                <RefreshCw size={12} /> Regenerate Video
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Global animation styles */}
      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
        @keyframes shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
      `}</style>
    </div>
  );
}

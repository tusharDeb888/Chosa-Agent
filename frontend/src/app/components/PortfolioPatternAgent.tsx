"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import {
  Brain, Loader2, TrendingUp, TrendingDown, Minus, ChevronDown, ChevronUp,
  ArrowUpRight, ArrowDownRight, RefreshCw, Sparkles, BarChart3, Activity,
  Shield, Target, Zap, Eye, AlertTriangle,
} from "lucide-react";

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/api/v1";
const STORAGE_KEY = "alpha-hunter-portfolio";

// ─── Types ───
interface Holding { symbol: string; qty: number; buy_price: number }

interface HoldingAnalysis {
  symbol: string;
  status: string;
  error?: string;
  price?: {
    current: number; prev_close: number; day_change_pct: number;
    buy_price: number; pnl_pct: number; pnl_value: number;
    qty: number; invested: number; current_value: number;
  };
  patterns?: Array<{
    name: string; type: string; signal: string;
    emoji: string; confidence: number; description: string;
  }>;
  signals?: {
    macd_divergence: boolean; macd_type: string | null;
    ma_crossover: boolean; ma_type: string | null;
  };
  trend?: {
    direction: string; strength: number; rsi: number;
    sma_20: number; sma_50: number | null; price_vs_sma20_pct: number;
  };
  backtest?: {
    win_rate_pct: number; avg_return_pct: number;
    max_drawdown_pct: number; total_trades: number;
  };
  recommendation?: {
    action: "BUY" | "SELL" | "HOLD";
    confidence: number; score: number; reasons: string[];
  };
  insight?: string;
  chart_data?: Array<{ o: number; h: number; l: number; c: number; v: number }>;
  latency_ms?: number;
}

interface ScanResult {
  holdings: HoldingAnalysis[];
  summary: { total: number; buy: number; sell: number; hold: number; scanned: number };
  latency_ms: number;
}

// ─── Candlestick Mini Chart ───
function CandlestickChart({ data, width = 280, height = 100 }: {
  data: Array<{ o: number; h: number; l: number; c: number }>;
  width?: number; height?: number;
}) {
  if (!data || data.length < 3) return null;

  const padding = { top: 4, bottom: 4, left: 4, right: 4 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  const allPrices = data.flatMap(d => [d.h, d.l]);
  const minP = Math.min(...allPrices);
  const maxP = Math.max(...allPrices);
  const range = maxP - minP || 1;

  const candleW = Math.max(2, (chartW / data.length) * 0.65);
  const gap = chartW / data.length;

  const y = (price: number) => padding.top + chartH - ((price - minP) / range) * chartH;

  return (
    <svg width={width} height={height} className="block">
      {data.map((d, i) => {
        const x = padding.left + i * gap + gap / 2;
        const isUp = d.c >= d.o;
        const bodyTop = y(Math.max(d.o, d.c));
        const bodyBot = y(Math.min(d.o, d.c));
        const bodyH = Math.max(bodyBot - bodyTop, 1);

        return (
          <g key={i}>
            {/* Wick */}
            <line x1={x} y1={y(d.h)} x2={x} y2={y(d.l)}
              stroke={isUp ? "#34d399" : "#f87171"} strokeWidth={0.8} opacity={0.7} />
            {/* Body */}
            <rect x={x - candleW / 2} y={bodyTop} width={candleW} height={bodyH}
              fill={isUp ? "#34d399" : "#f87171"} rx={0.5}
              opacity={0.9} />
          </g>
        );
      })}
    </svg>
  );
}

// ─── Action Badge ───
function ActionBadge({ action, confidence }: { action: string; confidence: number }) {
  const cfg = {
    BUY: {
      bg: "from-emerald-600/30 to-emerald-500/20",
      border: "border-emerald-500/40",
      text: "text-emerald-300",
      glow: "shadow-emerald-500/20",
      icon: <TrendingUp size={14} />,
    },
    SELL: {
      bg: "from-red-600/30 to-red-500/20",
      border: "border-red-500/40",
      text: "text-red-300",
      glow: "shadow-red-500/20",
      icon: <TrendingDown size={14} />,
    },
    HOLD: {
      bg: "from-amber-600/30 to-amber-500/20",
      border: "border-amber-500/40",
      text: "text-amber-300",
      glow: "shadow-amber-500/20",
      icon: <Minus size={14} />,
    },
  }[action] || { bg: "from-slate-600/30 to-slate-500/20", border: "border-slate-500/40", text: "text-slate-300", glow: "", icon: null };

  return (
    <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-gradient-to-r ${cfg.bg} border ${cfg.border} ${cfg.text} shadow-lg ${cfg.glow}`}>
      {cfg.icon}
      <span className="text-xs font-bold tracking-wide">{action}</span>
      <span className="text-[10px] opacity-70">{confidence.toFixed(0)}%</span>
    </div>
  );
}

// ─── RSI Gauge ───
function RSIGauge({ value }: { value: number }) {
  const clamp = Math.max(0, Math.min(100, value));
  const color = clamp < 30 ? "#34d399" : clamp > 70 ? "#f87171" : "#fbbf24";
  const label = clamp < 30 ? "Oversold" : clamp > 70 ? "Overbought" : "Neutral";

  return (
    <div className="flex items-center gap-2">
      <div className="relative w-16 h-1.5 bg-slate-700/60 rounded-full overflow-hidden">
        <div
          className="absolute h-full rounded-full transition-all duration-700"
          style={{ width: `${clamp}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-[10px] font-medium" style={{ color }}>{value.toFixed(0)} {label}</span>
    </div>
  );
}

// ─── Holding Card (Expanded) ───
function HoldingCard({ data, isExpanded, onToggle }: {
  data: HoldingAnalysis; isExpanded: boolean; onToggle: () => void;
}) {
  if (data.status !== "ok") {
    return (
      <div className="bg-slate-800/40 border border-slate-700/30 rounded-xl p-3 opacity-60">
        <div className="flex items-center gap-2">
          <AlertTriangle size={14} className="text-amber-500" />
          <span className="text-sm text-slate-400">{data.symbol}</span>
          <span className="text-xs text-slate-500 ml-auto">{data.error || "Analysis failed"}</span>
        </div>
      </div>
    );
  }

  const rec = data.recommendation!;
  const price = data.price!;
  const isUp = price.day_change_pct >= 0;
  const isProfitable = price.pnl_pct >= 0;

  return (
    <div className={`group bg-gradient-to-br from-slate-800/70 to-slate-900/80 border rounded-xl overflow-hidden transition-all duration-300 hover:shadow-xl ${
      rec.action === "BUY" ? "border-emerald-500/20 hover:border-emerald-500/40" :
      rec.action === "SELL" ? "border-red-500/20 hover:border-red-500/40" :
      "border-slate-700/30 hover:border-slate-600/50"
    }`}>
      {/* Main Row */}
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer select-none"
        onClick={onToggle}
      >
        {/* Symbol + Price */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="text-sm font-bold text-white tracking-wide">{data.symbol}</span>
            <ActionBadge action={rec.action} confidence={rec.confidence} />
          </div>
          <div className="flex items-center gap-3">
            <span className="text-lg font-semibold text-white">₹{price.current.toLocaleString("en-IN", { minimumFractionDigits: 1 })}</span>
            <span className={`flex items-center gap-0.5 text-xs font-medium ${isUp ? "text-emerald-400" : "text-red-400"}`}>
              {isUp ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
              {isUp ? "+" : ""}{price.day_change_pct.toFixed(2)}%
            </span>
          </div>
        </div>

        {/* Mini Chart */}
        <div className="hidden sm:block">
          <CandlestickChart data={data.chart_data || []} width={120} height={48} />
        </div>

        {/* P&L */}
        <div className="text-right">
          <p className={`text-sm font-bold ${isProfitable ? "text-emerald-400" : "text-red-400"}`}>
            {isProfitable ? "+" : ""}₹{price.pnl_value.toLocaleString("en-IN", { minimumFractionDigits: 0 })}
          </p>
          <p className={`text-[10px] ${isProfitable ? "text-emerald-400/70" : "text-red-400/70"}`}>
            {isProfitable ? "+" : ""}{price.pnl_pct.toFixed(2)}%
          </p>
        </div>

        {/* Expand icon */}
        <div className="text-slate-500 shrink-0">
          {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </div>

      {/* Expanded Details */}
      {isExpanded && (
        <div className="border-t border-slate-700/30 px-4 py-3 space-y-3 animate-fadeIn">
          {/* Candlestick Chart (Large) */}
          <div className="bg-slate-900/50 rounded-lg p-3">
            <CandlestickChart data={data.chart_data || []} width={560} height={120} />
          </div>

          {/* Pattern Badges */}
          {data.patterns && data.patterns.length > 0 && (
            <div>
              <p className="text-[10px] uppercase text-slate-500 tracking-wider mb-1.5 font-semibold">Candlestick Patterns</p>
              <div className="flex flex-wrap gap-1.5">
                {data.patterns.map((p, i) => (
                  <div key={i} className={`group/tip relative inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-medium border ${
                    p.signal === "bullish" ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300" :
                    p.signal === "bearish" ? "bg-red-500/10 border-red-500/30 text-red-300" :
                    "bg-slate-700/30 border-slate-600/30 text-slate-300"
                  }`}>
                    <span>{p.emoji}</span>
                    <span>{p.name}</span>
                    <span className="opacity-50 text-[9px]">{p.confidence}%</span>
                    {/* Tooltip */}
                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 w-48 p-2 bg-slate-800 border border-slate-600/50 rounded-lg shadow-xl text-[10px] text-slate-300 opacity-0 group-hover/tip:opacity-100 transition-opacity pointer-events-none z-10">
                      {p.description}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Technical Signals */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <div className="bg-slate-800/50 rounded-lg px-2.5 py-2">
              <p className="text-[10px] text-slate-500 mb-0.5">Trend</p>
              <p className={`text-xs font-bold capitalize ${
                data.trend?.direction === "bullish" ? "text-emerald-400" :
                data.trend?.direction === "bearish" ? "text-red-400" : "text-amber-400"
              }`}>{data.trend?.direction || "—"}</p>
            </div>
            <div className="bg-slate-800/50 rounded-lg px-2.5 py-2">
              <p className="text-[10px] text-slate-500 mb-0.5">RSI (14)</p>
              {data.trend?.rsi && <RSIGauge value={data.trend.rsi} />}
            </div>
            <div className="bg-slate-800/50 rounded-lg px-2.5 py-2">
              <p className="text-[10px] text-slate-500 mb-0.5">MACD</p>
              <p className={`text-xs font-bold ${data.signals?.macd_divergence ? "text-amber-400" : "text-slate-500"}`}>
                {data.signals?.macd_divergence ? `${data.signals.macd_type}` : "No signal"}
              </p>
            </div>
            <div className="bg-slate-800/50 rounded-lg px-2.5 py-2">
              <p className="text-[10px] text-slate-500 mb-0.5">Win Rate</p>
              <p className={`text-xs font-bold ${(data.backtest?.win_rate_pct || 0) >= 50 ? "text-emerald-400" : "text-amber-400"}`}>
                {data.backtest?.win_rate_pct.toFixed(1)}%
              </p>
            </div>
          </div>

          {/* AI Insight */}
          {data.insight && (
            <div className="bg-gradient-to-r from-violet-500/5 to-blue-500/5 border border-violet-500/20 rounded-lg px-3 py-2.5 flex items-start gap-2">
              <Sparkles size={14} className="text-violet-400 shrink-0 mt-0.5" />
              <p className="text-xs text-slate-300 leading-relaxed">{data.insight}</p>
            </div>
          )}

          {/* Recommendation Reasons */}
          {rec.reasons.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {rec.reasons.map((r, i) => (
                <span key={i} className="text-[10px] bg-slate-800/40 border border-slate-700/30 text-slate-400 px-2 py-0.5 rounded-full">
                  {r}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
//  MAIN COMPONENT — Portfolio Pattern Agent
// ═══════════════════════════════════════════════════════════

export default function PortfolioPatternAgent() {
  const [result, setResult] = useState<ScanResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [scanProgress, setScanProgress] = useState(0);
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const progressRef = useRef<NodeJS.Timeout | null>(null);

  // Load holdings from localStorage
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setHoldings(JSON.parse(raw));
    } catch {}
  }, []);

  const runScan = useCallback(async () => {
    const h = holdings.length > 0 ? holdings : (() => {
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        return raw ? JSON.parse(raw) : [];
      } catch { return []; }
    })();

    if (h.length === 0) {
      setError("No holdings in portfolio. Add stocks in the Portfolio Manager first.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    setScanProgress(5);

    // Animate progress
    progressRef.current = setInterval(() => {
      setScanProgress(prev => Math.min(prev + Math.random() * 12, 88));
    }, 800);

    try {
      const resp = await fetch(`${API_BASE}/patterns/portfolio-scan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ holdings: h }),
      });

      const data: ScanResult = await resp.json();

      if (!resp.ok) throw new Error((data as any).error || `HTTP ${resp.status}`);

      setScanProgress(100);
      setTimeout(() => {
        setResult(data);
        setLoading(false);
        if (progressRef.current) clearInterval(progressRef.current);
        // Auto-expand first holding
        if (data.holdings.length > 0) {
          setExpanded({ [data.holdings[0].symbol]: true });
        }
      }, 300);

    } catch (e: any) {
      setError(e.message || "Scan failed");
      setLoading(false);
      if (progressRef.current) clearInterval(progressRef.current);
    }
  }, [holdings]);

  const toggleExpand = (symbol: string) => {
    setExpanded(prev => ({ ...prev, [symbol]: !prev[symbol] }));
  };

  const sortedHoldings = result?.holdings?.slice().sort((a, b) => {
    const order = { SELL: 0, BUY: 1, HOLD: 2 };
    const aAction = a.recommendation?.action || "HOLD";
    const bAction = b.recommendation?.action || "HOLD";
    return (order[aAction as keyof typeof order] ?? 3) - (order[bAction as keyof typeof order] ?? 3);
  }) || [];

  return (
    <div className="bg-gradient-to-br from-slate-800/60 to-slate-900/80 border border-slate-700/40 rounded-2xl overflow-hidden backdrop-blur-sm shadow-2xl" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {/* ═══ Header ═══ */}
      <div style={{
        padding: "16px 20px",
        borderBottom: "1px solid var(--border-primary)",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        background: "rgba(17,26,46,0.3)",
        flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ position: "relative" }}>
            <div style={{
              background: "rgba(139,92,246,0.15)", padding: 8, borderRadius: 10,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <Brain size={15} style={{ color: "#8b5cf6" }} />
            </div>
            {loading && (
              <div style={{
                position: "absolute", top: -2, right: -2, width: 10, height: 10,
                background: "#8b5cf6", borderRadius: "50%",
              }} className="animate-pulse" />
            )}
          </div>
          <div>
            <h2 style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: 8 }}>
              Portfolio Pattern Agent
              <span style={{ fontSize: 9, padding: "2px 6px", background: "rgba(139,92,246,0.2)", color: "#a78bfa", borderRadius: 20, border: "1px solid rgba(139,92,246,0.3)" }}>AI</span>
            </h2>
            <span style={{ fontSize: 10, color: "var(--text-muted)" }}>Candlestick analysis • BUY / SELL / HOLD signals</span>
          </div>
        </div>

        <button
          onClick={runScan}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-violet-600 to-blue-600 hover:from-violet-500 hover:to-blue-500 disabled:from-slate-700 disabled:to-slate-700 text-white text-xs font-semibold rounded-xl transition-all duration-200 shadow-lg hover:shadow-violet-500/20 disabled:shadow-none"
        >
          {loading ? (
            <>
              <Loader2 size={14} className="animate-spin" />
              Scanning...
            </>
          ) : result ? (
            <>
              <RefreshCw size={14} />
              Re-Scan
            </>
          ) : (
            <>
              <Zap size={14} />
              Analyze Portfolio
            </>
          )}
        </button>
      </div>

      {/* ═══ Progress Bar (during scan) ═══ */}
      {loading && (
        <div className="px-5 py-3 border-b border-slate-700/20">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] text-slate-400">
              <Activity size={12} className="inline mr-1 text-violet-400" />
              Analyzing {holdings.length} holdings...
            </span>
            <span className="text-[10px] text-slate-500">{scanProgress.toFixed(0)}%</span>
          </div>
          <div className="h-1 bg-slate-700/50 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-violet-500 to-blue-400 rounded-full transition-all duration-500"
              style={{ width: `${scanProgress}%` }}
            />
          </div>
        </div>
      )}

      {/* ═══ Summary Bar ═══ */}
      {result && !loading && (
        <div className="px-5 py-3 border-b border-slate-700/20 flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-5">
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-xs text-slate-400">
                <span className="font-bold text-emerald-400">{result.summary.buy}</span> Buy
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full bg-red-400 animate-pulse" />
              <span className="text-xs text-slate-400">
                <span className="font-bold text-red-400">{result.summary.sell}</span> Sell
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full bg-amber-400" />
              <span className="text-xs text-slate-400">
                <span className="font-bold text-amber-400">{result.summary.hold}</span> Hold
              </span>
            </div>
          </div>
          <span className="text-[10px] text-slate-600 ml-auto">
            {result.summary.scanned}/{result.summary.total} scanned • {(result.latency_ms / 1000).toFixed(1)}s
          </span>
        </div>
      )}

      {/* ═══ Holdings List ═══ */}
      {result && !loading && (
        <div className="px-4 py-3 space-y-2 max-h-[600px] overflow-y-auto custom-scrollbar">
          {sortedHoldings.map((h) => (
            <HoldingCard
              key={h.symbol}
              data={h}
              isExpanded={!!expanded[h.symbol]}
              onToggle={() => toggleExpand(h.symbol)}
            />
          ))}
        </div>
      )}

      {/* ═══ Empty State ═══ */}
      {!result && !loading && !error && (
        <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "20px 24px", gap: 16 }}>
          <div style={{ position: "relative" }}>
            <div style={{ width: 64, height: 64, borderRadius: 16, background: "rgba(30,40,60,0.5)", border: "1px solid rgba(100,116,139,0.2)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <BarChart3 size={28} style={{ color: "rgba(100,116,139,0.5)" }} />
            </div>
            <div style={{ position: "absolute", bottom: -4, right: -4, padding: 4, background: "rgba(139,92,246,0.2)", borderRadius: 8, border: "1px solid rgba(139,92,246,0.3)" }}>
              <Brain size={12} style={{ color: "#a78bfa" }} />
            </div>
          </div>
          <div style={{ textAlign: "center" }}>
            <p style={{ fontSize: 14, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 6 }}>Autonomous Pattern Scanner</p>
            <p style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.6, maxWidth: 240 }}>
              Scans every portfolio holding for candlestick patterns, trend signals, and generates AI-powered BUY / SELL / HOLD recommendations.
            </p>
          </div>
          <button
            onClick={runScan}
            style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 20px", background: "linear-gradient(135deg, #7c3aed, #2563eb)", color: "#fff", fontSize: 12, fontWeight: 600, borderRadius: 12, border: "none", cursor: "pointer", boxShadow: "0 4px 16px rgba(124,58,237,0.3)" }}
          >
            <Zap size={14} />
            Run Analysis
          </button>
        </div>
      )}

      {/* ═══ Error ═══ */}
      {error && (
        <div className="px-5 py-4">
          <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2.5 flex items-center gap-2">
            <AlertTriangle size={14} className="text-red-400 shrink-0" />
            <span className="text-xs text-red-300">{error}</span>
          </div>
        </div>
      )}

      {/* CSS animation */}
      <style jsx>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(-4px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fadeIn { animation: fadeIn 0.3s ease-out; }
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(148, 163, 184, 0.2); border-radius: 4px; }
      `}</style>
    </div>
  );
}

"use client";
import { useState, useCallback } from "react";
import { Search, TrendingUp, TrendingDown, Activity, Loader2, BarChart3, Brain, AlertCircle } from "lucide-react";

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/api/v1";

interface PatternResult {
  ticker: string;
  interval: string;
  lookback: number;
  data_points: number;
  signals: {
    macd_divergence: boolean;
    ma_crossover: boolean;
    macd_crossover_type: string | null;
    ma_crossover_type: string | null;
  };
  backtest: {
    win_rate_pct: number;
    avg_return_pct: number;
    max_drawdown_pct: number;
    total_trades: number;
    sharpe_ratio: number | null;
    profit_factor: number | null;
  };
  summary: string;
  latency_ms: number;
}

export default function PatternScanCard() {
  const [ticker, setTicker] = useState("RELIANCE");
  const [result, setResult] = useState<PatternResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runScan = useCallback(async () => {
    if (!ticker) return;
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const resp = await fetch(
        `${API_BASE}/patterns/scan/${ticker.toUpperCase()}?lookback=365`
      );
      const data = await resp.json();

      if (!resp.ok) {
        throw new Error(data.error || data.detail || `HTTP ${resp.status}`);
      }

      setResult(data);
    } catch (e: any) {
      setError(e.message || "Scan failed");
    } finally {
      setLoading(false);
    }
  }, [ticker]);

  const hasSignals = result?.signals.macd_divergence || result?.signals.ma_crossover;

  return (
    <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/90 border border-slate-700/50 rounded-xl overflow-hidden backdrop-blur-sm shadow-lg">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-700/40 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-blue-500/20 rounded-lg">
            <Brain size={14} className="text-blue-400" />
          </div>
          <span className="text-sm font-semibold text-slate-200">Pattern Intelligence</span>
        </div>
        {result && (
          <span className="text-[10px] text-slate-500">
            {result.data_points} bars • {result.latency_ms.toFixed(0)}ms
          </span>
        )}
      </div>

      {/* Search */}
      <div className="p-3 flex gap-2">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && runScan()}
            placeholder="Enter NSE ticker..."
            className="w-full bg-slate-900/60 border border-slate-700/50 rounded-lg pl-9 pr-3 py-1.5 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-500/50"
          />
        </div>
        <button
          onClick={runScan}
          disabled={loading || !ticker}
          className="px-4 py-1.5 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 disabled:from-slate-600 disabled:to-slate-700 text-white text-sm font-medium rounded-lg transition-all flex items-center gap-1.5"
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Activity size={14} />}
          Scan
        </button>
      </div>

      {/* Results */}
      {loading && (
        <div className="px-3 pb-4 flex items-center justify-center gap-2 text-slate-400 text-sm">
          <Loader2 size={16} className="animate-spin" />
          Analyzing {ticker}...
        </div>
      )}

      {error && (
        <div className="px-3 pb-3">
          <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 flex items-center gap-2">
            <AlertCircle size={14} className="text-red-400 shrink-0" />
            <span className="text-xs text-red-300">{error}</span>
          </div>
        </div>
      )}

      {result && !loading && (
        <div className="px-3 pb-3 space-y-2.5">
          {/* Signal Badges */}
          <div className="flex gap-2">
            <div className={`flex-1 rounded-lg px-3 py-2 border ${
              result.signals.macd_divergence
                ? result.signals.macd_crossover_type === "bullish"
                  ? "bg-emerald-500/10 border-emerald-500/30"
                  : "bg-red-500/10 border-red-500/30"
                : "bg-slate-800/40 border-slate-700/30"
            }`}>
              <div className="flex items-center gap-1.5 mb-1">
                <BarChart3 size={12} className={result.signals.macd_divergence ? "text-amber-400" : "text-slate-500"} />
                <span className="text-[11px] font-medium text-slate-300">MACD Divergence</span>
              </div>
              <span className={`text-xs font-semibold ${
                result.signals.macd_divergence
                  ? result.signals.macd_crossover_type === "bullish" ? "text-emerald-400" : "text-red-400"
                  : "text-slate-500"
              }`}>
                {result.signals.macd_divergence
                  ? `${result.signals.macd_crossover_type === "bullish" ? "↑" : "↓"} ${result.signals.macd_crossover_type}`
                  : "Not detected"}
              </span>
            </div>

            <div className={`flex-1 rounded-lg px-3 py-2 border ${
              result.signals.ma_crossover
                ? result.signals.ma_crossover_type === "golden_cross"
                  ? "bg-emerald-500/10 border-emerald-500/30"
                  : "bg-red-500/10 border-red-500/30"
                : "bg-slate-800/40 border-slate-700/30"
            }`}>
              <div className="flex items-center gap-1.5 mb-1">
                {result.signals.ma_crossover && result.signals.ma_crossover_type === "golden_cross"
                  ? <TrendingUp size={12} className="text-emerald-400" />
                  : result.signals.ma_crossover
                    ? <TrendingDown size={12} className="text-red-400" />
                    : <Activity size={12} className="text-slate-500" />
                }
                <span className="text-[11px] font-medium text-slate-300">MA Crossover</span>
              </div>
              <span className={`text-xs font-semibold ${
                result.signals.ma_crossover
                  ? result.signals.ma_crossover_type === "golden_cross" ? "text-emerald-400" : "text-red-400"
                  : "text-slate-500"
              }`}>
                {result.signals.ma_crossover
                  ? result.signals.ma_crossover_type === "golden_cross" ? "↑ Golden Cross" : "↓ Death Cross"
                  : "Not detected"}
              </span>
            </div>
          </div>

          {/* Backtest Metrics */}
          {result.backtest.total_trades > 0 && (
            <div className="grid grid-cols-3 gap-1.5">
              <div className="bg-slate-800/50 rounded-lg px-2.5 py-2 text-center">
                <p className={`text-lg font-bold ${result.backtest.win_rate_pct >= 50 ? "text-emerald-400" : "text-amber-400"}`}>
                  {result.backtest.win_rate_pct}%
                </p>
                <p className="text-[10px] text-slate-500">Win Rate</p>
              </div>
              <div className="bg-slate-800/50 rounded-lg px-2.5 py-2 text-center">
                <p className={`text-lg font-bold ${result.backtest.avg_return_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                  {result.backtest.avg_return_pct > 0 ? "+" : ""}{result.backtest.avg_return_pct}%
                </p>
                <p className="text-[10px] text-slate-500">Avg Return</p>
              </div>
              <div className="bg-slate-800/50 rounded-lg px-2.5 py-2 text-center">
                <p className="text-lg font-bold text-red-400">
                  {result.backtest.max_drawdown_pct}%
                </p>
                <p className="text-[10px] text-slate-500">Max DD</p>
              </div>
            </div>
          )}

          {/* LLM Summary */}
          {result.summary && (
            <div className="bg-slate-800/30 border border-slate-700/20 rounded-lg px-3 py-2">
              <p className="text-xs text-slate-300 leading-relaxed">{result.summary}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

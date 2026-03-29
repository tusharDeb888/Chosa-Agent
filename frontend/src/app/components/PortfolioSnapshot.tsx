"use client";
import { useState, useEffect } from "react";
import { TrendingUp, TrendingDown, Clock, Sun, Moon, Calendar, AlertCircle, Newspaper } from "lucide-react";

interface MarketStatus {
  is_open: boolean;
  status: string;
  message: string;
  current_time_ist: string;
  last_trading_date: string;
}

interface CandleData {
  count: number;
  last_price: number;
  day_high: number;
  day_low: number;
  total_volume: number;
  candles: Array<{
    timestamp: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }>;
}

interface BatchResponse {
  date: string;
  interval: string;
  market_status: MarketStatus;
  data: Record<string, CandleData>;
}

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/api/v1";

export function MarketStatusBanner() {
  const [status, setStatus] = useState<MarketStatus | null>(null);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/market/status`);
        if (res.ok) setStatus(await res.json());
      } catch { /* ignore */ }
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  if (!status) return null;

  const statusConfig: Record<string, { bg: string; border: string; icon: typeof Sun; color: string }> = {
    OPEN: { bg: "rgba(16,185,129,0.08)", border: "rgba(16,185,129,0.2)", icon: Sun, color: "#10b981" },
    WEEKEND: { bg: "rgba(139,92,246,0.08)", border: "rgba(139,92,246,0.2)", icon: Calendar, color: "#8b5cf6" },
    PRE_MARKET: { bg: "rgba(59,130,246,0.08)", border: "rgba(59,130,246,0.2)", icon: Sun, color: "#3b82f6" },
    POST_MARKET: { bg: "rgba(245,158,11,0.08)", border: "rgba(245,158,11,0.2)", icon: Moon, color: "#f59e0b" },
    HOLIDAY: { bg: "rgba(239,68,68,0.08)", border: "rgba(239,68,68,0.2)", icon: Calendar, color: "#ef4444" },
  };

  const cfg = statusConfig[status.status] || statusConfig.POST_MARKET;
  const StatusIcon = cfg.icon;

  return (
    <div style={{
      padding: "10px 20px",
      background: cfg.bg,
      border: `1px solid ${cfg.border}`,
      borderRadius: 12,
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      marginBottom: 16,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <StatusIcon size={14} color={cfg.color} />
        <span style={{ fontSize: 12, fontWeight: 700, color: cfg.color }}>{status.status}</span>
        <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>{status.message}</span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <span style={{ fontSize: 10, color: "var(--text-muted)", display: "flex", alignItems: "center", gap: 4 }}>
          <Clock size={10} /> {status.current_time_ist} IST
        </span>
        <span style={{ fontSize: 10, color: "var(--text-muted)" }}>
          Last traded: <span style={{ color: "var(--text-secondary)", fontWeight: 600 }}>{status.last_trading_date}</span>
        </span>
        <span style={{
          fontSize: 9, padding: "2px 8px", borderRadius: 6,
          background: "rgba(6,182,212,0.1)", border: "1px solid rgba(6,182,212,0.2)",
          color: "#06b6d4", fontWeight: 700, display: "flex", alignItems: "center", gap: 3,
        }}>
          <Newspaper size={9} /> News Radar: ACTIVE
        </span>
      </div>
    </div>
  );
}

export function PortfolioSnapshot() {
  const [data, setData] = useState<BatchResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch(`${API_BASE}/market/candles-batch?symbols=RELIANCE,TCS,HDFCBANK,ICICIBANK,SBIN,INFY,ITC,BHARTIARTL&interval=30minute`);
        if (res.ok) {
          const json = await res.json();
          setData(json);
        }
      } catch { /* ignore */ }
      finally { setLoading(false); }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="card" style={{ padding: 20, textAlign: "center" }}>
        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Loading real market data...</span>
      </div>
    );
  }

  if (!data || Object.keys(data.data).length === 0) return null;

  // Don't show when market is open — live alerts take over
  if (data.market_status?.is_open) return null;

  return (
    <div className="card" style={{ overflow: "hidden", marginBottom: 20 }}>
      <div style={{
        padding: "14px 20px",
        borderBottom: "1px solid var(--border-primary)",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        background: "rgba(17,26,46,0.3)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            background: "rgba(6,182,212,0.15)", padding: 7, borderRadius: 9,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <TrendingUp size={14} color="#06b6d4" />
          </div>
          <div>
            <h2 style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)" }}>
              Portfolio Snapshot — Real NSE Data
            </h2>
            <span style={{ fontSize: 10, color: "var(--text-muted)" }}>
              Last trading day: {data.date} • Source: Upstox API
            </span>
          </div>
        </div>
        <span style={{
          fontSize: 9, fontWeight: 700, letterSpacing: "0.05em",
          color: "#06b6d4", background: "rgba(6,182,212,0.1)",
          padding: "4px 12px", borderRadius: 9999, border: "1px solid rgba(6,182,212,0.2)",
        }}>
          {Object.keys(data.data).length} STOCKS
        </span>
      </div>

      <div style={{ padding: 16 }}>
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: 12,
        }}>
          {Object.entries(data.data).map(([symbol, sdata]) => {
            if (!sdata.candles || sdata.candles.length === 0) return null;

            const openPrice = sdata.candles[sdata.candles.length - 1].open;
            const closePrice = sdata.last_price;
            const change = closePrice - openPrice;
            const changePct = (change / openPrice) * 100;
            const isUp = change >= 0;

            // Build mini sparkline from candle closes
            const closes = sdata.candles.map(c => c.close).reverse(); // chronological order
            const minP = Math.min(...closes);
            const maxP = Math.max(...closes);
            const range = maxP - minP || 1;

            const sparklinePoints = closes.map((p, i) => {
              const x = (i / (closes.length - 1)) * 120;
              const y = 28 - ((p - minP) / range) * 24;
              return `${x},${y}`;
            }).join(" ");

            return (
              <div key={symbol} style={{
                padding: "14px 16px",
                background: "rgba(10,14,26,0.5)",
                border: "1px solid var(--border-primary)",
                borderRadius: 12,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                transition: "border-color 0.2s ease",
              }}
              onMouseEnter={e => (e.currentTarget.style.borderColor = isUp ? "#10b98140" : "#ef444440")}
              onMouseLeave={e => (e.currentTarget.style.borderColor = "var(--border-primary)")}
              >
                {/* Left: Symbol + Price */}
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                    <span style={{ fontSize: 14, fontWeight: 800, color: "var(--text-primary)", letterSpacing: "-0.01em" }}>
                      {symbol}
                    </span>
                    <span style={{
                      fontSize: 9, padding: "2px 6px", borderRadius: 4,
                      background: isUp ? "rgba(16,185,129,0.1)" : "rgba(239,68,68,0.1)",
                      color: isUp ? "#10b981" : "#ef4444",
                      fontWeight: 700,
                      display: "flex", alignItems: "center", gap: 2,
                    }}>
                      {isUp ? <TrendingUp size={8} /> : <TrendingDown size={8} />}
                      {isUp ? "+" : ""}{changePct.toFixed(2)}%
                    </span>
                  </div>
                  <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                    <span style={{
                      fontSize: 18, fontWeight: 900, color: "var(--text-primary)",
                      fontFamily: "'JetBrains Mono', monospace", letterSpacing: "-0.02em",
                    }}>
                      ₹{closePrice.toLocaleString("en-IN", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
                    </span>
                    <span style={{
                      fontSize: 11, fontWeight: 600,
                      color: isUp ? "#10b981" : "#ef4444",
                    }}>
                      {isUp ? "+" : ""}₹{change.toFixed(1)}
                    </span>
                  </div>
                  <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 4, display: "flex", gap: 12 }}>
                    <span>H: ₹{sdata.day_high.toLocaleString("en-IN")}</span>
                    <span>L: ₹{sdata.day_low.toLocaleString("en-IN")}</span>
                    <span>Vol: {(sdata.total_volume / 1e6).toFixed(1)}M</span>
                  </div>
                </div>

                {/* Right: Mini Sparkline */}
                <div style={{ width: 130, height: 36, flexShrink: 0 }}>
                  <svg viewBox="0 0 120 32" style={{ width: "100%", height: "100%" }}>
                    <defs>
                      <linearGradient id={`grad-${symbol}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={isUp ? "#10b981" : "#ef4444"} stopOpacity="0.2" />
                        <stop offset="100%" stopColor={isUp ? "#10b981" : "#ef4444"} stopOpacity="0" />
                      </linearGradient>
                    </defs>
                    <polygon
                      points={`0,30 ${sparklinePoints} 120,30`}
                      fill={`url(#grad-${symbol})`}
                    />
                    <polyline
                      points={sparklinePoints}
                      fill="none"
                      stroke={isUp ? "#10b981" : "#ef4444"}
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

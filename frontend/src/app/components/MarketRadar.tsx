"use client";
import { useState, useEffect } from "react";
import { Radio, Activity, Zap, Shield, Newspaper, Moon, Clock, Calendar, TrendingUp, BarChart2 } from "lucide-react";

interface MarketStatus {
  is_open: boolean;
  status: string;
  message: string;
  current_time_ist: string;
  last_trading_date: string;
}

interface RadarProps {
  isActive: boolean;
  tickCount: number;
  symbolCount?: number;
  lastAnomalyAt?: string;
  alertCount: number;
}

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/api/v1";

const ANOMALY_TYPES = [
  { type: "VOLUME_SPIKE",     icon: "📊", label: "Volume",   color: "#10b981" },
  { type: "PRICE_DEVIATION",  icon: "📈", label: "Price",    color: "#3b82f6" },
  { type: "SPREAD_ANOMALY",   icon: "📉", label: "Spread",   color: "#f59e0b" },
  { type: "MOMENTUM_BREAK",   icon: "⚡", label: "Momentum", color: "#8b5cf6" },
  { type: "CORPORATE_FILING", icon: "📋", label: "Filing",   color: "#06b6d4" },
];

export default function MarketRadar({ isActive, tickCount, symbolCount = 20, lastAnomalyAt, alertCount }: RadarProps) {
  const [sweepAngle, setSweepAngle] = useState(0);
  const [blips, setBlips] = useState<Array<{ x: number; y: number; opacity: number; color: string }>>([]);
  const [marketStatus, setMarketStatus] = useState<MarketStatus | null>(null);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/market/status`);
        if (res.ok) setMarketStatus(await res.json());
      } catch { /* ignore */ }
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const marketOpen = marketStatus?.is_open ?? false;
  const radarActive = isActive; // Animation runs always if active

  useEffect(() => {
    if (!radarActive) return;
    const interval = setInterval(() => setSweepAngle(prev => (prev + 3) % 360), 50);
    return () => clearInterval(interval);
  }, [radarActive]);

  useEffect(() => {
    if (!radarActive) return;
    const interval = setInterval(() => {
      const angle = Math.random() * Math.PI * 2;
      const dist = 0.3 + Math.random() * 0.6;
      const colors = ["#10b981", "#3b82f6", "#f59e0b", "#8b5cf6", "#06b6d4"];
      setBlips(prev => [
        ...prev.slice(-8),
        { x: 50 + Math.cos(angle) * dist * 44, y: 50 + Math.sin(angle) * dist * 44, opacity: 1, color: colors[Math.floor(Math.random() * colors.length)] },
      ]);
    }, 2000);
    return () => clearInterval(interval);
  }, [radarActive]);

  useEffect(() => {
    const interval = setInterval(() => {
      setBlips(prev => prev.map(b => ({ ...b, opacity: Math.max(0, b.opacity - 0.05) })).filter(b => b.opacity > 0));
    }, 200);
    return () => clearInterval(interval);
  }, []);

  const timeAgo = lastAnomalyAt
    ? `${Math.max(1, Math.round((Date.now() - new Date(lastAnomalyAt).getTime()) / 60000))}m ago`
    : "—";

  const getStatusBadge = () => {
    if (!isActive) return { text: "PAUSED", color: "#5a6a82", bg: "rgba(90,106,130,0.1)", border: "rgba(90,106,130,0.2)" };
    return { text: "LIVE SCANNING", color: "#10b981", bg: "rgba(16,185,129,0.1)", border: "rgba(16,185,129,0.25)" };
  };
  const badge = getStatusBadge();

  const stats = [
    { label: "Ticks", value: tickCount.toLocaleString(), icon: Activity, color: marketOpen ? "#10b981" : "#5a6a82" },
    { label: "Alerts", value: alertCount.toString(), icon: Shield, color: "#8b5cf6" },
    { label: "Symbols", value: symbolCount.toString(), icon: BarChart2, color: "#06b6d4" },
    { label: "Last Signal", value: timeAgo, icon: Zap, color: "#f59e0b" },
  ];

  return (
    <div style={{
      background: "rgba(10,14,26,0.6)",
      border: "1px solid var(--border-primary)",
      borderRadius: 16,
      overflow: "hidden",
      height: "100%",
      display: "flex",
      flexDirection: "column",
      position: "relative",
    }}>
      {/* Ambient glow */}
      {radarActive && (
        <div style={{
          position: "absolute", top: -40, right: -40, width: 180, height: 180,
          background: "radial-gradient(circle, rgba(6,182,212,0.08) 0%, transparent 70%)",
          borderRadius: "50%", pointerEvents: "none",
        }} />
      )}

      {/* ── Header ── */}
      <div style={{
        padding: "14px 20px",
        borderBottom: "1px solid var(--border-primary)",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        background: "rgba(17,26,46,0.3)", flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Radio size={14} color={radarActive ? "#06b6d4" : "#5a6a82"}
            style={radarActive ? { animation: "pulse 2s ease-in-out infinite" } : {}} />
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", color: radarActive ? "#06b6d4" : "var(--text-muted)" }}>
            Market Radar
          </span>
          {/* Status badge */}
          <span style={{
            fontSize: 9, padding: "2px 8px", borderRadius: 6, fontWeight: 700,
            color: badge.color, background: badge.bg, border: `1px solid ${badge.border}`,
          }}>
            {badge.text}
          </span>
          {/* News always-on */}
          <span style={{
            fontSize: 9, padding: "2px 8px", borderRadius: 6, fontWeight: 700,
            background: "rgba(6,182,212,0.08)", border: "1px solid rgba(6,182,212,0.18)",
            color: "#06b6d4", display: "flex", alignItems: "center", gap: 3,
          }}>
            <Newspaper size={9} /> News Radar: 24/7
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {marketStatus && (
            <span style={{ fontSize: 10, color: "var(--text-dim)", fontFamily: "'JetBrains Mono', monospace", display: "flex", alignItems: "center", gap: 4 }}>
              <Clock size={9} /> {marketStatus.current_time_ist} IST
            </span>
          )}
        </div>
      </div>

      {/* ── Body ── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: "16px 20px", gap: 14 }}>

        {/* Top row: Radar + market message */}
        <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
          {/* Radar SVG — larger */}
          <div style={{ width: 110, height: 110, flexShrink: 0 }}>
            <svg viewBox="0 0 100 100" style={{ width: "100%", height: "100%" }}>
              {[15, 28, 41].map(r => (
                <circle key={r} cx="50" cy="50" r={r} fill="none" stroke="rgba(6,182,212,0.07)" strokeWidth="0.6" />
              ))}
              <line x1="50" y1="9" x2="50" y2="91" stroke="rgba(6,182,212,0.05)" strokeWidth="0.5" />
              <line x1="9" y1="50" x2="91" y2="50" stroke="rgba(6,182,212,0.05)" strokeWidth="0.5" />
              <line x1="19" y1="19" x2="81" y2="81" stroke="rgba(6,182,212,0.04)" strokeWidth="0.5" />
              <line x1="81" y1="19" x2="19" y2="81" stroke="rgba(6,182,212,0.04)" strokeWidth="0.5" />

              {radarActive && (
                <g transform={`rotate(${sweepAngle} 50 50)`}>
                  <defs>
                    <radialGradient id="sweepGrad" cx="50%" cy="100%" r="100%">
                      <stop offset="0%" stopColor="rgba(6,182,212,0)" />
                      <stop offset="100%" stopColor="rgba(6,182,212,0.25)" />
                    </radialGradient>
                  </defs>
                  <path d={`M50,50 L50,9 A41,41 0 0,1 ${50 + 41 * Math.sin(Math.PI / 5)},${50 - 41 * Math.cos(Math.PI / 5)} Z`}
                    fill="url(#sweepGrad)" />
                  <line x1="50" y1="50" x2="50" y2="9" stroke="#06b6d4" strokeWidth="1.2" opacity="0.7" />
                </g>
              )}



              {blips.map((b, i) => (
                <g key={i}>
                  <circle cx={b.x} cy={b.y} r="3.5" fill={b.color} opacity={b.opacity * 0.2} />
                  <circle cx={b.x} cy={b.y} r="1.8" fill={b.color} opacity={b.opacity} />
                </g>
              ))}

              <circle cx="50" cy="50" r="2.5" fill={marketOpen ? "#06b6d4" : "#5a6a82"} opacity="0.9" />
            </svg>
          </div>

          {/* Market status + last trading info */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <TrendingUp size={11} color="#10b981" />
              <span style={{ fontSize: 11, color: "#10b981", fontWeight: 600 }}>Live data streaming</span>
            </div>
          </div>
        </div>

        {/* ── Stats grid ── */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          {stats.map(({ label, value, icon: Icon, color }) => (
            <div key={label} style={{
              padding: "10px 12px", borderRadius: 10,
              background: "rgba(10,14,26,0.5)", border: "1px solid rgba(255,255,255,0.04)",
              display: "flex", alignItems: "center", gap: 8,
            }}>
              <div style={{ padding: 6, borderRadius: 8, background: `${color}15`, flexShrink: 0 }}>
                <Icon size={12} color={color} />
              </div>
              <div>
                <div style={{ fontSize: 16, fontWeight: 800, color, fontFamily: "'JetBrains Mono', monospace", lineHeight: 1 }}>
                  {value}
                </div>
                <div style={{ fontSize: 9, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginTop: 2 }}>
                  {label}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* ── Anomaly type legend ── */}
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: "auto" }}>
          {ANOMALY_TYPES.map(a => (
            <span key={a.type} style={{
              fontSize: 9, padding: "3px 9px", borderRadius: 6, fontWeight: 600,
              background: `${a.color}10`, color: a.color, border: `1px solid ${a.color}20`,
              display: "flex", alignItems: "center", gap: 4,
            }}>
              <span>{a.icon}</span> {a.label}
            </span>
          ))}
        </div>

      </div>
    </div>
  );
}

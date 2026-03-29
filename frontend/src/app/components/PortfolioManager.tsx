"use client";
import { useState, useEffect, useCallback } from "react";
import {
  Plus, X, TrendingUp, TrendingDown, DollarSign,
  PieChart, Activity, Briefcase, RefreshCw, BarChart3,
  ArrowUpRight, ArrowDownRight, Trash2, Edit3, Check, ChevronDown, Star, Eye,
} from "lucide-react";

/* ─── Types ─── */
interface Holding {
  symbol: string;
  qty: number;
  buy_price: number;
}

interface InstrumentMeta {
  symbol: string;
  name: string;
}

interface EnrichedHolding extends Holding {
  current_price: number;
  invested: number;
  current_value: number;
  pnl: number;
  pnl_pct: number;
  day_change: number;
  day_change_pct: number;
  day_high: number;
  day_low: number;
  total_volume: number;
  candles: Array<{
    timestamp: string; open: number; high: number;
    low: number; close: number; volume: number;
  }>;
}

interface PortfolioValuation {
  date: string;
  holdings: EnrichedHolding[];
  total_invested: number;
  total_current: number;
  total_pnl: number;
  total_pnl_pct: number;
  day_change: number;
}

interface HistoryCandle {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/api/v1";

const STORAGE_KEY = "alpha-hunter-portfolio";

/* ─── Helpers ─── */
function loadPortfolio(): Holding[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

function savePortfolio(holdings: Holding[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(holdings));
  // Dispatch storage event so KPI strip in page.tsx updates immediately
  try {
    window.dispatchEvent(new StorageEvent("storage", { key: STORAGE_KEY, newValue: JSON.stringify(holdings) }));
  } catch {}
}

function formatINR(n: number): string {
  return "₹" + n.toLocaleString("en-IN", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

function formatLargeINR(n: number): string {
  if (Math.abs(n) >= 1e7) return "₹" + (n / 1e7).toFixed(2) + " Cr";
  if (Math.abs(n) >= 1e5) return "₹" + (n / 1e5).toFixed(2) + " L";
  return "₹" + n.toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

/* ─── Sparkline Renderer ─── */
function Sparkline({ candles, isUp, height = 36, width = 140 }: {
  candles: Array<{ close: number }>; isUp: boolean; height?: number; width?: number;
}) {
  if (!candles || candles.length < 2) return null;
  const closes = [...candles].reverse().map(c => c.close);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const range = max - min || 1;
  const svgW = width - 8;
  const svgH = height - 4;
  const pts = closes.map((p, i) => {
    const x = (i / (closes.length - 1)) * svgW;
    const y = svgH - ((p - min) / range) * (svgH - 4) - 2;
    return `${x},${y}`;
  }).join(" ");

  const color = isUp ? "#10b981" : "#ef4444";
  const id = `sp-${Math.random().toString(36).slice(2, 8)}`;

  return (
    <svg viewBox={`0 0 ${svgW} ${svgH}`} style={{ width, height }}>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.2" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`0,${svgH} ${pts} ${svgW},${svgH}`} fill={`url(#${id})`} />
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/* ─── Mini Donut Chart ─── */
function PortfolioDonut({ holdings }: { holdings: EnrichedHolding[] }) {
  const colors = ["#06b6d4", "#10b981", "#8b5cf6", "#f59e0b", "#3b82f6", "#ef4444", "#ec4899", "#14b8a6", "#f97316", "#6366f1"];
  const total = holdings.reduce((a, h) => a + h.current_value, 0);
  if (total === 0) return null;

  let cumAngle = 0;
  const arcs = holdings.map((h, i) => {
    const fraction = h.current_value / total;
    const startAngle = cumAngle;
    cumAngle += fraction * 360;
    const endAngle = cumAngle;
    const color = colors[i % colors.length];
    return { symbol: h.symbol, fraction, startAngle, endAngle, color, value: h.current_value };
  });

  const r = 38;
  const cx = 50;
  const cy = 50;

  function describeArc(startDeg: number, endDeg: number) {
    const startRad = ((startDeg - 90) * Math.PI) / 180;
    const endRad = ((endDeg - 90) * Math.PI) / 180;
    const x1 = cx + r * Math.cos(startRad);
    const y1 = cy + r * Math.sin(startRad);
    const x2 = cx + r * Math.cos(endRad);
    const y2 = cy + r * Math.sin(endRad);
    const largeArc = endDeg - startDeg > 180 ? 1 : 0;
    return `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2} Z`;
  }

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
      <svg viewBox="0 0 100 100" style={{ width: 110, height: 110, flexShrink: 0 }}>
        {arcs.map((a, i) => (
          <path key={i} d={describeArc(a.startAngle, a.endAngle)}
            fill={a.color} stroke="rgba(10,14,26,0.8)" strokeWidth="0.8" />
        ))}
        <circle cx={cx} cy={cy} r="20" fill="rgba(10,14,26,0.9)" />
        <text x={cx} y={cy - 3} textAnchor="middle" fontSize="6" fill="var(--text-muted)"
          fontFamily="'Inter',sans-serif">Portfolio</text>
        <text x={cx} y={cy + 7} textAnchor="middle" fontSize="7" fill="var(--text-primary)"
          fontWeight="700" fontFamily="'JetBrains Mono',monospace">{holdings.length}</text>
      </svg>
      <div style={{ display: "flex", flexDirection: "column", gap: 3, flex: 1 }}>
        {arcs.slice(0, 6).map(a => (
          <div key={a.symbol} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 10 }}>
            <div style={{ width: 8, height: 8, borderRadius: 2, background: a.color, flexShrink: 0 }} />
            <span style={{ color: "var(--text-secondary)", flex: 1 }}>{a.symbol}</span>
            <span style={{ color: "var(--text-muted)", fontFamily: "'JetBrains Mono', monospace", fontSize: 9 }}>
              {(a.fraction * 100).toFixed(1)}%
            </span>
          </div>
        ))}
        {arcs.length > 6 && (
          <span style={{ fontSize: 9, color: "var(--text-dim)", marginLeft: 14 }}>
            +{arcs.length - 6} more
          </span>
        )}
      </div>
    </div>
  );
}

/* ─── Multi-Day Chart Modal ─── */
function StockDetailModal({ symbol, onClose }: { symbol: string; onClose: () => void }) {
  const [history, setHistory] = useState<HistoryCandle[]>([]);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState(30);

  useEffect(() => {
    setLoading(true);
    fetch(`${API_BASE}/market/history/${symbol}?days=${period}&interval=day`)
      .then(r => r.json())
      .then(data => { setHistory(data.candles || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, [symbol, period]);

  // Reverse for chronological order
  const chronological = [...history].reverse();
  const closes = chronological.map(c => c.close);
  const minP = Math.min(...(closes.length ? closes : [0]));
  const maxP = Math.max(...(closes.length ? closes : [1]));
  const rangeP = maxP - minP || 1;
  const latest = closes[closes.length - 1] || 0;
  const first = closes[0] || latest;
  const totalChange = latest - first;
  const totalChangePct = first ? (totalChange / first) * 100 : 0;
  const isUp = totalChange >= 0;

  const W = 500, H = 180;
  const pts = closes.map((p, i) => {
    const x = (i / (closes.length - 1 || 1)) * W;
    const y = H - ((p - minP) / rangeP) * (H - 20) - 10;
    return `${x},${y}`;
  }).join(" ");

  // Volume bars
  const vols = chronological.map(c => c.volume);
  const maxVol = Math.max(...(vols.length ? vols : [1]));

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)",
      zIndex: 9999, display: "flex", alignItems: "center", justifyContent: "center",
      backdropFilter: "blur(4px)",
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        background: "rgba(15,20,35,0.98)", border: "1px solid var(--border-primary)",
        borderRadius: 16, width: "min(600px, 90vw)", padding: 24,
        boxShadow: "0 24px 80px rgba(0,0,0,0.5)",
      }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <div>
            <h2 style={{ fontSize: 20, fontWeight: 800, color: "var(--text-primary)" }}>{symbol}</h2>
            <span style={{ fontSize: 12, color: "var(--text-muted)" }}>NSE • Upstox Historical Data</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{
              display: "flex", alignItems: "center", gap: 4,
              color: isUp ? "#10b981" : "#ef4444", fontSize: 22, fontWeight: 900,
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              {formatINR(latest)}
              <span style={{ fontSize: 12, fontWeight: 600 }}>
                ({isUp ? "+" : ""}{totalChangePct.toFixed(2)}%)
              </span>
            </div>
            <button onClick={onClose} style={{
              background: "none", border: "1px solid var(--border-primary)",
              borderRadius: 8, padding: 6, cursor: "pointer", color: "var(--text-muted)",
            }}><X size={14} /></button>
          </div>
        </div>

        {/* Period selector */}
        <div style={{ display: "flex", gap: 6, marginBottom: 16 }}>
          {[7, 14, 30, 60, 90].map(p => (
            <button key={p} onClick={() => setPeriod(p)} style={{
              padding: "4px 12px", borderRadius: 6, fontSize: 11, fontWeight: 600,
              border: period === p ? "1px solid #06b6d4" : "1px solid var(--border-primary)",
              background: period === p ? "rgba(6,182,212,0.1)" : "transparent",
              color: period === p ? "#06b6d4" : "var(--text-muted)",
              cursor: "pointer",
            }}>
              {p}D
            </button>
          ))}
        </div>

        {/* Chart */}
        {loading ? (
          <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <RefreshCw size={20} className="spin" style={{ color: "var(--text-muted)" }} />
          </div>
        ) : closes.length > 1 ? (
          <div style={{
            background: "rgba(10,14,26,0.5)", borderRadius: 12,
            padding: "16px 12px", border: "1px solid var(--border-primary)",
          }}>
            <svg viewBox={`0 0 ${W} ${H + 40}`} style={{ width: "100%", height: 220 }}>
              {/* Grid lines */}
              {[0.25, 0.5, 0.75].map(f => (
                <line key={f} x1={0} y1={H - f * (H - 20) - 10} x2={W}
                  y2={H - f * (H - 20) - 10} stroke="rgba(255,255,255,0.04)" strokeWidth="0.5" />
              ))}

              {/* Price area */}
              <defs>
                <linearGradient id="hist-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={isUp ? "#10b981" : "#ef4444"} stopOpacity="0.15" />
                  <stop offset="100%" stopColor={isUp ? "#10b981" : "#ef4444"} stopOpacity="0" />
                </linearGradient>
              </defs>
              <polygon points={`0,${H} ${pts} ${W},${H}`} fill="url(#hist-grad)" />
              <polyline points={pts} fill="none" stroke={isUp ? "#10b981" : "#ef4444"}
                strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />

              {/* Volume bars */}
              {vols.map((v, i) => {
                const barW = (W / vols.length) * 0.6;
                const barH = (v / maxVol) * 30;
                const x = (i / (vols.length - 1 || 1)) * W - barW / 2;
                return (
                  <rect key={i} x={x} y={H + 40 - barH} width={barW} height={barH}
                    fill="rgba(6,182,212,0.15)" rx="1" />
                );
              })}

              {/* Price labels */}
              <text x={4} y={12} fontSize="8" fill="var(--text-dim)">{formatINR(maxP)}</text>
              <text x={4} y={H - 2} fontSize="8" fill="var(--text-dim)">{formatINR(minP)}</text>
            </svg>
          </div>
        ) : (
          <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)" }}>
            No historical data available
          </div>
        )}

        {/* Stats row */}
        {chronological.length > 0 && (
          <div style={{
            display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginTop: 16,
          }}>
            {[
              { label: "Period High", value: formatINR(maxP), color: "#10b981" },
              { label: "Period Low", value: formatINR(minP), color: "#ef4444" },
              { label: "Change", value: `${isUp ? "+" : ""}${formatINR(totalChange)}`, color: isUp ? "#10b981" : "#ef4444" },
              { label: "Avg Volume", value: `${(vols.reduce((a, b) => a + b, 0) / vols.length / 1e6).toFixed(1)}M`, color: "#06b6d4" },
            ].map(s => (
              <div key={s.label} style={{
                padding: "10px 12px", borderRadius: 10,
                background: "rgba(10,14,26,0.5)", border: "1px solid var(--border-primary)",
              }}>
                <div style={{ fontSize: 9, color: "var(--text-muted)", marginBottom: 4 }}>{s.label}</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: s.color, fontFamily: "'JetBrains Mono', monospace" }}>
                  {s.value}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Wishlist Tab ─── */
const WISHLIST_SYMBOLS = "RELIANCE,TCS,HDFCBANK,ICICIBANK,SBIN,INFY,ITC,BHARTIARTL";

function WishlistTab() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch(`${API_BASE}/market/candles-batch?symbols=${WISHLIST_SYMBOLS}&interval=30minute`);
        if (res.ok) setData(await res.json());
      } catch { /* ignore */ }
      finally { setLoading(false); }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: "center" }}>
        <RefreshCw size={18} className="spin" style={{ color: "var(--text-dim)", marginBottom: 8 }} />
        <p style={{ fontSize: 12, color: "var(--text-muted)" }}>Loading real NSE data...</p>
      </div>
    );
  }

  if (!data || !data.data || Object.keys(data.data).length === 0) {
    return (
      <div style={{ padding: 40, textAlign: "center" }}>
        <Star size={24} style={{ color: "var(--text-dim)", marginBottom: 8 }} />
        <p style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)" }}>No Market Data Available</p>
        <p style={{ fontSize: 11, color: "var(--text-muted)" }}>NSE data will appear during trading hours</p>
      </div>
    );
  }

  return (
    <div>
      {/* Wishlist header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Eye size={12} color="#06b6d4" />
          <span style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)" }}>
            Portfolio Snapshot — Real NSE Data
          </span>
          <span style={{ fontSize: 9, color: "var(--text-muted)" }}>
            Source: Upstox API • {data.date}
          </span>
        </div>
        <span style={{
          fontSize: 9, fontWeight: 700, letterSpacing: "0.05em",
          color: "#06b6d4", background: "rgba(6,182,212,0.1)",
          padding: "3px 10px", borderRadius: 9999, border: "1px solid rgba(6,182,212,0.2)",
        }}>
          {Object.keys(data.data).length} STOCKS
        </span>
      </div>

      {/* Stock cards grid */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
        gap: 10,
      }}>
        {Object.entries(data.data).map(([symbol, sdata]: [string, any]) => {
          if (!sdata.candles || sdata.candles.length === 0) return null;

          const openPrice = sdata.candles[sdata.candles.length - 1].open;
          const closePrice = sdata.last_price;
          const change = closePrice - openPrice;
          const changePct = (change / openPrice) * 100;
          const isUp = change >= 0;

          // Build mini sparkline from candle closes
          const closes = sdata.candles.map((c: any) => c.close).reverse();
          const minP = Math.min(...closes);
          const maxP = Math.max(...closes);
          const range = maxP - minP || 1;

          const sparklinePoints = closes.map((p: number, i: number) => {
            const x = (i / (closes.length - 1)) * 110;
            const y = 26 - ((p - minP) / range) * 22;
            return `${x},${y}`;
          }).join(" ");

          const gradId = `wl-grad-${symbol}`;

          return (
            <div key={symbol} style={{
              padding: "12px 14px",
              background: "rgba(10,14,26,0.5)",
              border: "1px solid var(--border-primary)",
              borderRadius: 12,
              display: "flex", alignItems: "center", justifyContent: "space-between",
              transition: "border-color 0.2s ease, transform 0.2s ease",
              cursor: "pointer",
            }}
            onMouseEnter={e => {
              e.currentTarget.style.borderColor = isUp ? "#10b98140" : "#ef444440";
              e.currentTarget.style.transform = "translateY(-1px)";
            }}
            onMouseLeave={e => {
              e.currentTarget.style.borderColor = "var(--border-primary)";
              e.currentTarget.style.transform = "translateY(0)";
            }}
            >
              {/* Left: Symbol + Price */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
                  <span style={{ fontSize: 13, fontWeight: 800, color: "var(--text-primary)", letterSpacing: "-0.01em" }}>
                    {symbol}
                  </span>
                  <span style={{
                    fontSize: 8, padding: "2px 5px", borderRadius: 4,
                    background: isUp ? "rgba(16,185,129,0.1)" : "rgba(239,68,68,0.1)",
                    color: isUp ? "#10b981" : "#ef4444",
                    fontWeight: 700, display: "flex", alignItems: "center", gap: 2,
                  }}>
                    {isUp ? <TrendingUp size={7} /> : <TrendingDown size={7} />}
                    {isUp ? "+" : ""}{changePct.toFixed(2)}%
                  </span>
                </div>
                <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
                  <span style={{
                    fontSize: 16, fontWeight: 900, color: "var(--text-primary)",
                    fontFamily: "'JetBrains Mono', monospace", letterSpacing: "-0.02em",
                  }}>
                    ₹{closePrice.toLocaleString("en-IN", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
                  </span>
                  <span style={{ fontSize: 10, fontWeight: 600, color: isUp ? "#10b981" : "#ef4444" }}>
                    {isUp ? "+" : ""}₹{change.toFixed(1)}
                  </span>
                </div>
                <div style={{ fontSize: 9, color: "var(--text-dim)", marginTop: 3, display: "flex", gap: 10 }}>
                  <span>H: ₹{sdata.day_high?.toLocaleString("en-IN") || "—"}</span>
                  <span>L: ₹{sdata.day_low?.toLocaleString("en-IN") || "—"}</span>
                  <span>Vol: {sdata.total_volume ? (sdata.total_volume / 1e6).toFixed(1) + "M" : "—"}</span>
                </div>
              </div>

              {/* Right: Mini Sparkline */}
              <div style={{ width: 120, height: 30, flexShrink: 0 }}>
                <svg viewBox="0 0 110 28" style={{ width: "100%", height: "100%" }}>
                  <defs>
                    <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={isUp ? "#10b981" : "#ef4444"} stopOpacity="0.2" />
                      <stop offset="100%" stopColor={isUp ? "#10b981" : "#ef4444"} stopOpacity="0" />
                    </linearGradient>
                  </defs>
                  <polygon points={`0,27 ${sparklinePoints} 110,27`} fill={`url(#${gradId})`} />
                  <polyline points={sparklinePoints} fill="none" stroke={isUp ? "#10b981" : "#ef4444"}
                    strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════════ */
/*        MAIN PORTFOLIO MANAGER COMPONENT        */
/* ═══════════════════════════════════════════════ */

export default function PortfolioManager() {
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [valuation, setValuation] = useState<PortfolioValuation | null>(null);
  const [loading, setLoading] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [activeTab, setActiveTab] = useState<"holdings" | "composition" | "wishlist">("holdings");
  const [detailSymbol, setDetailSymbol] = useState<string | null>(null);
  const [availableSymbols, setAvailableSymbols] = useState<InstrumentMeta[]>([]);

  // Add stock form
  const [newSymbol, setNewSymbol] = useState("");
  const [newQty, setNewQty] = useState("");
  const [newPrice, setNewPrice] = useState("");
  const [showSymbolDropdown, setShowSymbolDropdown] = useState(false);
  const [editIdx, setEditIdx] = useState<number | null>(null);
  const [loadingPrice, setLoadingPrice] = useState(false);

  // Load from localStorage and fetch master symbol list
  useEffect(() => {
    setHoldings(loadPortfolio());
    fetch(`${API_BASE}/market/instruments`)
      .then(r => r.json())
      .then(d => {
        if (d.instruments) {
          setAvailableSymbols(d.instruments);
        }
      })
      .catch(() => {});
  }, []);

  // Fetch valuation whenever holdings change
  const fetchValuation = useCallback(async () => {
    if (holdings.length === 0) { setValuation(null); return; }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/market/portfolio-value`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ holdings }),
      });
      if (res.ok) {
        const data = await res.json();
        setValuation(data);
      }
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [holdings]);

  useEffect(() => {
    if (holdings.length > 0) fetchValuation();
  }, [holdings, fetchValuation]);

  // Add / Edit stock
  const handleAddStock = () => {
    if (!newSymbol || !newQty || !newPrice) return;
    const sym = newSymbol.toUpperCase();
    const qty = parseFloat(newQty);
    const price = parseFloat(newPrice);
    if (isNaN(qty) || isNaN(price) || qty <= 0 || price <= 0) return;

    let updated: Holding[];
    if (editIdx !== null) {
      updated = [...holdings];
      updated[editIdx] = { symbol: sym, qty, buy_price: price };
      setEditIdx(null);
    } else {
      // Check if symbol already exists
      const existing = holdings.findIndex(h => h.symbol === sym);
      if (existing >= 0) {
        // Merge: average out buy price
        const old = holdings[existing];
        const totalQty = old.qty + qty;
        const avgPrice = (old.qty * old.buy_price + qty * price) / totalQty;
        updated = [...holdings];
        updated[existing] = { symbol: sym, qty: totalQty, buy_price: round2(avgPrice) };
      } else {
        updated = [...holdings, { symbol: sym, qty, buy_price: price }];
      }
    }

    setHoldings(updated);
    savePortfolio(updated);
    setNewSymbol("");
    setNewQty("");
    setNewPrice("");
    setShowAdd(false);
  };

  const fetchLatestPrice = async (sym: string) => {
    setLoadingPrice(true);
    try {
      const res = await fetch(`${API_BASE}/market/portfolio-value`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ holdings: [{ symbol: sym, qty: 1, buy_price: 1 }] }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.holdings && data.holdings[0]) {
          setNewPrice(data.holdings[0].current_price.toString());
        }
      }
    } catch {}
    finally {
      setLoadingPrice(false);
    }
  };

  const handleRemove = (idx: number) => {
    const updated = holdings.filter((_, i) => i !== idx);
    setHoldings(updated);
    savePortfolio(updated);
  };

  const handleEdit = (idx: number) => {
    const h = holdings[idx];
    setNewSymbol(h.symbol);
    setNewQty(h.qty.toString());
    setNewPrice(h.buy_price.toString());
    setEditIdx(idx);
    setShowAdd(true);
  };

  function round2(n: number) { return Math.round(n * 100) / 100; }

  const q = newSymbol.toUpperCase();
  const filteredSymbols = availableSymbols.filter(
    s => (s.symbol.includes(q) || s.name.toUpperCase().includes(q)) && 
         !holdings.some(h => h.symbol === s.symbol && editIdx === null)
  ).slice(0, 50); // limit dropdown size for performance

  const totalPnlUp = valuation ? valuation.total_pnl >= 0 : true;

  return (
    <>
      {detailSymbol && <StockDetailModal symbol={detailSymbol} onClose={() => setDetailSymbol(null)} />}

      <div className="card" style={{ overflow: "hidden", height: "100%", display: "flex", flexDirection: "column" }}>
        {/* Header */}
        <div style={{
          padding: "16px 20px",
          borderBottom: "1px solid var(--border-primary)",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          background: "rgba(17,26,46,0.3)",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{
              background: "rgba(139,92,246,0.15)", padding: 8, borderRadius: 10,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <Briefcase size={15} color="#8b5cf6" />
            </div>
            <div>
              <h2 style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: 8 }}>
                My Portfolio
                {loading && <RefreshCw size={12} className="spin" style={{ color: "#06b6d4" }} />}
              </h2>
              <span style={{ fontSize: 10, color: "var(--text-muted)" }}>
                Real-time valuation • Upstox NSE Data
              </span>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={() => fetchValuation()} style={{
              padding: "6px 12px", borderRadius: 8, fontSize: 10, fontWeight: 600,
              border: "1px solid var(--border-primary)", background: "transparent",
              color: "var(--text-secondary)", cursor: "pointer",
              display: "flex", alignItems: "center", gap: 4,
            }}>
              <RefreshCw size={10} /> Refresh
            </button>
            <button onClick={() => { setShowAdd(true); setEditIdx(null); setNewSymbol(""); setNewQty(""); setNewPrice(""); }} style={{
              padding: "6px 14px", borderRadius: 8, fontSize: 10, fontWeight: 700,
              border: "none", background: "linear-gradient(135deg, #8b5cf6 0%, #06b6d4 100%)",
              color: "#fff", cursor: "pointer", display: "flex", alignItems: "center", gap: 4,
            }}>
              <Plus size={11} /> Add Stock
            </button>
          </div>
        </div>

        {/* Portfolio summary KPI cards */}
        {valuation && (
          <div style={{
            display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12,
            padding: "16px 20px", borderBottom: "1px solid var(--border-primary)",
          }}>
            <div style={{ padding: "10px 14px", borderRadius: 10, background: "rgba(10,14,26,0.4)", border: "1px solid var(--border-primary)" }}>
              <div style={{ fontSize: 9, color: "var(--text-muted)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.05em" }}>Invested</div>
              <div style={{ fontSize: 16, fontWeight: 800, color: "var(--text-primary)", fontFamily: "'JetBrains Mono', monospace" }}>
                {formatLargeINR(valuation.total_invested)}
              </div>
            </div>
            <div style={{ padding: "10px 14px", borderRadius: 10, background: "rgba(10,14,26,0.4)", border: "1px solid var(--border-primary)" }}>
              <div style={{ fontSize: 9, color: "var(--text-muted)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.05em" }}>Current Value</div>
              <div style={{ fontSize: 16, fontWeight: 800, color: "#06b6d4", fontFamily: "'JetBrains Mono', monospace" }}>
                {formatLargeINR(valuation.total_current)}
              </div>
            </div>
            <div style={{ padding: "10px 14px", borderRadius: 10, background: totalPnlUp ? "rgba(16,185,129,0.05)" : "rgba(239,68,68,0.05)", border: `1px solid ${totalPnlUp ? "rgba(16,185,129,0.15)" : "rgba(239,68,68,0.15)"}` }}>
              <div style={{ fontSize: 9, color: "var(--text-muted)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.05em" }}>Total P&L</div>
              <div style={{
                fontSize: 16, fontWeight: 800, fontFamily: "'JetBrains Mono', monospace",
                color: totalPnlUp ? "#10b981" : "#ef4444",
                display: "flex", alignItems: "center", gap: 4,
              }}>
                {totalPnlUp ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
                {totalPnlUp ? "+" : ""}{formatINR(valuation.total_pnl)}
                <span style={{ fontSize: 10, fontWeight: 600 }}>({totalPnlUp ? "+" : ""}{valuation.total_pnl_pct}%)</span>
              </div>
            </div>
            <div style={{ padding: "10px 14px", borderRadius: 10, background: "rgba(10,14,26,0.4)", border: "1px solid var(--border-primary)" }}>
              <div style={{ fontSize: 9, color: "var(--text-muted)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.05em" }}>Day Change</div>
              <div style={{
                fontSize: 16, fontWeight: 800, fontFamily: "'JetBrains Mono', monospace",
                color: valuation.day_change >= 0 ? "#10b981" : "#ef4444",
              }}>
                {valuation.day_change >= 0 ? "+" : ""}{formatINR(valuation.day_change)}
              </div>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div style={{
          display: "flex", gap: 0, borderBottom: "1px solid var(--border-primary)",
        }}>
          {[
            { id: "holdings" as const, label: "Holdings", icon: BarChart3 },
            { id: "composition" as const, label: "Composition", icon: PieChart },
            { id: "wishlist" as const, label: "Wishlist", icon: Star },
          ].map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)} style={{
              padding: "10px 20px", fontSize: 11, fontWeight: 600,
              border: "none", borderBottom: activeTab === tab.id ? "2px solid #8b5cf6" : "2px solid transparent",
              background: "transparent",
              color: activeTab === tab.id ? "#8b5cf6" : "var(--text-muted)",
              cursor: "pointer", display: "flex", alignItems: "center", gap: 5,
            }}>
              <tab.icon size={12} /> {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div style={{ padding: 16 }}>
          {/* Add stock form */}
          {showAdd && (
            <div style={{
              padding: 16, marginBottom: 16, borderRadius: 12,
              background: "rgba(139,92,246,0.05)", border: "1px solid rgba(139,92,246,0.15)",
            }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#8b5cf6", marginBottom: 12 }}>
                {editIdx !== null ? "Edit Holding" : "Add New Stock"}
              </div>
              <div style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
                <div style={{ flex: 1, position: "relative" }}>
                  <label style={{ fontSize: 9, color: "var(--text-muted)", display: "block", marginBottom: 4, textTransform: "uppercase" }}>Symbol</label>
                  <input
                    value={newSymbol}
                    onChange={e => { setNewSymbol(e.target.value.toUpperCase()); setShowSymbolDropdown(true); }}
                    onFocus={() => setShowSymbolDropdown(true)}
                    placeholder="e.g. RELIANCE"
                    style={{
                      width: "100%", padding: "8px 12px", borderRadius: 8, fontSize: 12,
                      background: "rgba(10,14,26,0.6)", border: "1px solid var(--border-primary)",
                      color: "var(--text-primary)", outline: "none", fontFamily: "'JetBrains Mono', monospace",
                    }}
                  />
                  {showSymbolDropdown && newSymbol && filteredSymbols.length > 0 && (
                    <div style={{
                      position: "absolute", top: "100%", left: 0, right: 0, zIndex: 100,
                      background: "rgba(15,20,35,0.98)", border: "1px solid var(--border-primary)",
                      borderRadius: 8, marginTop: 2, maxHeight: 180, overflowY: "auto",
                      boxShadow: "0 10px 40px rgba(0,0,0,0.5)"
                    }}>
                      {filteredSymbols.map(s => (
                        <div key={s.symbol} onClick={() => { 
                          setNewSymbol(s.symbol); 
                          setShowSymbolDropdown(false); 
                          fetchLatestPrice(s.symbol);
                        }}
                          style={{
                            padding: "8px 12px", borderBottom: "1px solid rgba(255,255,255,0.03)",
                            cursor: "pointer", display: "flex", flexDirection: "column", gap: 2
                          }}
                          onMouseEnter={e => (e.currentTarget.style.background = "rgba(139,92,246,0.1)")}
                          onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                        >
                          <span style={{ fontSize: 11, fontWeight: 700, color: "var(--text-primary)", fontFamily: "'JetBrains Mono', monospace" }}>
                            {s.symbol}
                          </span>
                          <span style={{ fontSize: 9, color: "var(--text-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                            {s.name}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <div style={{ width: 100 }}>
                  <label style={{ fontSize: 9, color: "var(--text-muted)", display: "block", marginBottom: 4, textTransform: "uppercase" }}>Quantity</label>
                  <input
                    value={newQty} onChange={e => setNewQty(e.target.value)} type="number"
                    placeholder="10" min="1"
                    style={{
                      width: "100%", padding: "8px 12px", borderRadius: 8, fontSize: 12,
                      background: "rgba(10,14,26,0.6)", border: "1px solid var(--border-primary)",
                      color: "var(--text-primary)", outline: "none", fontFamily: "'JetBrains Mono', monospace",
                    }}
                  />
                </div>
                <div style={{ width: 120 }}>
                  <label style={{ fontSize: 9, color: "var(--text-muted)", display: "flex", alignItems: "center", gap: 6, marginBottom: 4, textTransform: "uppercase" }}>
                    Buy Price (₹)
                    {loadingPrice && <RefreshCw size={8} className="spin" style={{ color: "#06b6d4" }} />}
                  </label>
                  <input
                    value={loadingPrice ? "Fetching..." : newPrice} onChange={e => setNewPrice(e.target.value)} type={loadingPrice ? "text" : "number"}
                    placeholder="1400.00" min="0.01" step="0.01" disabled={loadingPrice}
                    style={{
                      width: "100%", padding: "8px 12px", borderRadius: 8, fontSize: 12,
                      background: "rgba(10,14,26,0.6)", border: "1px solid var(--border-primary)",
                      color: "var(--text-primary)", outline: "none", fontFamily: "'JetBrains Mono', monospace",
                    }}
                  />
                </div>
                <button onClick={handleAddStock} style={{
                  padding: "8px 16px", borderRadius: 8, fontSize: 11, fontWeight: 700,
                  border: "none", background: "#8b5cf6", color: "#fff", cursor: "pointer",
                  display: "flex", alignItems: "center", gap: 4, whiteSpace: "nowrap",
                }}>
                  <Check size={12} /> {editIdx !== null ? "Save" : "Add"}
                </button>
                <button onClick={() => { setShowAdd(false); setEditIdx(null); }} style={{
                  padding: "8px", borderRadius: 8, border: "1px solid var(--border-primary)",
                  background: "transparent", color: "var(--text-muted)", cursor: "pointer",
                }}>
                  <X size={12} />
                </button>
              </div>
            </div>
          )}

          {/* Empty state */}
          {holdings.length === 0 ? (
            <div style={{ textAlign: "center", padding: "40px 20px" }}>
              <div style={{
                width: 56, height: 56, borderRadius: 14, margin: "0 auto 16px",
                background: "rgba(139,92,246,0.1)", border: "1px solid rgba(139,92,246,0.15)",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <Briefcase size={24} color="#8b5cf6" style={{ opacity: 0.5 }} />
              </div>
              <p style={{ fontSize: 14, fontWeight: 600, color: "var(--text-secondary)" }}>
                Build Your Portfolio
              </p>
              <p style={{ fontSize: 12, color: "var(--text-muted)", maxWidth: 360, margin: "8px auto 20px", lineHeight: 1.6 }}>
                Add stocks from the top 20 NSE companies. The agent will track your holdings
                against real Upstox data and alert you when anomalies affect your positions.
              </p>
              <button onClick={() => setShowAdd(true)} style={{
                padding: "10px 24px", borderRadius: 10, fontSize: 12, fontWeight: 700,
                border: "none", background: "linear-gradient(135deg, #8b5cf6 0%, #06b6d4 100%)",
                color: "#fff", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6,
              }}>
                <Plus size={14} /> Add Your First Stock
              </button>
            </div>
          ) : activeTab === "holdings" ? (
            /* ─── Holdings Table ─── */
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "separate", borderSpacing: "0 6px" }}>
                <thead>
                  <tr>
                    {["Symbol", "Qty", "Buy Price", "CMP", "Invested", "Current", "P&L", "Day Chg", "Chart", ""].map(h => (
                      <th key={h} style={{
                        fontSize: 9, fontWeight: 600, color: "var(--text-dim)",
                        textAlign: "left", padding: "4px 10px", textTransform: "uppercase",
                        letterSpacing: "0.06em", borderBottom: "1px solid var(--border-primary)",
                      }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(valuation?.holdings || holdings.map(h => ({ ...h, current_price: h.buy_price, invested: h.qty * h.buy_price, current_value: h.qty * h.buy_price, pnl: 0, pnl_pct: 0, day_change: 0, day_change_pct: 0, day_high: 0, day_low: 0, total_volume: 0, candles: [] }))).map((h, i) => {
                    const pUp = h.pnl >= 0;
                    const dayUp = h.day_change >= 0;
                    return (
                      <tr key={h.symbol} style={{
                        background: "rgba(10,14,26,0.3)",
                        transition: "background 0.15s",
                      }}
                      onMouseEnter={e => (e.currentTarget.style.background = "rgba(139,92,246,0.04)")}
                      onMouseLeave={e => (e.currentTarget.style.background = "rgba(10,14,26,0.3)")}
                      >
                        <td style={{ padding: "10px", fontWeight: 800, fontSize: 13, color: "var(--text-primary)", fontFamily: "'JetBrains Mono', monospace", borderRadius: "8px 0 0 8px", cursor: "pointer" }}
                          onClick={() => setDetailSymbol(h.symbol)}>
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            {h.symbol}
                            <ArrowUpRight size={10} color="#06b6d4" style={{ opacity: 0.5 }} />
                          </div>
                        </td>
                        <td style={{ padding: "10px", fontSize: 12, color: "var(--text-secondary)", fontFamily: "'JetBrains Mono', monospace" }}>
                          {h.qty}
                        </td>
                        <td style={{ padding: "10px", fontSize: 12, color: "var(--text-muted)", fontFamily: "'JetBrains Mono', monospace" }}>
                          {formatINR(h.buy_price)}
                        </td>
                        <td style={{ padding: "10px", fontSize: 12, fontWeight: 700, color: "var(--text-primary)", fontFamily: "'JetBrains Mono', monospace" }}>
                          {formatINR(h.current_price)}
                        </td>
                        <td style={{ padding: "10px", fontSize: 11, color: "var(--text-muted)", fontFamily: "'JetBrains Mono', monospace" }}>
                          {formatINR(h.invested)}
                        </td>
                        <td style={{ padding: "10px", fontSize: 11, color: "#06b6d4", fontWeight: 600, fontFamily: "'JetBrains Mono', monospace" }}>
                          {formatINR(h.current_value)}
                        </td>
                        <td style={{ padding: "10px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, fontWeight: 700, color: pUp ? "#10b981" : "#ef4444", fontFamily: "'JetBrains Mono', monospace" }}>
                            {pUp ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                            {pUp ? "+" : ""}{formatINR(h.pnl)}
                            <span style={{ fontSize: 9, opacity: 0.8 }}>({pUp ? "+" : ""}{h.pnl_pct}%)</span>
                          </div>
                        </td>
                        <td style={{ padding: "10px", fontSize: 10, fontWeight: 600, fontFamily: "'JetBrains Mono', monospace", color: dayUp ? "#10b981" : "#ef4444" }}>
                          {dayUp ? "+" : ""}{h.day_change_pct.toFixed(2)}%
                        </td>
                        <td style={{ padding: "10px", width: 90 }}>
                          <Sparkline candles={h.candles} isUp={pUp} height={28} width={80} />
                        </td>
                        <td style={{ padding: "10px", borderRadius: "0 8px 8px 0" }}>
                          <div style={{ display: "flex", gap: 4 }}>
                            <button onClick={() => handleEdit(i)} style={{
                              padding: 4, borderRadius: 4, border: "1px solid var(--border-primary)",
                              background: "transparent", cursor: "pointer", color: "var(--text-muted)",
                            }}><Edit3 size={10} /></button>
                            <button onClick={() => handleRemove(i)} style={{
                              padding: 4, borderRadius: 4, border: "1px solid rgba(239,68,68,0.2)",
                              background: "transparent", cursor: "pointer", color: "#ef4444",
                            }}><Trash2 size={10} /></button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : activeTab === "composition" ? (
            /* ─── Composition Tab ─── */
            <div style={{ padding: "8px 0" }}>
              {valuation && <PortfolioDonut holdings={valuation.holdings} />}
              {!valuation && <p style={{ fontSize: 12, color: "var(--text-muted)"}}>Loading portfolio data...</p>}
            </div>
          ) : (
            /* ─── Wishlist Tab (Portfolio Snapshot — Real NSE Data) ─── */
            <WishlistTab />
          )}
        </div>
      </div>
    </>
  );
}

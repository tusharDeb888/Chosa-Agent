"use client";
import { useState, useEffect, useCallback } from "react";
import {
  Newspaper, TrendingUp, TrendingDown, Minus, FileText, Globe, Clock,
  Filter, ChevronRight, ExternalLink, RefreshCw, Sparkles, Wifi, Radio,
} from "lucide-react";

interface NewsItem {
  id: string;
  ticker: string;
  headline: string;
  sentiment: "bullish" | "bearish" | "neutral";
  source: string;
  published_at: string;
  fetched_at: string;
  impact_score: number;
  category: "news" | "filing" | "macro";
  reasoning_id?: string;
  source_mode: "mock" | "live";
  url?: string;
  summary?: string;
}

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/api/v1";

const SENTIMENT_CONFIG = {
  bullish: { color: "#10b981", bg: "rgba(16,185,129,0.1)", border: "rgba(16,185,129,0.2)", icon: TrendingUp, label: "Bullish" },
  bearish: { color: "#ef4444", bg: "rgba(239,68,68,0.1)", border: "rgba(239,68,68,0.2)", icon: TrendingDown, label: "Bearish" },
  neutral: { color: "#f59e0b", bg: "rgba(245,158,11,0.1)", border: "rgba(245,158,11,0.2)", icon: Minus, label: "Neutral" },
};

const CATEGORY_ICONS = { news: Newspaper, filing: FileText, macro: Globe };

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function ImpactBar({ score }: { score: number }) {
  const color = score >= 70 ? "#ef4444" : score >= 40 ? "#f59e0b" : "#10b981";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{
        width: 40, height: 4, borderRadius: 2,
        background: "rgba(99,117,168,0.1)", overflow: "hidden",
      }}>
        <div style={{
          width: `${score}%`, height: "100%", borderRadius: 2,
          background: color, transition: "width 0.5s ease",
        }} />
      </div>
      <span style={{ fontSize: 9, fontWeight: 700, color, fontFamily: "'JetBrains Mono', monospace" }}>
        {score}
      </span>
    </div>
  );
}

export default function PortfolioNewsRadar() {
  const [news, setNews] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"news" | "filing" | "macro">("news");
  const [sentimentFilter, setSentimentFilter] = useState<string>("all");
  const [holdingsOnly, setHoldingsOnly] = useState(false);
  const [sourceMode, setSourceMode] = useState<string>("auto");
  const [lastRefresh, setLastRefresh] = useState<string>("");
  const [refreshing, setRefreshing] = useState(false);

  const fetchNews = useCallback(async (showSpinner = false) => {
    if (showSpinner) setRefreshing(true);
    try {
      const params = new URLSearchParams({
        category: activeTab,
        sentiment: sentimentFilter,
        holdings_only: holdingsOnly.toString(),
        mode: "live",
      });
      const res = await fetch(`${API_BASE}/news/portfolio?${params}`);
      if (res.ok) {
        const data = await res.json();
        setNews(data.items || []);
        setSourceMode(data.source_mode || "mock");
        setLastRefresh(new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }));
      }
    } catch { /* quiet fail */ }
    finally { setLoading(false); setRefreshing(false); }
  }, [activeTab, sentimentFilter, holdingsOnly]);

  useEffect(() => {
    fetchNews();
    const interval = setInterval(() => fetchNews(), 45000); // Poll every 45s
    return () => clearInterval(interval);
  }, [fetchNews]);

  const tabs = [
    { id: "news" as const, label: "Top News", icon: Newspaper, count: 0 },
    { id: "filing" as const, label: "Filings", icon: FileText, count: 0 },
    { id: "macro" as const, label: "Macro", icon: Globe, count: 0 },
  ];

  const sentimentFilters = [
    { id: "all", label: "All" },
    { id: "bullish", label: "Bullish", color: "#10b981" },
    { id: "bearish", label: "Bearish", color: "#ef4444" },
    { id: "neutral", label: "Neutral", color: "#f59e0b" },
  ];

  return (
    <div style={{
      background: "rgba(10,14,26,0.6)",
      border: "1px solid var(--border-primary)",
      borderRadius: 16,
      overflow: "hidden",
      display: "flex",
      flexDirection: "column",
      height: "100%",
    }}>
      {/* Header */}
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
            <Radio size={14} color="#06b6d4" style={{ animation: "pulse 2s ease-in-out infinite" }} />
          </div>
          <div>
            <h2 style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: 6 }}>
              Portfolio News Radar
              <span style={{
                fontSize: 8, padding: "2px 6px", borderRadius: 4,
                background: "rgba(16,185,129,0.1)", color: "#10b981",
                fontWeight: 800, letterSpacing: "0.06em",
              }}>
                24/7
              </span>
            </h2>
            <span style={{ fontSize: 10, color: "var(--text-muted)", display: "flex", alignItems: "center", gap: 4 }}>
              <Clock size={9} /> Updated {lastRefresh || "—"}
              {sourceMode && (
                <span style={{
                  fontSize: 8, padding: "1px 5px", borderRadius: 3, marginLeft: 4,
                  background: sourceMode === "live" ? "rgba(16,185,129,0.1)" : "rgba(139,92,246,0.1)",
                  color: sourceMode === "live" ? "#10b981" : "#a78bfa",
                  fontWeight: 700,
                }}>
                  {sourceMode === "live" ? "LIVE" : "DEMO"}
                </span>
              )}
            </span>
          </div>
        </div>
        <button
          onClick={() => fetchNews(true)}
          aria-label="Refresh news"
          style={{
            padding: "6px 12px", borderRadius: 8, fontSize: 10, fontWeight: 600,
            border: "1px solid var(--border-primary)", background: "transparent",
            color: "var(--text-secondary)", cursor: "pointer",
            display: "flex", alignItems: "center", gap: 4,
          }}
        >
          <RefreshCw size={10} className={refreshing ? "spin" : ""} /> Refresh
        </button>
      </div>

      {/* Tabs */}
      <div style={{
        display: "flex", borderBottom: "1px solid var(--border-primary)",
        padding: "0 12px",
      }}>
        {tabs.map(tab => {
          const TabIcon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              aria-label={`Show ${tab.label}`}
              style={{
                padding: "10px 16px", fontSize: 11, fontWeight: 600,
                border: "none",
                borderBottom: activeTab === tab.id ? "2px solid #06b6d4" : "2px solid transparent",
                background: "transparent",
                color: activeTab === tab.id ? "#06b6d4" : "var(--text-muted)",
                cursor: "pointer", display: "flex", alignItems: "center", gap: 5,
                transition: "all 0.2s",
              }}
            >
              <TabIcon size={11} /> {tab.label}
            </button>
          );
        })}
      </div>

      {/* Filters */}
      <div style={{
        padding: "10px 16px",
        display: "flex", alignItems: "center", gap: 6,
        borderBottom: "1px solid var(--border-primary)",
        flexWrap: "wrap",
      }}>
        <Filter size={10} color="var(--text-dim)" />
        {sentimentFilters.map(f => (
          <button
            key={f.id}
            onClick={() => setSentimentFilter(f.id)}
            style={{
              padding: "3px 10px", borderRadius: 6, fontSize: 10, fontWeight: 600,
              border: `1px solid ${sentimentFilter === f.id ? (f.color || "#06b6d4") + "40" : "var(--border-primary)"}`,
              background: sentimentFilter === f.id ? (f.color || "#06b6d4") + "15" : "transparent",
              color: sentimentFilter === f.id ? (f.color || "#06b6d4") : "var(--text-muted)",
              cursor: "pointer", transition: "all 0.2s",
            }}
          >
            {f.label}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        <button
          onClick={() => setHoldingsOnly(!holdingsOnly)}
          style={{
            padding: "3px 10px", borderRadius: 6, fontSize: 10, fontWeight: 600,
            border: `1px solid ${holdingsOnly ? "rgba(139,92,246,0.3)" : "var(--border-primary)"}`,
            background: holdingsOnly ? "rgba(139,92,246,0.1)" : "transparent",
            color: holdingsOnly ? "#a78bfa" : "var(--text-muted)",
            cursor: "pointer", transition: "all 0.2s",
          }}
        >
          Holdings Only
        </button>
      </div>

      {/* News List */}
      <div className="custom-scrollbar" style={{ flex: 1, overflowY: "auto", padding: "6px 0" }}>
        {loading ? (
          <div style={{ textAlign: "center", padding: 40 }}>
            <RefreshCw size={20} className="spin" style={{ color: "var(--text-dim)", marginBottom: 8 }} />
            <p style={{ fontSize: 12, color: "var(--text-muted)" }}>Scanning news sources...</p>
          </div>
        ) : news.length === 0 ? (
          <div style={{ textAlign: "center", padding: "40px 20px" }}>
            <Sparkles size={24} style={{ color: "var(--text-dim)", marginBottom: 8 }} />
            <p style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)" }}>No news in this category</p>
            <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>Try adjusting filters or switching tabs</p>
          </div>
        ) : (
          news.map((item, idx) => {
            const sc = SENTIMENT_CONFIG[item.sentiment];
            const SentIcon = sc.icon;
            const CatIcon = CATEGORY_ICONS[item.category] || Newspaper;

            return (
              <div
                key={item.id}
                style={{
                  padding: "12px 16px",
                  borderBottom: idx < news.length - 1 ? "1px solid rgba(99,117,168,0.05)" : "none",
                  transition: "background 0.15s",
                  cursor: "pointer",
                  animation: `fadeIn 0.3s ease ${idx * 0.04}s both`,
                }}
                onMouseEnter={e => (e.currentTarget.style.background = "rgba(6,182,212,0.03)")}
                onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
              >
                <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
                  {/* Sentiment indicator */}
                  <div style={{
                    width: 28, height: 28, borderRadius: 7, flexShrink: 0, marginTop: 2,
                    background: sc.bg, border: `1px solid ${sc.border}`,
                    display: "flex", alignItems: "center", justifyContent: "center",
                  }}>
                    <SentIcon size={12} color={sc.color} />
                  </div>

                  {/* Content */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                      <span style={{
                        fontSize: 10, fontWeight: 800, color: "var(--text-primary)",
                        fontFamily: "'JetBrains Mono', monospace",
                        background: "rgba(99,117,168,0.06)",
                        padding: "1px 6px", borderRadius: 3,
                      }}>
                        {item.ticker}
                      </span>
                      <span style={{
                        fontSize: 8, fontWeight: 700, color: sc.color,
                        padding: "1px 5px", borderRadius: 3,
                        background: sc.bg,
                        textTransform: "uppercase", letterSpacing: "0.04em",
                      }}>
                        {sc.label}
                      </span>
                      <span style={{
                        fontSize: 8, color: "var(--text-dim)",
                        display: "flex", alignItems: "center", gap: 3,
                      }}>
                        <CatIcon size={8} /> {item.category}
                      </span>
                    </div>

                    <p style={{
                      fontSize: 12, fontWeight: 500, color: "var(--text-primary)",
                      lineHeight: 1.5, margin: 0,
                      overflow: "hidden", textOverflow: "ellipsis",
                      display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" as any,
                    }}>
                      {item.headline}
                    </p>

                    <div style={{
                      display: "flex", alignItems: "center", gap: 10, marginTop: 6,
                    }}>
                      <span style={{ fontSize: 9, color: "var(--text-dim)" }}>{item.source}</span>
                      <span style={{ fontSize: 9, color: "var(--text-dim)", display: "flex", alignItems: "center", gap: 3 }}>
                        <Clock size={8} /> {timeAgo(item.published_at)}
                      </span>
                      <ImpactBar score={item.impact_score} />
                      {item.url && item.source_mode === "live" && (
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={e => e.stopPropagation()}
                          style={{
                            fontSize: 9, color: "#06b6d4",
                            display: "flex", alignItems: "center", gap: 2,
                            textDecoration: "none",
                          }}
                        >
                          <ExternalLink size={8} /> Source
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Footer */}
      <div style={{
        padding: "8px 16px",
        borderTop: "1px solid var(--border-primary)",
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <span style={{ fontSize: 10, color: "var(--text-dim)" }}>
          {news.length} articles • Auto-refreshes every 45s
        </span>
        <span style={{
          fontSize: 9, fontWeight: 600, color: "var(--text-dim)",
          display: "flex", alignItems: "center", gap: 4,
        }}>
          <Wifi size={8} color={sourceMode === "live" ? "#10b981" : "#a78bfa"} />
          {sourceMode === "live" ? "Google News Live" : "Demo Mode"}
        </span>
      </div>
    </div>
  );
}

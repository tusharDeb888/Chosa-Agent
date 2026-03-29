"use client";
import { useEffect, useState } from "react";
import {
  X, Shield, ExternalLink, Clock, AlertTriangle, CheckCircle, ChevronRight,
  Zap, FileText, Brain, BadgeCheck, Briefcase, PieChart, Building2,
} from "lucide-react";
import { Alert, confidenceLabel, getDecisionColor, Citation, StagedOrder } from "./types";

const FILING_ICONS: Record<string, string> = {
  QUARTERLY_RESULT: "📊",
  BOARD_MEETING: "📋",
  INSIDER_TRADING: "🔍",
  REGULATORY: "🏛️",
  DIVIDEND: "💰",
  MERGER: "🤝",
  CREDIT_RATING: "⭐",
  AGM: "🏢",
  BUYBACK: "🔄",
};

function timeAgoLabel(dateStr?: string): { text: string; color: string } {
  if (!dateStr) return { text: "unknown", color: "var(--text-dim)" };
  const hours = (Date.now() - new Date(dateStr).getTime()) / 3600000;
  if (hours < 1) return { text: `${Math.max(1, Math.round(hours * 60))}m ago`, color: "#10b981" };
  if (hours < 6) return { text: `${Math.round(hours)}h ago`, color: "#10b981" };
  if (hours < 24) return { text: `${Math.round(hours)}h ago`, color: "#f59e0b" };
  return { text: `${Math.round(hours / 24)}d ago`, color: "#ef4444" };
}

export default function ExplainDrawer({ alert, onClose, onOrderClick }: { alert: Alert; onClose: () => void; onOrderClick?: (order: StagedOrder) => void }) {
  const d = alert.decision;
  const color = getDecisionColor(d.final_decision);
  const conf = confidenceLabel(d.confidence);
  const ticker = alert.ticker || d.signal_id?.split("-")[0] || "???";
  const [ttlRemaining, setTtlRemaining] = useState(d.ttl_seconds);
  const portfolioCtx = d.portfolio_context;
  const stagedOrder = alert.staged_order || d.staged_order;

  useEffect(() => {
    const createdAt = new Date(d.created_at || alert.created_at).getTime();
    const interval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - createdAt) / 1000);
      setTtlRemaining(Math.max(0, d.ttl_seconds - elapsed));
    }, 1000);
    return () => clearInterval(interval);
  }, [d.created_at, d.ttl_seconds, alert.created_at]);

  const ttlPct = d.ttl_seconds > 0 ? (ttlRemaining / d.ttl_seconds) * 100 : 0;
  const ttlColor = ttlPct > 50 ? "#10b981" : ttlPct > 20 ? "#f59e0b" : "#ef4444";
  const formatTTL = (s: number) => `${Math.floor(s / 60)}m ${s % 60}s`;

  const Section = ({ icon: Icon, title, children, iconColor = "var(--text-muted)" }: { icon: React.ElementType; title: string; children: React.ReactNode; iconColor?: string }) => (
    <div style={{ marginBottom: 20 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <Icon size={14} color={iconColor} />
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--text-muted)" }}>{title}</span>
      </div>
      {children}
    </div>
  );

  const policyViolationLabels: Record<string, string> = {
    MAX_CONCENTRATION_EXCEEDED: "Position exceeds max concentration limit",
    DAILY_ACTION_LIMIT_REACHED: "Daily actionable recommendation limit hit",
    CONFIDENCE_BELOW_THRESHOLD: "Confidence below minimum for BUY/SELL",
    EVIDENCE_TOO_STALE: "Evidence exceeds max age threshold",
    PORTFOLIO_STALE: "Portfolio data is outdated",
  };

  // Separate filing vs non-filing citations
  const filingCitations = d.citations?.filter(c => c.source_type === "corporate_filing") || [];
  const newsCitations = d.citations?.filter(c => c.source_type !== "corporate_filing") || [];

  return (
    <>
      <div className="drawer-overlay" onClick={onClose} style={{ position: "fixed", inset: 0, zIndex: 150, background: "rgba(0,0,0,0.5)", backdropFilter: "blur(4px)" }} />
      <div className="drawer-panel" style={{
        position: "fixed", top: 0, right: 0, bottom: 0, width: 440, maxWidth: "100vw", zIndex: 160,
        background: "linear-gradient(180deg, #111a2e, #0d1321)", borderLeft: "1px solid var(--border-primary)",
        display: "flex", flexDirection: "column", boxShadow: "-8px 0 40px rgba(0,0,0,0.5)",
      }}>
        {/* Header */}
        <div style={{ padding: "20px 24px", borderBottom: "1px solid var(--border-primary)", background: "rgba(17,26,46,0.5)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                <span style={{ fontSize: 20, fontWeight: 800 }}>{ticker}</span>
                <span className={`badge badge-${d.final_decision.toLowerCase()}`}>{d.final_decision}</span>
                {d.original_decision !== d.final_decision && (
                  <span style={{ fontSize: 10, color: "var(--text-muted)" }}>was {d.original_decision}</span>
                )}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ fontSize: 22, fontWeight: 900, color }}>{d.confidence}%</span>
                <span style={{ fontSize: 11, color: conf.color, fontWeight: 600 }}>{conf.text}</span>
              </div>
            </div>
            <button onClick={onClose} style={{ background: "rgba(99,117,168,0.08)", border: "1px solid var(--border-primary)", borderRadius: 10, padding: 8, cursor: "pointer", color: "var(--text-muted)" }}>
              <X size={16} />
            </button>
          </div>
          {/* Confidence bar */}
          <div style={{ marginTop: 12, height: 4, background: "rgba(99,117,168,0.08)", borderRadius: 9999, overflow: "hidden" }}>
            <div className="confidence-bar" style={{ height: "100%", width: `${d.confidence}%`, background: color, borderRadius: 9999 }} />
          </div>
        </div>

        {/* Content */}
        <div className="custom-scrollbar" style={{ flex: 1, overflowY: "auto", padding: "20px 24px" }}>

          {/* 1-Click Order Button */}
          {stagedOrder && stagedOrder.status === "STAGED" && onOrderClick && (
            <div style={{ marginBottom: 20 }}>
              <button
                onClick={() => onOrderClick(stagedOrder)}
                style={{
                  width: "100%", padding: "14px 18px", borderRadius: 14, cursor: "pointer",
                  background: `linear-gradient(135deg, ${color}18, ${color}28)`,
                  border: `1.5px solid ${color}50`,
                  color, fontSize: 14, fontWeight: 800,
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
                  transition: "all 0.2s",
                  boxShadow: `0 4px 20px ${color}15`,
                }}
              >
                <Zap size={18} />
                {stagedOrder.action} {stagedOrder.quantity} shares at ₹{stagedOrder.price.toLocaleString()}
                <span style={{ fontSize: 12, opacity: 0.7, fontWeight: 600 }}>
                  (₹{stagedOrder.estimated_value.toLocaleString()})
                </span>
              </button>
            </div>
          )}

          {/* Your Exposure */}
          {portfolioCtx && (
            <Section icon={PieChart} title="Your Exposure" iconColor="#8b5cf6">
              <div style={{ padding: "14px 16px", background: "rgba(139,92,246,0.04)", border: "1px solid rgba(139,92,246,0.1)", borderRadius: 12 }}>
                {/* Personalized summary */}
                <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.6, marginBottom: 12, fontWeight: 500 }}>
                  {portfolioCtx.personalized_summary}
                </p>

                {/* Metrics */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                  {[
                    { label: "Your Holdings", value: `₹${(portfolioCtx.symbol_value / 100000).toFixed(1)}L`, sub: `${portfolioCtx.symbol_quantity} shares`, color: "#8b5cf6" },
                    { label: "Portfolio %", value: `${portfolioCtx.symbol_exposure_pct.toFixed(1)}%`, sub: `of your portfolio`, color: portfolioCtx.symbol_exposure_pct > 20 ? "#ef4444" : "#10b981" },
                    { label: "Sector", value: portfolioCtx.sector_name, sub: `${portfolioCtx.sector_exposure_pct.toFixed(1)}% exposure`, color: "#3b82f6" },
                    { label: "Related Holdings", value: portfolioCtx.sector_holdings.length > 0 ? portfolioCtx.sector_holdings.join(", ") : "None", sub: "same sector", color: "#06b6d4" },
                  ].map((m, i) => (
                    <div key={i} style={{ padding: "8px 10px", borderRadius: 8, background: `${m.color}06`, border: `1px solid ${m.color}10` }}>
                      <div style={{ fontSize: 9, fontWeight: 700, color: "var(--text-dim)", letterSpacing: "0.04em", marginBottom: 3 }}>{m.label}</div>
                      <div style={{ fontSize: 13, fontWeight: 800, color: m.color, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.value}</div>
                      <div style={{ fontSize: 9, color: "var(--text-muted)", marginTop: 1 }}>{m.sub}</div>
                    </div>
                  ))}
                </div>
              </div>
            </Section>
          )}

          {/* Trigger section */}
          <Section icon={Zap} title="Trigger Reason" iconColor="#06b6d4">
            <div style={{ padding: "12px 14px", background: "rgba(6,182,212,0.06)", border: "1px solid rgba(6,182,212,0.12)", borderRadius: 12, fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5 }}>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: "#06b6d4", fontWeight: 600 }}>
                {d.signal_id?.split("-").slice(-1)[0]?.toUpperCase() || "ANOMALY"}
              </span>
              <span style={{ color: "var(--text-dim)", margin: "0 6px" }}>·</span>
              Signal ID: <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11 }}>{d.signal_id?.slice(0, 12) || "—"}</span>
            </div>
          </Section>

          {/* Rationale */}
          <Section icon={Brain} title="AI Rationale" iconColor="#8b5cf6">
            <div style={{ padding: "14px 16px", background: "rgba(139,92,246,0.04)", border: "1px solid rgba(139,92,246,0.1)", borderRadius: 12, fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.65 }}>
              {d.rationale}
            </div>
            {d.degraded_context && (
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 8, fontSize: 11, color: "#f59e0b" }}>
                <AlertTriangle size={12} /> Degraded context — some evidence sources unavailable
              </div>
            )}
          </Section>

          {/* Corporate Filings */}
          {filingCitations.length > 0 && (
            <Section icon={Building2} title={`Corporate Filings (${filingCitations.length})`} iconColor="#06b6d4">
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {filingCitations.map((c, i) => {
                  const freshness = timeAgoLabel(c.published_at);
                  const filingIcon = c.title ? Object.entries(FILING_ICONS).find(([k]) => c.title?.toUpperCase().includes(k))?.[1] || "📋" : "📋";
                  return (
                    <a key={i} href={c.url} target="_blank" rel="noopener noreferrer" style={{
                      display: "block", padding: "12px 14px",
                      background: "rgba(6,182,212,0.04)", border: "1px solid rgba(6,182,212,0.12)",
                      borderRadius: 12, textDecoration: "none", transition: "all 0.2s",
                    }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                        <span style={{ fontSize: 16 }}>{filingIcon}</span>
                        <span style={{ fontSize: 12, fontWeight: 700, color: "#06b6d4", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {c.title || c.url.replace(/https?:\/\/(www\.)?/, "").split("/").slice(0, 2).join("/")}
                        </span>
                        <ExternalLink size={11} color="#06b6d4" style={{ flexShrink: 0 }} />
                      </div>
                      <div style={{
                        display: "flex", alignItems: "center", gap: 6, marginBottom: 6,
                      }}>
                        <span className="badge badge-buy" style={{ fontSize: 8, padding: "1px 6px", background: "rgba(6,182,212,0.12)", color: "#06b6d4", border: "1px solid rgba(6,182,212,0.2)" }}>
                          OFFICIAL FILING
                        </span>
                        <span style={{ fontSize: 10, color: freshness.color, fontWeight: 600 }}>{freshness.text}</span>
                      </div>
                      {c.plain_summary && (
                        <p style={{ fontSize: 11, color: "var(--text-secondary)", lineHeight: 1.5, margin: 0 }}>
                          💡 {c.plain_summary}
                        </p>
                      )}
                    </a>
                  );
                })}
              </div>
            </Section>
          )}

          {/* News & Analysis Evidence */}
          {newsCitations.length > 0 && (
            <Section icon={FileText} title={`News & Analysis (${newsCitations.length})`} iconColor="#3b82f6">
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {newsCitations.map((c, i) => {
                  const freshness = timeAgoLabel(c.published_at);
                  const typeLabel = c.source_type === "analysis" ? "ANALYSIS" : "NEWS";
                  const typeColor = c.source_type === "analysis" ? "#8b5cf6" : "#3b82f6";
                  return (
                    <a key={i} href={c.url} target="_blank" rel="noopener noreferrer" style={{
                      display: "block", padding: "12px 14px",
                      background: "rgba(59,130,246,0.04)", border: "1px solid rgba(59,130,246,0.1)",
                      borderRadius: 12, textDecoration: "none", transition: "all 0.2s",
                    }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                        <span style={{ fontSize: 12, fontWeight: 700, color: "#3b82f6", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {c.title || c.url.replace(/https?:\/\/(www\.)?/, "").split("/").slice(0, 2).join("/")}
                        </span>
                        <ExternalLink size={11} color="#3b82f6" style={{ flexShrink: 0 }} />
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
                        <span style={{ fontSize: 8, padding: "1px 6px", borderRadius: 4, background: `${typeColor}12`, color: typeColor, fontWeight: 700, border: `1px solid ${typeColor}20` }}>
                          {typeLabel}
                        </span>
                        <span style={{ fontSize: 10, color: freshness.color, fontWeight: 600 }}>{freshness.text}</span>
                      </div>
                      {c.plain_summary && (
                        <p style={{ fontSize: 11, color: "var(--text-secondary)", lineHeight: 1.5, margin: 0 }}>
                          💡 {c.plain_summary}
                        </p>
                      )}
                    </a>
                  );
                })}
              </div>
            </Section>
          )}

          {/* Portfolio Impact */}
          {d.portfolio_impact && (d.portfolio_impact.position_delta_pct !== 0 || d.portfolio_impact.cash_impact !== 0) && (
            <Section icon={Shield} title="Portfolio Impact" iconColor="#10b981">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
                {[
                  { label: "Position Δ", value: `${d.portfolio_impact.position_delta_pct > 0 ? "+" : ""}${d.portfolio_impact.position_delta_pct.toFixed(1)}%`, color: d.portfolio_impact.position_delta_pct > 0 ? "#10b981" : "#ef4444" },
                  { label: "Sector Δ", value: `${d.portfolio_impact.sector_exposure_delta_pct > 0 ? "+" : ""}${d.portfolio_impact.sector_exposure_delta_pct.toFixed(1)}%`, color: "#3b82f6" },
                  { label: "Cash", value: `₹${Math.abs(d.portfolio_impact.cash_impact).toLocaleString()}`, color: d.portfolio_impact.cash_impact > 0 ? "#10b981" : "#ef4444" },
                ].map((m, i) => (
                  <div key={i} style={{ padding: "10px 12px", background: "rgba(16,185,129,0.04)", border: "1px solid rgba(16,185,129,0.08)", borderRadius: 10, textAlign: "center" }}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.04em", marginBottom: 4 }}>{m.label}</div>
                    <div style={{ fontSize: 14, fontWeight: 800, color: m.color }}>{m.value}</div>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Policy */}
          <Section icon={BadgeCheck} title="Policy Result" iconColor={d.policy_passed ? "#10b981" : "#ef4444"}>
            <div style={{
              padding: "12px 14px", borderRadius: 12,
              background: d.policy_passed ? "rgba(16,185,129,0.06)" : "rgba(239,68,68,0.06)",
              border: `1px solid ${d.policy_passed ? "rgba(16,185,129,0.15)" : "rgba(239,68,68,0.15)"}`,
              display: "flex", alignItems: "center", gap: 10,
            }}>
              {d.policy_passed ? <CheckCircle size={16} color="#10b981" /> : <AlertTriangle size={16} color="#ef4444" />}
              <div>
                <div style={{ fontSize: 13, fontWeight: 700, color: d.policy_passed ? "#10b981" : "#ef4444" }}>
                  {d.policy_passed ? "All checks passed" : "Policy violation — downgraded"}
                </div>
                {d.policy_reason_codes?.length > 0 && (
                  <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
                    {d.policy_reason_codes.map(c => policyViolationLabels[c] || c).join(" · ")}
                  </div>
                )}
              </div>
            </div>
          </Section>

          {/* Risk Flags */}
          {d.risk_flags && d.risk_flags.length > 0 && (
            <Section icon={AlertTriangle} title="Risk Flags" iconColor="#f59e0b">
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {d.risk_flags.map((f, i) => (
                  <span key={i} style={{
                    padding: "4px 10px", borderRadius: 8, fontSize: 11, fontWeight: 600,
                    background: "rgba(245,158,11,0.08)", color: "#f59e0b", border: "1px solid rgba(245,158,11,0.15)",
                    fontFamily: "'JetBrains Mono', monospace",
                  }}>
                    {f}
                  </span>
                ))}
              </div>
            </Section>
          )}

          {/* TTL */}
          <Section icon={Clock} title="TTL Expiry" iconColor={ttlColor}>
            <div style={{ padding: "12px 14px", background: `${ttlColor}08`, border: `1px solid ${ttlColor}18`, borderRadius: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <span className={ttlRemaining > 0 ? "countdown-active" : ""} style={{ fontSize: 20, fontWeight: 800, color: ttlColor, fontFamily: "'JetBrains Mono', monospace" }}>
                  {ttlRemaining > 0 ? formatTTL(ttlRemaining) : "EXPIRED"}
                </span>
                <span style={{ fontSize: 11, color: "var(--text-muted)" }}>of {formatTTL(d.ttl_seconds)}</span>
              </div>
              <div style={{ height: 4, background: "rgba(99,117,168,0.08)", borderRadius: 9999, overflow: "hidden" }}>
                <div style={{ height: "100%", width: `${ttlPct}%`, background: ttlColor, borderRadius: 9999, transition: "width 1s linear" }} />
              </div>
            </div>
          </Section>

          {/* Trace */}
          <div style={{ padding: "10px 14px", background: "rgba(99,117,168,0.03)", borderRadius: 10, border: "1px solid rgba(99,117,168,0.06)", marginTop: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--text-dim)", fontFamily: "'JetBrains Mono', monospace" }}>
              <span>trace: {d.trace_id?.slice(0, 10) || "—"}</span>
              <span>workflow: {d.workflow_id?.slice(0, 10) || "—"}</span>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}


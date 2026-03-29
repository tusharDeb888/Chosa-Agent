"use client";
import { useState } from "react";
import {
  ArrowUpRight, ArrowDownRight, TrendingUp, Shield, ChevronDown, ChevronUp,
  Clock, AlertTriangle, Briefcase, Zap, ShieldCheck,
} from "lucide-react";
import { Alert, AlertGroup, ViewMode, StagedOrder, confidenceLabel, getDecisionColor, decisionColors } from "./types";
import { computeTrustScore, computeTrustLabel } from "../store";

// ── Trust Score Badge ──
function TrustBadge({ alert }: { alert: Alert }) {
  const score = computeTrustScore(alert);
  const label = computeTrustLabel(score);
  const color = score >= 70 ? "#10b981" : score >= 40 ? "#f59e0b" : "#ef4444";

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 5, marginTop: 4,
    }}>
      <div style={{
        fontSize: 9, fontWeight: 700, padding: "2px 7px", borderRadius: 5,
        background: `${color}10`, color, border: `1px solid ${color}20`,
        display: "flex", alignItems: "center", gap: 3,
      }}>
        <ShieldCheck size={9} /> {score} — {label}
      </div>
    </div>
  );
}

// ── Portfolio impact chip (inline on each alert card) ──
function PortfolioChip({ alert }: { alert: Alert }) {
  const pi = alert.decision.portfolio_impact;
  if (!pi || (pi.position_delta_pct === 0 && pi.cash_impact === 0)) return null;

  const risk = Math.abs(pi.position_delta_pct) > 6 ? "High" : Math.abs(pi.position_delta_pct) > 3 ? "Med" : "Low";
  const riskColor = risk === "High" ? "#ef4444" : risk === "Med" ? "#f59e0b" : "#10b981";
  const sectorLabel = pi.sector_exposure_delta_pct !== 0
    ? `${pi.sector_exposure_delta_pct > 0 ? "+" : ""}${pi.sector_exposure_delta_pct.toFixed(1)}% sector`
    : null;

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginTop: 6,
    }}>
      {sectorLabel && (
        <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 6, background: "rgba(59,130,246,0.08)", color: "#3b82f6", fontWeight: 600, border: "1px solid rgba(59,130,246,0.12)" }}>
          <Briefcase size={9} style={{ marginRight: 3, display: "inline", verticalAlign: "middle" }} />
          {sectorLabel}
        </span>
      )}
      <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 6, background: `${riskColor}10`, color: riskColor, fontWeight: 700, border: `1px solid ${riskColor}20` }}>
        Risk: {risk}
      </span>
      {pi.cash_impact !== 0 && (
        <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 6, background: "rgba(99,117,168,0.06)", color: "var(--text-secondary)", fontWeight: 600, border: "1px solid rgba(99,117,168,0.08)" }}>
          ₹{Math.abs(pi.cash_impact).toLocaleString()}
        </span>
      )}
    </div>
  );
}

// ── Confidence UX ──
function ConfidenceDisplay({ confidence, decision, simple }: { confidence: number; decision: string; simple?: boolean }) {
  const color = getDecisionColor(decision);
  const cl = confidenceLabel(confidence);

  return (
    <div style={{ textAlign: "right", flexShrink: 0, minWidth: 70 }}>
      <div style={{ fontSize: 20, fontWeight: 900, letterSpacing: "-0.02em", color }}>{confidence}%</div>
      <div style={{ fontSize: 9, fontWeight: 600, color: cl.color, marginTop: 1, whiteSpace: "nowrap" }}>
        {simple ? cl.text : "CONF."}
      </div>
    </div>
  );
}

// ── Single alert card ──
export function AlertCard({ alert, index, onClick, simple, onOrderClick }: { alert: Alert; index: number; onClick: () => void; simple?: boolean; onOrderClick?: (order: StagedOrder) => void }) {
  const d = alert.decision;
  const decision = d?.final_decision || "WATCH";
  const confidence = d?.confidence || 0;
  const policyPassed = d?.policy_passed !== false;
  const ticker = alert.ticker || d?.signal_id?.split("-")[0] || "???";
  const bgColor = decisionColors[decision] || "#5a6a82";
  const DecisionIcon = decision === "BUY" ? ArrowUpRight : decision === "SELL" ? ArrowDownRight : TrendingUp;
  const portfolioCtx = d?.portfolio_context;
  const stagedOrder = alert.staged_order || d?.staged_order;

  // Exposure badge color
  const exposurePct = portfolioCtx?.symbol_exposure_pct || 0;
  const exposureBadgeColor = exposurePct > 20 ? "#ef4444" : exposurePct > 10 ? "#f59e0b" : "#10b981";

  return (
    <div
      className="animate-slideUp"
      onClick={onClick}
      style={{
        position: "relative", overflow: "hidden", borderRadius: 14,
        padding: "14px 18px 14px 22px", cursor: "pointer",
        background: "rgba(10,14,26,0.4)", border: "1px solid var(--border-primary)",
        display: "flex", alignItems: "flex-start", gap: 14,
        transition: "all 0.25s", animationDelay: `${Math.min(index * 30, 300)}ms`,
      }}
    >
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, background: bgColor, opacity: 0.6, borderRadius: "14px 0 0 14px" }} />

      <div style={{
        width: 40, height: 40, borderRadius: 11, display: "flex", alignItems: "center", justifyContent: "center",
        flexShrink: 0, background: `${bgColor}12`, border: `1px solid ${bgColor}25`, marginTop: 2,
      }}>
        <DecisionIcon size={18} style={{ color: bgColor }} />
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 6, marginBottom: 3 }}>
          <span style={{ fontWeight: 700, fontSize: 14, color: "var(--text-primary)" }}>{ticker}</span>
          <span className={`badge badge-${decision.toLowerCase()}`} style={{ fontSize: 10, padding: "2px 8px" }}>{decision}</span>
          {!policyPassed && (
            <span className="badge badge-terminated" style={{ fontSize: 9, padding: "2px 7px" }}>
              <Shield size={8} /> BLOCKED
            </span>
          )}
          {d.degraded_context && (
            <span style={{ fontSize: 9, color: "#f59e0b" }}>
              <AlertTriangle size={9} style={{ display: "inline", verticalAlign: "middle", marginRight: 2 }} />degraded
            </span>
          )}
          {/* Exposure badge */}
          {portfolioCtx && exposurePct > 0 && (
            <span style={{
              fontSize: 9, padding: "2px 7px", borderRadius: 6,
              background: `${exposureBadgeColor}10`, color: exposureBadgeColor,
              fontWeight: 700, border: `1px solid ${exposureBadgeColor}20`,
            }}>
              {exposurePct.toFixed(1)}% exposed
            </span>
          )}
        </div>
        <p style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5, overflow: "hidden", textOverflow: "ellipsis", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>
          {simple ? d?.rationale?.split(".")[0] + "." : (d?.rationale || "Processing...")}
        </p>

        {/* Personalized portfolio one-liner */}
        {portfolioCtx?.personalized_summary && (
          <div style={{
            display: "flex", alignItems: "center", gap: 6, marginTop: 6,
            fontSize: 10, color: exposureBadgeColor, fontWeight: 600,
            padding: "4px 8px", borderRadius: 6,
            background: `${exposureBadgeColor}06`, border: `1px solid ${exposureBadgeColor}10`,
          }}>
            <Briefcase size={10} />
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {portfolioCtx.personalized_summary.split(".")[0]}.
            </span>
          </div>
        )}

        <PortfolioChip alert={alert} />

        {/* Quick-action order button */}
        {stagedOrder && stagedOrder.status === "STAGED" && onOrderClick && (
          <button
            onClick={(e) => { e.stopPropagation(); onOrderClick(stagedOrder); }}
            style={{
              marginTop: 8, padding: "6px 14px", borderRadius: 8,
              background: `linear-gradient(135deg, ${bgColor}20, ${bgColor}30)`,
              border: `1px solid ${bgColor}40`, cursor: "pointer",
              color: bgColor, fontSize: 11, fontWeight: 800,
              display: "flex", alignItems: "center", gap: 6,
              transition: "all 0.2s",
            }}
          >
            <Zap size={11} />
            {stagedOrder.action} {stagedOrder.quantity} @ ₹{stagedOrder.price.toLocaleString()}
            <span style={{ color: "var(--text-muted)", fontWeight: 600, marginLeft: 4 }}>
              (₹{stagedOrder.estimated_value.toLocaleString()})
            </span>
          </button>
        )}
        <TrustBadge alert={alert} />
      </div>

      <ConfidenceDisplay confidence={confidence} decision={decision} simple={simple} />
    </div>
  );
}

// ── Grouped alert card ──
export function GroupedAlertCard({ group, onExpand, onAlertClick, simple, onOrderClick }: {
  group: AlertGroup; onExpand: () => void; onAlertClick: (a: Alert) => void; simple?: boolean; onOrderClick?: (order: StagedOrder) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const latest = group.latestAlert;
  const d = latest.decision;
  const color = getDecisionColor(group.decision);
  const timeAgo = Math.max(1, Math.round((Date.now() - group.lastAt) / 60000));
  const span = Math.max(1, Math.round((group.lastAt - group.firstAt) / 60000));
  const DecisionIcon = group.decision === "BUY" ? ArrowUpRight : group.decision === "SELL" ? ArrowDownRight : TrendingUp;

  if (group.alerts.length === 1) {
    return <AlertCard alert={group.alerts[0]} index={0} onClick={() => onAlertClick(group.alerts[0])} simple={simple} onOrderClick={onOrderClick} />;
  }

  return (
    <div className="animate-slideUp grouped-card" style={{ borderRadius: 14, border: "1px solid var(--border-primary)", overflow: "hidden" }}>
      {/* Group header */}
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          padding: "14px 18px 14px 22px", cursor: "pointer",
          display: "flex", alignItems: "center", gap: 14, position: "relative",
          transition: "background 0.2s",
        }}
      >
        <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, background: color, opacity: 0.6 }} />

        <div style={{
          width: 40, height: 40, borderRadius: 11, display: "flex", alignItems: "center", justifyContent: "center",
          flexShrink: 0, background: `${color}12`, border: `1px solid ${color}25`, position: "relative",
        }}>
          <DecisionIcon size={18} style={{ color }} />
          <div style={{
            position: "absolute", top: -4, right: -4, width: 18, height: 18, borderRadius: 9,
            background: color, color: "white", fontSize: 10, fontWeight: 800,
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: `0 0 8px ${color}60`,
          }}>
            {group.alerts.length}
          </div>
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
            <span style={{ fontWeight: 700, fontSize: 14, color: "var(--text-primary)" }}>{group.ticker}</span>
            <span className={`badge badge-${group.decision.toLowerCase()}`} style={{ fontSize: 10, padding: "2px 8px" }}>{group.decision}</span>
          </div>
          <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
            <span style={{ fontWeight: 600 }}>{group.alerts.length} similar alerts</span>
            <span style={{ color: "var(--text-dim)", margin: "0 6px" }}>·</span>
            <Clock size={10} style={{ display: "inline", verticalAlign: "middle", marginRight: 3 }} />
            <span>over {span}m</span>
            <span style={{ color: "var(--text-dim)", margin: "0 6px" }}>·</span>
            <span>last {timeAgo}m ago</span>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <ConfidenceDisplay confidence={d.confidence} decision={d.final_decision} simple={simple} />
          {expanded ? <ChevronUp size={16} color="var(--text-muted)" /> : <ChevronDown size={16} color="var(--text-muted)" />}
        </div>
      </div>

      {/* Expanded timeline */}
      {expanded && (
        <div style={{ borderTop: "1px solid var(--border-primary)", padding: "8px 12px", background: "rgba(6,10,20,0.3)" }}>
          {group.alerts.map((a, i) => (
            <div key={`${a.alert_id}-${i}-${a.created_at}`} onClick={() => onAlertClick(a)} style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "10px 12px", borderRadius: 10, cursor: "pointer",
              transition: "background 0.15s", marginBottom: 2,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div style={{ width: 6, height: 6, borderRadius: 3, background: color, flexShrink: 0, boxShadow: `0 0 6px ${color}40` }} />
                <span style={{ fontSize: 11, color: "var(--text-secondary)", fontFamily: "'JetBrains Mono', monospace" }}>
                  {new Date(a.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                </span>
                <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
                  {a.decision.confidence}% · {a.decision.rationale?.slice(0, 60)}...
                </span>
              </div>
              <ChevronDown size={12} color="var(--text-dim)" style={{ transform: "rotate(-90deg)" }} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Group alerts by ticker+decision ──
export function groupAlerts(alerts: Alert[]): AlertGroup[] {
  const map = new Map<string, Alert[]>();
  for (const a of alerts) {
    const key = `${a.ticker || a.decision?.signal_id?.split("-")[0] || "?"}_${a.decision?.final_decision || "?"}`;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(a);
  }

  const groups: AlertGroup[] = [];
  for (const [, groupAlerts] of map) {
    const sorted = groupAlerts.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    const ticker = sorted[0].ticker || sorted[0].decision?.signal_id?.split("-")[0] || "???";
    groups.push({
      ticker,
      decision: sorted[0].decision?.final_decision || "WATCH",
      alerts: sorted,
      latestAlert: sorted[0],
      firstAt: new Date(sorted[sorted.length - 1].created_at).getTime(),
      lastAt: new Date(sorted[0].created_at).getTime(),
    });
  }
  return groups.sort((a, b) => b.lastAt - a.lastAt);
}

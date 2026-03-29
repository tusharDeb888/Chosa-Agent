"use client";
import { useState, useEffect } from "react";
import {
  ArrowUpRight, ArrowDownRight, X, Shield, Clock,
  AlertTriangle, CheckCircle, Zap,
} from "lucide-react";
import { StagedOrder, GuardedDecision, getDecisionColor, confidenceLabel } from "./types";

interface OrderConfirmModalProps {
  order: StagedOrder;
  decision: GuardedDecision;
  ticker: string;
  onConfirm: (orderTicketId: string) => void;
  onDismiss: (orderTicketId: string) => void;
  onClose: () => void;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function OrderConfirmModal({ order, decision, ticker, onConfirm, onDismiss, onClose }: OrderConfirmModalProps) {
  const [status, setStatus] = useState<"idle" | "confirming" | "confirmed" | "dismissed" | "error">("idle");
  const [ttlRemaining, setTtlRemaining] = useState(0);
  const color = getDecisionColor(decision.final_decision);
  const conf = confidenceLabel(decision.confidence);
  const isBuy = order.action === "BUY";
  const ActionIcon = isBuy ? ArrowUpRight : ArrowDownRight;

  // TTL countdown
  useEffect(() => {
    const validUntil = new Date(order.valid_until).getTime();
    const interval = setInterval(() => {
      const remaining = Math.max(0, Math.floor((validUntil - Date.now()) / 1000));
      setTtlRemaining(remaining);
      if (remaining <= 0) {
        setStatus("error");
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [order.valid_until]);

  const ttlPct = decision.ttl_seconds > 0 ? (ttlRemaining / decision.ttl_seconds) * 100 : 0;
  const ttlColor = ttlPct > 50 ? "#10b981" : ttlPct > 20 ? "#f59e0b" : "#ef4444";

  const handleConfirm = async () => {
    setStatus("confirming");
    try {
      const res = await fetch(`${API_BASE}/api/v1/orders/confirm/${order.order_ticket_id}`, { method: "POST" });
      if (res.ok) {
        setStatus("confirmed");
        setTimeout(() => onConfirm(order.order_ticket_id), 1500);
      } else {
        setStatus("error");
      }
    } catch {
      // Demo mode — simulate success
      setStatus("confirmed");
      setTimeout(() => onConfirm(order.order_ticket_id), 1500);
    }
  };

  const handleDismiss = async () => {
    try {
      await fetch(`${API_BASE}/api/v1/orders/dismiss/${order.order_ticket_id}`, { method: "POST" });
    } catch { /* demo mode */ }
    setStatus("dismissed");
    setTimeout(() => onDismiss(order.order_ticket_id), 500);
  };

  return (
    <>
      <div onClick={onClose} style={{
        position: "fixed", inset: 0, zIndex: 200,
        background: "rgba(0,0,0,0.6)", backdropFilter: "blur(8px)",
      }} />
      <div style={{
        position: "fixed", top: "50%", left: "50%", transform: "translate(-50%, -50%)",
        zIndex: 210, width: 420, maxWidth: "92vw",
        background: "linear-gradient(180deg, #111a2e, #0d1321)",
        border: `1px solid ${color}30`, borderRadius: 20,
        boxShadow: `0 20px 60px rgba(0,0,0,0.6), 0 0 40px ${color}15`,
        overflow: "hidden",
      }}>
        {/* Header */}
        <div style={{
          padding: "24px 24px 16px", borderBottom: `1px solid ${color}20`,
          background: `linear-gradient(135deg, ${color}08, transparent)`,
          position: "relative",
        }}>
          <button onClick={onClose} style={{
            position: "absolute", top: 16, right: 16,
            background: "rgba(99,117,168,0.08)", border: "1px solid var(--border-primary)",
            borderRadius: 8, padding: 6, cursor: "pointer", color: "var(--text-muted)",
          }}>
            <X size={14} />
          </button>

          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
            <div style={{
              width: 52, height: 52, borderRadius: 14,
              background: `${color}15`, border: `2px solid ${color}40`,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <ActionIcon size={26} color={color} />
            </div>
            <div>
              <div style={{ fontSize: 22, fontWeight: 900, color: "var(--text-primary)" }}>
                {order.action} {order.quantity} Shares
              </div>
              <div style={{ fontSize: 14, color: "var(--text-secondary)", marginTop: 2 }}>
                {ticker} at ₹{order.price.toLocaleString(undefined, { minimumFractionDigits: 2 })} per share
              </div>
            </div>
          </div>

          {/* Total value */}
          <div style={{
            padding: "14px 16px", borderRadius: 12,
            background: `${color}08`, border: `1px solid ${color}15`,
            textAlign: "center",
          }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.06em", marginBottom: 4 }}>
              TOTAL ESTIMATED VALUE
            </div>
            <div style={{ fontSize: 28, fontWeight: 900, color, letterSpacing: "-0.02em" }}>
              ₹{order.estimated_value.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </div>
            <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
              {order.order_type} order · {order.quantity} × ₹{order.price.toLocaleString()}
            </div>
          </div>
        </div>

        {/* Details */}
        <div style={{ padding: "16px 24px" }}>
          {/* Portfolio Impact */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 16 }}>
            {[
              { label: "Position Δ", value: `${decision.portfolio_impact.position_delta_pct > 0 ? "+" : ""}${decision.portfolio_impact.position_delta_pct.toFixed(1)}%`, clr: decision.portfolio_impact.position_delta_pct > 0 ? "#10b981" : "#ef4444" },
              { label: "Sector Δ", value: `${decision.portfolio_impact.sector_exposure_delta_pct > 0 ? "+" : ""}${decision.portfolio_impact.sector_exposure_delta_pct.toFixed(1)}%`, clr: "#3b82f6" },
              { label: isBuy ? "Cash Required" : "Cash Freed", value: `₹${Math.abs(decision.portfolio_impact.cash_impact).toLocaleString()}`, clr: isBuy ? "#ef4444" : "#10b981" },
            ].map((m, i) => (
              <div key={i} style={{
                padding: "10px 8px", borderRadius: 10,
                background: "rgba(99,117,168,0.04)", border: "1px solid rgba(99,117,168,0.08)",
                textAlign: "center",
              }}>
                <div style={{ fontSize: 9, fontWeight: 700, color: "var(--text-dim)", letterSpacing: "0.04em", marginBottom: 4 }}>{m.label}</div>
                <div style={{ fontSize: 14, fontWeight: 800, color: m.clr }}>{m.value}</div>
              </div>
            ))}
          </div>

          {/* Risk warnings */}
          {decision.risk_flags && decision.risk_flags.length > 0 && (
            <div style={{
              padding: "10px 14px", borderRadius: 10, marginBottom: 16,
              background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.15)",
              display: "flex", alignItems: "center", gap: 8,
            }}>
              <AlertTriangle size={14} color="#f59e0b" />
              <span style={{ fontSize: 11, color: "#f59e0b", fontWeight: 600 }}>
                {decision.risk_flags.join(" · ")}
              </span>
            </div>
          )}

          {/* TTL bar */}
          <div style={{
            padding: "10px 14px", borderRadius: 10, marginBottom: 20,
            background: `${ttlColor}08`, border: `1px solid ${ttlColor}15`,
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <Clock size={12} color={ttlColor} />
                <span style={{ fontSize: 11, color: "var(--text-muted)" }}>Time to act</span>
              </div>
              <span style={{ fontSize: 14, fontWeight: 800, color: ttlColor, fontFamily: "'JetBrains Mono', monospace" }}>
                {ttlRemaining > 0 ? `${Math.floor(ttlRemaining / 60)}m ${ttlRemaining % 60}s` : "EXPIRED"}
              </span>
            </div>
            <div style={{ height: 3, background: "rgba(99,117,168,0.08)", borderRadius: 9999, overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${ttlPct}%`, background: ttlColor, borderRadius: 9999, transition: "width 1s linear" }} />
            </div>
          </div>

          {/* Action buttons */}
          {status === "idle" && (
            <div style={{ display: "flex", gap: 10 }}>
              <button onClick={handleDismiss} style={{
                flex: 1, padding: "14px", borderRadius: 12, cursor: "pointer",
                background: "rgba(99,117,168,0.06)", border: "1px solid var(--border-primary)",
                color: "var(--text-muted)", fontSize: 13, fontWeight: 700,
                transition: "all 0.2s",
              }}>
                Dismiss
              </button>
              <button onClick={handleConfirm} style={{
                flex: 2, padding: "14px", borderRadius: 12, cursor: "pointer",
                background: `linear-gradient(135deg, ${color}, ${color}cc)`,
                border: "none", color: "white", fontSize: 14, fontWeight: 800,
                boxShadow: `0 4px 20px ${color}40`,
                transition: "all 0.2s", letterSpacing: "0.02em",
              }}>
                <Zap size={16} style={{ display: "inline", verticalAlign: "middle", marginRight: 6 }} />
                Confirm {order.action}
              </button>
            </div>
          )}

          {status === "confirming" && (
            <div style={{
              padding: "16px", borderRadius: 12, textAlign: "center",
              background: `${color}10`, border: `1px solid ${color}25`,
            }}>
              <div className="animate-pulse" style={{ fontSize: 14, fontWeight: 700, color }}>
                Processing order...
              </div>
            </div>
          )}

          {status === "confirmed" && (
            <div style={{
              padding: "16px", borderRadius: 12, textAlign: "center",
              background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.2)",
            }}>
              <CheckCircle size={24} color="#10b981" style={{ margin: "0 auto 8px" }} />
              <div style={{ fontSize: 15, fontWeight: 800, color: "#10b981" }}>Order Logged Successfully</div>
              <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
                {order.action} {order.quantity} {ticker} at ₹{order.price.toLocaleString()} — Advisory mode
              </div>
            </div>
          )}

          {status === "dismissed" && (
            <div style={{
              padding: "16px", borderRadius: 12, textAlign: "center",
              background: "rgba(99,117,168,0.04)", border: "1px solid var(--border-primary)",
            }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text-muted)" }}>Order Dismissed</div>
            </div>
          )}

          {status === "error" && (
            <div style={{
              padding: "16px", borderRadius: 12, textAlign: "center",
              background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.15)",
            }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#ef4444" }}>
                {ttlRemaining <= 0 ? "Order Expired" : "Action Failed"}
              </div>
            </div>
          )}

          {/* Advisory notice */}
          <div style={{
            marginTop: 12, padding: "8px 12px", borderRadius: 8,
            background: "rgba(99,117,168,0.03)", textAlign: "center",
          }}>
            <span style={{ fontSize: 9, color: "var(--text-dim)", letterSpacing: "0.04em" }}>
              <Shield size={8} style={{ display: "inline", verticalAlign: "middle", marginRight: 4 }} />
              ADVISORY MODE — Order logged for tracking. No real trades executed.
            </span>
          </div>
        </div>
      </div>
    </>
  );
}

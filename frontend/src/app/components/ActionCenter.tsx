"use client";
import { useState } from "react";
import {
  CheckSquare, Clock, XCircle, ArrowUp, ShoppingCart, Bell,
  ChevronDown, MoreHorizontal, Shield, Zap, Target,
} from "lucide-react";
import { ActionItem } from "../store";

interface ActionCenterProps {
  actions: ActionItem[];
  onAction: (id: string, action: "prepare" | "snooze" | "ignore" | "escalate", snoozeMins?: number) => void;
  onOpenAlert: (alertId: string) => void;
}

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/api/v1";

const DECISION_COLORS: Record<string, { bg: string; color: string; border: string }> = {
  BUY: { bg: "rgba(16,185,129,0.1)", color: "#10b981", border: "rgba(16,185,129,0.2)" },
  SELL: { bg: "rgba(239,68,68,0.1)", color: "#ef4444", border: "rgba(239,68,68,0.2)" },
  HOLD: { bg: "rgba(59,130,246,0.1)", color: "#3b82f6", border: "rgba(59,130,246,0.2)" },
  WATCH: { bg: "rgba(245,158,11,0.1)", color: "#f59e0b", border: "rgba(245,158,11,0.2)" },
};

const TRUST_COLORS: Record<string, { bg: string; color: string }> = {
  "Safe Advisory": { bg: "rgba(16,185,129,0.08)", color: "#10b981" },
  "Review Needed": { bg: "rgba(245,158,11,0.08)", color: "#f59e0b" },
  "High Risk": { bg: "rgba(239,68,68,0.08)", color: "#ef4444" },
};

function SnoozeDropdown({ onSnooze }: { onSnooze: (mins: number) => void }) {
  const [open, setOpen] = useState(false);
  const durations = [
    { label: "30 min", mins: 30 },
    { label: "1 hour", mins: 60 },
    { label: "4 hours", mins: 240 },
    { label: "Until tomorrow", mins: 960 },
  ];

  return (
    <div style={{ position: "relative" }}>
      <button
        onClick={() => setOpen(!open)}
        aria-label="Snooze alert"
        style={{
          padding: "5px 10px", borderRadius: 6, fontSize: 10, fontWeight: 600,
          border: "1px solid rgba(245,158,11,0.2)",
          background: "rgba(245,158,11,0.06)", color: "#f59e0b",
          cursor: "pointer", display: "flex", alignItems: "center", gap: 4,
        }}
      >
        <Clock size={10} /> Snooze <ChevronDown size={8} />
      </button>
      {open && (
        <div style={{
          position: "absolute", top: "100%", left: 0, zIndex: 50, marginTop: 4,
          background: "rgba(15,20,35,0.98)", border: "1px solid var(--border-primary)",
          borderRadius: 8, boxShadow: "0 8px 32px rgba(0,0,0,0.5)", minWidth: 130,
        }}>
          {durations.map(d => (
            <button
              key={d.mins}
              onClick={() => { onSnooze(d.mins); setOpen(false); }}
              style={{
                display: "block", width: "100%", padding: "8px 12px",
                fontSize: 11, color: "var(--text-secondary)",
                background: "transparent", border: "none",
                borderBottom: "1px solid rgba(255,255,255,0.03)",
                cursor: "pointer", textAlign: "left",
              }}
              onMouseEnter={e => (e.currentTarget.style.background = "rgba(245,158,11,0.06)")}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
            >
              {d.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ActionCenter({ actions, onAction, onOpenAlert }: ActionCenterProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [showCompleted, setShowCompleted] = useState(false);

  const pendingActions = actions.filter(a => a.status === "pending");
  const completedActions = actions.filter(a => a.status !== "pending");

  const toggleSelect = (id: string) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelectedIds(next);
  };

  const handleBulkAction = async (action: "ignore" | "snooze") => {
    for (const id of selectedIds) {
      onAction(id, action, action === "snooze" ? 30 : undefined);
    }
    setSelectedIds(new Set());
  };

  if (actions.length === 0) return null;

  return (
    <div className="card" style={{ overflow: "hidden", marginBottom: 20 }}>
      {/* Header */}
      <div style={{
        padding: "14px 20px",
        borderBottom: "1px solid var(--border-primary)",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        background: "rgba(17,26,46,0.3)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            background: "rgba(245,158,11,0.15)", padding: 7, borderRadius: 9,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <Target size={14} color="#f59e0b" />
          </div>
          <div>
            <h2 style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: 8 }}>
              Action Center
              {pendingActions.length > 0 && (
                <span style={{
                  fontSize: 10, fontWeight: 800, color: "#f59e0b",
                  background: "rgba(245,158,11,0.1)", padding: "2px 8px",
                  borderRadius: 6, border: "1px solid rgba(245,158,11,0.2)",
                }}>
                  {pendingActions.length} pending
                </span>
              )}
            </h2>
            <span style={{ fontSize: 10, color: "var(--text-muted)" }}>Review and act on agent recommendations</span>
          </div>
        </div>

        {/* Bulk actions */}
        {selectedIds.size > 0 && (
          <div style={{ display: "flex", gap: 6 }}>
            <button onClick={() => handleBulkAction("snooze")} style={{
              padding: "5px 10px", borderRadius: 6, fontSize: 10, fontWeight: 600,
              border: "1px solid rgba(245,158,11,0.2)", background: "rgba(245,158,11,0.06)",
              color: "#f59e0b", cursor: "pointer",
            }}>
              Snooze ({selectedIds.size})
            </button>
            <button onClick={() => handleBulkAction("ignore")} style={{
              padding: "5px 10px", borderRadius: 6, fontSize: 10, fontWeight: 600,
              border: "1px solid rgba(99,117,168,0.15)", background: "transparent",
              color: "var(--text-muted)", cursor: "pointer",
            }}>
              Dismiss ({selectedIds.size})
            </button>
          </div>
        )}
      </div>

      {/* Pending Actions */}
      <div style={{ maxHeight: 360, overflowY: "auto" }}>
        {pendingActions.length === 0 && !showCompleted ? (
          <div style={{ textAlign: "center", padding: "30px 20px" }}>
            <CheckSquare size={24} style={{ color: "#10b981", marginBottom: 8, opacity: 0.5 }} />
            <p style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)" }}>All caught up!</p>
            <p style={{ fontSize: 11, color: "var(--text-muted)" }}>No pending actions. Agent is monitoring.</p>
          </div>
        ) : (
          pendingActions.map((item, idx) => {
            const dc = DECISION_COLORS[item.decision] || DECISION_COLORS.WATCH;
            const tc = TRUST_COLORS[item.trust_label] || TRUST_COLORS["Review Needed"];
            const isSelected = selectedIds.has(item.id);

            return (
              <div
                key={item.id}
                style={{
                  padding: "12px 16px",
                  borderBottom: "1px solid rgba(99,117,168,0.05)",
                  background: isSelected ? "rgba(6,182,212,0.04)" : "transparent",
                  transition: "background 0.15s",
                  animation: `fadeIn 0.3s ease ${idx * 0.05}s both`,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  {/* Checkbox */}
                  <button
                    onClick={() => toggleSelect(item.id)}
                    aria-label={isSelected ? "Deselect" : "Select"}
                    style={{
                      width: 18, height: 18, borderRadius: 4, flexShrink: 0,
                      border: `1.5px solid ${isSelected ? "#06b6d4" : "var(--border-primary)"}`,
                      background: isSelected ? "rgba(6,182,212,0.15)" : "transparent",
                      cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
                    }}
                  >
                    {isSelected && <div style={{ width: 8, height: 8, borderRadius: 2, background: "#06b6d4" }} />}
                  </button>

                  {/* Decision badge */}
                  <span style={{
                    fontSize: 10, fontWeight: 800, padding: "3px 8px", borderRadius: 5,
                    background: dc.bg, color: dc.color, border: `1px solid ${dc.border}`,
                    letterSpacing: "0.04em",
                  }}>
                    {item.decision}
                  </span>

                  {/* Ticker + rationale */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{
                        fontSize: 13, fontWeight: 800, color: "var(--text-primary)",
                        fontFamily: "'JetBrains Mono', monospace",
                      }}>
                        {item.ticker}
                      </span>
                      <span style={{ fontSize: 10, color: "var(--text-muted)", fontFamily: "'JetBrains Mono', monospace" }}>
                        {item.confidence}%
                      </span>
                    </div>
                    <p style={{
                      fontSize: 11, color: "var(--text-secondary)", margin: "2px 0 0 0",
                      overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                    }}>
                      {item.rationale_snippet}
                    </p>
                  </div>

                  {/* Trust badge */}
                  <span style={{
                    fontSize: 9, fontWeight: 700, padding: "3px 8px", borderRadius: 5,
                    background: tc.bg, color: tc.color, flexShrink: 0,
                    display: "flex", alignItems: "center", gap: 4,
                  }}>
                    <Shield size={9} /> {item.trust_score}
                  </span>

                  {/* Action buttons */}
                  <div style={{ display: "flex", gap: 4, flexShrink: 0 }}>
                    {(item.decision === "BUY" || item.decision === "SELL") && (
                      <button
                        onClick={() => onAction(item.id, "prepare")}
                        aria-label="Prepare order"
                        style={{
                          padding: "5px 10px", borderRadius: 6, fontSize: 10, fontWeight: 700,
                          border: "none",
                          background: `linear-gradient(135deg, ${dc.color}, ${dc.color}cc)`,
                          color: "#fff", cursor: "pointer",
                          display: "flex", alignItems: "center", gap: 4,
                          boxShadow: `0 2px 8px ${dc.color}30`,
                        }}
                      >
                        <ShoppingCart size={10} /> Prepare
                      </button>
                    )}
                    <SnoozeDropdown onSnooze={(mins) => onAction(item.id, "snooze", mins)} />
                    <button
                      onClick={() => onAction(item.id, "ignore")}
                      aria-label="Dismiss alert"
                      style={{
                        padding: "5px 8px", borderRadius: 6,
                        border: "1px solid var(--border-primary)",
                        background: "transparent", color: "var(--text-dim)",
                        cursor: "pointer", fontSize: 10,
                      }}
                    >
                      <XCircle size={10} />
                    </button>
                    <button
                      onClick={() => onAction(item.id, "escalate")}
                      aria-label="Escalate alert"
                      style={{
                        padding: "5px 8px", borderRadius: 6,
                        border: "1px solid rgba(139,92,246,0.2)",
                        background: "rgba(139,92,246,0.06)", color: "#a78bfa",
                        cursor: "pointer", fontSize: 10,
                      }}
                    >
                      <ArrowUp size={10} />
                    </button>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Completed footer */}
      {completedActions.length > 0 && (
        <div style={{
          padding: "8px 16px",
          borderTop: "1px solid var(--border-primary)",
        }}>
          <button
            onClick={() => setShowCompleted(!showCompleted)}
            style={{
              fontSize: 10, color: "var(--text-dim)", background: "none",
              border: "none", cursor: "pointer", display: "flex", alignItems: "center", gap: 4,
            }}
          >
            <ChevronDown size={10} style={{ transform: showCompleted ? "rotate(180deg)" : "none", transition: "transform 0.2s" }} />
            {completedActions.length} completed actions
          </button>
          {showCompleted && (
            <div style={{ marginTop: 8 }}>
              {completedActions.slice(0, 5).map(a => (
                <div key={a.id} style={{
                  display: "flex", alignItems: "center", gap: 8, padding: "4px 0",
                  fontSize: 10, color: "var(--text-dim)",
                }}>
                  <CheckSquare size={10} color="#10b981" />
                  <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>{a.ticker}</span>
                  <span>{a.decision}</span>
                  <span style={{ color: "var(--text-muted)" }}>→ {a.status}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

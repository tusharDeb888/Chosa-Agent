"use client";
import { useState } from "react";
import { X, AlertTriangle } from "lucide-react";

export default function KillConfirmModal({ onConfirm, onCancel }: { onConfirm: () => void; onCancel: () => void }) {
  const [typed, setTyped] = useState("");
  const canKill = typed === "KILL";

  return (
    <div className="modal-overlay" style={{
      position: "fixed", inset: 0, zIndex: 200,
      background: "rgba(0,0,0,0.7)", backdropFilter: "blur(8px)",
      display: "flex", alignItems: "center", justifyContent: "center", padding: 24,
    }}>
      <div className="modal-content" style={{
        background: "linear-gradient(145deg, #1a1020, #140a14)",
        border: "1px solid rgba(239,68,68,0.2)",
        borderRadius: 24, padding: "32px 28px", maxWidth: 400, width: "100%",
        boxShadow: "0 24px 80px rgba(239,68,68,0.15)",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: "rgba(239,68,68,0.15)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <AlertTriangle size={18} color="#ef4444" />
            </div>
            <div>
              <h2 style={{ fontSize: 18, fontWeight: 800, color: "#ef4444" }}>Terminate Agent</h2>
              <p style={{ fontSize: 12, color: "var(--text-muted)" }}>This will stop all processing</p>
            </div>
          </div>
          <button onClick={onCancel} style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer" }}>
            <X size={16} />
          </button>
        </div>

        <p style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 20, lineHeight: 1.6 }}>
          Terminating the agent will immediately stop all market monitoring, signal processing, and alert generation.
          In-flight decisions will be discarded.
        </p>

        <div style={{ marginBottom: 20 }}>
          <label style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.06em", display: "block", marginBottom: 8 }}>
            TYPE &quot;KILL&quot; TO CONFIRM
          </label>
          <input
            className="kill-input"
            value={typed}
            onChange={e => setTyped(e.target.value.toUpperCase())}
            placeholder="KILL"
            style={{
              width: "100%", padding: "12px 16px", borderRadius: 12,
              background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.2)",
              color: "#ef4444", fontSize: 16, fontWeight: 800, letterSpacing: "0.15em",
              textAlign: "center", outline: "none", fontFamily: "'JetBrains Mono', monospace",
            }}
          />
        </div>

        <div style={{ display: "flex", gap: 10 }}>
          <button onClick={onCancel} style={{
            flex: 1, padding: "11px 20px", borderRadius: 12, fontSize: 13, fontWeight: 600,
            background: "transparent", color: "var(--text-secondary)",
            border: "1px solid var(--border-primary)", cursor: "pointer",
          }}>
            Cancel
          </button>
          <button disabled={!canKill} onClick={onConfirm} style={{
            flex: 1, padding: "11px 20px", borderRadius: 12, fontSize: 13, fontWeight: 700,
            background: canKill ? "rgba(239,68,68,0.15)" : "rgba(239,68,68,0.05)",
            color: canKill ? "#ef4444" : "rgba(239,68,68,0.3)",
            border: `1px solid ${canKill ? "rgba(239,68,68,0.3)" : "rgba(239,68,68,0.1)"}`,
            cursor: canKill ? "pointer" : "not-allowed",
          }}>
            Terminate Agent
          </button>
        </div>
      </div>
    </div>
  );
}

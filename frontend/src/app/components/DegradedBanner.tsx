"use client";
import { AlertTriangle, Wifi, ExternalLink } from "lucide-react";

interface DegradedBannerProps {
  agentState: string;
  degradedReason?: string;
}

export default function DegradedBanner({ agentState, degradedReason }: DegradedBannerProps) {
  if (agentState !== "DEGRADED") return null;

  return (
    <div
      role="alert"
      aria-live="assertive"
      style={{
        position: "sticky",
        top: 0,
        zIndex: 70,
        padding: "10px 24px",
        background: "linear-gradient(90deg, rgba(139,92,246,0.15) 0%, rgba(245,158,11,0.12) 50%, rgba(139,92,246,0.15) 100%)",
        borderBottom: "1px solid rgba(139,92,246,0.3)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        backdropFilter: "blur(12px)",
        animation: "fadeIn 0.4s ease forwards",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div
          style={{
            width: 28, height: 28, borderRadius: 8,
            background: "rgba(139,92,246,0.2)",
            display: "flex", alignItems: "center", justifyContent: "center",
            animation: "pulse-dot 2s ease-in-out infinite",
          }}
        >
          <AlertTriangle size={14} color="#a78bfa" />
        </div>
        <div>
          <span style={{
            fontSize: 12, fontWeight: 700, color: "#a78bfa",
            letterSpacing: "0.03em",
          }}>
            DEGRADED MODE
          </span>
          <span style={{
            fontSize: 12, color: "var(--text-secondary)",
            marginLeft: 8,
          }}>
            {degradedReason || "Some services unavailable — advisory-only recommendations active"}
          </span>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <span style={{
          fontSize: 10, padding: "3px 10px", borderRadius: 6,
          background: "rgba(245,158,11,0.1)", border: "1px solid rgba(245,158,11,0.2)",
          color: "#f59e0b", fontWeight: 700,
          display: "flex", alignItems: "center", gap: 4,
        }}>
          <Wifi size={9} /> Advisory Only
        </span>
        <button
          onClick={() => {
            const el = document.getElementById("worker-status-section");
            if (el) el.scrollIntoView({ behavior: "smooth" });
          }}
          aria-label="View system health details"
          style={{
            fontSize: 10, padding: "3px 10px", borderRadius: 6,
            background: "rgba(99,117,168,0.06)",
            border: "1px solid var(--border-primary)",
            color: "var(--text-secondary)", fontWeight: 600,
            cursor: "pointer",
            display: "flex", alignItems: "center", gap: 4,
          }}
        >
          View Health <ExternalLink size={8} />
        </button>
      </div>
    </div>
  );
}

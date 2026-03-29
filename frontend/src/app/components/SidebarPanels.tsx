"use client";
import { Layers, Database, Clock } from "lucide-react";
import { Metrics, AgentStatus, ViewMode } from "./types";

function SidebarCard({ icon: Icon, title, iconColor, iconBg, children }: {
  icon: React.ElementType; title: string; iconColor: string; iconBg: string; children: React.ReactNode;
}) {
  return (
    <div className="card" style={{ overflow: "hidden" }}>
      <div style={{
        padding: "14px 18px", borderBottom: "1px solid var(--border-primary)",
        display: "flex", alignItems: "center", gap: 10, background: "rgba(17,26,46,0.3)",
      }}>
        <div style={{ background: iconBg, padding: 6, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Icon size={13} color={iconColor} />
        </div>
        <h3 style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", letterSpacing: "0.02em" }}>{title}</h3>
      </div>
      {children}
    </div>
  );
}

function WorkerRow({ name, status }: { name: string; status: string }) {
  const isHealthy = status === "healthy";
  const isPaused = status === "paused";
  const dot = isHealthy ? "#10b981" : status === "degraded" ? "#f59e0b" : isPaused ? "#64748b" : "#ef4444";
  const text = isHealthy ? "#10b981" : status === "degraded" ? "#f59e0b" : isPaused ? "#64748b" : "#ef4444";

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "9px 12px", borderRadius: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{ position: "relative", width: 8, height: 8 }}>
          {isHealthy && <span className="animate-pulse-dot" style={{ position: "absolute", inset: 0, borderRadius: "50%", background: dot, opacity: 0.4 }} />}
          <span style={{ position: "relative", display: "inline-flex", borderRadius: "50%", width: 8, height: 8, background: dot, boxShadow: isHealthy ? `0 0 6px ${dot}80` : "none" }} />
        </div>
        <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)" }}>{name}</span>
      </div>
      <span style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", color: text }}>{status}</span>
    </div>
  );
}

function StreamRow({ topic, count }: { topic: string; count: number }) {
  const shortName = topic.replace("alpha-hunter:", "").replace("market.ticks.", "ticks/").replace("signals.", "sig/").replace("agent.", "").replace("alerts.", "alert/");
  const barWidth = Math.min((count / 1000) * 100, 100);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, fontWeight: 600, color: "var(--text-secondary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{shortName}</span>
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, fontWeight: 700, color: "#22d3ee", flexShrink: 0 }}>{count.toLocaleString()}</span>
      </div>
      <div style={{ height: 4, background: "rgba(99,117,168,0.06)", borderRadius: 9999, overflow: "hidden" }}>
        <div className="animate-shimmer" style={{ height: "100%", background: "linear-gradient(90deg,#3b82f6,#06b6d4)", borderRadius: 9999, transition: "width 1s ease-out", width: `${Math.max(barWidth, 2)}%` }} />
      </div>
    </div>
  );
}

export default function SidebarPanels({ metrics, status, agentState, connected, viewMode }: {
  metrics: Metrics | null; status: AgentStatus | null; agentState: string; connected: boolean; viewMode: ViewMode;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Stream Pipeline (pro only) */}
      {viewMode === "pro" && (
        <SidebarCard icon={Layers} title="Stream Pipeline" iconColor="#06b6d4" iconBg="rgba(6,182,212,0.15)">
          <div style={{ padding: 16 }}>
            {metrics?.streams && Object.entries(metrics.streams).length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {Object.entries(metrics.streams).map(([topic, count]) => (
                  <StreamRow key={topic} topic={topic} count={count as number} />
                ))}
              </div>
            ) : (
              <p style={{ fontSize: 12, color: "var(--text-muted)", textAlign: "center", padding: "8px 0" }}>Pipeline is empty</p>
            )}
          </div>
        </SidebarCard>
      )}

      {/* Worker Status */}
      <SidebarCard icon={Database} title="Worker Status" iconColor="#8b5cf6" iconBg="rgba(139,92,246,0.15)">
        <div style={{ padding: "6px 8px" }}>
          <WorkerRow name="Ingestion" status={metrics?.workers?.ingestion?.status || "unknown"} />
          <WorkerRow name="Qualification" status={agentState === "RUNNING" ? "healthy" : "paused"} />
          <WorkerRow name="Orchestrator" status={agentState === "RUNNING" ? "healthy" : "paused"} />
          <WorkerRow name="Notifications" status={connected ? "healthy" : "degraded"} />
          <WorkerRow name="News Radar (24/7)" status="healthy" />
        </div>
      </SidebarCard>

      {/* State History */}
      <SidebarCard icon={Clock} title="State History" iconColor="#f59e0b" iconBg="rgba(245,158,11,0.15)">
        <div className="custom-scrollbar" style={{ padding: 14, maxHeight: 200, overflowY: "auto" }}>
          {status?.recent_transitions && status.recent_transitions.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {status.recent_transitions.map((t, i) => (
                <div key={i} style={{
                  padding: "8px 12px", background: "rgba(10,14,26,0.5)", borderRadius: 8,
                  fontSize: 10, color: "var(--text-secondary)", fontFamily: "'JetBrains Mono', monospace",
                  border: "1px solid var(--border-primary)", lineHeight: 1.5, wordBreak: "break-word",
                }}>
                  {t}
                </div>
              ))}
            </div>
          ) : (
            <p style={{ fontSize: 12, color: "var(--text-muted)", textAlign: "center", padding: "8px 0" }}>No transitions recorded</p>
          )}
        </div>
      </SidebarCard>
    </div>
  );
}

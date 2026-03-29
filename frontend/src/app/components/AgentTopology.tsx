"use client";
import { useEffect, useState } from "react";
import { Activity, AlertTriangle, Bot, Check, Database, Eye, Filter, Gauge, Shield, Zap } from "lucide-react";

interface AgentNode {
  id: string;
  name: string;
  role: string;
  type: string;
  capabilities: string[];
  status: string;
  model_used: string | null;
}

interface TopologyData {
  agents: AgentNode[];
  edges: { from: string; to: string; channel: string; protocol: string }[];
  orchestration: { pattern: string; framework: string };
  communication: { inter_agent: string; real_time: string; control_plane: string };
  fault_tolerance: { circuit_breakers: any[]; retry_policy: string };
  agent_state: string;
}

const AGENT_ICONS: Record<string, any> = {
  "ingestion-agent": Activity,
  "qualification-agent": Filter,
  "enrichment-agent": Database,
  "synthesis-agent": Bot,
  "policy-agent": Shield,
  "notification-agent": Zap,
};

const AGENT_COLORS: Record<string, string> = {
  "ingestion-agent": "#3b82f6",
  "qualification-agent": "#8b5cf6",
  "enrichment-agent": "#f59e0b",
  "synthesis-agent": "#10b981",
  "policy-agent": "#ef4444",
  "notification-agent": "#06b6d4",
};

const STATUS_COLOR: Record<string, string> = {
  healthy: "#22c55e",
  paused: "#f59e0b",
  stale: "#ef4444",
  unknown: "#6b7280",
};

export default function AgentTopology({
  apiBase,
  agentState,
}: {
  apiBase: string;
  agentState: string;
}) {
  const [topology, setTopology] = useState<TopologyData | null>(null);
  const [activeEdge, setActiveEdge] = useState(0);

  useEffect(() => {
    fetch(`${apiBase}/ops/topology`)
      .then((r) => r.json())
      .then(setTopology)
      .catch(() => {});
    const id = setInterval(() => {
      fetch(`${apiBase}/ops/topology`)
        .then((r) => r.json())
        .then(setTopology)
        .catch(() => {});
    }, 10000);
    return () => clearInterval(id);
  }, [apiBase]);

  // Animate edge flow
  useEffect(() => {
    if (agentState !== "RUNNING") return;
    const id = setInterval(() => setActiveEdge((p) => (p + 1) % 5), 800);
    return () => clearInterval(id);
  }, [agentState]);

  if (!topology) {
    return (
      <div className="glass-card p-6 text-center">
        <Bot className="mx-auto mb-2 opacity-40" size={32} />
        <p className="text-sm opacity-60">Loading agent topology…</p>
      </div>
    );
  }

  return (
    <div className="glass-card p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold flex items-center gap-2">
          <Bot size={18} /> Multi-Agent Pipeline
        </h3>
        <span
          className="px-2 py-0.5 rounded text-xs font-mono"
          style={{
            background: agentState === "RUNNING" ? "rgba(34,197,94,0.15)" : "rgba(245,158,11,0.15)",
            color: agentState === "RUNNING" ? "#22c55e" : "#f59e0b",
          }}
        >
          {topology.orchestration.pattern}
        </span>
      </div>

      {/* Pipeline nodes */}
      <div className="topology-pipeline">
        {topology.agents.map((agent, idx) => {
          const Icon = AGENT_ICONS[agent.id] || Bot;
          const color = AGENT_COLORS[agent.id] || "#6b7280";
          const statusColor = STATUS_COLOR[agent.status] || STATUS_COLOR.unknown;
          const isActive = agentState === "RUNNING" && activeEdge === idx;

          return (
            <div key={agent.id} className="topology-node-wrapper">
              {/* Node */}
              <div
                className={`topology-node ${isActive ? "topology-node-active" : ""}`}
                style={{ borderColor: color }}
                title={agent.role}
              >
                {/* Status dot */}
                <div
                  className="topology-status-dot"
                  style={{ background: statusColor }}
                />
                <Icon size={20} style={{ color }} />
                <div className="topology-node-label">
                  {agent.name.replace(" Agent", "")}
                </div>
                <div className="topology-node-type">{agent.type}</div>
                {agent.model_used && (
                  <div className="topology-node-model">
                    🤖 {agent.model_used.split("/").pop()}
                  </div>
                )}
              </div>

              {/* Edge arrow */}
              {idx < topology.agents.length - 1 && (
                <div className={`topology-edge ${activeEdge === idx && agentState === "RUNNING" ? "topology-edge-active" : ""}`}>
                  <div className="topology-edge-line" />
                  <div className="topology-edge-arrow">→</div>
                  <div className="topology-edge-label">
                    {topology.edges[idx]?.channel || ""}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Communication info */}
      <div className="mt-4 grid grid-cols-2 gap-2 text-xs opacity-70">
        <div className="flex items-center gap-1">
          <Database size={12} />
          <span>Inter-agent: Redis Streams</span>
        </div>
        <div className="flex items-center gap-1">
          <Zap size={12} />
          <span>Real-time: WebSocket + SSE</span>
        </div>
        <div className="flex items-center gap-1">
          <Shield size={12} />
          <span>Retry: Exponential backoff + jitter</span>
        </div>
        <div className="flex items-center gap-1">
          <AlertTriangle size={12} />
          <span>
            Circuit breakers:{" "}
            {topology.fault_tolerance.circuit_breakers.length > 0
              ? topology.fault_tolerance.circuit_breakers
                  .map((cb: any) => `${cb.name}:${cb.state}`)
                  .join(", ")
              : "All CLOSED ✓"}
          </span>
        </div>
      </div>
    </div>
  );
}

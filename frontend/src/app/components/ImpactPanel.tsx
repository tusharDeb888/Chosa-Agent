"use client";
import { useEffect, useState } from "react";
import {
  Activity, BarChart3, Clock, DollarSign, Shield, TrendingUp, Zap, Bot,
} from "lucide-react";

interface ImpactData {
  pipeline_throughput: {
    market_ticks_processed: number;
    anomalies_detected: number;
    signals_qualified: number;
    qualification_rate_pct: number;
    decisions_made: number;
    alerts_delivered: number;
  };
  risk_management: {
    policy_violations_caught: number;
    bad_trades_prevented: number;
    estimated_loss_prevented_inr: number;
    dlq_events_quarantined: number;
  };
  efficiency: {
    avg_signal_to_alert_ms: number;
    human_equivalent_time: string;
    decisions_per_minute: number;
    automation_coverage_pct: number;
  };
  cost_optimization: {
    total_calls: number;
    calls_by_model: Record<string, number>;
    total_cost_usd: number;
    cost_savings_pct: number;
    routing_strategy: string;
  };
  comparison_vs_manual: {
    speedup_factor: string;
    cost_per_decision_usd: number;
  };
}

function MetricCard({
  icon: Icon,
  label,
  value,
  subtext,
  color,
}: {
  icon: any;
  label: string;
  value: string | number;
  subtext?: string;
  color: string;
}) {
  return (
    <div className="impact-metric-card">
      <div className="impact-metric-icon" style={{ background: `${color}22`, color }}>
        <Icon size={18} />
      </div>
      <div className="impact-metric-content">
        <div className="impact-metric-value">{value}</div>
        <div className="impact-metric-label">{label}</div>
        {subtext && <div className="impact-metric-sub">{subtext}</div>}
      </div>
    </div>
  );
}

export default function ImpactPanel({ apiBase }: { apiBase: string }) {
  const [data, setData] = useState<ImpactData | null>(null);

  useEffect(() => {
    const load = () => {
      fetch(`${apiBase}/ops/impact`)
        .then((r) => r.json())
        .then(setData)
        .catch(() => {});
    };
    load();
    const id = setInterval(load, 8000);
    return () => clearInterval(id);
  }, [apiBase]);

  if (!data) {
    return (
      <div className="glass-card p-6 text-center">
        <BarChart3 className="mx-auto mb-2 opacity-40" size={32} />
        <p className="text-sm opacity-60">Loading impact metrics…</p>
      </div>
    );
  }

  const tp = data.pipeline_throughput;
  const rm = data.risk_management;
  const ef = data.efficiency;
  const co = data.cost_optimization;
  const cmp = data.comparison_vs_manual;

  return (
    <div className="glass-card p-5" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold flex items-center gap-2">
          <BarChart3 size={18} /> Business Impact Dashboard
        </h3>
        <span className="px-2 py-0.5 rounded text-xs font-mono bg-green-500/10 text-green-400">
          Live
        </span>
      </div>

      {/* Primary metrics grid */}
      <div className="impact-grid">
        <MetricCard
          icon={Activity}
          label="Signals Analyzed"
          value={tp.anomalies_detected.toLocaleString()}
          subtext={`from ${tp.market_ticks_processed.toLocaleString()} ticks`}
          color="#3b82f6"
        />
        <MetricCard
          icon={Shield}
          label="Bad Trades Blocked"
          value={rm.bad_trades_prevented}
          subtext={`₹${(rm.estimated_loss_prevented_inr / 1000).toFixed(0)}K saved`}
          color="#ef4444"
        />
        <MetricCard
          icon={Zap}
          label="Signal→Alert Latency"
          value={`${ef.avg_signal_to_alert_ms}ms`}
          subtext={`vs hours for manual`}
          color="#f59e0b"
        />
        <MetricCard
          icon={TrendingUp}
          label="Speedup vs Manual"
          value={cmp.speedup_factor}
          subtext={ef.human_equivalent_time}
          color="#10b981"
        />
        <MetricCard
          icon={Bot}
          label="Model Routing"
          value={`${co.cost_savings_pct}% saved`}
          subtext={co.routing_strategy.split(":")[0]}
          color="#8b5cf6"
        />
        <MetricCard
          icon={DollarSign}
          label="Cost/Decision"
          value={`$${cmp.cost_per_decision_usd.toFixed(5)}`}
          subtext={`${co.total_calls} total calls`}
          color="#06b6d4"
        />
      </div>

      {/* Model routing breakdown */}
      {co.total_calls > 0 && (
        <div className="mt-4 pt-3 border-t border-white/5">
          <div className="text-xs font-semibold mb-2 opacity-70 flex items-center gap-1">
            <Bot size={12} /> Smart Model Routing Breakdown
          </div>
          <div className="flex gap-2 flex-wrap">
            {Object.entries(co.calls_by_model).map(([model, count]) => (
              <div
                key={model}
                className="px-2 py-1 rounded text-xs font-mono"
                style={{
                  background: model.includes("70b")
                    ? "rgba(139,92,246,0.12)"
                    : model.includes("8b")
                    ? "rgba(16,185,129,0.12)"
                    : "rgba(107,114,128,0.12)",
                  color: model.includes("70b")
                    ? "#a78bfa"
                    : model.includes("8b")
                    ? "#6ee7b7"
                    : "#9ca3af",
                }}
              >
                {model.split("-").slice(0, 3).join("-")}: {count as number} calls
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Qualification funnel */}
      <div className="mt-3 pt-3 border-t border-white/5" style={{ marginTop: "auto" }}>
        <div className="text-xs font-semibold mb-2 opacity-70">Pipeline Funnel</div>
        <div className="flex items-center gap-1 text-xs">
          <span className="text-blue-400">{tp.market_ticks_processed} ticks</span>
          <span className="opacity-30">→</span>
          <span className="text-purple-400">{tp.anomalies_detected} anomalies</span>
          <span className="opacity-30">→</span>
          <span className="text-amber-400">{tp.signals_qualified} qualified</span>
          <span className="opacity-30">→</span>
          <span className="text-green-400">{tp.decisions_made} decisions</span>
          <span className="opacity-30">→</span>
          <span className="text-cyan-400">{tp.alerts_delivered} alerts</span>
        </div>
        <div className="mt-1 text-xs opacity-50">
          Qualification rate: {tp.qualification_rate_pct}% — DLQ quarantined: {rm.dlq_events_quarantined}
        </div>
      </div>
    </div>
  );
}

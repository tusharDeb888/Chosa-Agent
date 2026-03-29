"use client";
import { useState, useEffect } from "react";
import {
  Zap, Play, TrendingUp, FileText, Moon, CheckCircle, Loader2,
  Target, ChevronRight, BarChart3, AlertTriangle, X,
} from "lucide-react";

interface Scenario {
  id: string;
  name: string;
  description: string;
  expected_outcomes: string[];
  event_count: number;
  duration_seconds: number;
}

interface DemoScenarioModalProps {
  onClose: () => void;
  onRunScenario: (scenarioId: string, events: any[]) => void;
}

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/api/v1";

const SCENARIO_ICONS: Record<string, typeof Zap> = {
  earnings_shock: BarChart3,
  volume_spike: TrendingUp,
  market_closed_filing: Moon,
};

const SCENARIO_COLORS: Record<string, string> = {
  earnings_shock: "#f59e0b",
  volume_spike: "#10b981",
  market_closed_filing: "#8b5cf6",
};

export default function DemoScenarioModal({ onClose, onRunScenario }: DemoScenarioModalProps) {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [completed, setCompleted] = useState(false);
  const [result, setResult] = useState<any>(null);

  useEffect(() => {
    fetch(`${API_BASE}/demo/scenarios`)
      .then(r => r.json())
      .then(data => {
        setScenarios(data.scenarios || []);
        setLoading(false);
      })
      .catch(() => {
        // Fallback scenarios
        setScenarios([
          {
            id: "earnings_shock", name: "Earnings Shock",
            description: "TCS announces surprise buyback + strong Q4. INFY misses estimates.",
            expected_outcomes: ["TCS: HOLD (buyback support)", "INFY: WATCH (miss + degraded)", "Banking: BUY (sector rotation)"],
            event_count: 3, duration_seconds: 12,
          },
          {
            id: "volume_spike", name: "Volume Spike",
            description: "ICICIBANK sees 4x volume with institutional buying. HDFCBANK under RBI pressure.",
            expected_outcomes: ["ICICIBANK: BUY (volume confirmed)", "HDFCBANK: SELL (concentration + regulatory)", "Portfolio risk warning"],
            event_count: 2, duration_seconds: 10,
          },
          {
            id: "market_closed_filing", name: "Market Closed + Filing",
            description: "After-hours corporate filing triggers advisory during market closed.",
            expected_outcomes: ["RELIANCE: WATCH (promoter sale)", "News Radar 24/7 active", "Advisory-only mode"],
            event_count: 2, duration_seconds: 8,
          },
        ]);
        setLoading(false);
      });
  }, []);

  const handleRun = async (scenarioId: string) => {
    setRunning(scenarioId);
    setProgress(0);
    setCompleted(false);

    const sc = scenarios.find(s => s.id === scenarioId);
    const duration = (sc?.duration_seconds || 10) * 1000;

    // Progress animation
    const steps = 20;
    const stepTime = duration / steps;
    for (let i = 0; i <= steps; i++) {
      await new Promise(r => setTimeout(r, stepTime));
      setProgress(Math.min(((i + 1) / steps) * 100, 100));
    }

    try {
      const res = await fetch(`${API_BASE}/demo/run?scenario=${scenarioId}`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setResult(data);
        // Pass events up for client-side playback
        if (data.events) {
          onRunScenario(scenarioId, data.events);
        }
      }
    } catch { /* quiet */ }

    setCompleted(true);
    setTimeout(() => {
      setRunning(null);
      setCompleted(false);
      setProgress(0);
      onClose();
    }, 2000);
  };

  return (
    <div className="modal-overlay" style={{
      position: "fixed", inset: 0, zIndex: 200,
      background: "rgba(0,0,0,0.7)", backdropFilter: "blur(8px)",
      display: "flex", alignItems: "center", justifyContent: "center", padding: 24,
    }}>
      <div className="modal-content" style={{
        background: "linear-gradient(145deg, #111a2e, #0d1321)",
        border: "1px solid rgba(99,117,168,0.15)",
        borderRadius: 24, padding: "32px 28px", maxWidth: 560, width: "100%",
        boxShadow: "0 24px 80px rgba(0,0,0,0.6)",
        animation: "fadeIn 0.3s ease",
      }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
              <div style={{
                width: 36, height: 36, borderRadius: 10,
                background: "linear-gradient(135deg, #f59e0b, #ef4444)",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <Zap size={18} color="white" />
              </div>
              <h2 style={{ fontSize: 20, fontWeight: 800, letterSpacing: "-0.01em" }}>Demo Scenarios</h2>
            </div>
            <p style={{ fontSize: 13, color: "var(--text-secondary)" }}>
              Run pre-built market scenarios to see the agent in action
            </p>
          </div>
          <button onClick={onClose} aria-label="Close" style={{
            background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", padding: 4,
          }}>
            <X size={18} />
          </button>
        </div>

        {/* Scenarios */}
        {loading ? (
          <div style={{ textAlign: "center", padding: 40 }}>
            <Loader2 size={24} className="spin" style={{ color: "var(--text-dim)" }} />
          </div>
        ) : running ? (
          // Running state
          <div style={{ textAlign: "center", padding: "20px 0" }}>
            <div style={{
              width: 72, height: 72, borderRadius: 18, margin: "0 auto 20px",
              background: `${SCENARIO_COLORS[running] || "#f59e0b"}20`,
              border: `2px solid ${SCENARIO_COLORS[running] || "#f59e0b"}40`,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              {completed ? (
                <CheckCircle size={32} color="#10b981" />
              ) : (
                <Loader2 size={32} color={SCENARIO_COLORS[running] || "#f59e0b"} className="spin" />
              )}
            </div>

            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>
              {completed ? "Scenario Complete!" : `Running: ${scenarios.find(s => s.id === running)?.name}`}
            </h3>
            <p style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 20 }}>
              {completed ? "Events published to live feed" : "Publishing events to alert stream..."}
            </p>

            {/* Progress bar */}
            <div style={{
              height: 6, background: "rgba(99,117,168,0.1)", borderRadius: 9999,
              overflow: "hidden", margin: "0 40px",
            }}>
              <div style={{
                height: "100%", width: `${progress}%`, borderRadius: 9999,
                background: completed
                  ? "linear-gradient(90deg, #10b981, #06b6d4)"
                  : `linear-gradient(90deg, ${SCENARIO_COLORS[running] || "#f59e0b"}, #06b6d4)`,
                transition: "width 0.3s ease",
              }} />
            </div>

            {/* Expected outcomes */}
            {result && (
              <div style={{ marginTop: 20, textAlign: "left", padding: "0 12px" }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: "var(--text-dim)", marginBottom: 8, letterSpacing: "0.05em" }}>
                  EXPECTED OUTCOMES
                </div>
                {(result.expected_outcomes || []).map((o: string, i: number) => (
                  <div key={i} style={{
                    display: "flex", alignItems: "center", gap: 8, padding: "6px 0",
                    fontSize: 12, color: "var(--text-secondary)",
                  }}>
                    <CheckCircle size={12} color="#10b981" />
                    {o}
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          // Scenario picker
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {scenarios.map(sc => {
              const ScIcon = SCENARIO_ICONS[sc.id] || Zap;
              const color = SCENARIO_COLORS[sc.id] || "#f59e0b";

              return (
                <button
                  key={sc.id}
                  onClick={() => handleRun(sc.id)}
                  style={{
                    display: "flex", alignItems: "flex-start", gap: 14, padding: "16px 18px",
                    background: "rgba(99,117,168,0.04)",
                    border: "1px solid rgba(99,117,168,0.08)",
                    borderRadius: 14, cursor: "pointer", transition: "all 0.2s",
                    textAlign: "left", width: "100%",
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.background = `${color}10`;
                    e.currentTarget.style.borderColor = `${color}30`;
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.background = "rgba(99,117,168,0.04)";
                    e.currentTarget.style.borderColor = "rgba(99,117,168,0.08)";
                  }}
                >
                  <div style={{
                    width: 38, height: 38, borderRadius: 10, flexShrink: 0,
                    background: `${color}15`, border: `1px solid ${color}25`,
                    display: "flex", alignItems: "center", justifyContent: "center",
                  }}>
                    <ScIcon size={16} color={color} />
                  </div>

                  <div style={{ flex: 1 }}>
                    <div style={{
                      fontSize: 14, fontWeight: 700, color: "var(--text-primary)", marginBottom: 4,
                      display: "flex", alignItems: "center", gap: 8,
                    }}>
                      {sc.name}
                      <span style={{
                        fontSize: 9, padding: "2px 6px", borderRadius: 4,
                        background: `${color}15`, color, fontWeight: 700,
                      }}>
                        {sc.event_count} events
                      </span>
                    </div>
                    <p style={{ fontSize: 11, color: "var(--text-secondary)", margin: "0 0 8px 0", lineHeight: 1.5 }}>
                      {sc.description}
                    </p>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                      {sc.expected_outcomes.slice(0, 3).map((o, i) => (
                        <span key={i} style={{
                          fontSize: 9, padding: "2px 8px", borderRadius: 4,
                          background: "rgba(99,117,168,0.06)", color: "var(--text-muted)",
                          display: "flex", alignItems: "center", gap: 3,
                        }}>
                          <Target size={7} /> {o}
                        </span>
                      ))}
                    </div>
                  </div>

                  <ChevronRight size={16} color="var(--text-dim)" style={{ flexShrink: 0, marginTop: 10 }} />
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

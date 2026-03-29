"use client";
import { useState } from "react";
import {
  Rocket, Database, Shield, Zap, CheckCircle, Play, X, ChevronRight,
  ChevronLeft, BarChart3, Briefcase, Upload, Sliders, Eye, Monitor,
} from "lucide-react";

interface OnboardingModalProps {
  onClose: () => void;
  onStartDemo: () => void;
}

type Step = "mode" | "portfolio" | "risk" | "launch";
type Mode = "demo" | "live";
type RiskProfile = "conservative" | "balanced" | "aggressive";

const RISK_PROFILES: Record<RiskProfile, { label: string; color: string; desc: string; maxConcentration: number; minConfidence: number }> = {
  conservative: {
    label: "Conservative", color: "#3b82f6",
    desc: "Lower risk tolerance. Smaller position sizes, higher confidence threshold for BUY/SELL.",
    maxConcentration: 15, minConfidence: 75,
  },
  balanced: {
    label: "Balanced", color: "#10b981",
    desc: "Standard risk management. Moderate position sizes with policy guardrails.",
    maxConcentration: 25, minConfidence: 60,
  },
  aggressive: {
    label: "Aggressive", color: "#f59e0b",
    desc: "Higher risk tolerance. Larger positions allowed, lower confidence thresholds.",
    maxConcentration: 40, minConfidence: 45,
  },
};

const DEMO_HOLDINGS = [
  { symbol: "RELIANCE", qty: 40, buy_price: 2400 },
  { symbol: "TCS", qty: 20, buy_price: 3800 },
  { symbol: "HDFCBANK", qty: 110, buy_price: 1680 },
  { symbol: "ICICIBANK", qty: 50, buy_price: 1040 },
  { symbol: "INFY", qty: 30, buy_price: 1380 },
];

export default function OnboardingModal({ onClose, onStartDemo }: OnboardingModalProps) {
  const [currentStep, setCurrentStep] = useState<Step>("mode");
  const [mode, setMode] = useState<Mode>("demo");
  const [riskProfile, setRiskProfile] = useState<RiskProfile>("balanced");
  const [portfolioChoice, setPortfolioChoice] = useState<"demo" | "manual" | "upload">("demo");
  const [launching, setLaunching] = useState(false);

  const steps: { id: Step; label: string; icon: typeof Rocket }[] = [
    { id: "mode", label: "Choose Mode", icon: Monitor },
    { id: "portfolio", label: "Portfolio", icon: Briefcase },
    { id: "risk", label: "Risk Profile", icon: Shield },
    { id: "launch", label: "Launch", icon: Rocket },
  ];

  const stepIdx = steps.findIndex(s => s.id === currentStep);

  const goNext = () => {
    const next = steps[stepIdx + 1];
    if (next) setCurrentStep(next.id);
  };

  const goPrev = () => {
    const prev = steps[stepIdx - 1];
    if (prev) setCurrentStep(prev.id);
  };

  const handleLaunch = async () => {
    setLaunching(true);

    // Save preferences
    localStorage.setItem("ah-onboarded", "1");
    localStorage.setItem("ah-risk", riskProfile);
    localStorage.setItem("ah-mode", mode);

    if (portfolioChoice === "demo") {
      localStorage.setItem("alpha-hunter-portfolio", JSON.stringify(DEMO_HOLDINGS));
    }

    await new Promise(r => setTimeout(r, 1200));
    setLaunching(false);
    onClose();

    if (mode === "demo") {
      onStartDemo();
    }
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
        borderRadius: 24, padding: "32px 28px", maxWidth: 520, width: "100%",
        boxShadow: "0 24px 80px rgba(0,0,0,0.6)",
        animation: "fadeIn 0.3s ease",
      }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
              <div style={{ width: 36, height: 36, borderRadius: 10, background: "linear-gradient(135deg, #3b82f6, #06b6d4)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Rocket size={18} color="white" />
              </div>
              <h2 style={{ fontSize: 20, fontWeight: 800, letterSpacing: "-0.01em" }}>Get Started</h2>
            </div>
            <p style={{ fontSize: 13, color: "var(--text-secondary)" }}>Set up Chōsa Agent in 60 seconds</p>
          </div>
          <button onClick={onClose} aria-label="Close" style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", padding: 4 }}>
            <X size={18} />
          </button>
        </div>

        {/* Step indicator */}
        <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 24 }}>
          {steps.map((s, i) => (
            <div key={s.id} style={{ display: "flex", alignItems: "center", gap: 4, flex: 1 }}>
              <div style={{
                width: 24, height: 24, borderRadius: 12,
                background: i <= stepIdx ? "linear-gradient(135deg, #3b82f6, #06b6d4)" : "rgba(99,117,168,0.1)",
                border: `1.5px solid ${i <= stepIdx ? "transparent" : "rgba(99,117,168,0.15)"}`,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 10, fontWeight: 800,
                color: i <= stepIdx ? "white" : "var(--text-dim)",
                transition: "all 0.3s ease",
              }}>
                {i < stepIdx ? <CheckCircle size={12} /> : i + 1}
              </div>
              <span style={{
                fontSize: 10, fontWeight: 600,
                color: i === stepIdx ? "var(--text-primary)" : "var(--text-dim)",
                display: i === stepIdx ? "block" : "none",
              }}>
                {s.label}
              </span>
              {i < steps.length - 1 && (
                <div style={{
                  flex: 1, height: 2, borderRadius: 1,
                  background: i < stepIdx ? "#3b82f6" : "rgba(99,117,168,0.1)",
                  transition: "background 0.3s ease",
                }} />
              )}
            </div>
          ))}
        </div>

        {/* Step content */}
        <div style={{ minHeight: 240, marginBottom: 24 }}>
          {/* ── Step 1: Mode ── */}
          {currentStep === "mode" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 10, animation: "fadeIn 0.3s ease" }}>
              <p style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 8 }}>
                How would you like to experience Chōsa Agent?
              </p>
              {([
                {
                  id: "demo" as Mode, label: "Demo Mode", icon: Play, color: "#3b82f6",
                  desc: "Pre-loaded portfolio with simulated market events. Perfect for exploring features.",
                  tag: "RECOMMENDED",
                },
                {
                  id: "live" as Mode, label: "Live Mode", icon: BarChart3, color: "#10b981",
                  desc: "Connect to real Upstox market data. Add your own portfolio for live monitoring.",
                  tag: "REAL DATA",
                },
              ]).map(m => (
                <button key={m.id} onClick={() => setMode(m.id)} style={{
                  display: "flex", alignItems: "center", gap: 14, padding: "16px 18px",
                  background: mode === m.id ? `${m.color}08` : "rgba(99,117,168,0.04)",
                  border: `1.5px solid ${mode === m.id ? `${m.color}30` : "rgba(99,117,168,0.08)"}`,
                  borderRadius: 14, cursor: "pointer", transition: "all 0.2s", textAlign: "left", width: "100%",
                }}>
                  <div style={{
                    width: 40, height: 40, borderRadius: 12,
                    background: mode === m.id ? `${m.color}15` : "rgba(99,117,168,0.06)",
                    display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                    transition: "all 0.2s",
                  }}>
                    <m.icon size={18} color={mode === m.id ? m.color : "var(--text-dim)"} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                      <span style={{ fontSize: 14, fontWeight: 700, color: mode === m.id ? m.color : "var(--text-primary)" }}>
                        {m.label}
                      </span>
                      <span style={{
                        fontSize: 8, padding: "2px 6px", borderRadius: 4,
                        background: `${m.color}10`, color: m.color, fontWeight: 800,
                        letterSpacing: "0.04em",
                      }}>
                        {m.tag}
                      </span>
                    </div>
                    <span style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.5 }}>
                      {m.desc}
                    </span>
                  </div>
                  <div style={{
                    width: 18, height: 18, borderRadius: 9,
                    border: `2px solid ${mode === m.id ? m.color : "rgba(99,117,168,0.2)"}`,
                    display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                  }}>
                    {mode === m.id && <div style={{ width: 8, height: 8, borderRadius: 4, background: m.color }} />}
                  </div>
                </button>
              ))}
            </div>
          )}

          {/* ── Step 2: Portfolio ── */}
          {currentStep === "portfolio" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 10, animation: "fadeIn 0.3s ease" }}>
              <p style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 8 }}>
                {mode === "demo" ? "We'll seed a sample portfolio for you." : "How would you like to set up your portfolio?"}
              </p>
              {([
                {
                  id: "demo" as const, label: "Use Demo Portfolio", icon: Zap, color: "#3b82f6",
                  desc: `5 stocks: RELIANCE, TCS, HDFCBANK, ICICIBANK, INFY — ₹${(DEMO_HOLDINGS.reduce((a, h) => a + h.qty * h.buy_price, 0) / 100000).toFixed(1)}L value`,
                },
                {
                  id: "manual" as const, label: "Add Manually", icon: Database, color: "#10b981",
                  desc: "Search and add NSE stocks one by one after setup",
                },
                {
                  id: "upload" as const, label: "Import JSON/CSV", icon: Upload, color: "#8b5cf6",
                  desc: "Upload portfolio from a broker export file",
                },
              ]).map(o => (
                <button key={o.id} onClick={() => setPortfolioChoice(o.id)} style={{
                  display: "flex", alignItems: "center", gap: 14, padding: "14px 16px",
                  background: portfolioChoice === o.id ? `${o.color}08` : "rgba(99,117,168,0.04)",
                  border: `1.5px solid ${portfolioChoice === o.id ? `${o.color}30` : "rgba(99,117,168,0.08)"}`,
                  borderRadius: 12, cursor: "pointer", transition: "all 0.2s", textAlign: "left", width: "100%",
                }}>
                  <div style={{
                    width: 32, height: 32, borderRadius: 10,
                    background: portfolioChoice === o.id ? `${o.color}15` : "rgba(99,117,168,0.06)",
                    display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                  }}>
                    <o.icon size={14} color={portfolioChoice === o.id ? o.color : "var(--text-dim)"} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: portfolioChoice === o.id ? o.color : "var(--text-primary)" }}>{o.label}</div>
                    <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2, lineHeight: 1.4 }}>{o.desc}</div>
                  </div>
                  {portfolioChoice === o.id && <CheckCircle size={16} color={o.color} />}
                </button>
              ))}
            </div>
          )}

          {/* ── Step 3: Risk Profile ── */}
          {currentStep === "risk" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 10, animation: "fadeIn 0.3s ease" }}>
              <p style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 8 }}>
                Set your risk tolerance. This controls position limits and confidence thresholds.
              </p>
              {(Object.entries(RISK_PROFILES) as [RiskProfile, typeof RISK_PROFILES[RiskProfile]][]).map(([id, profile]) => (
                <button key={id} onClick={() => setRiskProfile(id)} style={{
                  display: "flex", alignItems: "flex-start", gap: 14, padding: "14px 16px",
                  background: riskProfile === id ? `${profile.color}08` : "rgba(99,117,168,0.04)",
                  border: `1.5px solid ${riskProfile === id ? `${profile.color}30` : "rgba(99,117,168,0.08)"}`,
                  borderRadius: 12, cursor: "pointer", transition: "all 0.2s", textAlign: "left", width: "100%",
                }}>
                  <div style={{
                    width: 32, height: 32, borderRadius: 10,
                    background: riskProfile === id ? `${profile.color}15` : "rgba(99,117,168,0.06)",
                    display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                  }}>
                    <Sliders size={14} color={riskProfile === id ? profile.color : "var(--text-dim)"} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: riskProfile === id ? profile.color : "var(--text-primary)", marginBottom: 2 }}>
                      {profile.label}
                    </div>
                    <div style={{ fontSize: 10, color: "var(--text-muted)", lineHeight: 1.5 }}>
                      {profile.desc}
                    </div>
                    <div style={{ display: "flex", gap: 12, marginTop: 6 }}>
                      <span style={{ fontSize: 9, color: "var(--text-dim)", fontFamily: "'JetBrains Mono', monospace" }}>
                        Max position: {profile.maxConcentration}%
                      </span>
                      <span style={{ fontSize: 9, color: "var(--text-dim)", fontFamily: "'JetBrains Mono', monospace" }}>
                        Min confidence: {profile.minConfidence}%
                      </span>
                    </div>
                  </div>
                  <div style={{
                    width: 18, height: 18, borderRadius: 9,
                    border: `2px solid ${riskProfile === id ? profile.color : "rgba(99,117,168,0.2)"}`,
                    display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                  }}>
                    {riskProfile === id && <div style={{ width: 8, height: 8, borderRadius: 4, background: profile.color }} />}
                  </div>
                </button>
              ))}
            </div>
          )}

          {/* ── Step 4: Launch ── */}
          {currentStep === "launch" && (
            <div style={{ textAlign: "center", padding: "16px 0", animation: "fadeIn 0.3s ease" }}>
              {!launching ? (
                <>
                  <div style={{
                    width: 64, height: 64, borderRadius: 16, margin: "0 auto 16px",
                    background: "linear-gradient(135deg, rgba(59,130,246,0.15), rgba(6,182,212,0.15))",
                    border: "1px solid rgba(59,130,246,0.2)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                  }}>
                    <Rocket size={28} color="#3b82f6" />
                  </div>
                  <h3 style={{ fontSize: 18, fontWeight: 800, marginBottom: 8 }}>Ready to Launch!</h3>
                  <p style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 20, lineHeight: 1.6 }}>
                    Chōsa Agent will monitor markets 24/7, detect anomalies, and deliver personalized recommendations.
                  </p>
                  <div style={{
                    display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10,
                    padding: "16px", borderRadius: 12,
                    background: "rgba(99,117,168,0.04)", border: "1px solid rgba(99,117,168,0.08)",
                    marginBottom: 20, textAlign: "left",
                  }}>
                    {[
                      { label: "Mode", value: mode === "demo" ? "Demo" : "Live", color: mode === "demo" ? "#3b82f6" : "#10b981" },
                      { label: "Portfolio", value: portfolioChoice === "demo" ? "Demo (5 stocks)" : portfolioChoice === "manual" ? "Manual" : "Import", color: "#8b5cf6" },
                      { label: "Risk", value: RISK_PROFILES[riskProfile].label, color: RISK_PROFILES[riskProfile].color },
                      { label: "News Radar", value: "24/7 Active", color: "#06b6d4" },
                    ].map(item => (
                      <div key={item.label} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                        <span style={{ fontSize: 9, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.05em" }}>{item.label}</span>
                        <span style={{ fontSize: 12, fontWeight: 700, color: item.color }}>{item.value}</span>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div>
                  <div style={{
                    width: 64, height: 64, borderRadius: 16, margin: "0 auto 16px",
                    background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.2)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                  }}>
                    <CheckCircle size={28} color="#10b981" />
                  </div>
                  <h3 style={{ fontSize: 18, fontWeight: 800, color: "#10b981", marginBottom: 8 }}>Launching...</h3>
                  <p style={{ fontSize: 12, color: "var(--text-secondary)" }}>Setting up your workspace</p>
                  <div style={{ height: 4, background: "rgba(99,117,168,0.1)", borderRadius: 9999, margin: "20px 40px", overflow: "hidden" }}>
                    <div className="confidence-bar" style={{
                      height: "100%", width: "100%", borderRadius: 9999,
                      background: "linear-gradient(90deg, #10b981, #06b6d4)",
                      animation: "shimmer 1.5s linear infinite",
                    }} />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer buttons */}
        <div style={{ display: "flex", gap: 10 }}>
          {stepIdx > 0 && !launching && (
            <button onClick={goPrev} style={{
              padding: "12px 20px", borderRadius: 12, fontSize: 13, fontWeight: 600,
              background: "transparent", color: "var(--text-secondary)",
              border: "1px solid var(--border-primary)", cursor: "pointer",
              display: "flex", alignItems: "center", gap: 6,
            }}>
              <ChevronLeft size={14} /> Back
            </button>
          )}
          <div style={{ flex: 1 }} />
          {currentStep === "launch" ? (
            <button onClick={handleLaunch} disabled={launching} style={{
              flex: 1, padding: "12px 20px", borderRadius: 12, fontSize: 13, fontWeight: 700,
              background: launching ? "rgba(16,185,129,0.2)" : "linear-gradient(135deg, #3b82f6, #2563eb)",
              color: "white", border: "none", cursor: launching ? "not-allowed" : "pointer",
              display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
              boxShadow: launching ? "none" : "0 4px 16px rgba(59,130,246,0.3)",
            }}>
              <Rocket size={14} /> {launching ? "Setting up..." : "Launch Chōsa Agent"}
            </button>
          ) : (
            <>
              <button onClick={goNext} style={{
                flex: 1, padding: "12px 20px", borderRadius: 12, fontSize: 13, fontWeight: 700,
                background: "linear-gradient(135deg, #3b82f6, #2563eb)", color: "white",
                border: "none", cursor: "pointer",
                display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                boxShadow: "0 4px 16px rgba(59,130,246,0.3)",
              }}>
                Next <ChevronRight size={14} />
              </button>
              <button onClick={() => { onClose(); onStartDemo(); }} style={{
                padding: "12px 16px", borderRadius: 12, fontSize: 13, fontWeight: 600,
                background: "transparent", color: "var(--text-secondary)",
                border: "1px solid var(--border-primary)", cursor: "pointer",
              }}>
                Skip
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

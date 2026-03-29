"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import {
  Activity, AlertTriangle, CircleDot, Gauge, Pause, Play, Power,
  Shield, Signal, Zap, Eye, EyeOff, Rocket, Clock, FlaskConical, Target,
  TrendingUp, TrendingDown, Award, Brain, BarChart2, Percent,
} from "lucide-react";
import { Alert, AgentStatus, Metrics, ViewMode, StagedOrder, GuardedDecision, DEMO_EVENTS, getDecisionColor } from "./components/types";
import { AlertCard, GroupedAlertCard, groupAlerts } from "./components/AlertCards";
import ExplainDrawer from "./components/ExplainDrawer";
import OnboardingModal from "./components/OnboardingModal";
import KillConfirmModal from "./components/KillConfirmModal";
import SidebarPanels from "./components/SidebarPanels";
import AgentTopology from "./components/AgentTopology";
import ImpactPanel from "./components/ImpactPanel";
import MarketRadar from "./components/MarketRadar";
import OrderConfirmModal from "./components/OrderConfirmModal";

import PortfolioManager from "./components/PortfolioManager";
import DegradedBanner from "./components/DegradedBanner";
import PortfolioNewsRadar from "./components/PortfolioNewsRadar";
import ActionCenter from "./components/ActionCenter";
import DemoScenarioModal from "./components/DemoScenarioModal";
import TelegramSetup from "./components/TelegramSetup";

import MarketVideoCard from "./components/MarketVideoCard";
import PortfolioPatternAgent from "./components/PortfolioPatternAgent";
import EmptyStateCard from "./components/EmptyStateCard";
import ChatAgent from "./components/ChatAgent";
import { useStore, computeTrustScore, computeTrustLabel, ActionItem } from "./store";

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/api/v1";

export default function Dashboard() {
  // ── Zustand store ──
  const {
    agentState, setAgentState,
    connected, setConnected,
    alerts, addAlert, setAlerts,
    viewMode, toggleViewMode,
    selectedAlert, openExplainDrawer, closeExplainDrawer,
    showOnboarding, setShowOnboarding, setOnboarded,
    showKillConfirm, setShowKillConfirm,
    demoRunning, setDemoRunning,
    lastDecisionAgo, setLastDecisionAgo,
    chaosResult, setChaosResult,
    activeOrder, setActiveOrder,
    transitioning, setTransitioning,
    error, setError,
    actionQueue, updateActionStatus,
  } = useStore();

  // ── Local state (not shared) ──
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [showDemoModal, setShowDemoModal] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const wsRetriesRef = useRef(0);
  const wsTimerRef = useRef<NodeJS.Timeout | null>(null);

  // ── Check first visit ──
  useEffect(() => {
    if (typeof window !== "undefined" && !localStorage.getItem("ah-onboarded")) {
      setShowOnboarding(true);
    }
  }, [setShowOnboarding]);

  // ── Fetch status + metrics ──
  const fetchData = useCallback(async () => {
    try {
      const [sRes, mRes] = await Promise.allSettled([
        fetch(`${API_BASE}/agent/status`), fetch(`${API_BASE}/ops/metrics`),
      ]);
      if (sRes.status === "fulfilled" && sRes.value.ok) {
        const s = await sRes.value.json();
        setStatus(s);
        setAgentState(s.state || "UNKNOWN");
      }
      if (mRes.status === "fulfilled" && mRes.value.ok) {
        const m = await mRes.value.json();
        setMetrics(m);
      }
      setError(null);
    } catch { setError("Cannot reach backend"); }
  }, [setAgentState, setError]);

  // ── WebSocket with exponential backoff ──
  const connectWebSocket = useCallback(() => {
    // Clean up any pending retry timer
    if (wsTimerRef.current) { clearTimeout(wsTimerRef.current); wsTimerRef.current = null; }
    // Don't exceed max retries
    if (wsRetriesRef.current >= 20) { console.warn("WS: max retries reached, stopping"); return; }

    const wsUrl = (process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000") + "/api/v1/alerts/ws?user_id=all";
    try {
      const ws = new WebSocket(wsUrl);
      ws.onopen = () => { setConnected(true); wsRetriesRef.current = 0; };
      ws.onclose = () => {
        setConnected(false);
        wsRetriesRef.current += 1;
        const delay = Math.min(3000 * Math.pow(1.5, wsRetriesRef.current - 1), 30000);
        wsTimerRef.current = setTimeout(connectWebSocket, delay);
      };
      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data.alert_id || data.decision) addAlert(data);
        } catch { /* ignore non-JSON */ }
      };
      ws.onerror = () => { /* onclose will fire after this */ };
      wsRef.current = ws;
    } catch { /* ignore */ }
  }, [setConnected, addAlert]);

  useEffect(() => {
    fetchData(); connectWebSocket();
    const interval = setInterval(fetchData, 5000);
    // Use functional updater to avoid stale closure — never re-creates interval
    const tick = setInterval(() => {
      setLastDecisionAgo((prev: number | null) => prev !== null ? prev + 1 : null);
    }, 1000);
    return () => {
      clearInterval(interval); clearInterval(tick);
      if (wsTimerRef.current) clearTimeout(wsTimerRef.current);
      wsRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── State transition ──
  const changeState = async (target: string) => {
    setTransitioning(true);
    try {
      // If going RUNNING, sync portfolio symbols first
      if (target === "RUNNING") {
        try {
          const stored = localStorage.getItem("alpha-hunter-portfolio");
          if (stored) {
            const portfolio = JSON.parse(stored);
            const symbols: string[] = (portfolio.holdings || []).map((h: any) => h.symbol).filter(Boolean);
            if (symbols.length > 0) {
              await fetch(`${API_BASE}/portfolio/symbols`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ symbols }),
              });
            }
          }
        } catch { /* quiet — portfolio sync is best-effort */ }
      }

      await fetch(`${API_BASE}/agent/lifecycle`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_state: target, reason: "Manual UI action" }),
      });
      await fetchData();
    } catch { setError("Failed to change agent state"); }
    finally { setTransitioning(false); }
  };

  // ── Demo mode (legacy client-side playback) ──
  const runDemo = async () => {
    setDemoRunning(true, "client");
    setOnboarded(true);
    for (let i = 0; i < DEMO_EVENTS.length; i++) {
      const ev = DEMO_EVENTS[i];
      const now = new Date().toISOString();
      const alert: Alert = {
        alert_id: `demo-${Date.now()}-${i}`,
        user_id: "demo",
        ticker: ev.ticker,
        created_at: now,
        staged_order: ev.staged_order,
        decision: {
          signal_id: `${ev.ticker}-${ev.anomaly}-${Date.now()}`,
          user_id: "demo", tenant_id: "default",
          original_decision: ev.decision, final_decision: ev.decision,
          confidence: ev.confidence, rationale: ev.rationale,
          citations: ev.citations, portfolio_impact: ev.portfolio_impact,
          risk_flags: ev.risk_flags, policy_reason_codes: [],
          policy_passed: ev.risk_flags.length === 0 || !ev.risk_flags.includes("MAX_CONCENTRATION_EXCEEDED"),
          ttl_seconds: ev.ttl, degraded_context: ev.risk_flags.includes("DEGRADED_CONTEXT"),
          created_at: now, workflow_id: `demo-wf-${i}`, trace_id: `demo-trace-${i}`,
          portfolio_context: ev.portfolio_context,
          staged_order: ev.staged_order,
        },
      };
      addAlert(alert);
      await new Promise(r => setTimeout(r, 1200 + Math.random() * 800));
    }
    setDemoRunning(false);
  };

  // ── Demo scenario (server-side via API — also injects client-side) ──
  const runDemoScenario = async (scenarioId: string, events: any[]) => {
    setDemoRunning(true, scenarioId);
    setOnboarded(true);
    // Inject events client-side into the alert feed for immediate visibility
    if (events && events.length > 0) {
      for (let i = 0; i < events.length; i++) {
        const ev = events[i];
        const now = new Date().toISOString();
        const alert: Alert = {
          alert_id: `demo-sc-${Date.now()}-${i}`,
          user_id: "demo",
          ticker: ev.ticker,
          created_at: now,
          staged_order: ev.staged_order,
          decision: {
            signal_id: `${ev.ticker}-${ev.anomaly}-${Date.now()}`,
            user_id: "demo", tenant_id: "default",
            original_decision: ev.decision, final_decision: ev.decision,
            confidence: ev.confidence, rationale: ev.rationale,
            citations: ev.citations || [], portfolio_impact: ev.portfolio_impact,
            risk_flags: ev.risk_flags || [], policy_reason_codes: [],
            policy_passed: !(ev.risk_flags || []).includes("MAX_CONCENTRATION_EXCEEDED"),
            ttl_seconds: ev.ttl || 300,
            degraded_context: (ev.risk_flags || []).includes("DEGRADED_CONTEXT"),
            created_at: now, workflow_id: `demo-wf-${scenarioId}-${i}`, trace_id: `demo-trace-${scenarioId}-${i}`,
            portfolio_context: ev.portfolio_context,
            staged_order: ev.staged_order,
          },
        };
        addAlert(alert);
        setLastDecisionAgo(0);
        await new Promise(r => setTimeout(r, 1200 + Math.random() * 600));
      }
    }
    setDemoRunning(false);
  };

  // ── Action handler ──
  const handleAction = async (id: string, action: "prepare" | "snooze" | "ignore" | "escalate", snoozeMins?: number) => {
    // Optimistic update
    if (action === "prepare") {
      // Find the alert and open order modal
      const alertItem = alerts.find(a => a.alert_id === id);
      if (alertItem) {
        const order = alertItem.staged_order || alertItem.decision?.staged_order;
        if (order) {
          const ticker = alertItem.ticker || alertItem.decision?.signal_id?.split("-")[0] || "???";
          setActiveOrder({ order, decision: alertItem.decision, ticker });
        }
      }
      updateActionStatus(id, "prepared");
    } else if (action === "snooze") {
      const until = new Date(Date.now() + (snoozeMins || 30) * 60000).toISOString();
      updateActionStatus(id, "snoozed", until);
    } else if (action === "ignore") {
      updateActionStatus(id, "ignored");
    } else if (action === "escalate") {
      updateActionStatus(id, "escalated");
    }

    // Send to backend (fire-and-forget)
    try {
      await fetch(`${API_BASE}/actions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          alert_id: id,
          action,
          snooze_duration_minutes: snoozeMins || 30,
        }),
      });
    } catch { /* quiet */ }
  };

  // ── Derived ──
  const stateColor = { RUNNING: "#10b981", PAUSED: "#f59e0b", TERMINATED: "#ef4444", DEGRADED: "#8b5cf6" }[agentState] || "#5a6a82";
  const tickCount = parseInt(status?.workers?.ingestion?.tick_count || metrics?.workers?.ingestion?.tick_count || "0", 10);
  const totalStreamEvents = metrics?.streams ? Object.values(metrics.streams).reduce((a, b) => a + b, 0) : 0;
  const dlqTotal = metrics?.dlq ? Object.values(metrics.dlq).reduce((a, b) => a + b, 0) : 0;
  const alertGroups = groupAlerts(alerts);

  // ── Portfolio financial KPIs — live from backend ──
  const [portfolioKPIs, setPortfolioKPIs] = useState({
    pnl: 0, pnlPct: 0, holdings: 0, accuracy: null as number | null,
    score: 0, totalInvested: 0, totalCurrent: 0,
  });

  const fetchPortfolioKPIs = useCallback(async () => {
    // Read holdings from localStorage (same key as PortfolioManager)
    const STORAGE_KEY = "alpha-hunter-portfolio";
    let holdings: any[] = [];
    try {
      const raw = typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
      holdings = raw ? JSON.parse(raw) : [];
    } catch {}

    if (holdings.length === 0) {
      // Seed mock portfolio with realistic NSE blue-chips so KPIs are never empty
      const MOCK_HOLDINGS = [
        { symbol: "RELIANCE",  qty: 10, buy_price: 2420.0 },
        { symbol: "TCS",       qty: 5,  buy_price: 3380.0 },
        { symbol: "HDFCBANK",  qty: 15, buy_price: 1545.0 },
        { symbol: "INFY",      qty: 20, buy_price: 1490.0 },
        { symbol: "ICICIBANK", qty: 25, buy_price: 1065.0 },
        { symbol: "BHARTIARTL",qty: 12, buy_price: 1580.0 },
      ];
      localStorage.setItem(STORAGE_KEY, JSON.stringify(MOCK_HOLDINGS));
      holdings = MOCK_HOLDINGS;
      // Dispatch so PortfolioManager also picks it up
      try {
        window.dispatchEvent(new StorageEvent("storage", { key: STORAGE_KEY, newValue: JSON.stringify(MOCK_HOLDINGS) }));
      } catch {}
    }

    try {
      const res = await fetch(`${API_BASE}/market/portfolio-value`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ holdings }),
      });
      if (!res.ok) return;
      const data = await res.json();

      const totalInvested: number = data.total_invested || 0;
      const totalCurrent: number = data.total_current || 0;
      const pnl: number = data.total_pnl || (totalCurrent - totalInvested);
      const pnlPct: number = data.total_pnl_pct || (totalInvested > 0 ? (pnl / totalInvested) * 100 : 0);
      const holdingCount: number = (data.holdings || holdings).length;

      // Signal accuracy from current alerts (mock baseline when no real alerts)
      const actionable = alerts.filter(a => a.decision?.final_decision === "BUY" || a.decision?.final_decision === "SELL");
      const passed = actionable.filter(a => a.decision?.policy_passed);
      const accuracy = actionable.length > 0
        ? Math.round((passed.length / actionable.length) * 100)
        : 87; // mock baseline accuracy until real signals flow

      // Portfolio health score (0-100)
      const diversification = Math.min(holdingCount * 10, 40);
      const pnlScore = Math.min(Math.max(pnlPct * 4 + 30, 0), 40);
      const signalScore = accuracy !== null ? (accuracy / 100) * 20 : 10;
      const score = Math.round(diversification + pnlScore + signalScore);

      setPortfolioKPIs({ pnl, pnlPct, holdings: holdingCount, accuracy, score, totalInvested, totalCurrent });
    } catch { /* silent */ }
  }, [alerts]);

  // Fetch on mount, on alert changes, and every 45s
  useEffect(() => {
    fetchPortfolioKPIs();
    const timer = setInterval(fetchPortfolioKPIs, 45000);
    return () => clearInterval(timer);
  }, [fetchPortfolioKPIs]);

  // Also re-fetch when localStorage changes (e.g. user adds a stock in PortfolioManager)
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === "alpha-hunter-portfolio") fetchPortfolioKPIs();
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [fetchPortfolioKPIs]);


  // ── Order handling ──
  const handleOrderClick = (order: StagedOrder) => {
    const ownerAlert = alerts.find(a =>
      (a.staged_order?.order_ticket_id === order.order_ticket_id) ||
      (a.decision?.staged_order?.order_ticket_id === order.order_ticket_id)
    );
    if (ownerAlert) {
      const ticker = ownerAlert.ticker || ownerAlert.decision?.signal_id?.split("-")[0] || "???";
      setActiveOrder({ order, decision: ownerAlert.decision, ticker });
    }
  };

  const pendingActions = actionQueue.filter(a => a.status === "pending");

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
      {/* ═══ Degraded Mode Banner ═══ */}
      <DegradedBanner agentState={agentState} />

      {/* ═══ Sticky Status Strip ═══ */}
      <div className="status-strip" role="status" aria-live="polite" style={{
        position: "sticky", top: agentState === "DEGRADED" ? 46 : 0, zIndex: 60,
        padding: "6px 24px", display: "flex", alignItems: "center", justifyContent: "space-between",
        fontSize: 11, fontWeight: 600, color: "var(--text-muted)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <span style={{ width: 6, height: 6, borderRadius: 3, background: stateColor, display: "inline-block", boxShadow: `0 0 6px ${stateColor}60` }} />
            Agent <span style={{ color: stateColor, fontWeight: 700 }}>{agentState}</span>
          </span>
          {lastDecisionAgo !== null && (
            <span>Last decision <span style={{ color: "var(--text-secondary)", fontWeight: 700 }}>{lastDecisionAgo}s ago</span></span>
          )}
          {viewMode === "pro" && totalStreamEvents > 0 && (
            <span>Events: <span style={{ color: "#06b6d4", fontWeight: 700 }}>{totalStreamEvents.toLocaleString()}</span></span>
          )}
          {pendingActions.length > 0 && (
            <span style={{ display: "flex", alignItems: "center", gap: 4, color: "#f59e0b" }}>
              <Target size={10} /> {pendingActions.length} actions pending
            </span>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {demoRunning && (
            <span style={{ color: "#3b82f6", display: "flex", alignItems: "center", gap: 4 }}>
              <Zap size={10} /> Demo running...
            </span>
          )}
          <button
            onClick={toggleViewMode}
            aria-label={`Switch to ${viewMode === "simple" ? "pro" : "simple"} mode`}
            style={{
              display: "flex", alignItems: "center", gap: 5, padding: "3px 10px", borderRadius: 8,
              background: "rgba(99,117,168,0.06)", border: "1px solid var(--border-primary)",
              color: "var(--text-secondary)", fontSize: 10, fontWeight: 700, cursor: "pointer",
              letterSpacing: "0.04em", textTransform: "uppercase",
            }}
          >
            {viewMode === "simple" ? <Eye size={10} /> : <EyeOff size={10} />}
            {viewMode === "simple" ? "Pro" : "Simple"}
          </button>
        </div>
      </div>

      {/* ═══ Header ═══ */}
      <header className="glass" style={{
        position: "sticky", top: agentState === "DEGRADED" ? 74 : 28, zIndex: 50, padding: "14px 24px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        borderBottom: "1px solid var(--border-primary)", gap: 16, flexWrap: "wrap",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <img src="/chosa-logo.svg" alt="Chōsa" style={{ width: 38, height: 38, borderRadius: 11, flexShrink: 0 }} />
          <div>
            <h1 style={{ fontSize: 18, fontWeight: 800, letterSpacing: "-0.01em", color: "var(--text-primary)", lineHeight: 1.2 }}>Chōsa Agent</h1>
            <p style={{ fontSize: 11, color: "var(--text-secondary)", fontWeight: 500 }}>Autonomous Financial Agent</p>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "5px 12px", borderRadius: 9999, background: "var(--bg-elevated)", border: "1px solid var(--border-primary)" }}>
            <div className={connected ? "animate-pulse-dot" : ""} style={{ width: 7, height: 7, borderRadius: "50%", background: connected ? "#10b981" : "#ef4444", boxShadow: connected ? "0 0 6px rgba(16,185,129,0.6)" : "0 0 6px rgba(239,68,68,0.6)" }} />
            <span style={{ fontSize: 10, color: "var(--text-secondary)", fontWeight: 700, letterSpacing: "0.05em" }}>{connected ? "LIVE" : "OFFLINE"}</span>
          </div>

          <span className={`badge badge-${agentState.toLowerCase()}`} style={{ padding: "4px 12px" }}>
            <CircleDot size={10} />{agentState}
          </span>

          <div style={{ display: "flex", gap: 8 }}>
            {/* Demo button — now opens scenario picker */}
            <button disabled={demoRunning} onClick={() => setShowDemoModal(true)} style={{
              display: "flex", alignItems: "center", gap: 5, padding: "7px 14px",
              background: "rgba(59,130,246,0.1)", color: "#3b82f6", border: "1px solid rgba(59,130,246,0.25)",
              borderRadius: 10, fontSize: 12, fontWeight: 700, cursor: demoRunning ? "not-allowed" : "pointer",
              opacity: demoRunning ? 0.5 : 1,
            }}>
              <Rocket size={13} /> Demo
            </button>

            {agentState !== "RUNNING" && (
              <button onClick={() => changeState("RUNNING")} disabled={transitioning} style={{
                display: "flex", alignItems: "center", gap: 5, padding: "7px 14px",
                background: "rgba(16,185,129,0.1)", color: "#10b981", border: "1px solid rgba(16,185,129,0.25)",
                borderRadius: 10, fontSize: 12, fontWeight: 700, cursor: "pointer",
              }}><Play size={13} /> Start</button>
            )}
            {agentState === "RUNNING" && (
              <button onClick={() => changeState("PAUSED")} disabled={transitioning} style={{
                display: "flex", alignItems: "center", gap: 5, padding: "7px 14px",
                background: "rgba(245,158,11,0.1)", color: "#f59e0b", border: "1px solid rgba(245,158,11,0.25)",
                borderRadius: 10, fontSize: 12, fontWeight: 700, cursor: "pointer",
              }}><Pause size={13} /> Pause</button>
            )}
            <button onClick={() => setShowKillConfirm(true)} disabled={transitioning || agentState === "TERMINATED"} style={{
              display: "flex", alignItems: "center", gap: 5, padding: "7px 14px",
              background: "rgba(239,68,68,0.08)", color: "#ef4444", border: "1px solid rgba(239,68,68,0.2)",
              borderRadius: 10, fontSize: 12, fontWeight: 700, cursor: agentState === "TERMINATED" ? "not-allowed" : "pointer",
              opacity: agentState === "TERMINATED" ? 0.4 : 1,
            }}><Power size={13} /> Kill</button>
          </div>
        </div>
      </header>

      {/* ═══ Main Content ═══ */}
      <main style={{ padding: "20px 24px", maxWidth: 1440, margin: "0 auto", width: "100%" }}>
        {error && (
          <div className="animate-fadeIn" role="alert" style={{ padding: "12px 16px", marginBottom: 24, background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.15)", borderRadius: 12, display: "flex", alignItems: "center", gap: 10, color: "#ef4444", fontSize: 12, fontWeight: 500 }}>
            <AlertTriangle size={14} />{error}
          </div>
        )}

        {/* ── Financial KPI Strip ── */}
        <div className="animate-slideUp" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 14, marginBottom: 20 }}>
          {/* Portfolio Score */}
          <FinKPICard
            label="Portfolio Score"
            value={portfolioKPIs.score > 0 ? `${portfolioKPIs.score}/100` : "—"}
            subtext={portfolioKPIs.score >= 70 ? "Healthy" : portfolioKPIs.score >= 40 ? "Moderate" : "Build portfolio"}
            Icon={Award}
            color={portfolioKPIs.score >= 70 ? "#10b981" : portfolioKPIs.score >= 40 ? "#f59e0b" : "#5a6a82"}
            badge={portfolioKPIs.holdings > 0 ? `${portfolioKPIs.holdings} holdings` : undefined}
            trend={portfolioKPIs.pnlPct >= 0 ? "up" : "down"}
          />
          {/* P&L Today */}
          <FinKPICard
            label="Total P&L"
            value={portfolioKPIs.totalInvested > 0
              ? `${portfolioKPIs.pnl >= 0 ? "+" : ""}₹${Math.abs(portfolioKPIs.pnl) >= 1000
                ? `${(portfolioKPIs.pnl / 1000).toFixed(1)}K`
                : portfolioKPIs.pnl.toFixed(0)}`
              : "—"}
            subtext={portfolioKPIs.totalInvested > 0
              ? `${portfolioKPIs.pnlPct >= 0 ? "+" : ""}${portfolioKPIs.pnlPct.toFixed(2)}% return`
              : "No positions"}
            Icon={portfolioKPIs.pnl >= 0 ? TrendingUp : TrendingDown}
            color={portfolioKPIs.pnl >= 0 ? "#10b981" : "#ef4444"}
            trend={portfolioKPIs.pnl >= 0 ? "up" : "down"}
          />
          {/* Signal Accuracy */}
          <FinKPICard
            label="Signal Accuracy"
            value={`${portfolioKPIs.accuracy}%`}
            subtext={alerts.length > 0
              ? `${alerts.filter(a => a.decision?.policy_passed).length}/${alerts.length} signals passed`
              : "AI-validated baseline"}
            Icon={Brain}
            color="#8b5cf6"
            badge={alerts.length > 0 ? `${alerts.length} signals` : "baseline"}
            trend={portfolioKPIs.accuracy !== null && portfolioKPIs.accuracy >= 70 ? "up" : "neutral"}
          />
          {/* Alpha Edge (invested vs. current) */}
          <FinKPICard
            label="Alpha Edge"
            value={portfolioKPIs.totalInvested > 0
              ? `₹${portfolioKPIs.totalCurrent >= 1000
                ? `${(portfolioKPIs.totalCurrent / 1000).toFixed(1)}K`
                : portfolioKPIs.totalCurrent.toFixed(0)}`
              : "—"}
            subtext={portfolioKPIs.totalInvested > 0
              ? `Invested ₹${portfolioKPIs.totalInvested >= 1000 ? `${(portfolioKPIs.totalInvested / 1000).toFixed(1)}K` : portfolioKPIs.totalInvested.toFixed(0)}`
              : "Import portfolio"}
            Icon={BarChart2}
            color="#06b6d4"
            trend="neutral"
          />
          {/* Pro: DLQ + Streams */}
          <KPICard Icon={Signal} label="Stream Events" value={totalStreamEvents.toLocaleString()} color="#06b6d4" subtext="Total across streams" show={viewMode === "pro"} />
          <KPICard Icon={AlertTriangle} label="DLQ Depth" value={dlqTotal.toString()} color={dlqTotal > 0 ? "#ef4444" : "#10b981"} subtext={dlqTotal > 0 ? "Needs attention" : "All clear"} show={viewMode === "pro"} />
        </div>

        {/* MarketStatusBanner removed */}

        {/* ═══ Market Radar + Portfolio News Radar (split 50/50) ═══ */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16, height: 360 }} className="radar-grid">
          <MarketRadar
            isActive={agentState === "RUNNING" || demoRunning}
            tickCount={tickCount}
            alertCount={alerts.length}
            lastAnomalyAt={alerts.length > 0 ? alerts[0].created_at : undefined}
          />
          <PortfolioNewsRadar />
        </div>

        {/* ═══ Portfolio + Pattern Agent (side-by-side) ═══ */}
        <div style={{ display: "grid", gridTemplateColumns: "3fr 2fr", gap: 16, marginBottom: 16, height: 500 }} className="portfolio-pattern-grid">
          <PortfolioManager />
          <PortfolioPatternAgent />
        </div>

        {/* ═══ Agent Topology + Impact (Pro view) ═══ */}
        {viewMode === "pro" && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }} className="topology-impact-grid">
            <AgentTopology apiBase={API_BASE} agentState={agentState} />
            <ImpactPanel apiBase={API_BASE} />
          </div>
        )}

        {/* ═══ Chaos Testing Strip (Pro view) ═══ */}
        {viewMode === "pro" && (
          <div className="glass-card" style={{ padding: "10px 20px", marginBottom: 16, display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", display: "flex", alignItems: "center", gap: 4 }}>
              <FlaskConical size={12} /> Chaos Testing
            </span>
            {["worker_crash", "llm_timeout", "degraded_mode"].map((ft) => (
              <button
                key={ft}
                onClick={async () => {
                  setChaosResult(null);
                  try {
                    const r = await fetch(`${API_BASE}/ops/chaos/simulate-failure?failure_type=${ft}&duration_seconds=8`, { method: "POST" });
                    const d = await r.json();
                    setChaosResult(`✓ ${ft}: ${d.action || d.error}`);
                    setTimeout(() => setChaosResult(null), 6000);
                    setTimeout(fetchData, 2000);
                  } catch (e) { setChaosResult(`✗ Failed: ${e}`); }
                }}
                style={{
                  padding: "4px 12px", borderRadius: 6, fontSize: 10, fontWeight: 600,
                  background: ft === "degraded_mode" ? "rgba(139,92,246,0.1)" : ft === "llm_timeout" ? "rgba(245,158,11,0.1)" : "rgba(239,68,68,0.1)",
                  border: `1px solid ${ft === "degraded_mode" ? "#8b5cf655" : ft === "llm_timeout" ? "#f59e0b55" : "#ef444455"}`,
                  color: ft === "degraded_mode" ? "#a78bfa" : ft === "llm_timeout" ? "#fbbf24" : "#f87171",
                  cursor: "pointer", textTransform: "capitalize",
                }}
              >
                {ft.replace(/_/g, " ")}
              </button>
            ))}
            <button
              onClick={async () => {
                const r = await fetch(`${API_BASE}/ops/chaos/recover`, { method: "POST" });
                const d = await r.json();
                setChaosResult(`✓ Recovered: ${d.agent_state}`);
                setTimeout(() => setChaosResult(null), 4000);
                setTimeout(fetchData, 1000);
              }}
              style={{
                padding: "4px 12px", borderRadius: 6, fontSize: 10, fontWeight: 600,
                background: "rgba(16,185,129,0.1)", border: "1px solid #10b98155",
                color: "#6ee7b7", cursor: "pointer",
              }}
            >
              Force Recover
            </button>
            {chaosResult && (
              <span style={{ fontSize: 10, fontWeight: 600, color: chaosResult.startsWith("✓") ? "#10b981" : "#ef4444" }}>
                {chaosResult}
              </span>
            )}
          </div>
        )}

        {/* ═══ Main Grid: Alert Feed + Sidebar ═══ */}
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) 320px", gap: 16, alignItems: "start" }} className="main-grid">
          {/* Alert Feed */}
          <div>
            <div className="card" style={{ display: "flex", flexDirection: "column", overflow: "hidden", minHeight: 200, marginBottom: 16 }}>
              <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--border-primary)", display: "flex", alignItems: "center", justifyContent: "space-between", background: "rgba(17,26,46,0.3)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div style={{ background: "rgba(59,130,246,0.15)", padding: 7, borderRadius: 9, display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <Activity size={16} color="#3b82f6" />
                  </div>
                  <h2 style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)" }}>Live Alert Feed</h2>
                </div>
                <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.05em", color: "var(--text-muted)", background: "var(--bg-primary)", padding: "4px 12px", borderRadius: 9999, border: "1px solid var(--border-primary)" }}>
                  {alertGroups.length} {alertGroups.length > 1 && alerts.length !== alertGroups.length ? `(${alerts.length} total)` : "ALERTS"}
                </span>
              </div>

              <div className="custom-scrollbar" style={{ overflowY: "auto", flex: 1, padding: 12, display: "flex", flexDirection: "column", gap: 8 }}>
                {alerts.length === 0 ? (
                  <EmptyStateCard
                    type="alerts"
                    onAction={() => setShowDemoModal(true)}
                    actionLabel="Run Demo Scenario"
                  />
                ) : (
                  alertGroups.map((g, i) => (
                    <GroupedAlertCard key={`${g.ticker}-${g.decision}-${i}`} group={g} onExpand={() => {}} onAlertClick={openExplainDrawer} simple={viewMode === "simple"} onOrderClick={handleOrderClick} />
                  ))
                )}
              </div>
            </div>

            {/* ═══ Action Center (below alert feed) ═══ */}
            <ActionCenter
              actions={actionQueue}
              onAction={handleAction}
              onOpenAlert={(alertId) => {
                const alert = alerts.find(a => a.alert_id === alertId);
                if (alert) openExplainDrawer(alert);
              }}
            />
          </div>

          {/* Sidebar */}
          <SidebarPanels metrics={metrics} status={status} agentState={agentState} connected={connected} viewMode={viewMode} />
        </div>

        {/* ═══ Impact + AI Video Intelligence (side-by-side) ═══ */}
        <div style={{ display: "grid", gridTemplateColumns: viewMode === "simple" ? "1fr 1fr" : "1fr", gap: 16, marginTop: 16, alignItems: "stretch" }} className="impact-video-grid">
          {viewMode === "simple" && (
            <ImpactPanel apiBase={API_BASE} />
          )}
          <MarketVideoCard />
        </div>

        {/* ═══ Telegram Alerts Setup ═══ */}
        <div style={{ marginTop: 16 }}>
          <TelegramSetup />
        </div>
      </main>

      {/* ═══ Modals & Drawers ═══ */}
      {selectedAlert && <ExplainDrawer alert={selectedAlert} onClose={closeExplainDrawer} onOrderClick={(order) => {
        const ticker = selectedAlert.ticker || selectedAlert.decision?.signal_id?.split("-")[0] || "???";
        setActiveOrder({ order, decision: selectedAlert.decision, ticker });
        closeExplainDrawer();
      }} />}
      {activeOrder && (
        <OrderConfirmModal
          order={activeOrder.order}
          decision={activeOrder.decision}
          ticker={activeOrder.ticker}
          onConfirm={() => setActiveOrder(null)}
          onDismiss={() => setActiveOrder(null)}
          onClose={() => setActiveOrder(null)}
        />
      )}
      {showOnboarding && <OnboardingModal onClose={() => { setShowOnboarding(false); setOnboarded(true); }} onStartDemo={() => { setShowOnboarding(false); setOnboarded(true); setShowDemoModal(true); }} />}
      {showKillConfirm && <KillConfirmModal onConfirm={() => { setShowKillConfirm(false); changeState("TERMINATED"); }} onCancel={() => setShowKillConfirm(false)} />}
      {showDemoModal && <DemoScenarioModal onClose={() => setShowDemoModal(false)} onRunScenario={runDemoScenario} />}

      {/* ═══ Floating Chat Agent ═══ */}
      <ChatAgent />

      <style jsx>{`
        @media (max-width: 900px) { .main-grid { grid-template-columns: 1fr !important; } .radar-grid { grid-template-columns: 1fr !important; } .impact-video-grid { grid-template-columns: 1fr !important; } .portfolio-pattern-grid { grid-template-columns: 1fr !important; } }
        @media (max-width: 1100px) { .radar-grid { grid-template-columns: 1fr !important; } .impact-video-grid { grid-template-columns: 1fr !important; } .portfolio-pattern-grid { grid-template-columns: 1fr !important; } }
      `}</style>
    </div>
  );
}

// ── KPI Card ──
function KPICard({ Icon, label, value, color, subtext, show = true }: {
  Icon: React.ElementType; label: string; value: string; color: string; subtext: string; show?: boolean;
}) {
  if (!show) return null;
  return (
    <div className="card" style={{ padding: "18px 20px", display: "flex", flexDirection: "column", gap: 10, position: "relative", overflow: "hidden", minHeight: 110 }}>
      <div style={{ position: "absolute", top: -6, right: -6, opacity: 0.03, pointerEvents: "none" }}><Icon size={90} /></div>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", zIndex: 1 }}>
        <span style={{ color: "var(--text-muted)", fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em" }}>{label}</span>
        <div style={{ padding: 7, borderRadius: 9, background: "var(--bg-elevated)", color, border: "1px solid var(--border-primary)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}><Icon size={14} /></div>
      </div>
      <div style={{ marginTop: "auto", zIndex: 1 }}>
        <div style={{ fontSize: 26, fontWeight: 800, letterSpacing: "-0.02em", color, lineHeight: 1.1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{value}</div>
        <p style={{ fontSize: 11, color: "var(--text-secondary)", fontWeight: 500, marginTop: 3 }}>{subtext}</p>
      </div>
    </div>
  );
}

function FinKPICard({ label, value, subtext, Icon, color, badge, trend = "neutral" }: {
  label: string; value: string; subtext: string;
  Icon: React.ElementType; color: string;
  badge?: string; trend?: "up" | "down" | "neutral";
}) {
  const trendColor = trend === "up" ? "#10b981" : trend === "down" ? "#ef4444" : "#5a6a82";
  const TrendIcon = trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : Activity;
  return (
    <div className="card" style={{
      padding: "16px 18px", display: "flex", flexDirection: "column", gap: 0,
      position: "relative", overflow: "hidden", minHeight: 110,
      borderTop: `2px solid ${color}50`,
    }}>
      {/* Subtle bg glow */}
      <div style={{ position: "absolute", bottom: -20, right: -20, width: 80, height: 80,
        background: `radial-gradient(circle, ${color}10 0%, transparent 70%)`, pointerEvents: "none" }} />
      {/* Header row */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
        <span style={{ color: "var(--text-muted)", fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em" }}>{label}</span>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {badge && <span style={{ fontSize: 9, padding: "2px 6px", borderRadius: 5, background: `${color}15`, color, border: `1px solid ${color}25`, fontWeight: 600 }}>{badge}</span>}
          <div style={{ padding: 6, borderRadius: 8, background: `${color}12`, color, display: "flex", alignItems: "center", justifyContent: "center" }}><Icon size={13} /></div>
        </div>
      </div>
      {/* Value */}
      <div style={{ fontSize: 24, fontWeight: 900, letterSpacing: "-0.03em", color, lineHeight: 1, fontFamily: "'JetBrains Mono', monospace", marginBottom: 4 }}>{value}</div>
      {/* Subtext + trend */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: "auto" }}>
        <p style={{ fontSize: 10, color: "var(--text-secondary)", fontWeight: 500 }}>{subtext}</p>
        <TrendIcon size={11} color={trendColor} />
      </div>
    </div>
  );
}

function AgentStateKPI({ agentState, stateColor, reason }: { agentState: string; stateColor: string; reason: string }) {
  return (
    <div className="card" style={{ padding: "18px 20px", display: "flex", flexDirection: "column", gap: 10, position: "relative", overflow: "hidden", minHeight: 120 }}>
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 2, background: stateColor, opacity: 0.5 }} />
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", zIndex: 1 }}>
        <span style={{ color: "var(--text-muted)", fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em" }}>Agent State</span>
        <div style={{ padding: 7, borderRadius: 9, background: "var(--bg-elevated)", color: stateColor, border: `1px solid ${stateColor}30`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}><Gauge size={14} /></div>
      </div>
      <div style={{ marginTop: "auto", zIndex: 1 }}>
        <span className={`badge badge-${agentState.toLowerCase()}`} style={{ fontSize: 12, fontWeight: 800, padding: "4px 12px" }}><CircleDot size={9} />{agentState}</span>
        <p style={{ fontSize: 11, color: "var(--text-secondary)", fontWeight: 500, marginTop: 6, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{reason}</p>
      </div>
    </div>
  );
}

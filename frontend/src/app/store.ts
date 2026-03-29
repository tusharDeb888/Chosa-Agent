"use client";
import { create } from "zustand";
import { Alert, AlertGroup, ViewMode, StagedOrder } from "./components/types";

// ── News Item ──
export interface NewsItem {
  id: string;
  ticker: string;
  headline: string;
  sentiment: "bullish" | "bearish" | "neutral";
  source: string;
  published_at: string;
  fetched_at: string;
  impact_score: number; // 0–100
  category: "news" | "filing" | "macro";
  reasoning_id?: string;
  source_mode: "mock" | "live";
  url?: string;
  summary?: string;
}

// ── Action Item ──
export interface ActionItem {
  id: string;
  alert_id: string;
  ticker: string;
  decision: string;
  confidence: number;
  rationale_snippet: string;
  trust_score: number;
  trust_label: string;
  status: "pending" | "prepared" | "snoozed" | "ignored" | "escalated";
  snooze_until?: string;
  created_at: string;
}

// ── Trust Score (backend-computed) ──
export interface TrustScore {
  score: number; // 0–100
  label: "Safe Advisory" | "Review Needed" | "High Risk";
  factors: {
    confidence_normalized: number;
    freshness_normalized: number;
    policy_pass: boolean;
    source_reliability: number;
  };
}

// ── System Health ──
export interface SystemHealth {
  agent_state: string;
  last_heartbeat: string | null;
  degraded_reason?: string;
  workers: Record<string, { status: string; last_heartbeat: string | null }>;
}

// ── Store Interface ──
interface AlphaHunterStore {
  // Agent
  agentState: string;
  setAgentState: (state: string) => void;

  // Connection
  connected: boolean;
  setConnected: (c: boolean) => void;

  // Alerts
  alerts: Alert[];
  addAlert: (alert: Alert) => void;
  setAlerts: (alerts: Alert[]) => void;
  clearAlerts: () => void;

  // News
  portfolioNews: NewsItem[];
  setPortfolioNews: (news: NewsItem[]) => void;
  addNewsItem: (item: NewsItem) => void;

  // Explainability
  selectedAlertId: string | null;
  selectedAlert: Alert | null;
  openExplainDrawer: (alert: Alert) => void;
  closeExplainDrawer: () => void;

  // UI Mode
  viewMode: ViewMode;
  toggleViewMode: () => void;

  // Onboarding
  onboarded: boolean;
  setOnboarded: (v: boolean) => void;
  riskProfile: "conservative" | "balanced" | "aggressive";
  setRiskProfile: (p: "conservative" | "balanced" | "aggressive") => void;

  // Demo
  demoRunning: boolean;
  demoScenario: string | null;
  setDemoRunning: (running: boolean, scenario?: string | null) => void;

  // Action Center
  actionQueue: ActionItem[];
  setActionQueue: (items: ActionItem[]) => void;
  updateActionStatus: (id: string, status: ActionItem["status"], snooze_until?: string) => void;

  // System Health
  systemHealth: SystemHealth | null;
  setSystemHealth: (h: SystemHealth) => void;

  // Last decision timing
  lastDecisionAgo: number | null;
  setLastDecisionAgo: (v: number | null | ((prev: number | null) => number | null)) => void;

  // Error
  error: string | null;
  setError: (e: string | null) => void;

  // Active modals
  showOnboarding: boolean;
  setShowOnboarding: (v: boolean) => void;
  showKillConfirm: boolean;
  setShowKillConfirm: (v: boolean) => void;

  // Order flow
  activeOrder: { order: StagedOrder; decision: any; ticker: string } | null;
  setActiveOrder: (o: { order: StagedOrder; decision: any; ticker: string } | null) => void;

  // Transitioning state
  transitioning: boolean;
  setTransitioning: (v: boolean) => void;

  // Chaos result
  chaosResult: string | null;
  setChaosResult: (v: string | null) => void;
}

export const useStore = create<AlphaHunterStore>((set, get) => ({
  // ── Agent ──
  agentState: "UNKNOWN",
  setAgentState: (state) => set({ agentState: state }),

  // ── Connection ──
  connected: false,
  setConnected: (c) => set({ connected: c }),

  // ── Alerts ──
  alerts: [],
  addAlert: (alert) =>
    set((s) => ({
      alerts: [alert, ...s.alerts].slice(0, 50),
      lastDecisionAgo: 0,
      // Auto-create action item
      actionQueue: [
        {
          id: alert.alert_id,
          alert_id: alert.alert_id,
          ticker: alert.ticker || alert.decision?.signal_id?.split("-")[0] || "???",
          decision: alert.decision?.final_decision || "WATCH",
          confidence: alert.decision?.confidence || 0,
          rationale_snippet: alert.decision?.rationale?.split(".")[0] + "." || "",
          trust_score: computeTrustScore(alert),
          trust_label: computeTrustLabel(computeTrustScore(alert)),
          status: "pending",
          created_at: alert.created_at,
        },
        ...s.actionQueue,
      ].slice(0, 100),
    })),
  setAlerts: (alerts) => set({ alerts }),
  clearAlerts: () => set({ alerts: [], actionQueue: [] }),

  // ── News ──
  portfolioNews: [],
  setPortfolioNews: (news) => set({ portfolioNews: news }),
  addNewsItem: (item) =>
    set((s) => ({
      portfolioNews: [item, ...s.portfolioNews].slice(0, 100),
    })),

  // ── Explainability ──
  selectedAlertId: null,
  selectedAlert: null,
  openExplainDrawer: (alert) =>
    set({ selectedAlertId: alert.alert_id, selectedAlert: alert }),
  closeExplainDrawer: () =>
    set({ selectedAlertId: null, selectedAlert: null }),

  // ── UI Mode ──
  viewMode: (typeof window !== "undefined" && (localStorage.getItem("ah-viewMode") as ViewMode)) || "simple",
  toggleViewMode: () =>
    set((s) => {
      const next = s.viewMode === "simple" ? "pro" : "simple";
      if (typeof window !== "undefined") localStorage.setItem("ah-viewMode", next);
      return { viewMode: next as ViewMode };
    }),

  // ── Onboarding ──
  onboarded: typeof window !== "undefined" ? !!localStorage.getItem("ah-onboarded") : false,
  setOnboarded: (v) => {
    if (typeof window !== "undefined") {
      if (v) localStorage.setItem("ah-onboarded", "1");
      else localStorage.removeItem("ah-onboarded");
    }
    set({ onboarded: v, showOnboarding: !v });
  },
  riskProfile: (typeof window !== "undefined" && (localStorage.getItem("ah-risk") as any)) || "balanced",
  setRiskProfile: (p) => {
    if (typeof window !== "undefined") localStorage.setItem("ah-risk", p);
    set({ riskProfile: p });
  },

  // ── Demo ──
  demoRunning: false,
  demoScenario: null,
  setDemoRunning: (running, scenario = null) =>
    set({ demoRunning: running, demoScenario: scenario }),

  // ── Action Center ──
  actionQueue: [],
  setActionQueue: (items) => set({ actionQueue: items }),
  updateActionStatus: (id, status, snooze_until) =>
    set((s) => ({
      actionQueue: s.actionQueue.map((a) =>
        a.id === id ? { ...a, status, snooze_until } : a
      ),
    })),

  // ── System Health ──
  systemHealth: null,
  setSystemHealth: (h) => set({ systemHealth: h, agentState: h.agent_state }),

  // ── Timing ──
  lastDecisionAgo: null,
  setLastDecisionAgo: (v) => set((state) => ({
    lastDecisionAgo: typeof v === 'function' ? (v as (prev: number | null) => number | null)(state.lastDecisionAgo) : v,
  })),

  // ── Error ──
  error: null,
  setError: (e) => set({ error: e }),

  // ── Modals ──
  showOnboarding: false,
  setShowOnboarding: (v) => set({ showOnboarding: v }),
  showKillConfirm: false,
  setShowKillConfirm: (v) => set({ showKillConfirm: v }),

  // ── Order ──
  activeOrder: null,
  setActiveOrder: (o) => set({ activeOrder: o }),

  // ── Transitioning ──
  transitioning: false,
  setTransitioning: (v) => set({ transitioning: v }),

  // ── Chaos ──
  chaosResult: null,
  setChaosResult: (v) => set({ chaosResult: v }),
}));

// ── Trust score computation (client-side for demo, backend for real) ──
function computeTrustScore(alert: Alert): number {
  const d = alert.decision;
  if (!d) return 0;

  const confidence = Math.min(d.confidence, 100) / 100; // 0-1
  const createdAgo = (Date.now() - new Date(d.created_at || alert.created_at).getTime()) / 3600000;
  const freshness = Math.max(0, 1 - createdAgo / 24); // decays over 24h
  const policyPass = d.policy_passed ? 1 : 0;
  const sourceReliability = d.citations?.length > 0 ? Math.min(d.citations.length / 3, 1) : 0.2;
  const degradedPenalty = d.degraded_context ? 0.3 : 0;

  const raw = confidence * 0.4 + freshness * 0.3 + policyPass * 0.2 + sourceReliability * 0.1 - degradedPenalty;
  return Math.round(Math.max(0, Math.min(1, raw)) * 100);
}

function computeTrustLabel(score: number): "Safe Advisory" | "Review Needed" | "High Risk" {
  if (score >= 70) return "Safe Advisory";
  if (score >= 40) return "Review Needed";
  return "High Risk";
}

export { computeTrustScore, computeTrustLabel };

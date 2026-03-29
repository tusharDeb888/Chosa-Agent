// ═══════════════════════════════════════════════════
// Shared Types — mirrors backend core/schemas.py
// ═══════════════════════════════════════════════════

export interface Citation {
  url: string;
  published_at?: string;
  title?: string;
  source_type?: string; // corporate_filing | news | analysis
  plain_summary?: string;
}

export interface PortfolioImpact {
  position_delta_pct: number;
  sector_exposure_delta_pct: number;
  cash_impact: number;
}

export interface PortfolioContext {
  symbol_exposure_pct: number;
  symbol_value: number;
  symbol_quantity: number;
  sector_name: string;
  sector_exposure_pct: number;
  sector_holdings: string[];
  personalized_summary: string;
}

export interface StagedOrder {
  order_ticket_id: string;
  action: string; // BUY | SELL
  symbol: string;
  quantity: number;
  price: number;
  order_type: string; // LIMIT | MARKET
  estimated_value: number;
  valid_until: string;
  status: string; // STAGED | CONFIRMED | EXPIRED | CANCELLED
}

export interface GuardedDecision {
  signal_id: string;
  user_id: string;
  tenant_id: string;
  original_decision: string;
  final_decision: string;
  confidence: number;
  rationale: string;
  citations: Citation[];
  portfolio_impact: PortfolioImpact;
  risk_flags: string[];
  policy_reason_codes: string[];
  policy_passed: boolean;
  ttl_seconds: number;
  degraded_context: boolean;
  created_at: string;
  workflow_id: string;
  trace_id: string;
  portfolio_context?: PortfolioContext;
  staged_order?: StagedOrder;
}

export interface Alert {
  alert_id: string;
  user_id: string;
  decision: GuardedDecision;
  created_at: string;
  ticker?: string;
  staged_order?: StagedOrder;
}

export interface AgentStatus {
  state: string;
  updated_at: number | null;
  reason: string;
  recent_transitions: string[];
  workers: {
    ingestion: {
      last_heartbeat: string | null;
      tick_count: string | null;
    };
  };
}

export interface Metrics {
  streams: Record<string, number>;
  dlq: Record<string, number>;
  workers: {
    ingestion: {
      last_heartbeat: string | null;
      tick_count: string | null;
      status: string;
    };
  };
  agent_state: string;
  timestamp: string;
}

export interface AlertGroup {
  ticker: string;
  decision: string;
  alerts: Alert[];
  latestAlert: Alert;
  firstAt: number;
  lastAt: number;
}

export type ViewMode = "simple" | "pro";

export interface DemoEvent {
  ticker: string;
  decision: string;
  confidence: number;
  rationale: string;
  anomaly: string;
  risk_flags: string[];
  portfolio_impact: PortfolioImpact;
  citations: Citation[];
  ttl: number;
  portfolio_context?: PortfolioContext;
  staged_order?: StagedOrder;
}

// Demo scenario data
export const DEMO_EVENTS: DemoEvent[] = [
  {
    ticker: "ICICIBANK", decision: "BUY", confidence: 78,
    rationale: "Your ₹5.2L in ICICIBANK (8.2% of your portfolio) could benefit from this volume surge — 3.2x above 5-minute EMA. Institutional buying pattern shows consistent bid-side pressure. Technical breakout above ₹1,240 resistance with strong buying momentum confirmed.",
    anomaly: "VOLUME_SPIKE", risk_flags: ["SECTOR_CONCENTRATION"],
    portfolio_impact: { position_delta_pct: 4.2, sector_exposure_delta_pct: 3.4, cash_impact: -52000 },
    citations: [
      { url: "https://economictimes.com/icici-q4-results", published_at: "2026-03-28T10:00:00Z", title: "ICICI Bank Q4 Results: Net Profit Surges 22%", source_type: "news", plain_summary: "ICICI Bank reported strong quarterly results with 22% profit growth, beating analyst expectations." },
      { url: "https://www.bseindia.com/corporates/annDet.aspx?scrip=532174", published_at: "2026-03-28T09:30:00Z", title: "ICICI Bank — Board Approves Final Dividend", source_type: "corporate_filing", plain_summary: "The board approved a dividend of ₹10 per share, meaning shareholders will receive ₹10 for each share they own." },
    ],
    ttl: 300,
    portfolio_context: {
      symbol_exposure_pct: 8.2, symbol_value: 520000, symbol_quantity: 495,
      sector_name: "Banking & Finance", sector_exposure_pct: 28.5,
      sector_holdings: ["HDFCBANK", "SBIN"],
      personalized_summary: "Your ₹5.2L in ICICIBANK represents 8.2% of your portfolio. You also hold HDFCBANK, SBIN in the Banking & Finance sector.",
    },
    staged_order: {
      order_ticket_id: "order-demo-001", action: "BUY", symbol: "ICICIBANK",
      quantity: 50, price: 1052.50, order_type: "LIMIT", estimated_value: 52625,
      valid_until: new Date(Date.now() + 300000).toISOString(), status: "STAGED",
    },
  },
  {
    ticker: "RELIANCE", decision: "WATCH", confidence: 42,
    rationale: "Moderate price movement detected (1.8σ deviation). A Reliance promoter entity sold ₹957 crore worth of shares — this is a small fraction of their total holdings but could signal profit-booking. Insufficient conviction for actionable recommendation — monitor for sector rotation signals.",
    anomaly: "PRICE_DEVIATION", risk_flags: ["LLM_UNCERTAINTY", "EVIDENCE_SPARSE"],
    portfolio_impact: { position_delta_pct: 0, sector_exposure_delta_pct: 0, cash_impact: 0 },
    citations: [
      { url: "https://www.nseindia.com/companies-listing/corporate-filings-insider-trading", published_at: "2026-03-28T09:30:00Z", title: "Reliance — Promoter Stake Sale (SAST)", source_type: "corporate_filing", plain_summary: "A Reliance promoter company sold ₹957 crore worth of shares, reducing the promoter stake slightly to 50.29%." },
      { url: "https://moneycontrol.com/reliance-restructuring", published_at: "2026-03-28T09:30:00Z", title: "Jio Platforms Restructuring Update", source_type: "news", plain_summary: "Reliance is reorganizing its Jio subsidiary, which investors are watching closely for impact on the stock." },
    ],
    ttl: 180,
    portfolio_context: {
      symbol_exposure_pct: 15.1, symbol_value: 955000, symbol_quantity: 390,
      sector_name: "Energy & Conglomerate", sector_exposure_pct: 15.1,
      sector_holdings: [],
      personalized_summary: "Your ₹9.6L in RELIANCE represents 15.1% of your portfolio — your single largest holding.",
    },
  },
  {
    ticker: "HDFCBANK", decision: "SELL", confidence: 71,
    rationale: "⚠️ Your ₹18.5L in HDFCBANK represents 28% of your portfolio — this exceeds your 25% max concentration limit. RBI's new regulation requiring banks to keep more money aside for personal loans will squeeze HDFC Bank's lending margins. Combined with the spread anomaly showing heavy selling pressure (2.4x normal ask volume), we recommend reducing your position.",
    anomaly: "SPREAD_ANOMALY", risk_flags: ["MAX_CONCENTRATION_EXCEEDED"],
    portfolio_impact: { position_delta_pct: -8.5, sector_exposure_delta_pct: -6.2, cash_impact: 185000 },
    citations: [
      { url: "https://rbi.org.in/Scripts/NotificationUser.aspx?Id=12540", published_at: "2026-03-28T08:00:00Z", title: "RBI Circular: Revised Risk Weights on Consumer Lending", source_type: "corporate_filing", plain_summary: "RBI is making banks keep more money aside for personal loans — this reduces how much they can lend and could hurt profits." },
      { url: "https://livemint.com/hdfc-technical-analysis", published_at: "2026-03-28T11:00:00Z", title: "HDFC Bank Under Selling Pressure Post-RBI Circular", source_type: "analysis", plain_summary: "Large investors are selling HDFC Bank shares after the RBI regulation, putting downward pressure on the stock price." },
    ],
    ttl: 240,
    portfolio_context: {
      symbol_exposure_pct: 28.0, symbol_value: 1850000, symbol_quantity: 1121,
      sector_name: "Banking & Finance", sector_exposure_pct: 42.3,
      sector_holdings: ["ICICIBANK", "SBIN"],
      personalized_summary: "Your ₹18.5L in HDFCBANK represents 28% of your portfolio — this EXCEEDS your 25% max concentration limit. You also hold ICICIBANK, SBIN in Banking & Finance (total sector: 42.3%).",
    },
    staged_order: {
      order_ticket_id: "order-demo-002", action: "SELL", symbol: "HDFCBANK",
      quantity: 112, price: 1647.50, order_type: "LIMIT", estimated_value: 184520,
      valid_until: new Date(Date.now() + 240000).toISOString(), status: "STAGED",
    },
  },
  {
    ticker: "TCS", decision: "HOLD", confidence: 65,
    rationale: "Your ₹7.6L in TCS (12% of portfolio) is well-positioned. TCS board is considering a share buyback — this is when a company buys back its own shares from investors, usually at a price higher than market value, giving you an opportunity to sell at a profit. Hold your current position for now.",
    anomaly: "MOMENTUM_BREAK", risk_flags: [],
    portfolio_impact: { position_delta_pct: 0, sector_exposure_delta_pct: 0.5, cash_impact: 0 },
    citations: [
      { url: "https://www.bseindia.com/corporates/annDet.aspx?scrip=532540", published_at: "2026-03-28T07:00:00Z", title: "TCS Board Meeting — Share Buyback Proposal", source_type: "corporate_filing", plain_summary: "TCS may buy back its shares from investors at a premium price — this is good news for current shareholders." },
    ],
    ttl: 600,
    portfolio_context: {
      symbol_exposure_pct: 12.0, symbol_value: 760000, symbol_quantity: 200,
      sector_name: "IT Services", sector_exposure_pct: 18.5,
      sector_holdings: ["INFY"],
      personalized_summary: "Your ₹7.6L in TCS represents 12% of your portfolio. You also hold INFY in IT Services.",
    },
  },
  {
    ticker: "ICICIBANK", decision: "BUY", confidence: 82,
    rationale: "Second volume confirmation in 12 minutes validates the earlier signal. Your banking sector exposure is at 28.5%, within your 40% sector limit. ICICI Bank's 22% profit growth and ₹10 dividend make this an attractive addition. Recommend increasing your position to ₹7.8L (12% portfolio weight).",
    anomaly: "VOLUME_SPIKE", risk_flags: [],
    portfolio_impact: { position_delta_pct: 3.8, sector_exposure_delta_pct: 2.1, cash_impact: -48000 },
    citations: [
      { url: "https://economictimes.com/banking-sector-rally", published_at: "2026-03-28T10:15:00Z", title: "Banking Sector Rally: ICICI, Axis Lead Gains", source_type: "news", plain_summary: "Banking stocks are rallying with ICICI Bank leading gains — analysts say strong quarterly results are driving fresh buying." },
    ],
    ttl: 300,
    portfolio_context: {
      symbol_exposure_pct: 8.2, symbol_value: 520000, symbol_quantity: 495,
      sector_name: "Banking & Finance", sector_exposure_pct: 28.5,
      sector_holdings: ["HDFCBANK", "SBIN"],
      personalized_summary: "Your ₹5.2L in ICICIBANK represents 8.2% of your portfolio. Banking & Finance sector total: 28.5%.",
    },
    staged_order: {
      order_ticket_id: "order-demo-003", action: "BUY", symbol: "ICICIBANK",
      quantity: 45, price: 1055.00, order_type: "LIMIT", estimated_value: 47475,
      valid_until: new Date(Date.now() + 300000).toISOString(), status: "STAGED",
    },
  },
  {
    ticker: "INFY", decision: "WATCH", confidence: 15,
    rationale: "System Advisory: Unusual market activity detected for INFY. Our AI analysis engine is running in reduced capacity mode — some evidence sources were unavailable. Your ₹4.1L in INFY (6.5% of portfolio) is not at immediate risk, but please monitor this stock manually.",
    anomaly: "VOLUME_SPIKE", risk_flags: ["LLM_UNAVAILABLE", "DEGRADED_CONTEXT"],
    portfolio_impact: { position_delta_pct: 0, sector_exposure_delta_pct: 0, cash_impact: 0 },
    citations: [],
    ttl: 120,
    portfolio_context: {
      symbol_exposure_pct: 6.5, symbol_value: 410000, symbol_quantity: 264,
      sector_name: "IT Services", sector_exposure_pct: 18.5,
      sector_holdings: ["TCS"],
      personalized_summary: "Your ₹4.1L in INFY represents 6.5% of your portfolio. You also hold TCS in IT Services.",
    },
  },
];

export const confidenceLabel = (c: number) => {
  if (c >= 75) return { text: "High confidence", color: "#10b981" };
  if (c >= 50) return { text: "Moderate confidence", color: "#3b82f6" };
  if (c >= 30) return { text: "Low confidence (advisory)", color: "#f59e0b" };
  return { text: "Very low (advisory only)", color: "#ef4444" };
};

export const decisionColors: Record<string, string> = {
  BUY: "#10b981", SELL: "#ef4444", HOLD: "#3b82f6", WATCH: "#f59e0b",
};

export const getDecisionColor = (d: string) => decisionColors[d] || "#5a6a82";

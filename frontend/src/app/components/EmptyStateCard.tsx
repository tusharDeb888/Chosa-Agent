"use client";
import { Play, Plus, Newspaper, TrendingUp, Briefcase } from "lucide-react";

interface EmptyStateCardProps {
  type: "alerts" | "news" | "portfolio" | "generic";
  onAction?: () => void;
  actionLabel?: string;
  title?: string;
  description?: string;
}

const PRESETS = {
  alerts: {
    icon: TrendingUp,
    title: "No Live Alerts",
    description: "The agent is monitoring the market. Alerts will appear here when anomalies are detected in your portfolio.",
    actionLabel: "Run Demo Scenario",
    color: "#06b6d4",
  },
  news: {
    icon: Newspaper,
    title: "News Radar Starting",
    description: "Portfolio News Radar is scanning sources. Recent headlines and filings will appear momentarily.",
    actionLabel: "Enable News Radar",
    color: "#8b5cf6",
  },
  portfolio: {
    icon: Briefcase,
    title: "Build Your Portfolio",
    description: "Add stocks to track real-time impact from market events. The agent will monitor your holdings 24/7.",
    actionLabel: "Add Holdings",
    color: "#f59e0b",
  },
  generic: {
    icon: Play,
    title: "Getting Started",
    description: "Start the agent to begin monitoring markets.",
    actionLabel: "Start",
    color: "#10b981",
  },
};

export default function EmptyStateCard({
  type,
  onAction,
  actionLabel,
  title,
  description,
}: EmptyStateCardProps) {
  const preset = PRESETS[type] || PRESETS.generic;
  const Icon = preset.icon;
  const color = preset.color;

  return (
    <div style={{
      textAlign: "center",
      padding: "36px 24px",
      animation: "fadeIn 0.5s ease",
    }}>
      <div style={{
        width: 52, height: 52, borderRadius: 14, margin: "0 auto 16px",
        background: `${color}12`, border: `1px solid ${color}20`,
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <Icon size={22} color={color} style={{ opacity: 0.6 }} />
      </div>

      <p style={{
        fontSize: 14, fontWeight: 700, color: "var(--text-primary)",
        marginBottom: 6,
      }}>
        {title || preset.title}
      </p>

      <p style={{
        fontSize: 12, color: "var(--text-muted)", lineHeight: 1.6,
        maxWidth: 340, margin: "0 auto 20px",
      }}>
        {description || preset.description}
      </p>

      {onAction && (
        <button
          onClick={onAction}
          style={{
            padding: "10px 22px", borderRadius: 10, fontSize: 12, fontWeight: 700,
            border: "none",
            background: `linear-gradient(135deg, ${color}, ${color}cc)`,
            color: "#fff", cursor: "pointer",
            display: "inline-flex", alignItems: "center", gap: 7,
            boxShadow: `0 4px 16px ${color}30`,
            transition: "transform 0.15s, box-shadow 0.15s",
          }}
          onMouseEnter={e => {
            e.currentTarget.style.transform = "translateY(-1px)";
            e.currentTarget.style.boxShadow = `0 6px 20px ${color}40`;
          }}
          onMouseLeave={e => {
            e.currentTarget.style.transform = "translateY(0)";
            e.currentTarget.style.boxShadow = `0 4px 16px ${color}30`;
          }}
        >
          <Play size={12} />
          {actionLabel || preset.actionLabel}
        </button>
      )}
    </div>
  );
}

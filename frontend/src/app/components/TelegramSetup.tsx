"use client";

import React, { useState, useEffect } from "react";
import {
  Send,
  Check,
  X,
  AlertTriangle,
  Settings,
  RefreshCw,
  ExternalLink,
  Copy,
  CheckCircle,
  MessageCircle,
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface TelegramStatus {
  configured: boolean;
  connected: boolean;
  bot_username?: string;
  bot_name?: string;
  chat_id?: string;
  message: string;
  setup_instructions?: Record<string, string>;
}

interface DiscoverResult {
  ok: boolean;
  chats?: Array<{
    chat_id: string;
    type: string;
    first_name: string;
    username: string;
    last_message: string;
  }>;
  recommended_chat_id?: string;
  error?: string;
}

export default function TelegramSetup() {
  const [status, setStatus] = useState<TelegramStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [setupMode, setSetupMode] = useState(false);
  const [botToken, setBotToken] = useState("");
  const [chatId, setChatId] = useState("");
  const [setupResult, setSetupResult] = useState<any>(null);
  const [discovering, setDiscovering] = useState(false);
  const [discoverResult, setDiscoverResult] = useState<DiscoverResult | null>(null);
  const [testResult, setTestResult] = useState<any>(null);
  const [sending, setSending] = useState(false);
  const [copied, setCopied] = useState("");

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API}/api/v1/telegram/status`);
      const data = await res.json();
      setStatus(data);
    } catch (e) {
      setStatus({
        configured: false,
        connected: false,
        message: "Failed to reach backend",
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleSetup = async () => {
    if (!botToken || !chatId) return;
    setSetupResult(null);
    try {
      const res = await fetch(`${API}/api/v1/telegram/setup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bot_token: botToken, chat_id: chatId }),
      });
      const data = await res.json();
      setSetupResult(data);
      if (data.ok) {
        fetchStatus();
      }
    } catch (e) {
      setSetupResult({ ok: false, error: "Network error" });
    }
  };

  const handleDiscover = async () => {
    if (!botToken) return;
    setDiscovering(true);
    setDiscoverResult(null);
    try {
      const res = await fetch(
        `${API}/api/v1/telegram/discover?token=${encodeURIComponent(botToken)}`
      );
      const data = await res.json();
      setDiscoverResult(data);
      if (data.recommended_chat_id) {
        setChatId(data.recommended_chat_id);
      }
    } catch (e) {
      setDiscoverResult({ ok: false, error: "Network error" });
    } finally {
      setDiscovering(false);
    }
  };

  const handleTest = async () => {
    setSending(true);
    setTestResult(null);
    try {
      const res = await fetch(`${API}/api/v1/telegram/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: "RELIANCE",
          decision: "BUY",
          confidence: 82,
          rationale:
            "Volume spike 3.8x above EMA. Institutional flow confirmed. Q4 results support.",
        }),
      });
      const data = await res.json();
      setTestResult(data);
    } catch (e) {
      setTestResult({ ok: false, error: "Network error" });
    } finally {
      setSending(false);
    }
  };

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(""), 2000);
  };

  if (loading) {
    return (
      <div style={styles.container}>
        <div style={styles.loadingPulse}>
          <MessageCircle size={24} color="#60a5fa" />
          <span>Checking Telegram status...</span>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <MessageCircle size={20} color="#60a5fa" />
          <h3 style={styles.title}>Telegram Alerts</h3>
          <span
            style={{
              ...styles.badge,
              background: status?.connected
                ? "rgba(16, 185, 129, 0.15)"
                : "rgba(239, 68, 68, 0.15)",
              color: status?.connected ? "#10b981" : "#ef4444",
            }}
          >
            {status?.connected ? "CONNECTED" : "NOT CONFIGURED"}
          </span>
        </div>
        <div style={styles.headerActions}>
          <button onClick={fetchStatus} style={styles.iconBtn} title="Refresh">
            <RefreshCw size={14} />
          </button>
          {!status?.configured && (
            <button
              onClick={() => setSetupMode(!setupMode)}
              style={{
                ...styles.btn,
                background: setupMode
                  ? "rgba(239, 68, 68, 0.2)"
                  : "rgba(96, 165, 250, 0.15)",
                color: setupMode ? "#ef4444" : "#60a5fa",
              }}
            >
              {setupMode ? (
                <X size={14} />
              ) : (
                <Settings size={14} />
              )}
              {setupMode ? "Cancel" : "Setup"}
            </button>
          )}
        </div>
      </div>

      {/* Connected State */}
      {status?.connected && (
        <div style={styles.connectedBox}>
          <div style={styles.connectedHeader}>
            <CheckCircle size={16} color="#10b981" />
            <span style={{ color: "#d1d5db" }}>
              Bot <strong style={{ color: "#60a5fa" }}>@{status.bot_username}</strong> is
              active
            </span>
          </div>
          <div style={styles.connectedMeta}>
            <span>Chat ID: <code style={styles.code}>{status.chat_id}</code></span>
          </div>
          <div style={styles.testSection}>
            <button
              onClick={handleTest}
              disabled={sending}
              style={{
                ...styles.btn,
                background: "rgba(16, 185, 129, 0.15)",
                color: "#10b981",
                opacity: sending ? 0.6 : 1,
              }}
            >
              <Send size={14} />
              {sending ? "Sending..." : "Send Test Alert"}
            </button>
            {testResult && (
              <span
                style={{
                  color: testResult.ok ? "#10b981" : "#ef4444",
                  fontSize: 12,
                }}
              >
                {testResult.ok
                  ? `✅ Sent! (ID: ${testResult.message_id})`
                  : `❌ ${testResult.error}`}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Not Configured + Instructions */}
      {!status?.configured && !setupMode && (
        <div style={styles.instructionsBox}>
          <p style={{ color: "#9ca3af", fontSize: 13, marginBottom: 12 }}>
            Receive real-time trading alerts directly on your phone via Telegram.
          </p>
          <div style={styles.steps}>
            {status?.setup_instructions &&
              Object.entries(status.setup_instructions).map(([key, val]) => (
                <div key={key} style={styles.step}>
                  <span style={styles.stepNum}>
                    {key.replace("step_", "")}
                  </span>
                  <span style={styles.stepText}>{val}</span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Setup Form */}
      {setupMode && (
        <div style={styles.setupForm}>
          <div style={styles.formGroup}>
            <label style={styles.label}>Bot Token</label>
            <input
              type="text"
              value={botToken}
              onChange={(e) => setBotToken(e.target.value)}
              placeholder="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
              style={styles.input}
            />
            <span style={styles.hint}>Get from @BotFather on Telegram</span>
          </div>

          {botToken && (
            <div style={styles.discoverSection}>
              <button
                onClick={handleDiscover}
                disabled={discovering}
                style={{
                  ...styles.btn,
                  background: "rgba(168, 85, 247, 0.15)",
                  color: "#a78bfa",
                  opacity: discovering ? 0.6 : 1,
                }}
              >
                <RefreshCw
                  size={14}
                  style={{
                    animation: discovering ? "spin 1s linear infinite" : "none",
                  }}
                />
                {discovering ? "Discovering..." : "Auto-Discover Chat ID"}
              </button>
              <span style={styles.hint}>
                Send a message to your bot first, then click discover
              </span>

              {discoverResult && (
                <div
                  style={{
                    ...styles.resultBox,
                    borderColor: discoverResult.ok
                      ? "rgba(16, 185, 129, 0.3)"
                      : "rgba(239, 68, 68, 0.3)",
                  }}
                >
                  {discoverResult.ok && discoverResult.chats ? (
                    discoverResult.chats.map((chat) => (
                      <div
                        key={chat.chat_id}
                        style={styles.chatItem}
                        onClick={() => setChatId(chat.chat_id)}
                      >
                        <span>
                          {chat.first_name || chat.username} ({chat.type})
                        </span>
                        <code style={styles.code}>{chat.chat_id}</code>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setChatId(chat.chat_id);
                          }}
                          style={{
                            ...styles.btn,
                            background: "rgba(16, 185, 129, 0.15)",
                            color: "#10b981",
                            fontSize: 11,
                            padding: "2px 8px",
                          }}
                        >
                          Use this
                        </button>
                      </div>
                    ))
                  ) : (
                    <span style={{ color: "#ef4444", fontSize: 12 }}>
                      {discoverResult.error}
                    </span>
                  )}
                </div>
              )}
            </div>
          )}

          <div style={styles.formGroup}>
            <label style={styles.label}>Chat ID</label>
            <input
              type="text"
              value={chatId}
              onChange={(e) => setChatId(e.target.value)}
              placeholder="123456789"
              style={styles.input}
            />
          </div>

          <div style={styles.setupActions}>
            <button
              onClick={handleSetup}
              disabled={!botToken || !chatId}
              style={{
                ...styles.btn,
                background:
                  botToken && chatId
                    ? "rgba(16, 185, 129, 0.2)"
                    : "rgba(107, 114, 128, 0.15)",
                color: botToken && chatId ? "#10b981" : "#6b7280",
                opacity: botToken && chatId ? 1 : 0.5,
              }}
            >
              <Check size={14} />
              Validate & Connect
            </button>
          </div>

          {setupResult && (
            <div
              style={{
                ...styles.resultBox,
                borderColor: setupResult.ok
                  ? "rgba(16, 185, 129, 0.3)"
                  : "rgba(239, 68, 68, 0.3)",
              }}
            >
              {setupResult.ok ? (
                <>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#10b981" }}>
                    <CheckCircle size={14} />
                    <span>{setupResult.message}</span>
                  </div>
                  <div style={{ marginTop: 8 }}>
                    {setupResult.env_values &&
                      Object.entries(setupResult.env_values).map(
                        ([key, val]) => (
                          <div
                            key={key}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: 6,
                              marginBottom: 4,
                            }}
                          >
                            <code style={styles.code}>
                              {key}={String(val).substring(0, 30)}...
                            </code>
                            <button
                              onClick={() => copyToClipboard(`${key}=${val}`, key)}
                              style={{
                                ...styles.iconBtn,
                                padding: 2,
                              }}
                            >
                              {copied === key ? (
                                <Check size={10} color="#10b981" />
                              ) : (
                                <Copy size={10} />
                              )}
                            </button>
                          </div>
                        )
                      )}
                  </div>
                  <p style={{ color: "#9ca3af", fontSize: 11, marginTop: 8 }}>
                    Add these to <code style={styles.code}>backend/.env</code> and restart the server.
                  </p>
                </>
              ) : (
                <div style={{ color: "#ef4444", display: "flex", alignItems: "center", gap: 8 }}>
                  <AlertTriangle size={14} />
                  <span>{setupResult.error}</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    background: "rgba(30, 41, 59, 0.5)",
    borderRadius: 16,
    border: "1px solid rgba(148, 163, 184, 0.08)",
    padding: 20,
  },
  loadingPulse: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    color: "#9ca3af",
    fontSize: 13,
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 16,
  },
  headerLeft: {
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  headerActions: {
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  title: {
    color: "#f1f5f9",
    fontSize: 16,
    fontWeight: 600,
    margin: 0,
  },
  badge: {
    fontSize: 10,
    fontWeight: 700,
    padding: "2px 8px",
    borderRadius: 6,
    letterSpacing: 0.5,
  },
  btn: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    padding: "6px 12px",
    borderRadius: 8,
    border: "none",
    cursor: "pointer",
    fontSize: 12,
    fontWeight: 500,
    transition: "all 0.2s",
  },
  iconBtn: {
    background: "none",
    border: "none",
    cursor: "pointer",
    color: "#94a3b8",
    padding: 4,
  },
  connectedBox: {
    background: "rgba(16, 185, 129, 0.05)",
    border: "1px solid rgba(16, 185, 129, 0.15)",
    borderRadius: 12,
    padding: 16,
  },
  connectedHeader: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    marginBottom: 8,
  },
  connectedMeta: {
    color: "#9ca3af",
    fontSize: 12,
    marginBottom: 12,
  },
  testSection: {
    display: "flex",
    alignItems: "center",
    gap: 12,
  },
  instructionsBox: {
    background: "rgba(96, 165, 250, 0.05)",
    border: "1px solid rgba(96, 165, 250, 0.1)",
    borderRadius: 12,
    padding: 16,
  },
  steps: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  step: {
    display: "flex",
    alignItems: "flex-start",
    gap: 10,
    fontSize: 12,
    color: "#d1d5db",
  },
  stepNum: {
    background: "rgba(96, 165, 250, 0.2)",
    color: "#60a5fa",
    width: 20,
    height: 20,
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 10,
    fontWeight: 700,
    flexShrink: 0,
  },
  stepText: {
    lineHeight: 1.5,
  },
  setupForm: {
    display: "flex",
    flexDirection: "column",
    gap: 16,
  },
  formGroup: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
  label: {
    color: "#94a3b8",
    fontSize: 12,
    fontWeight: 500,
  },
  input: {
    background: "rgba(15, 23, 42, 0.6)",
    border: "1px solid rgba(148, 163, 184, 0.15)",
    borderRadius: 8,
    padding: "8px 12px",
    color: "#f1f5f9",
    fontSize: 13,
    outline: "none",
    fontFamily: "monospace",
  },
  hint: {
    color: "#6b7280",
    fontSize: 11,
  },
  discoverSection: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
  },
  chatItem: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "6px 8px",
    background: "rgba(30, 41, 59, 0.5)",
    borderRadius: 6,
    cursor: "pointer",
    fontSize: 12,
    color: "#d1d5db",
  },
  setupActions: {
    display: "flex",
    justifyContent: "flex-end",
  },
  resultBox: {
    border: "1px solid",
    borderRadius: 8,
    padding: 12,
    fontSize: 12,
    marginTop: 8,
  },
  code: {
    background: "rgba(15, 23, 42, 0.8)",
    padding: "1px 6px",
    borderRadius: 4,
    fontSize: 11,
    color: "#60a5fa",
    fontFamily: "monospace",
  },
};

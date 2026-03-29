"use client";
import { useState, useCallback, useRef, useEffect } from "react";
import {
  MessageCircle, Send, X, Bot, User, Loader2,
  TrendingUp, Briefcase, Newspaper, BarChart3,
  Sparkles, ChevronDown
} from "lucide-react";

const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/api/v1";
const STORAGE_KEY = "alpha-hunter-portfolio";

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

const QUICK_PROMPTS = [
  { text: "How is my portfolio doing?", icon: Briefcase },
  { text: "Should I buy TCS?", icon: TrendingUp },
  { text: "Analyze candlestick patterns for RELIANCE", icon: BarChart3 },
  { text: "Latest market news", icon: Newspaper },
];

export default function ChatAgent() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  // Focus input when opened
  useEffect(() => {
    if (open && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 200);
    }
  }, [open]);

  // Get portfolio from localStorage
  const getPortfolio = useCallback(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch { return []; }
  }, []);

  const sendMessage = useCallback(async (text?: string) => {
    const msg = (text || input).trim();
    if (!msg || loading) return;

    const userMsg: Message = { role: "user", content: msg, timestamp: Date.now() };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const portfolio = getPortfolio();
      const history = messages.slice(-10).map(m => ({ role: m.role, content: m.content }));

      const resp = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg, history, portfolio }),
      });

      if (!resp.ok) {
        const d = await resp.json().catch(() => null);
        throw new Error(d?.detail || `HTTP ${resp.status}`);
      }

      const data = await resp.json();
      const botMsg: Message = { role: "assistant", content: data.reply, timestamp: Date.now() };
      setMessages(prev => [...prev, botMsg]);
    } catch (e: any) {
      const errMsg: Message = {
        role: "assistant",
        content: `❌ ${e.message || "Failed to get response"}`,
        timestamp: Date.now(),
      };
      setMessages(prev => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, messages, getPortfolio]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // Format message content with markdown-like rendering
  const formatContent = (text: string) => {
    return text
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`(.*?)`/g, '<code style="background:rgba(139,92,246,0.15);padding:1px 4px;border-radius:3px;font-size:11px">$1</code>')
      .replace(/^- (.*)/gm, '• $1')
      .replace(/^#{1,3} (.*)/gm, '<strong>$1</strong>')
      .replace(/\n/g, '<br/>');
  };

  return (
    <>
      {/* Floating Chat Button */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          style={{
            position: "fixed", bottom: 24, right: 24, zIndex: 1000,
            width: 56, height: 56, borderRadius: "50%", border: "none",
            background: "linear-gradient(135deg, #8b5cf6, #6366f1)",
            color: "#fff", cursor: "pointer",
            boxShadow: "0 4px 24px rgba(139,92,246,0.4)",
            display: "flex", alignItems: "center", justifyContent: "center",
            transition: "all 0.3s ease",
          }}
          onMouseEnter={e => { (e.target as HTMLElement).style.transform = "scale(1.1)"; }}
          onMouseLeave={e => { (e.target as HTMLElement).style.transform = "scale(1)"; }}
        >
          <MessageCircle size={24} />
          {/* Pulse indicator */}
          <span style={{
            position: "absolute", top: 0, right: 0,
            width: 14, height: 14, borderRadius: "50%",
            background: "#10b981", border: "2px solid #0f172a",
          }} />
        </button>
      )}

      {/* Chat Panel */}
      {open && (
        <div style={{
          position: "fixed", bottom: 24, right: 24, zIndex: 1000,
          width: 420, height: 600, maxHeight: "80vh",
          borderRadius: 20, overflow: "hidden",
          background: "linear-gradient(180deg, rgba(15,23,42,0.98), rgba(15,23,42,0.95))",
          border: "1px solid rgba(139,92,246,0.25)",
          boxShadow: "0 8px 48px rgba(0,0,0,0.5), 0 0 0 1px rgba(139,92,246,0.1)",
          backdropFilter: "blur(20px)",
          display: "flex", flexDirection: "column",
          animation: "chatSlideUp 0.3s ease-out",
        }}>
          {/* Header */}
          <div style={{
            padding: "14px 16px",
            background: "linear-gradient(135deg, rgba(139,92,246,0.12), rgba(99,102,241,0.08))",
            borderBottom: "1px solid rgba(139,92,246,0.15)",
            display: "flex", alignItems: "center", justifyContent: "space-between",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{
                width: 36, height: 36, borderRadius: 12,
                background: "linear-gradient(135deg, #8b5cf6, #6366f1)",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <Bot size={18} color="#fff" />
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, color: "#e2e8f0" }}>Chōsa AI</div>
                <div style={{ fontSize: 10, color: "#10b981", display: "flex", alignItems: "center", gap: 4 }}>
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#10b981", display: "inline-block" }} />
                  Online • Portfolio + News + Patterns
                </div>
              </div>
            </div>
            <button
              onClick={() => setOpen(false)}
              style={{
                width: 32, height: 32, borderRadius: 8, border: "none",
                background: "rgba(100,116,139,0.15)", cursor: "pointer",
                display: "flex", alignItems: "center", justifyContent: "center",
                color: "#94a3b8",
              }}
            >
              <X size={16} />
            </button>
          </div>

          {/* Messages */}
          <div ref={scrollRef} style={{
            flex: 1, overflowY: "auto", padding: "12px 14px",
            display: "flex", flexDirection: "column", gap: 12,
          }}>
            {/* Welcome message if empty */}
            {messages.length === 0 && (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14, padding: "20px 0" }}>
                <div style={{
                  width: 56, height: 56, borderRadius: 16,
                  background: "linear-gradient(135deg, rgba(139,92,246,0.15), rgba(99,102,241,0.1))",
                  border: "1px solid rgba(139,92,246,0.2)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  <Sparkles size={24} style={{ color: "#a78bfa" }} />
                </div>
                <div style={{ textAlign: "center" }}>
                  <p style={{ fontSize: 14, fontWeight: 600, color: "#e2e8f0", margin: 0 }}>
                    Hi! I'm your AI financial assistant
                  </p>
                  <p style={{ fontSize: 11, color: "#64748b", margin: "6px 0 0", maxWidth: 280 }}>
                    Ask me about your portfolio, stock analysis, buy/sell signals, candlestick patterns, or market news.
                  </p>
                </div>

                {/* Quick prompts */}
                <div style={{ display: "flex", flexDirection: "column", gap: 6, width: "100%", marginTop: 4 }}>
                  {QUICK_PROMPTS.map((q, i) => {
                    const Icon = q.icon;
                    return (
                      <button
                        key={i}
                        onClick={() => sendMessage(q.text)}
                        style={{
                          padding: "10px 14px", borderRadius: 10,
                          background: "rgba(30,41,59,0.5)",
                          border: "1px solid rgba(100,116,139,0.2)",
                          cursor: "pointer", textAlign: "left",
                          display: "flex", alignItems: "center", gap: 10,
                          transition: "all 0.2s",
                          color: "#cbd5e1",
                        }}
                        onMouseEnter={e => {
                          (e.currentTarget as HTMLElement).style.background = "rgba(139,92,246,0.08)";
                          (e.currentTarget as HTMLElement).style.borderColor = "rgba(139,92,246,0.3)";
                        }}
                        onMouseLeave={e => {
                          (e.currentTarget as HTMLElement).style.background = "rgba(30,41,59,0.5)";
                          (e.currentTarget as HTMLElement).style.borderColor = "rgba(100,116,139,0.2)";
                        }}
                      >
                        <Icon size={14} style={{ color: "#a78bfa", flexShrink: 0 }} />
                        <span style={{ fontSize: 12 }}>{q.text}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Message bubbles */}
            {messages.map((msg, i) => (
              <div key={i} style={{
                display: "flex", gap: 8,
                flexDirection: msg.role === "user" ? "row-reverse" : "row",
                alignItems: "flex-start",
              }}>
                {/* Avatar */}
                <div style={{
                  width: 28, height: 28, borderRadius: 8, flexShrink: 0,
                  background: msg.role === "user"
                    ? "linear-gradient(135deg, #3b82f6, #2563eb)"
                    : "linear-gradient(135deg, #8b5cf6, #6366f1)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  {msg.role === "user"
                    ? <User size={14} color="#fff" />
                    : <Bot size={14} color="#fff" />}
                </div>

                {/* Bubble */}
                <div style={{
                  maxWidth: "80%", padding: "10px 14px", borderRadius: 14,
                  background: msg.role === "user"
                    ? "linear-gradient(135deg, #3b82f6, #2563eb)"
                    : "rgba(30,41,59,0.6)",
                  border: msg.role === "user" ? "none" : "1px solid rgba(100,116,139,0.2)",
                  borderTopRightRadius: msg.role === "user" ? 4 : 14,
                  borderTopLeftRadius: msg.role === "user" ? 14 : 4,
                }}>
                  <div
                    style={{
                      fontSize: 12, color: msg.role === "user" ? "#fff" : "#cbd5e1",
                      lineHeight: 1.6, wordBreak: "break-word",
                    }}
                    dangerouslySetInnerHTML={{ __html: formatContent(msg.content) }}
                  />
                  <div style={{
                    fontSize: 9, color: msg.role === "user" ? "rgba(255,255,255,0.5)" : "#475569",
                    marginTop: 4, textAlign: msg.role === "user" ? "right" as const : "left" as const,
                  }}>
                    {new Date(msg.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </div>
                </div>
              </div>
            ))}

            {/* Loading indicator */}
            {loading && (
              <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                <div style={{
                  width: 28, height: 28, borderRadius: 8, flexShrink: 0,
                  background: "linear-gradient(135deg, #8b5cf6, #6366f1)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  <Bot size={14} color="#fff" />
                </div>
                <div style={{
                  padding: "12px 16px", borderRadius: 14, borderTopLeftRadius: 4,
                  background: "rgba(30,41,59,0.6)",
                  border: "1px solid rgba(100,116,139,0.2)",
                  display: "flex", alignItems: "center", gap: 8,
                }}>
                  <Loader2 size={14} style={{ color: "#a78bfa", animation: "spin 1s linear infinite" }} />
                  <span style={{ fontSize: 12, color: "#94a3b8" }}>Analyzing with live data...</span>
                </div>
              </div>
            )}
          </div>

          {/* Input */}
          <div style={{
            padding: "12px 14px",
            borderTop: "1px solid rgba(100,116,139,0.15)",
            background: "rgba(15,23,42,0.8)",
          }}>
            <div style={{
              display: "flex", gap: 8, alignItems: "center",
              background: "rgba(30,41,59,0.6)",
              border: "1px solid rgba(100,116,139,0.25)",
              borderRadius: 12, padding: "4px 6px 4px 14px",
            }}>
              <input
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about stocks, patterns, portfolio..."
                disabled={loading}
                style={{
                  flex: 1, background: "none", border: "none", outline: "none",
                  color: "#e2e8f0", fontSize: 13,
                  padding: "8px 0",
                }}
              />
              <button
                onClick={() => sendMessage()}
                disabled={!input.trim() || loading}
                style={{
                  width: 36, height: 36, borderRadius: 10, border: "none",
                  background: input.trim() && !loading
                    ? "linear-gradient(135deg, #8b5cf6, #6366f1)"
                    : "rgba(51,65,85,0.5)",
                  cursor: input.trim() && !loading ? "pointer" : "not-allowed",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  color: "#fff",
                  transition: "all 0.2s",
                }}
              >
                <Send size={14} />
              </button>
            </div>
            <div style={{
              display: "flex", alignItems: "center", justifyContent: "center",
              gap: 4, marginTop: 6,
            }}>
              <Bot size={8} style={{ color: "#475569" }} />
              <span style={{ fontSize: 8, color: "#475569" }}>
                Powered by Groq LLM • Upstox API • Candlestick Patterns
              </span>
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes chatSlideUp {
          from { opacity: 0; transform: translateY(20px) scale(0.95); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </>
  );
}

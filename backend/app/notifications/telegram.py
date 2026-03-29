"""
Telegram Bot Alert Service — Delivers Alpha-Hunter alerts to Telegram.

Features:
- Rich formatted alert messages with decision badges
- Portfolio impact summaries
- Citation links
- Risk flag warnings
- /status command for bot health check
- Graceful degradation when token is missing
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.config import get_settings
from app.core.observability import get_logger

logger = get_logger("notifications.telegram")

TELEGRAM_API = "https://api.telegram.org/bot{token}"

# Decision emoji mapping
DECISION_EMOJI = {
    "BUY": "🟢",
    "SELL": "🔴",
    "HOLD": "🟡",
    "WATCH": "👁️",
}

CONFIDENCE_BAR = {
    range(0, 20): "▓░░░░",
    range(20, 40): "▓▓░░░",
    range(40, 60): "▓▓▓░░",
    range(60, 80): "▓▓▓▓░",
    range(80, 101): "▓▓▓▓▓",
}


def _get_confidence_bar(confidence: int) -> str:
    for r, bar in CONFIDENCE_BAR.items():
        if confidence in r:
            return bar
    return "░░░░░"


def _format_inr(amount: float) -> str:
    """Format number as Indian Rupee."""
    if abs(amount) >= 1e5:
        return f"₹{amount/1e5:.1f}L"
    elif abs(amount) >= 1e3:
        return f"₹{amount/1e3:.1f}K"
    return f"₹{amount:,.0f}"


def _escape_md(text: str) -> str:
    """Escape Markdown V2 special characters."""
    special = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in str(text))


def format_alert_message(alert: dict) -> str:
    """
    Format an alert payload into a rich Telegram message (MarkdownV2).
    """
    decision_data = alert.get("decision", {})
    ticker = alert.get("ticker", decision_data.get("ticker", "UNKNOWN"))
    decision = decision_data.get("final_decision", decision_data.get("original_decision", "WATCH"))
    confidence = decision_data.get("confidence", 0)
    rationale = decision_data.get("rationale", "No rationale provided.")
    risk_flags = decision_data.get("risk_flags", [])
    citations = decision_data.get("citations", [])
    portfolio_impact = decision_data.get("portfolio_impact", {})
    degraded = decision_data.get("degraded_context", False)
    ttl = decision_data.get("ttl_seconds", 0)

    emoji = DECISION_EMOJI.get(decision, "📊")
    conf_bar = _get_confidence_bar(confidence)

    # Build message parts
    lines = []

    # Header
    lines.append(f"{emoji} *{_escape_md(ticker)}* — *{_escape_md(decision)}*")
    lines.append(f"Confidence: `{conf_bar}` {confidence}%")
    lines.append("")

    # Rationale
    lines.append(f"📋 *Rationale*")
    # Truncate rationale for Telegram
    rat_text = rationale[:500] + "..." if len(rationale) > 500 else rationale
    lines.append(_escape_md(rat_text))
    lines.append("")

    # Portfolio Impact
    if portfolio_impact:
        pos_delta = portfolio_impact.get("position_delta_pct", 0)
        sector_delta = portfolio_impact.get("sector_exposure_delta_pct", 0)
        cash = portfolio_impact.get("cash_impact", 0)

        lines.append("💼 *Portfolio Impact*")
        if pos_delta:
            sign = "\\+" if pos_delta > 0 else ""
            lines.append(f"  Position: {sign}{pos_delta}%")
        if sector_delta:
            sign = "\\+" if sector_delta > 0 else ""
            lines.append(f"  Sector: {sign}{sector_delta}%")
        if cash:
            lines.append(f"  Cash: {_escape_md(_format_inr(cash))}")
        lines.append("")

    # Risk Flags
    if risk_flags:
        lines.append("⚠️ *Risk Flags*")
        for flag in risk_flags:
            lines.append(f"  🔸 `{_escape_md(flag)}`")
        lines.append("")

    # Degraded warning
    if degraded:
        lines.append("🟠 _⚠️ Degraded context — some evidence sources were unavailable_")
        lines.append("")

    # Citations
    if citations:
        lines.append("📰 *Sources*")
        for cite in citations[:3]:
            title = cite.get("title", cite.get("url", ""))[:60]
            url = cite.get("url", "")
            if url:
                lines.append(f"  [🔗 {_escape_md(title)}]({url})")
            else:
                lines.append(f"  📄 {_escape_md(title)}")
        lines.append("")

    # Staged Order
    staged = alert.get("staged_order") or decision_data.get("staged_order")
    if staged and staged.get("status") == "STAGED":
        action = staged.get("action", "")
        symbol = staged.get("symbol", ticker)
        qty = staged.get("quantity", 0)
        price = staged.get("price", 0)
        est_val = staged.get("estimated_value", 0)
        lines.append("📦 *Staged Order*")
        lines.append(f"  {_escape_md(action)} {qty} × {_escape_md(symbol)} @ {_escape_md(_format_inr(price))}")
        lines.append(f"  Est\\. Value: {_escape_md(_format_inr(est_val))}")
        lines.append("")

    # TTL
    if ttl:
        ttl_mins = ttl // 60
        lines.append(f"⏱ Valid for {ttl_mins} min")

    # Footer
    ts = alert.get("created_at", datetime.now(timezone.utc).isoformat())
    lines.append(f"\n_Chōsa Agent • {_escape_md(ts[:19])}_")

    return "\n".join(lines)


def format_alert_html(alert: dict) -> str:
    """
    Format an alert payload into an HTML Telegram message (simpler, more reliable).
    """
    decision_data = alert.get("decision", {})
    ticker = alert.get("ticker", decision_data.get("ticker", "UNKNOWN"))
    decision = decision_data.get("final_decision", decision_data.get("original_decision", "WATCH"))
    confidence = decision_data.get("confidence", 0)
    rationale = decision_data.get("rationale", "No rationale provided.")
    risk_flags = decision_data.get("risk_flags", [])
    citations = decision_data.get("citations", [])
    portfolio_impact = decision_data.get("portfolio_impact", {})
    degraded = decision_data.get("degraded_context", False)
    ttl = decision_data.get("ttl_seconds", 0)

    emoji = DECISION_EMOJI.get(decision, "📊")
    conf_bar = _get_confidence_bar(confidence)

    lines = []

    # Header
    lines.append(f"{emoji} <b>{ticker}</b> — <b>{decision}</b>")
    lines.append(f"Confidence: <code>{conf_bar}</code> {confidence}%")
    lines.append("")

    # Rationale
    lines.append("📋 <b>Rationale</b>")
    rat_text = rationale[:500] + "..." if len(rationale) > 500 else rationale
    lines.append(rat_text)
    lines.append("")

    # Portfolio Impact
    if portfolio_impact:
        pos_delta = portfolio_impact.get("position_delta_pct", 0)
        sector_delta = portfolio_impact.get("sector_exposure_delta_pct", 0)
        cash = portfolio_impact.get("cash_impact", 0)

        lines.append("💼 <b>Portfolio Impact</b>")
        if pos_delta:
            sign = "+" if pos_delta > 0 else ""
            lines.append(f"  Position: {sign}{pos_delta}%")
        if sector_delta:
            sign = "+" if sector_delta > 0 else ""
            lines.append(f"  Sector: {sign}{sector_delta}%")
        if cash:
            lines.append(f"  Cash: {_format_inr(cash)}")
        lines.append("")

    # Risk Flags
    if risk_flags:
        lines.append("⚠️ <b>Risk Flags</b>")
        for flag in risk_flags:
            lines.append(f"  🔸 <code>{flag}</code>")
        lines.append("")

    # Degraded
    if degraded:
        lines.append("🟠 <i>⚠️ Degraded context — some evidence sources unavailable</i>")
        lines.append("")

    # Citations
    if citations:
        lines.append("📰 <b>Sources</b>")
        for cite in citations[:3]:
            title = cite.get("title", cite.get("url", ""))[:60]
            url = cite.get("url", "")
            if url:
                lines.append(f'  <a href="{url}">🔗 {title}</a>')
            else:
                lines.append(f"  📄 {title}")
        lines.append("")

    # Staged Order
    staged = alert.get("staged_order") or decision_data.get("staged_order")
    if staged and staged.get("status") == "STAGED":
        action = staged.get("action", "")
        symbol = staged.get("symbol", ticker)
        qty = staged.get("quantity", 0)
        price = staged.get("price", 0)
        est_val = staged.get("estimated_value", 0)
        lines.append("📦 <b>Staged Order</b>")
        lines.append(f"  {action} {qty} × {symbol} @ {_format_inr(price)}")
        lines.append(f"  Est. Value: {_format_inr(est_val)}")
        lines.append("")

    # TTL
    if ttl:
        lines.append(f"⏱ Valid for {ttl // 60} min")

    # Footer
    ts = alert.get("created_at", datetime.now(timezone.utc).isoformat())
    lines.append(f"\n<i>Chōsa Agent • {ts[:19]}</i>")

    return "\n".join(lines)


class TelegramBot:
    """Async Telegram Bot client for sending alerts."""

    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = TELEGRAM_API.format(token=token)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def send_message(
        self,
        text: str,
        parse_mode: str = "HTML",
        chat_id: Optional[str] = None,
        disable_preview: bool = True,
    ) -> dict:
        """Send a text message to the configured chat."""
        client = await self._get_client()
        target_chat = chat_id or self.chat_id

        try:
            resp = await client.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": target_chat,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": disable_preview,
                },
            )
            result = resp.json()

            if not result.get("ok"):
                logger.warning(
                    "telegram_send_failed",
                    error=result.get("description", "unknown"),
                    error_code=result.get("error_code"),
                )
                return {"ok": False, "error": result.get("description")}

            logger.info(
                "telegram_message_sent",
                chat_id=target_chat,
                message_id=result.get("result", {}).get("message_id"),
            )
            return {"ok": True, "message_id": result.get("result", {}).get("message_id")}

        except Exception as e:
            logger.error("telegram_send_error", error=str(e))
            return {"ok": False, "error": str(e)}

    async def send_alert(self, alert: dict) -> dict:
        """Format and send an alert to Telegram."""
        message = format_alert_html(alert)
        return await self.send_message(message, parse_mode="HTML")

    async def get_me(self) -> dict:
        """Test bot connectivity — returns bot info."""
        client = await self._get_client()
        try:
            resp = await client.get(f"{self.base_url}/getMe")
            return resp.json()
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def get_updates(self, offset: int = 0, limit: int = 10) -> dict:
        """Get recent updates — useful for discovering chat_id."""
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{self.base_url}/getUpdates",
                params={"offset": offset, "limit": limit},
            )
            return resp.json()
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ── Singleton ──
_bot: Optional[TelegramBot] = None


def get_telegram_bot() -> Optional[TelegramBot]:
    """Get the singleton TelegramBot instance (None if not configured)."""
    global _bot
    settings = get_settings()
    if not settings.telegram_bot_token:
        return None
    if _bot is None:
        _bot = TelegramBot(settings.telegram_bot_token, settings.telegram_chat_id)
    return _bot


async def send_telegram_alert(alert: dict) -> dict:
    """
    Convenience function — send an alert via Telegram.
    Returns {"ok": True/False, ...}
    No-op if bot is not configured.
    """
    bot = get_telegram_bot()
    if bot is None:
        return {"ok": False, "error": "Telegram bot not configured"}
    return await bot.send_alert(alert)


async def close_telegram_bot():
    """Close the bot HTTP client on shutdown."""
    global _bot
    if _bot:
        await _bot.close()
        _bot = None


async def send_startup_notification(symbols: list[str], market_status: str) -> dict:
    """
    Send a startup confirmation alert to Telegram when the agent goes RUNNING.
    """
    bot = get_telegram_bot()
    if bot is None:
        return {"ok": False, "error": "Telegram bot not configured"}

    symbol_list = ", ".join(symbols[:10]) + (f" +{len(symbols) - 10} more" if len(symbols) > 10 else "")
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

    msg = (
        "🟢 <b>Chōsa Agent — LIVE</b>\n"
        f"Market: <code>{market_status}</code>\n"
        f"Watching: <code>{symbol_list or 'Default symbols'}</code>\n"
        f"Pipeline: Upstox → Anomaly → LangGraph → Alerts\n"
        f"\n<i>Started at {ts}</i>"
    )
    return await bot.send_message(msg, parse_mode="HTML")

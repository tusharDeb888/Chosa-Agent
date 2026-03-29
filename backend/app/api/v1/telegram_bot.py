"""
Telegram Bot API — Setup, test, and manage Telegram alert delivery.

Endpoints:
- GET  /telegram/status    — Check bot configuration & connectivity
- POST /telegram/test      — Send a test alert to Telegram
- POST /telegram/setup     — Configure bot token and chat ID
- GET  /telegram/discover  — Get chat_id from recent messages
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.config import get_settings
from app.core.observability import get_logger
from app.notifications.telegram import (
    TelegramBot,
    format_alert_html,
    get_telegram_bot,
    send_telegram_alert,
)

logger = get_logger("api.telegram")
router = APIRouter(prefix="/telegram")


class TelegramSetupRequest(BaseModel):
    bot_token: str
    chat_id: str


class TelegramTestRequest(BaseModel):
    ticker: str = "RELIANCE"
    decision: str = "BUY"
    confidence: int = 82
    rationale: str = "Volume spike 3.8x above EMA confirmed by institutional order flow. Strong Q4 results support fundamental case."


@router.get("/status")
async def telegram_status():
    """Check Telegram bot configuration and connectivity."""
    settings = get_settings()

    if not settings.telegram_bot_token:
        return {
            "configured": False,
            "connected": False,
            "message": "Telegram bot not configured. Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to .env",
            "setup_instructions": {
                "step_1": "Open Telegram and search for @BotFather",
                "step_2": "Send /newbot and follow instructions to create a bot",
                "step_3": "Copy the bot token (looks like 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11)",
                "step_4": "Start a chat with your new bot and send any message",
                "step_5": "Call POST /api/v1/telegram/setup with your token to auto-discover chat_id",
                "step_6": "Or manually add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to backend/.env",
            },
        }

    bot = get_telegram_bot()
    if not bot:
        return {"configured": False, "connected": False, "message": "Bot initialization failed"}

    # Test connectivity
    me = await bot.get_me()
    if me.get("ok"):
        bot_info = me.get("result", {})
        return {
            "configured": True,
            "connected": True,
            "bot_username": bot_info.get("username"),
            "bot_name": bot_info.get("first_name"),
            "chat_id": settings.telegram_chat_id or "Not set — use /discover endpoint",
            "message": f"✅ Bot @{bot_info.get('username')} is connected and ready",
        }

    return {
        "configured": True,
        "connected": False,
        "message": f"Bot token set but connection failed: {me.get('error', 'unknown')}",
    }


@router.post("/test")
async def send_test_alert(req: TelegramTestRequest):
    """Send a test alert message to Telegram."""
    settings = get_settings()

    if not settings.telegram_bot_token:
        return {
            "ok": False,
            "error": "Telegram not configured. Set TELEGRAM_BOT_TOKEN in .env first.",
        }

    if not settings.telegram_chat_id:
        return {
            "ok": False,
            "error": "TELEGRAM_CHAT_ID not set. Use /discover endpoint or set it manually.",
        }

    # Build a mock alert
    test_alert = {
        "alert_id": f"test-{datetime.now(timezone.utc).strftime('%H%M%S')}",
        "user_id": "demo",
        "ticker": req.ticker,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": {
            "signal_id": f"test-signal-{req.ticker}",
            "user_id": "demo",
            "tenant_id": "default",
            "original_decision": req.decision,
            "final_decision": req.decision,
            "confidence": req.confidence,
            "rationale": req.rationale,
            "citations": [
                {
                    "url": "https://economictimes.com/example",
                    "published_at": datetime.now(timezone.utc).isoformat(),
                    "title": f"{req.ticker} — Market Update (Test Alert)",
                    "source_type": "news",
                }
            ],
            "portfolio_impact": {
                "position_delta_pct": 4.5 if req.decision == "BUY" else -3.2,
                "sector_exposure_delta_pct": 2.1,
                "cash_impact": -55000 if req.decision == "BUY" else 72000,
            },
            "risk_flags": ["TEST_MODE"] if req.decision != "WATCH" else [],
            "policy_reason_codes": [],
            "policy_passed": True,
            "ttl_seconds": 300,
            "degraded_context": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    result = await send_telegram_alert(test_alert)

    return {
        "ok": result.get("ok", False),
        "message_id": result.get("message_id"),
        "error": result.get("error"),
        "preview": format_alert_html(test_alert)[:500],
    }


@router.post("/setup")
async def setup_telegram(req: TelegramSetupRequest):
    """
    Validate a bot token and chat_id. 
    
    Returns setup status. You still need to add the values to .env manually.
    """
    bot = TelegramBot(req.bot_token, req.chat_id)

    # Test bot token
    me = await bot.get_me()
    if not me.get("ok"):
        await bot.close()
        return {
            "ok": False,
            "error": f"Invalid bot token: {me.get('error', 'unknown')}",
        }

    bot_info = me.get("result", {})

    # Test sending a message to verify chat_id
    test_msg = f"✅ Alpha-Hunter connected!\n\nBot: @{bot_info.get('username')}\nChat ID: {req.chat_id}\n\nYou'll receive real-time trading alerts here."
    send_result = await bot.send_message(test_msg, parse_mode="HTML", chat_id=req.chat_id)
    await bot.close()

    if not send_result.get("ok"):
        return {
            "ok": False,
            "bot_valid": True,
            "bot_username": bot_info.get("username"),
            "error": f"Chat ID invalid or bot not started: {send_result.get('error')}",
            "hint": "Make sure you've sent a message to the bot first, then try /discover endpoint",
        }

    return {
        "ok": True,
        "bot_username": bot_info.get("username"),
        "bot_name": bot_info.get("first_name"),
        "chat_id": req.chat_id,
        "message": "✅ Setup complete! Add these to your backend/.env file:",
        "env_values": {
            "TELEGRAM_BOT_TOKEN": req.bot_token,
            "TELEGRAM_CHAT_ID": req.chat_id,
        },
    }


@router.get("/discover")
async def discover_chat_id(
    token: str = Query(default="", description="Bot token (uses .env token if empty)"),
):
    """
    Discover your chat_id by reading recent messages sent to the bot.
    
    Steps:
    1. Send any message to your bot in Telegram
    2. Call this endpoint
    3. It returns the chat_id from the most recent message
    """
    settings = get_settings()
    bot_token = token or settings.telegram_bot_token

    if not bot_token:
        return {
            "ok": False,
            "error": "No bot token. Provide ?token=YOUR_BOT_TOKEN or set TELEGRAM_BOT_TOKEN in .env",
        }

    bot = TelegramBot(bot_token, "")
    updates = await bot.get_updates()
    await bot.close()

    if not updates.get("ok"):
        return {"ok": False, "error": updates.get("error", "Failed to get updates")}

    results = updates.get("result", [])
    if not results:
        return {
            "ok": False,
            "error": "No messages found. Send a message to your bot first, then retry.",
        }

    # Extract unique chat IDs
    chats = {}
    for update in results:
        msg = update.get("message", {})
        chat = msg.get("chat", {})
        chat_id = str(chat.get("id", ""))
        if chat_id and chat_id not in chats:
            chats[chat_id] = {
                "chat_id": chat_id,
                "type": chat.get("type"),
                "first_name": chat.get("first_name", ""),
                "username": chat.get("username", ""),
                "last_message": msg.get("text", "")[:50],
            }

    return {
        "ok": True,
        "chats": list(chats.values()),
        "recommended_chat_id": list(chats.keys())[0] if chats else None,
        "next_step": "Add the chat_id to TELEGRAM_CHAT_ID in backend/.env, then restart the server.",
    }

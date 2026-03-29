"""
Chat Router — AI Assistant endpoint.

POST /api/v1/chat  → Process a user chat message with tool-calling LLM.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.observability import get_logger

logger = get_logger("api.chat")
router = APIRouter(prefix="/chat")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[dict] = Field(default_factory=list)
    portfolio: list[dict] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    tools_used: list[str] = Field(default_factory=list)


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Process a chat message with the AI financial assistant."""
    if not req.message.strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty")

    try:
        from app.services.chat_service import process_chat

        reply = await process_chat(
            message=req.message,
            history=req.history,
            portfolio=req.portfolio,
        )

        return ChatResponse(reply=reply)

    except Exception as e:
        logger.error("chat_endpoint_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.get("/health")
async def chat_health():
    from app.config import get_settings
    settings = get_settings()
    return {
        "enabled": bool(settings.groq_api_key),
        "model": settings.groq_model,
        "status": "ok" if settings.groq_api_key else "no_api_key",
    }

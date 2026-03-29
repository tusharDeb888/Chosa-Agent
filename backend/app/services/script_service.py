"""
Script Service — LLM-powered video script generation.

Uses Groq (same LLM as decision engine) to convert market data
into a structured broadcast script with narration and visual cues.
"""

from __future__ import annotations

import json
from typing import Optional

from app.config import get_settings
from app.core.observability import get_logger
from app.schemas.video import VideoScript, ScriptScene, VideoTheme

logger = get_logger("services.script")


SCRIPT_SYSTEM_PROMPT = """You are a professional financial news anchor writing a market broadcast script.

You MUST respond with valid JSON matching this exact schema:
{
  "title": "string — catchy headline",
  "ticker": "string — primary ticker",
  "opening_line": "string — attention-grabbing 1-sentence opening",
  "scenes": [
    {
      "scene_id": 1,
      "narration": "string — what the anchor says (10-20 words)",
      "visual_cue": "string — one of: price_chart, volume_bar, comparison, trend_arrow, metric_card",
      "duration_sec": 8.0
    }
  ],
  "closing_line": "string — wrap-up sentence with clear takeaway"
}

Rules:
1. Write 3-5 scenes. Each scene narration should be 10-20 words.
2. Total narration should fill 30-60 seconds when read aloud (~150 words/min)
3. Use plain English — no jargon. A retail investor must understand.
4. Visual cues MUST be one of: price_chart, volume_bar, comparison, trend_arrow, metric_card
5. Be factual and balanced — never give specific advice.
6. Opening should hook the viewer. Closing should summarize the key takeaway.
"""


async def generate_script(
    ticker: str,
    theme: VideoTheme,
    duration_sec: int = 45,
    additional_tickers: list[str] | None = None,
    market_data: dict | None = None,
) -> VideoScript:
    """
    Generate a structured video broadcast script using Groq LLM.

    Args:
        ticker: Primary stock ticker
        theme: Video theme (market_wrap, earnings, etc.)
        duration_sec: Target video duration
        additional_tickers: Extra tickers to mention
        market_data: Optional raw market data for context

    Returns:
        VideoScript with structured scenes and narration
    """
    settings = get_settings()

    # Build user prompt with context
    user_prompt = _build_prompt(ticker, theme, duration_sec, additional_tickers, market_data)

    if not settings.groq_api_key:
        logger.warning("llm_not_configured_script_fallback")
        return _fallback_script(ticker, theme, duration_sec)

    try:
        from groq import AsyncGroq

        client = AsyncGroq(api_key=settings.groq_api_key)

        response = await client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": SCRIPT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=800,
            temperature=0.4,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content.strip()
        data = json.loads(content)

        scenes = [
            ScriptScene(
                scene_id=s.get("scene_id", i + 1),
                narration=s.get("narration", ""),
                visual_cue=s.get("visual_cue", "price_chart"),
                duration_sec=float(s.get("duration_sec", 8)),
            )
            for i, s in enumerate(data.get("scenes", []))
        ]

        script = VideoScript(
            title=data.get("title", f"{ticker} Market Update"),
            ticker=ticker,
            opening_line=data.get("opening_line", f"Here's what's happening with {ticker} today."),
            scenes=scenes,
            closing_line=data.get("closing_line", "That's your market update. Stay informed."),
        )

        # Build total narration
        all_text = [script.opening_line]
        all_text.extend(s.narration for s in script.scenes)
        all_text.append(script.closing_line)
        script.total_narration = " ".join(all_text)

        logger.info("script_generated", ticker=ticker, scenes=len(scenes))
        return script

    except Exception as e:
        logger.error("script_generation_failed", ticker=ticker, error=str(e))
        return _fallback_script(ticker, theme, duration_sec)


def _build_prompt(
    ticker: str,
    theme: VideoTheme,
    duration_sec: int,
    additional_tickers: list[str] | None = None,
    market_data: dict | None = None,
) -> str:
    """Build LLM prompt with market context."""
    extras = ", ".join(additional_tickers) if additional_tickers else "none"

    theme_guidance = {
        VideoTheme.MARKET_WRAP: "Give a comprehensive market wrap covering the stock's day in the broader market context.",
        VideoTheme.EARNINGS: "Focus on recent or upcoming earnings, financial results, and what they mean for investors.",
        VideoTheme.SECTOR_ROTATION: "Analyze sector rotation trends and how this stock fits into the broader sector movement.",
        VideoTheme.STOCK_FOCUS: "Deep dive into this specific stock — price action, key levels, and recent catalysts.",
    }

    data_section = ""
    if market_data:
        data_section = f"\nMarket Data Available:\n{json.dumps(market_data, indent=2, default=str)[:1000]}\n"

    return f"""Generate a market broadcast script for:

Primary Ticker: {ticker}
Also Mention: {extras}
Theme: {theme.value} — {theme_guidance.get(theme, 'General market update')}
Target Duration: {duration_sec} seconds (~{int(duration_sec * 150 / 60)} words total narration)
{data_section}
Create an engaging, informative script. Use the structured JSON format."""


def _fallback_script(ticker: str, theme: VideoTheme, duration_sec: int) -> VideoScript:
    """Template fallback when LLM is unavailable."""
    scenes = [
        ScriptScene(
            scene_id=1,
            narration=f"Let's look at {ticker}'s recent price action on the daily chart.",
            visual_cue="price_chart",
            duration_sec=8.0,
        ),
        ScriptScene(
            scene_id=2,
            narration=f"Trading volume has been active, showing strong market participation.",
            visual_cue="volume_bar",
            duration_sec=7.0,
        ),
        ScriptScene(
            scene_id=3,
            narration=f"Key technical levels suggest monitoring support and resistance zones.",
            visual_cue="trend_arrow",
            duration_sec=7.0,
        ),
        ScriptScene(
            scene_id=4,
            narration=f"Here are the key metrics that investors should be watching for {ticker}.",
            visual_cue="metric_card",
            duration_sec=8.0,
        ),
    ]

    opening = f"Welcome to your market update. Today we're focusing on {ticker}."
    closing = f"That's your {ticker} update. Remember to do your own research before making any decisions."

    all_text = [opening] + [s.narration for s in scenes] + [closing]

    return VideoScript(
        title=f"{ticker} — Market Intelligence Update",
        ticker=ticker,
        opening_line=opening,
        scenes=scenes,
        closing_line=closing,
        total_narration=" ".join(all_text),
    )

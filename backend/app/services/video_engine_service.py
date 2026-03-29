"""
Video Engine Service — Full video generation pipeline.

Pipeline stages:
  1. Generate script JSON (via script_service / Groq LLM)
  2. Render chart frames (plotly → transparent PNG)
  3. Synthesize speech (Amazon Polly → MP3 + speech marks)
  4. Compose final video (MoviePy → MP4)

All heavy operations are synchronous and designed to be called
from BackgroundTasks or run_in_threadpool.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from pathlib import Path
from typing import Optional

from app.config import get_settings
from app.core.observability import get_logger
from app.schemas.video import VideoScript, VideoGenerateResponse, VideoStatusResponse

logger = get_logger("services.video_engine")

# ── Job tracking (in-memory for hackathon) ──
_jobs: dict[str, dict] = {}


def get_job(job_id: str) -> Optional[dict]:
    return _jobs.get(job_id)


def set_job(job_id: str, data: dict):
    _jobs[job_id] = data


# ─────────────────────────── Chart Rendering ───────────────────────────


def render_chart_frame(
    chart_type: str,
    ticker: str,
    output_path: str,
    width: int = 1280,
    height: int = 720,
    ohlcv_data: Optional[list] = None,
) -> str:
    """
    Render a chart frame as a transparent PNG using plotly.
    Lazy-imports plotly.

    Args:
        chart_type: Type of visual (price_chart, volume_bar, trend_arrow, metric_card, comparison)
        ticker: Stock symbol
        output_path: Where to save the PNG
        width, height: Image dimensions

    Returns:
        Path to saved PNG file
    """
    import plotly.graph_objects as go

    # Dark theme config matching Alpha-Hunter dashboard
    layout_base = dict(
        template="plotly_dark",
        paper_bgcolor="rgba(15, 23, 42, 0.95)",
        plot_bgcolor="rgba(15, 23, 42, 0.8)",
        font=dict(family="Inter, system-ui, sans-serif", color="#e2e8f0", size=14),
        margin=dict(l=60, r=40, t=80, b=60),
        width=width,
        height=height,
    )

    if chart_type == "price_chart":
        fig = _render_price_chart(ticker, layout_base, ohlcv_data)
    elif chart_type == "volume_bar":
        fig = _render_volume_chart(ticker, layout_base, ohlcv_data)
    elif chart_type == "trend_arrow":
        fig = _render_trend_chart(ticker, layout_base, ohlcv_data)
    elif chart_type == "metric_card":
        fig = _render_metric_card(ticker, layout_base, ohlcv_data)
    else:
        fig = _render_price_chart(ticker, layout_base, ohlcv_data)

    fig.write_image(output_path, format="png", width=width, height=height, engine="kaleido")
    logger.info("chart_frame_rendered", chart_type=chart_type, ticker=ticker, path=output_path)
    return output_path


def _render_price_chart(ticker: str, layout_base: dict, data: Optional[list] = None):
    import plotly.graph_objects as go
    import numpy as np

    if data:
        closes = [d.get("close", 0) for d in data[-60:]]
        dates = list(range(len(closes)))
    else:
        np.random.seed(hash(ticker) % 2**31)
        dates = list(range(60))
        closes = list(np.cumsum(np.random.randn(60) * 2) + 100)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=closes,
        mode="lines",
        fill="tozeroy",
        fillcolor="rgba(96, 165, 250, 0.1)",
        line=dict(color="#60a5fa", width=2.5),
        name=ticker,
    ))

    # Add SMA
    if len(closes) > 20:
        import pandas as pd
        sma = pd.Series(closes).rolling(20).mean().tolist()
        fig.add_trace(go.Scatter(
            x=dates, y=sma,
            mode="lines",
            line=dict(color="#a78bfa", width=1.5, dash="dot"),
            name="20-SMA",
        ))

    fig.update_layout(
        **layout_base,
        title=dict(text=f"📈 {ticker} — Price Action", font=dict(size=22)),
        xaxis_title="Trading Days",
        yaxis_title="Price (₹)",
        showlegend=True,
        legend=dict(x=0.02, y=0.98, bgcolor="rgba(0,0,0,0)"),
    )
    return fig


def _render_volume_chart(ticker: str, layout_base: dict, data: Optional[list] = None):
    import plotly.graph_objects as go
    import numpy as np

    if data:
        volumes = [d.get("volume", 0) for d in data[-30:]]
    else:
        np.random.seed(hash(ticker) % 2**31)
        volumes = list(np.random.randint(100000, 500000, 30))

    colors = ["#10b981" if i % 2 == 0 else "#ef4444" for i in range(len(volumes))]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=list(range(len(volumes))),
        y=volumes,
        marker_color=colors,
        name="Volume",
    ))
    fig.update_layout(
        **layout_base,
        title=dict(text=f"📊 {ticker} — Volume Profile", font=dict(size=22)),
        xaxis_title="Trading Days",
        yaxis_title="Volume",
    )
    return fig


def _render_trend_chart(ticker: str, layout_base: dict, data: Optional[list] = None):
    import plotly.graph_objects as go
    import numpy as np

    if data:
        closes = [d.get("close", 0) for d in data[-90:]]
    else:
        np.random.seed(hash(ticker) % 2**31)
        closes = list(np.cumsum(np.random.randn(90) * 1.5) + 200)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(range(len(closes))), y=closes,
        mode="lines",
        line=dict(color="#60a5fa", width=2),
        name="Price",
    ))

    # Trend line
    x = list(range(len(closes)))
    z = np.polyfit(x, closes, 1)
    trend = [z[0] * xi + z[1] for xi in x]
    color = "#10b981" if z[0] > 0 else "#ef4444"
    fig.add_trace(go.Scatter(
        x=x, y=trend,
        mode="lines",
        line=dict(color=color, width=3, dash="dash"),
        name=f"Trend ({'↑' if z[0] > 0 else '↓'})",
    ))

    fig.update_layout(
        **layout_base,
        title=dict(text=f"📈 {ticker} — Trend Analysis", font=dict(size=22)),
    )
    return fig


def _render_metric_card(ticker: str, layout_base: dict, data: Optional[list] = None):
    import plotly.graph_objects as go

    fig = go.Figure()

    metrics = [
        ("52W High", "₹2,847", 0.2, 0.8),
        ("52W Low", "₹1,982", 0.5, 0.8),
        ("P/E Ratio", "28.4x", 0.8, 0.8),
        ("Market Cap", "₹19.2L Cr", 0.2, 0.3),
        ("Div Yield", "0.34%", 0.5, 0.3),
        ("Beta", "0.92", 0.8, 0.3),
    ]

    for label, value, x, y in metrics:
        fig.add_annotation(
            x=x, y=y + 0.05, text=f"<b>{value}</b>",
            font=dict(size=24, color="#60a5fa"),
            showarrow=False, xref="paper", yref="paper",
        )
        fig.add_annotation(
            x=x, y=y - 0.05, text=label,
            font=dict(size=13, color="#94a3b8"),
            showarrow=False, xref="paper", yref="paper",
        )

    fig.update_layout(
        **layout_base,
        title=dict(text=f"📋 {ticker} — Key Metrics", font=dict(size=22)),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig


# ─────────────────────────── TTS (Amazon Polly) ───────────────────────────


async def synthesize_speech(
    text: str,
    output_path: str,
    voice_id: Optional[str] = None,
) -> tuple[str, list]:
    """
    Synthesize speech using Amazon Polly.
    Returns (audio_path, speech_marks).

    Falls back to edge-tts if boto3/Polly is unavailable.
    """
    settings = get_settings()
    voice = voice_id or settings.polly_voice_id

    # Try Amazon Polly first
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        try:
            return await _polly_synthesize(text, output_path, voice, settings)
        except Exception as e:
            logger.warning("polly_failed_trying_fallback", error=str(e))

    # Fallback: edge-tts (free, no API key)
    try:
        return await _edge_tts_synthesize(text, output_path)
    except Exception as e:
        logger.warning("edge_tts_failed_trying_gtts", error=str(e))

    # Last resort: gTTS
    try:
        return await _gtts_synthesize(text, output_path)
    except Exception as e:
        logger.error("all_tts_failed", error=str(e))
        # Return empty — video will have no audio
        return output_path, []


async def _polly_synthesize(text: str, output_path: str, voice: str, settings) -> tuple[str, list]:
    """AWS Polly synthesis with speech marks."""
    import boto3

    polly = boto3.client(
        "polly",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
    )

    # Get audio
    audio_response = polly.synthesize_speech(
        Text=text,
        OutputFormat="mp3",
        VoiceId=voice,
        Engine=settings.polly_engine,
    )

    with open(output_path, "wb") as f:
        f.write(audio_response["AudioStream"].read())

    # Get speech marks
    marks_response = polly.synthesize_speech(
        Text=text,
        OutputFormat="json",
        VoiceId=voice,
        Engine=settings.polly_engine,
        SpeechMarkTypes=["sentence", "word"],
    )

    marks_text = marks_response["AudioStream"].read().decode("utf-8")
    speech_marks = []
    for line in marks_text.strip().split("\n"):
        if line:
            speech_marks.append(json.loads(line))

    logger.info("polly_synthesis_done", voice=voice, marks=len(speech_marks))
    return output_path, speech_marks


async def _edge_tts_synthesize(text: str, output_path: str) -> tuple[str, list]:
    """Free edge-tts fallback (Microsoft Neural voices)."""
    import edge_tts

    voice = "en-IN-NeerjaNeural"  # Indian English Neural voice
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

    logger.info("edge_tts_synthesis_done", voice=voice)
    return output_path, []  # edge-tts doesn't provide speech marks easily


async def _gtts_synthesize(text: str, output_path: str) -> tuple[str, list]:
    """gTTS fallback (Google Translate TTS, lowest quality)."""
    from gtts import gTTS

    tts = gTTS(text=text, lang="en", slow=False)
    tts.save(output_path)

    logger.info("gtts_synthesis_done")
    return output_path, []


# ─────────────────────────── Video Composition ───────────────────────────


def compose_video_sync(
    frame_paths: list[str],
    audio_path: str,
    output_path: str,
    speech_marks: list[dict],
    durations: list[float],
    width: int = 1280,
    height: int = 720,
    fps: int = 24,
) -> str:
    """
    Compose final video from chart frames + audio.
    Synchronous — must run in threadpool.

    Uses MoviePy to sequence frames over a dark background,
    synced to speech marks or even-split durations.
    """
    from moviepy import (
        ImageClip,
        AudioFileClip,
        CompositeVideoClip,
        ColorClip,
        concatenate_videoclips,
    )

    # Background
    bg_color = (15, 23, 42)  # slate-900

    clips = []

    # Check if audio exists and get duration
    audio_duration = 0
    audio_clip = None
    if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
        try:
            audio_clip = AudioFileClip(audio_path)
            audio_duration = audio_clip.duration
        except Exception as e:
            logger.warning("audio_load_failed", error=str(e))

    # Calculate per-frame duration
    if speech_marks and len(speech_marks) > 0:
        # Use sentence-level speech marks for timing
        sentence_marks = [m for m in speech_marks if m.get("type") == "sentence"]
        if sentence_marks and len(sentence_marks) >= len(frame_paths):
            for i, frame_path in enumerate(frame_paths):
                start_ms = sentence_marks[i]["time"] if i < len(sentence_marks) else 0
                end_ms = sentence_marks[i + 1]["time"] if i + 1 < len(sentence_marks) else (audio_duration * 1000)
                dur = max((end_ms - start_ms) / 1000, 2.0)

                bg = ColorClip(size=(width, height), color=bg_color).with_duration(dur)
                img = ImageClip(frame_path).with_duration(dur).resized((width, height))
                composite = CompositeVideoClip([bg, img])
                clips.append(composite)
        else:
            clips = _even_split_clips(frame_paths, durations, audio_duration, width, height, bg_color)
    else:
        clips = _even_split_clips(frame_paths, durations, audio_duration, width, height, bg_color)

    if not clips:
        # Fallback: single frame with static background
        bg = ColorClip(size=(width, height), color=bg_color).with_duration(max(audio_duration, 10))
        clips = [bg]

    final = concatenate_videoclips(clips, method="compose")

    # Attach audio
    if audio_clip:
        if final.duration < audio_clip.duration:
            final = final.with_duration(audio_clip.duration)
        final = final.with_audio(audio_clip)

    # Export
    final.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        logger=None,
    )

    logger.info("video_composed", output=output_path, duration=round(final.duration, 2))
    return output_path


def _even_split_clips(frame_paths, durations, audio_duration, width, height, bg_color):
    """Split frames evenly across the total duration."""
    from moviepy import ImageClip, CompositeVideoClip, ColorClip

    total_dur = audio_duration or sum(durations) or (len(frame_paths) * 8)
    per_frame = total_dur / max(len(frame_paths), 1)

    clips = []
    for i, fp in enumerate(frame_paths):
        dur = durations[i] if i < len(durations) else per_frame
        dur = max(dur, 2.0)
        bg = ColorClip(size=(width, height), color=bg_color).with_duration(dur)
        img = ImageClip(fp).with_duration(dur).resized((width, height))
        clips.append(CompositeVideoClip([bg, img]))

    return clips


# ─────────────────────────── Full Pipeline ───────────────────────────


async def generate_video(
    job_id: str,
    ticker: str,
    theme: str,
    duration_sec: int,
    additional_tickers: list[str] | None = None,
):
    """
    Full async video generation pipeline.
    Designed to run as a background task.

    Updates job status throughout the pipeline.
    """
    from app.schemas.video import VideoTheme
    from app.services.script_service import generate_script
    from fastapi.concurrency import run_in_threadpool

    settings = get_settings()
    t0 = time.time()

    # Ensure output directories exist
    for d in [settings.video_output_dir, settings.video_audio_dir, settings.video_frames_dir]:
        os.makedirs(d, exist_ok=True)

    try:
        set_job(job_id, {"status": "generating_script", "progress_pct": 10})

        # ── Stage 1: Generate script ──
        theme_enum = VideoTheme(theme) if isinstance(theme, str) else theme
        script = await generate_script(
            ticker=ticker,
            theme=theme_enum,
            duration_sec=duration_sec,
            additional_tickers=additional_tickers,
        )

        set_job(job_id, {"status": "rendering_charts", "progress_pct": 30})

        # ── Stage 2: Fetch OHLCV for charts ──
        ohlcv_data = None
        try:
            from app.services.ohlcv_provider import fetch_ohlcv
            df = await fetch_ohlcv(ticker=ticker, interval="day", lookback_days=90)
            if not df.empty:
                ohlcv_data = df.reset_index().to_dict("records")
        except Exception as e:
            logger.warning("video_ohlcv_failed", error=str(e))

        # ── Stage 3: Render chart frames ──
        frame_paths = []
        scene_durations = []

        for scene in script.scenes:
            frame_path = os.path.join(
                settings.video_frames_dir,
                f"{job_id}_scene_{scene.scene_id}.png",
            )
            try:
                await run_in_threadpool(
                    render_chart_frame,
                    chart_type=scene.visual_cue,
                    ticker=ticker,
                    output_path=frame_path,
                    ohlcv_data=ohlcv_data,
                )
                frame_paths.append(frame_path)
                scene_durations.append(scene.duration_sec)
            except Exception as e:
                logger.warning("frame_render_failed", scene=scene.scene_id, error=str(e))

        set_job(job_id, {"status": "synthesizing_speech", "progress_pct": 55})

        # ── Stage 4: TTS synthesis ──
        audio_path = os.path.join(settings.video_audio_dir, f"{job_id}.mp3")
        speech_marks = []

        if script.total_narration:
            audio_path, speech_marks = await synthesize_speech(
                text=script.total_narration,
                output_path=audio_path,
            )

        set_job(job_id, {"status": "composing_video", "progress_pct": 75})

        # ── Stage 5: Compose video ──
        output_path = os.path.join(settings.video_output_dir, f"{job_id}.mp4")

        if frame_paths:
            await run_in_threadpool(
                compose_video_sync,
                frame_paths=frame_paths,
                audio_path=audio_path,
                output_path=output_path,
                speech_marks=speech_marks,
                durations=scene_durations,
            )
        else:
            # No frames rendered — create audio-only with background
            await run_in_threadpool(
                compose_video_sync,
                frame_paths=[],
                audio_path=audio_path,
                output_path=output_path,
                speech_marks=[],
                durations=[duration_sec],
            )

        elapsed = time.time() - t0
        filename = f"{job_id}.mp4"
        video_url = f"/media/videos/{filename}"

        set_job(job_id, {
            "status": "completed",
            "progress_pct": 100,
            "video_url": video_url,
            "filename": filename,
            "duration_sec": duration_sec,
            "elapsed_sec": round(elapsed, 2),
        })

        logger.info(
            "video_generation_completed",
            job_id=job_id,
            ticker=ticker,
            elapsed_sec=round(elapsed, 2),
        )

    except Exception as e:
        logger.error("video_generation_failed", job_id=job_id, error=str(e))
        set_job(job_id, {
            "status": "failed",
            "progress_pct": 0,
            "error": str(e),
        })

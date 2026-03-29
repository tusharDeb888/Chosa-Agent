"""
Portfolio Video Service — Fast 30-50s narrated video reports.

Pipeline (optimized for speed):
  1. Report data → 3-4 short scenes (brief narration)
  2. Pillow frames at 854×480 (faster render)
  3. TTS via edge-tts (fast, no API latency) → Polly fallback
  4. MoviePy compose with ultrafast preset → MP4
"""

from __future__ import annotations

import asyncio
import os
import time
import traceback
from typing import Optional

from app.config import get_settings
from app.core.observability import get_logger

logger = get_logger("services.portfolio_video")

# ── Job tracking ──
_video_jobs: dict[str, dict] = {}

def get_video_job(job_id: str) -> Optional[dict]:
    return _video_jobs.get(job_id)

def set_video_job(job_id: str, data: dict):
    _video_jobs[job_id] = data

# ── Constants ──
W, H = 854, 480  # 480p for speed
BG = (15, 23, 42)
MAX_VIDEO_DURATION = 45  # Target 30-50s


# ═══════════════════════════════════════════════════════════
#  Frame Rendering — Pillow 854×480
# ═══════════════════════════════════════════════════════════

def _get_font(size: int):
    from PIL import ImageFont
    for path in [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _render_frame(texts: list[dict], output_path: str) -> str:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    for item in texts:
        font = _get_font(item.get("size", 20))
        color = tuple(item.get("color", [226, 232, 240]))
        draw.text((item.get("x", 30), item.get("y", 30)), str(item.get("text", "")), fill=color, font=font)
    img.save(output_path, "PNG", optimize=False)
    return output_path


# ═══════════════════════════════════════════════════════════
#  Scene Builders — COMPACT (3-4 scenes, short narration)
# ═══════════════════════════════════════════════════════════

def _fmt(v: float) -> str:
    if v >= 1e7: return f"₹{v/1e7:.1f}Cr"
    if v >= 1e5: return f"₹{v/1e5:.1f}L"
    if v >= 1e3: return f"₹{v/1e3:.0f}K"
    return f"₹{v:,.0f}"


def _build_health_scenes(r: dict) -> list[dict]:
    pnl = r.get("total_pnl_pct", 0)
    val = r.get("total_current_value", 0)
    cnt = r.get("holdings_count", 0)
    div = r.get("diversification_score", 0)
    best = r.get("best_performer", "N/A")
    worst = r.get("worst_performer", "N/A")
    best_p = r.get("best_performer_pnl_pct", 0)
    worst_p = r.get("worst_performer_pnl_pct", 0)
    mc = r.get("max_concentration_symbol", "")
    mc_pct = r.get("max_concentration_pct", 0)
    c = (16,185,129) if pnl >= 0 else (239,68,68)

    return [
        {
            "narration": f"Your portfolio has {cnt} stocks worth {_fmt(val)} with an overall return of {pnl:+.1f} percent.",
            "texts": [
                {"text": "Portfolio Health", "x": 30, "y": 20, "size": 30, "color": [139,92,246]},
                {"text": f"Value: {_fmt(val)}", "x": 40, "y": 90, "size": 38, "color": list(c)},
                {"text": f"P&L: {pnl:+.1f}%", "x": 40, "y": 150, "size": 32, "color": list(c)},
                {"text": f"Holdings: {cnt}", "x": 40, "y": 220, "size": 22, "color": [148,163,184]},
            ],
            "duration": 8,
        },
        {
            "narration": f"Diversification score is {div:.0f} out of 100. {mc} makes up {mc_pct:.0f} percent.",
            "texts": [
                {"text": "Risk Assessment", "x": 30, "y": 20, "size": 30, "color": [251,191,36]},
                {"text": f"Diversification: {div:.0f}/100", "x": 40, "y": 100, "size": 36, "color": [16,185,129] if div > 50 else [239,68,68]},
                {"text": f"Top: {mc} ({mc_pct:.0f}%)", "x": 40, "y": 170, "size": 24, "color": [251,191,36]},
            ],
            "duration": 7,
        },
        {
            "narration": f"Best performer is {best} at {best_p:+.1f} percent. Worst is {worst} at {worst_p:+.1f} percent.",
            "texts": [
                {"text": "Performance", "x": 30, "y": 20, "size": 30, "color": [139,92,246]},
                {"text": f"Best: {best} {best_p:+.1f}%", "x": 40, "y": 110, "size": 30, "color": [16,185,129]},
                {"text": f"Worst: {worst} {worst_p:+.1f}%", "x": 40, "y": 200, "size": 30, "color": [239,68,68]},
            ],
            "duration": 7,
        },
    ]


def _build_market_scenes(r: dict) -> list[dict]:
    sb = r.get("strong_buy_count", 0)
    b = r.get("buy_count", 0)
    n = r.get("neutral_count", 0)
    s = r.get("sell_count", 0)
    ss = r.get("strong_sell_count", 0)
    rsi = r.get("avg_rsi", 50)
    bull = r.get("bullish_pct", 0)

    scenes = [
        {
            "narration": f"Market analysis shows {sb} strong buy, {b} buy, {n} neutral, {s} sell, and {ss} strong sell signals. Average RSI is {rsi:.0f}.",
            "texts": [
                {"text": "Market Signals", "x": 30, "y": 20, "size": 30, "color": [96,165,250]},
                {"text": f"Buy: {sb+b}  Neutral: {n}  Sell: {s+ss}", "x": 40, "y": 100, "size": 26, "color": [226,232,240]},
                {"text": f"RSI: {rsi:.0f}", "x": 40, "y": 170, "size": 34, "color": [226,232,240]},
                {"text": f"Bullish: {bull:.0f}%", "x": 40, "y": 240, "size": 24, "color": [16,185,129]},
            ],
            "duration": 8,
        },
    ]

    # Per-stock (top 2)
    holdings = r.get("holdings", [])
    for h in holdings[:2]:
        sym = h.get("symbol", "?")
        sig = h.get("signal_strength", "neutral").replace("_", " ").title()
        rsi_h = h.get("rsi", 50)
        chg = h.get("day_change_pct", 0)
        sc = [16,185,129] if "buy" in sig.lower() else [239,68,68] if "sell" in sig.lower() else [148,163,184]
        scenes.append({
            "narration": f"{sym}: {sig} signal, RSI {rsi_h:.0f}, day change {chg:+.1f} percent.",
            "texts": [
                {"text": sym, "x": 30, "y": 20, "size": 36, "color": [226,232,240]},
                {"text": f"Signal: {sig}", "x": 40, "y": 110, "size": 28, "color": sc},
                {"text": f"RSI: {rsi_h:.0f}  |  Day: {chg:+.1f}%", "x": 40, "y": 180, "size": 22, "color": [148,163,184]},
            ],
            "duration": 6,
        })

    return scenes


def _build_historical_scenes(r: dict) -> list[dict]:
    ytd = r.get("portfolio_ytd_return_pct", 0)
    yr = r.get("portfolio_1y_return_pct", 0)
    vol = r.get("avg_portfolio_volatility", 0)
    regime = r.get("vol_regime", "normal")
    month = r.get("current_month", "")
    wr = r.get("current_month_win_rate", 0)
    outlook = r.get("current_month_outlook", "neutral")
    win = r.get("portfolio_avg_win_rate", 0)
    dd = r.get("portfolio_avg_drawdown", 0)

    return [
        {
            "narration": f"Year to date return is {ytd:+.1f} percent. One year return is {yr:+.1f} percent. Volatility is {vol:.1f} percent in {regime} regime.",
            "texts": [
                {"text": "Historical Performance", "x": 30, "y": 20, "size": 28, "color": [251,191,36]},
                {"text": f"YTD: {ytd:+.1f}%", "x": 40, "y": 100, "size": 36, "color": [16,185,129] if ytd >= 0 else [239,68,68]},
                {"text": f"1Y: {yr:+.1f}%", "x": 40, "y": 170, "size": 30, "color": [16,185,129] if yr >= 0 else [239,68,68]},
                {"text": f"Vol: {vol:.1f}% ({regime.upper()})", "x": 40, "y": 240, "size": 22, "color": [148,163,184]},
            ],
            "duration": 8,
        },
        {
            "narration": f"For {month}, the historical win rate is {wr:.0f} percent with a {outlook} outlook.",
            "texts": [
                {"text": f"{month} Seasonality", "x": 30, "y": 20, "size": 28, "color": [251,191,36]},
                {"text": f"Win Rate: {wr:.0f}%", "x": 40, "y": 120, "size": 36, "color": [226,232,240]},
                {"text": f"Outlook: {outlook.upper()}", "x": 40, "y": 200, "size": 28, "color": [16,185,129] if outlook=="favorable" else [239,68,68] if outlook=="unfavorable" else [148,163,184]},
            ],
            "duration": 7,
        },
        {
            "narration": f"Backtest shows {win:.0f} percent win rate with max drawdown of {dd:.1f} percent.",
            "texts": [
                {"text": "Backtest Results", "x": 30, "y": 20, "size": 28, "color": [139,92,246]},
                {"text": f"Win Rate: {win:.0f}%", "x": 40, "y": 120, "size": 36, "color": [16,185,129] if win > 50 else [251,191,36]},
                {"text": f"Max Drawdown: {dd:.1f}%", "x": 40, "y": 200, "size": 28, "color": [239,68,68]},
            ],
            "duration": 7,
        },
    ]


# ═══════════════════════════════════════════════════════════
#  TTS — edge-tts first (fastest free option), Polly fallback
# ═══════════════════════════════════════════════════════════

async def _synthesize_tts(text: str, output_path: str) -> str:
    settings = get_settings()

    # edge-tts first — fastest
    try:
        import edge_tts
        comm = edge_tts.Communicate(text, "en-IN-NeerjaNeural", rate="+15%")
        await comm.save(output_path)
        logger.info("tts_done_edgetts")
        return output_path
    except Exception as e:
        logger.warning("edge_tts_failed", error=str(e))

    # Polly fallback
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        try:
            import boto3
            polly = boto3.client(
                "polly",
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_region,
            )
            resp = polly.synthesize_speech(
                Text=text, OutputFormat="mp3",
                VoiceId=settings.polly_voice_id, Engine=settings.polly_engine,
            )
            with open(output_path, "wb") as f:
                f.write(resp["AudioStream"].read())
            logger.info("tts_done_polly")
            return output_path
        except Exception as e:
            logger.warning("polly_failed", error=str(e))

    # gTTS last resort
    try:
        from gtts import gTTS
        gTTS(text=text, lang="en", slow=False).save(output_path)
        logger.info("tts_done_gtts")
        return output_path
    except Exception as e:
        logger.error("all_tts_failed", error=str(e))
        return output_path


# ═══════════════════════════════════════════════════════════
#  Video Composition — ultrafast preset
# ═══════════════════════════════════════════════════════════

def _compose(frame_paths: list[str], audio_path: str, output_path: str, durations: list[float]) -> str:
    from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

    # Load audio
    audio_clip = None
    audio_dur = 0
    if os.path.exists(audio_path) and os.path.getsize(audio_path) > 100:
        try:
            audio_clip = AudioFileClip(audio_path)
            audio_dur = audio_clip.duration
        except Exception:
            pass

    # Scale durations to fit audio (max 50s)
    total_spec = sum(durations) or 1
    target = min(audio_dur, MAX_VIDEO_DURATION) if audio_dur > 0 else min(total_spec, MAX_VIDEO_DURATION)
    scale = target / total_spec
    durations = [max(d * scale, 2.0) for d in durations]

    clips = []
    for i, fp in enumerate(frame_paths):
        dur = durations[i] if i < len(durations) else 4.0
        clip = ImageClip(fp).with_duration(dur).resized((W, H))
        clips.append(clip)

    if not clips:
        return output_path

    final = concatenate_videoclips(clips, method="compose")

    if audio_clip:
        if final.duration < audio_clip.duration:
            final = final.with_duration(min(audio_clip.duration, MAX_VIDEO_DURATION))
        elif audio_clip.duration < final.duration:
            audio_clip = audio_clip.with_duration(final.duration)
        final = final.with_audio(audio_clip)

    # ultrafast preset for speed
    final.write_videofile(
        output_path,
        fps=12,  # Lower fps = much faster encode
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast",
        logger=None,
        threads=4,
    )
    return output_path


# ═══════════════════════════════════════════════════════════
#  Main Pipeline
# ═══════════════════════════════════════════════════════════

async def generate_portfolio_video(job_id: str, category: str, report_data: dict):
    settings = get_settings()
    t0 = time.time()

    for d in [settings.video_output_dir, settings.video_audio_dir, settings.video_frames_dir]:
        os.makedirs(d, exist_ok=True)

    try:
        # Stage 1: Build scenes
        set_video_job(job_id, {"status": "building_scenes", "progress_pct": 15, "category": category})
        if category == "health":
            scenes = _build_health_scenes(report_data)
        elif category == "market":
            scenes = _build_market_scenes(report_data)
        elif category == "historical":
            scenes = _build_historical_scenes(report_data)
        else:
            raise ValueError(f"Unknown category: {category}")

        # Stage 2: Render frames (Pillow — instant)
        set_video_job(job_id, {"status": "rendering_frames", "progress_pct": 30, "category": category})
        frame_paths = []
        durations = []
        for i, sc in enumerate(scenes):
            fp = os.path.join(settings.video_frames_dir, f"{job_id}_s{i}.png")
            _render_frame(sc["texts"], fp)
            frame_paths.append(fp)
            durations.append(sc.get("duration", 7))

        # Stage 3: TTS
        set_video_job(job_id, {"status": "synthesizing_speech", "progress_pct": 50, "category": category})
        narration = " ".join(sc["narration"] for sc in scenes)
        audio_path = os.path.join(settings.video_audio_dir, f"{job_id}.mp3")
        await _synthesize_tts(narration, audio_path)

        # Stage 4: Compose
        set_video_job(job_id, {"status": "composing_video", "progress_pct": 75, "category": category})
        output_path = os.path.join(settings.video_output_dir, f"{job_id}.mp4")
        _compose(frame_paths, audio_path, output_path, durations)

        elapsed = time.time() - t0
        set_video_job(job_id, {
            "status": "completed", "progress_pct": 100,
            "video_url": f"/media/videos/{job_id}.mp4",
            "filename": f"{job_id}.mp4",
            "category": category, "elapsed_sec": round(elapsed, 2),
        })
        logger.info("video_done", job_id=job_id, elapsed=round(elapsed, 2))

    except Exception as e:
        logger.error("video_failed", job_id=job_id, error=str(e), tb=traceback.format_exc())
        set_video_job(job_id, {
            "status": "failed", "progress_pct": 0,
            "error": str(e), "category": category,
        })

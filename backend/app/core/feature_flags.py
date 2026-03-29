"""
Feature Flags — Runtime guards for optional capabilities.

Each flag is backed by an env var and can be disabled without restarting
(via config reload) to safely roll back features.
"""

from __future__ import annotations

from app.config import get_settings


def is_pattern_scan_enabled() -> bool:
    """Check if Chart Pattern Intelligence module is enabled."""
    return get_settings().enable_pattern_scan


def is_video_engine_enabled() -> bool:
    """Check if AI Market Video Engine module is enabled."""
    return get_settings().enable_video_engine

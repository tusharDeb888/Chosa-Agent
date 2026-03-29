"""
Dependency Guards — Safe runtime checks for optional heavy libraries.

Each guard returns (available: bool, message: str) so the API can
return a clear 424 response instead of crashing on ImportError.
"""

from __future__ import annotations

import shutil
from typing import Tuple


def check_pandas_ta() -> Tuple[bool, str]:
    try:
        import pandas_ta  # noqa: F401
        return True, "pandas_ta available"
    except ImportError:
        return False, "pandas_ta not installed. Run: pip install pandas_ta"


def check_vectorbt() -> Tuple[bool, str]:
    try:
        import vectorbt  # noqa: F401
        return True, "vectorbt available"
    except ImportError:
        return False, "vectorbt not installed. Run: pip install vectorbt"


def check_moviepy() -> Tuple[bool, str]:
    try:
        import moviepy  # noqa: F401
        return True, "moviepy available"
    except ImportError:
        return False, "moviepy not installed. Run: pip install moviepy"


def check_plotly() -> Tuple[bool, str]:
    try:
        import plotly  # noqa: F401
        return True, "plotly available"
    except ImportError:
        return False, "plotly not installed. Run: pip install plotly kaleido"


def check_boto3() -> Tuple[bool, str]:
    try:
        import boto3  # noqa: F401
        return True, "boto3 available"
    except ImportError:
        return False, "boto3 not installed. Run: pip install boto3"


def check_ffmpeg() -> Tuple[bool, str]:
    path = shutil.which("ffmpeg")
    if path:
        return True, f"ffmpeg found at {path}"
    return False, "ffmpeg not found. Install: brew install ffmpeg (macOS) or apt install ffmpeg (Linux)"


def check_pattern_deps() -> Tuple[bool, str]:
    """Check all dependencies needed for Pattern Intelligence.
    Now uses pure-pandas indicators + fallback backtest, so only pandas is needed."""
    try:
        import pandas  # noqa: F401
        import numpy  # noqa: F401
        return True, "All pattern dependencies available (pure-pandas mode)"
    except ImportError as e:
        return False, f"Missing core dependency: {e}"


def check_video_deps() -> Tuple[bool, str]:
    """Check all dependencies needed for Video Engine.
    boto3 is optional — edge-tts provides free TTS fallback."""
    for fn in [check_moviepy, check_plotly, check_ffmpeg]:
        ok, msg = fn()
        if not ok:
            return False, msg
    return True, "All video dependencies available"

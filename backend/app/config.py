"""
Alpha-Hunter Configuration — Pydantic Settings with environment variable binding.

All config is grouped by service domain and loaded from .env or environment.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──
    app_name: str = "Alpha-Hunter"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"
    secret_key: str = "change-me-in-production"

    # ── Database ──
    database_url: str = "postgresql+asyncpg://ahuser:ahpass@localhost:5432/alphahunter"
    database_url_sync: str = "postgresql://ahuser:ahpass@localhost:5432/alphahunter"
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_timeout: int = 30

    # ── Redis ──
    redis_url: str = "redis://localhost:6379/0"

    # ── Market Data Provider ──
    market_provider: Literal["mock", "upstox"] = "mock"

    # Upstox (optional)
    upstox_api_key: str = ""
    upstox_api_secret: str = ""
    upstox_redirect_uri: str = ""
    upstox_access_token: str = ""

    # ── LLM (Groq) ──
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_fallback_model: str = "llama-3.1-8b-instant"
    groq_max_retries: int = 3
    groq_timeout_seconds: int = 30

    # ── Embeddings ──
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # ── Agent Control ──
    control_channel: str = "agent.control"
    agent_default_state: str = "PAUSED"

    # ── Stream Configuration ──
    stream_retention_ticks_maxlen: int = 50000
    stream_retention_signals_maxlen: int = 10000
    stream_retention_decisions_maxlen: int = 10000
    stream_consumer_group: str = "alphahunter-workers"
    stream_block_ms: int = 5000
    stream_batch_size: int = 10

    # ── Idempotency ──
    idempotency_ttl_seconds: int = 86400

    # ── Policy Defaults ──
    policy_max_position_concentration_pct: float = 25.0
    policy_max_daily_actions: int = 20
    policy_min_confidence_buy_sell: int = 60
    policy_max_evidence_age_hours: int = 24

    # ── SLO Thresholds ──
    slo_p50_alert_latency_ms: int = 1200
    slo_p95_alert_latency_ms: int = 3000
    slo_p99_alert_latency_ms: int = 5000
    slo_breach_window_count: int = 5

    # ── Enrichment ──
    scraper_max_concurrent: int = 5
    scraper_timeout_seconds: int = 15
    scraper_allowed_domains: str = (
        "moneycontrol.com,economictimes.com,livemint.com,reuters.com,bloomberg.com"
    )

    @property
    def allowed_domains_list(self) -> list[str]:
        return [d.strip() for d in self.scraper_allowed_domains.split(",") if d.strip()]

    # ── Worker ──
    worker_heartbeat_interval_seconds: int = 5
    worker_max_restart_attempts: int = 10
    worker_restart_backoff_base_seconds: float = 1.0
    worker_restart_backoff_max_seconds: float = 60.0

    # ── Circuit Breaker ──
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout_seconds: int = 30
    circuit_breaker_half_open_max_calls: int = 3

    # ── Orchestrator ──
    orchestrator_max_concurrent_tasks: int = 50
    orchestrator_llm_semaphore_limit: int = 10

    # ── Finnhub (News) ──
    finnhub_api_key: str = ""

    # ── Telegram Bot (Stretch) ──
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # ── Feature Flags ──
    enable_pattern_scan: bool = True
    enable_video_engine: bool = True

    # ── AWS Polly (Video Engine TTS) ──
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "ap-south-1"
    polly_voice_id: str = "Kajal"
    polly_engine: str = "neural"

    # ── Video Engine ──
    video_output_dir: str = "./storage/videos"
    video_audio_dir: str = "./storage/audio"
    video_frames_dir: str = "./storage/frames"
    video_max_concurrent_jobs: int = 3
    video_generation_timeout_seconds: int = 120

    # ── Pattern Scan ──
    pattern_scan_cache_ttl_seconds: int = 120
    pattern_scan_default_lookback: int = 365
    pattern_scan_max_lookback: int = 730


@lru_cache
def get_settings() -> Settings:
    """Singleton settings instance — cached for the process lifetime."""
    return Settings()

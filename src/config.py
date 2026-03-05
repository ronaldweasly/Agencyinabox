"""
config.py — Centralised configuration and secrets loader.

All secrets fetched at runtime via Doppler (or os.environ when run under
`doppler run --`). No hardcoded keys. No .env files in production.

No Supabase: uses DATABASE_URL for any standard PostgreSQL provider
(Fly Postgres, Neon, Railway, local Docker, etc.).
"""
from __future__ import annotations

import logging
import os
import socket
from functools import lru_cache

log = logging.getLogger(__name__)


def _require(key: str) -> str:
    """Fetch a required environment variable or raise immediately."""
    val = os.environ.get(key)
    if not val:
        raise RuntimeError(
            f"Missing required secret: {key}. Ensure Doppler is configured."
        )
    return val


@lru_cache(maxsize=1)
def load_config() -> dict[str, str]:
    """
    Load all required configuration.
    Called once at worker startup; cached thereafter.
    """
    return {
        # Database — any PostgreSQL provider (Fly Postgres, Neon, Render, Docker)
        "DATABASE_URL": _require("DATABASE_URL"),
        # AI models
        "ANTHROPIC_API_KEY": _require("ANTHROPIC_API_KEY"),
        "GEMINI_API_KEY": _require("GEMINI_API_KEY"),
        # Telegram
        "TELEGRAM_BOT_TOKEN": _require("TELEGRAM_BOT_TOKEN"),
        "TELEGRAM_CHAT_ID": _require("TELEGRAM_CHAT_ID"),
        "TELEGRAM_WEBHOOK_SECRET": _require("TELEGRAM_WEBHOOK_SECRET"),
        # GitHub (DMZ holds the PAT — worker does NOT need it)
        "GITHUB_PAT": _require("GITHUB_PAT"),
        "GITHUB_ORG": _require("GITHUB_ORG"),
        # Fly.io sandbox
        "FLY_API_TOKEN": _require("FLY_API_TOKEN"),
        "FLY_APP_NAME": os.environ.get("FLY_APP_NAME", "agency-sandbox"),
        # Budget limits (safe defaults)
        "DAILY_BUDGET_CAP": os.environ.get("DAILY_BUDGET_CAP", "15.00"),
        "PROJECT_BUDGET_CAP": os.environ.get("PROJECT_BUDGET_CAP", "50.00"),
        # DMZ internal URL
        "DMZ_INTERNAL_URL": os.environ.get(
            "DMZ_INTERNAL_URL", "http://localhost:8001"
        ),
        # GDPR pepper for domain hashing
        "DOMAIN_PEPPER": _require("DOMAIN_PEPPER"),
    }


# ── Optional API keys (graceful degradation if missing) ──────────────────────

def get_firecrawl_key() -> str | None:
    """Return Firecrawl API key, or None if not configured."""
    return os.environ.get("FIRECRAWL_API_KEY")


def get_outscraper_key() -> str | None:
    """Return Outscraper API key, or None if not configured."""
    return os.environ.get("OUTSCRAPER_API_KEY")


def get_apollo_key() -> str | None:
    """Return Apollo.io API key, or None if not configured."""
    return os.environ.get("APOLLO_API_KEY")


def get_anymail_key() -> str | None:
    """Return AnyMail Finder API key, or None if not configured."""
    return os.environ.get("ANYMAIL_API_KEY")


def get_kvk_key() -> str | None:
    """Return KvK API key, or None if not configured."""
    return os.environ.get("KVK_API_KEY")


def get_instantly_key() -> str | None:
    """Return Instantly.ai API key, or None if not configured."""
    return os.environ.get("INSTANTLY_API_KEY")


# Unique worker identity — hostname + PID guarantees uniqueness per process
WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"

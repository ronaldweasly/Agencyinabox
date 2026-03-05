"""
__main__.py — Worker + Alert Poller startup entry point.

Run with:
    doppler run -- python -m src
  or (from src/ directory):
    doppler run -- python worker_core.py

Starts:
  1. AlertPoller — background thread, polls alerts table → Telegram
  2. Worker loop — main thread, claims and processes jobs

Handles SIGTERM / SIGINT for graceful shutdown of both components.
"""
from __future__ import annotations

import logging
import os
import sys

# Load .env file for local development (no-op if file doesn't exist)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass  # python-dotenv not installed — rely on Doppler in production

from config import load_config
from lead_poller import AlertPoller
from worker_core import run_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


def main() -> None:
    """
    Main entry point. Validates config, starts poller, runs worker loop.

    Raises:
        RuntimeError: If any required environment variable is missing.
    """
    # Validate all required secrets at startup — fail fast
    config = load_config()
    log.info(
        f"Agency-in-a-Box starting. "
        f"Daily budget cap: ${config['DAILY_BUDGET_CAP']}"
    )

    # Start the background alert poller
    poller = AlertPoller()
    poller.start()

    try:
        # Run the blocking worker loop (handles SIGTERM internally)
        run_worker()
    finally:
        # Ensure poller is cleaned up even if worker crashes
        poller.stop()
        log.info("Agency-in-a-Box shutdown complete.")


if __name__ == "__main__":
    main()

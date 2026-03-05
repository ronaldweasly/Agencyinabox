"""
queue_manager.py — Redis + Celery queue infrastructure.
Replaces Postgres SKIP LOCKED polling with proper message queues.
"""
from __future__ import annotations

import logging
import os
import time

import redis
from celery import Celery

log = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# ── Celery app ───────────────────────────────────────────────────────────────

celery_app = Celery(
    "agencyinabox",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "src.workers.discovery_worker.*": {"queue": "raw_discovery_queue"},
        "src.workers.dedup_worker.*": {"queue": "dedup_queue"},
        "src.workers.enrichment_worker.*": {"queue": "enrichment_queue"},
        "src.workers.ai_scoring_worker.*": {"queue": "ai_scoring_queue"},
        "src.workers.email_verify_worker.*": {"queue": "email_verify_queue"},
        "src.workers.outreach_worker.*": {"queue": "outreach_queue"},
    },
)

# ── Redis client ─────────────────────────────────────────────────────────────

redis_client = redis.from_url(REDIS_URL, decode_responses=True)


# ── Rate limiter ─────────────────────────────────────────────────────────────

class ApiRateLimiter:
    """
    Token bucket rate limiter backed by Redis.
    Use as a context manager: `with ApiRateLimiter('claude'): ...`
    """

    _LUA_SCRIPT = """
    local tokens = tonumber(redis.call('GET', KEYS[1])) or tonumber(ARGV[1])
    if tokens >= 1 then
        redis.call('SET', KEYS[1], tokens - 1)
        redis.call('EXPIRE', KEYS[1], 60)
        return 1
    end
    return 0
    """

    LIMITS: dict[str, int] = {
        "clearbit": 600,
        "hunter": 400,
        "neverbounce": 250,
        "zerobounce": 250,
        "claude": 50,
        "google_maps": 100,
        "instantly": 200,
        "apollo": 300,
        "outscraper": 60,
        "pagespeed": 100,
    }

    def __init__(self, service: str) -> None:
        self.service = service
        self.capacity = self.LIMITS.get(service, 100)
        self.key = f"rate_limit:{service}"
        self._script = redis_client.register_script(self._LUA_SCRIPT)

    def acquire(self, block: bool = True, timeout: float = 30.0) -> bool:
        """Acquire a token. Returns True on success, False on timeout."""
        deadline = time.monotonic() + timeout
        while True:
            result = self._script(keys=[self.key], args=[self.capacity])
            if result:
                return True
            if not block or time.monotonic() > deadline:
                log.warning(
                    f"Rate limit timeout for service '{self.service}' "
                    f"after {timeout}s"
                )
                return False
            time.sleep(0.1)

    def __enter__(self) -> "ApiRateLimiter":
        if not self.acquire():
            raise RuntimeError(
                f"Rate limit acquire timeout for service '{self.service}'"
            )
        return self

    def __exit__(self, *_: object) -> None:
        pass


# ── Queue introspection ──────────────────────────────────────────────────────

QUEUE_NAMES = [
    "raw_discovery_queue",
    "dedup_queue",
    "enrichment_queue",
    "contact_disc_queue",
    "email_verify_queue",
    "ai_scoring_queue",
    "outreach_queue",
    "dlq_poison",
]


def get_queue_depth(queue_name: str) -> int:
    """Return current number of jobs waiting in a queue."""
    try:
        return redis_client.llen(queue_name)
    except redis.RedisError as e:
        log.error(f"Redis error reading queue depth for '{queue_name}': {e}")
        return -1


def _classify_depth(depth: int) -> str:
    if depth < 0:
        return "error"
    if depth > 10_000:
        return "backlogged"
    if depth > 1_000:
        return "busy"
    return "healthy"


def get_all_queue_stats() -> list[dict]:
    """Return depth and status for all queues. Safe to call from API routes."""
    stats = []
    for q in QUEUE_NAMES:
        depth = get_queue_depth(q)
        stats.append(
            {
                "name": q,
                "depth": depth,
                "status": _classify_depth(depth),
                "throughput": 0,   # populated by Prometheus scrape in production
                "workers": 0,      # populated by Celery inspect in production
            }
        )
    return stats


def health_check() -> dict:
    """Ping Redis. Returns {'ok': True} or {'ok': False, 'error': str}."""
    try:
        redis_client.ping()
        return {"ok": True}
    except redis.RedisError as e:
        return {"ok": False, "error": str(e)}

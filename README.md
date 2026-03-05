# Agency-in-a-Box

Fully autonomous Dutch e-commerce lead-to-revenue system.

## Project Structure

```
src/
├── config.py           # Doppler secrets loader, constants
├── schemas.py          # Shared Pydantic models (single source of truth)
├── worker_core.py      # Job queue consumer, heartbeat, budget, audit
├── gsd_executor.py     # Claude code engine (RESEARCH→IMPL)
├── critic_agent.py     # Gemini cross-model QA reviewer
├── telegram_bot.py     # Telegram notification & approval messages
├── sandbox.py          # Fly.io machine orchestrator
dmz/
├── main.py             # FastAPI DMZ (Telegram→GitHub bridge)
fly-sandbox/
├── Dockerfile
├── entrypoint.sh
sql/
├── 001_schema.sql      # Core tables
├── 002_watchdog.sql    # Watchdog reclaim query
├── 003_gdpr.sql        # GDPR TTL cron
```

## Setup

See `PROBLEMS.md` for the 27 issues found in the original blueprint and how they are resolved in this codebase.

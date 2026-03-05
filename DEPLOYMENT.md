# Agency-in-a-Box — Deployment Guide

This guide walks from zero to a live system. Every step is ordered and executable.
Estimated time: **45–90 minutes** (mostly API setup, not code).

---

## Prerequisites

| Tool | Install | Version needed |
|---|---|---|
| Python | python.org | 3.12+ |
| Fly CLI | `brew install flyctl` / [fly.io/docs](https://fly.io/docs/hands-on/install-flyctl/) | latest |
| Doppler CLI | `brew install dopplerhq/cli/doppler` / [docs.doppler.com](https://docs.doppler.com/docs/install-cli) | latest |
| Git | git-scm.com | any |

---

## Step 1 — PostgreSQL Database

Choose any Postgres provider. **Free options**:

| Option | Free tier | Setup time |
|---|---|---|
| **Neon** (recommended) | 0.5 GB free forever | 2 min ([neon.tech](https://neon.tech)) |
| Fly Postgres | $0 with shared CPU | `fly postgres create` |
| Railway | 500 MB free | [railway.app](https://railway.app) |
| Local Docker | unlimited | `docker run -e POSTGRES_PASSWORD=pw -p 5432:5432 postgres:16` |

After creating your DB, get the `DATABASE_URL` (PostgreSQL connection string).

### Run the schema

In your Postgres SQL editor (or psql), run these files **in order**:

```sql
-- 1. Core tables, indexes, helper functions
\i sql/001_schema.sql

-- 2. Watchdog CTE (you'll schedule this via pg_cron)
-- (Already embedded in 004_pg_cron.sql — skip if using pg_cron)

-- 3. GDPR TTL (embedded in 004_pg_cron.sql — skip if using pg_cron)

-- 4. Register pg_cron jobs (requires pg_cron extension)
\i sql/004_pg_cron.sql
```

> [!NOTE]
> pg_cron is optional. If your Postgres provider doesn't support it, you can
> run the watchdog and GDPR SQL manually or via an external cron job.

---

## Step 2 — Telegram Bot

1. Open [@BotFather](https://t.me/BotFather) on Telegram
2. `/newbot` → choose name → get `TELEGRAM_BOT_TOKEN`
3. Message [@userinfobot](https://t.me/userinfobot) → get your `TELEGRAM_CHAT_ID`
4. Keep a random secret for `TELEGRAM_WEBHOOK_SECRET` (min 32 characters)

---

## Step 3 — GitHub Personal Access Token

1. GitHub → Settings → Developer Settings → Personal Access Tokens → Fine-grained
2. Scope: **Contents** (read/write), **Pull requests** (write), **Metadata** (read)
3. Copy the token as `GITHUB_PAT`

---

## Step 4 — AI API Keys

| Service | Free tier | URL |
|---|---|---|
| **Anthropic** (Claude) | $5 credit on signup | [console.anthropic.com](https://console.anthropic.com) |
| **Google Gemini** | Free (15 RPM / 1M tokens/day) | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| Firecrawl (optional) | 500 credits free | [firecrawl.dev](https://www.firecrawl.dev) |

---

## Step 5 — Doppler Setup

```bash
# Install Doppler CLI (see prerequisites above)
doppler login
doppler setup          # links this repo to your Doppler project
doppler secrets set \
  DATABASE_URL="postgresql://..." \
  ANTHROPIC_API_KEY="sk-ant-..." \
  GEMINI_API_KEY="AIzaSy..." \
  TELEGRAM_BOT_TOKEN="1234:..." \
  TELEGRAM_CHAT_ID="123456" \
  TELEGRAM_WEBHOOK_SECRET="your-32-char-secret" \
  GITHUB_PAT="ghp_..." \
  GITHUB_ORG="your-github-org" \
  FLY_API_TOKEN="fo1_..." \
  FLY_APP_NAME="agency-sandbox" \
  DOMAIN_PEPPER="$(openssl rand -hex 16)"
```

---

## Step 6 — Fly.io Sandbox Setup

The sandbox runs AI-generated code in isolated microVMs.

```bash
# 1. Create the sandbox app
fly apps create agency-sandbox --region ams

# 2. Build and push the sandbox Docker image
fly deploy --app agency-sandbox --config fly-sandbox/ \
  --dockerfile fly-sandbox/Dockerfile

# 3. Verify it exists
fly apps list | grep sandbox
```

---

## Step 7 — Deploy the DMZ (FastAPI)

The DMZ handles Telegram webhook callbacks → GitHub merges.

```bash
# 1. Create DMZ app
fly apps create agency-dmz --region ams

# 2. Set secrets (pulled from Doppler)
doppler run -- sh -c \
  'fly secrets set DATABASE_URL="$DATABASE_URL" \
     TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
     TELEGRAM_WEBHOOK_SECRET="$TELEGRAM_WEBHOOK_SECRET" \
     GITHUB_PAT="$GITHUB_PAT" GITHUB_ORG="$GITHUB_ORG" \
     --app agency-dmz'

# 3. Deploy
fly deploy --config fly.dmz.toml

# 4. Get the DMZ URL
fly status --app agency-dmz
# Note the URL: https://agency-dmz.fly.dev
```

### Register Telegram Webhook

```bash
curl -s -X POST \
  "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -d "url=https://agency-dmz.fly.dev/internal/telegram/callback" \
  -d "secret_token=${TELEGRAM_WEBHOOK_SECRET}"
# Response: {"ok":true,"description":"Webhook was set"}
```

---

## Step 8 — Deploy the Worker

```bash
# 1. Create worker app
fly apps create agency-worker --region ams

# 2. Set secrets
doppler run -- sh -c \
  'fly secrets set DATABASE_URL="$DATABASE_URL" \
     ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
     GEMINI_API_KEY="$GEMINI_API_KEY" \
     TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
     TELEGRAM_CHAT_ID="$TELEGRAM_CHAT_ID" \
     GITHUB_PAT="$GITHUB_PAT" GITHUB_ORG="$GITHUB_ORG" \
     FLY_API_TOKEN="$FLY_API_TOKEN" FLY_APP_NAME="agency-sandbox" \
     TELEGRAM_WEBHOOK_SECRET="$TELEGRAM_WEBHOOK_SECRET" \
     DOMAIN_PEPPER="$DOMAIN_PEPPER" \
     --app agency-worker'

# 3. Deploy
fly deploy --config fly.worker.toml

# 4. Tail logs to confirm startup
fly logs --app agency-worker
# Expected: "Agency-in-a-Box starting. Daily budget cap: $15.00"
```

---

## Step 9 — Smoke Test

```bash
# Insert a test job directly into the DB
psql "$DATABASE_URL" << 'SQL'
-- First create a project budget and project
INSERT INTO project_budgets (project_cap) VALUES (50.00);
INSERT INTO projects (budget_id, deliverable, tech_stack)
  VALUES (
    (SELECT project_id FROM project_budgets LIMIT 1),
    'Hello World CLI tool',
    '{"language": "python"}'::jsonb
  );

-- Queue a test job
INSERT INTO jobs (project_id, job_type, payload)
  VALUES (
    (SELECT id FROM projects LIMIT 1),
    'gsd_task',
    '{"brief": {"task": "Write a hello world CLI"}, "libraries": [], "acceptance_criteria": ["prints Hello World"]}'
  );
SQL

# Watch the worker pick it up
fly logs --app agency-worker
# Watch Telegram for Gate 4 message with PR link
```

---

## Local Development

```bash
# Run everything locally (requires Doppler + local Postgres)
pip install -r requirements.txt

# Worker
doppler run -- python -m src

# DMZ (separate terminal)
doppler run -- uvicorn dmz.main:app --host 0.0.0.0 --port 8001 --reload

# Tests (no API keys needed)
python -m pytest tests/ -v
```

---

## Troubleshooting

| Symptom | Check |
|---|---|
| Worker crashes immediately | `fly logs --app agency-worker` — likely missing secret |
| Telegram callbacks not arriving | Verify webhook: `curl https://api.telegram.org/botTOKEN/getWebhookInfo` |
| Budget cap exceeded immediately | Check `daily_spend` table — run `SELECT ensure_daily_spend()` |
| PR not created | Check `GITHUB_PAT` scopes — needs Contents + Pull requests |
| Sandbox timeout | Increase `SANDBOX_TIMEOUT_SECONDS` in `sandbox.py` (default: 120s) |
| `db: connection refused` | Verify `DATABASE_URL` format and that DB is accessible |

# How It Works: Agency-in-a-Box Architecture

Agency-in-a-Box is a highly decoupled, asynchronously coordinated, multi-agent AI framework designed to run autonomously while incorporating human-in-the-loop (Gate 4) approvals for safety.

## System Components

### 1. The PostgreSQL Database (The Nervous System)
Instead of relying on message brokers like Kafka or Redis, the system uses a standard PostgreSQL database for all state management, locking, and inter-process communication. 
- **`jobs` table:** The primary queue. Workers use `SELECT ... FOR UPDATE SKIP LOCKED` to concurrently pick up jobs without stepping on each other's toes. 
- **`alerts` table:** Used to queue notifications that the `lead_poller` will independently fetch and send to Telegram.
- **Budget tables:** Strict constraints to ensure the AI does not overspend on external APIs.

### 2. The Core Worker Loop (`worker_core.py`)
This runs as an infinite daemon. It performs the following duties:
1. Validates the global daily budget and project-level budgets.
2. Claims a pending job from the database.
3. Spawns a dedicated heartbeat thread to keep the job locked while it's being worked on.
4. Defers execution to the "Get Shit Done" (GSD) executor or other specialized engines according to the `job_type`.
5. Records the outcome (success or failure) and updates the budget with the actual API costs incurred.

### 3. The "Get Shit Done" Engine (`gsd_executor.py`)
The main AI brain of the operation. It uses Claude 3.5 Sonnet to perform multi-stage implementation tasks safely:
- **Phase 1: Planning/Research.** Reviews requirements and makes an action plan.
- **Phase 2: Implementation.** Generates the code according to constraints (e.g., small functions, TDD).
- **Phase 3: Test Generation.** Writes unit tests for the implementation.
- **Phase 4: Handoff.** Triggers the Critic and Sandbox sequence.

### 4. Cross-Model Validation (`critic_agent.py`)
No code is merged unreviewed. Gemini 1.5 Pro acts as an adversarial critic. It reviews Claude's output against the acceptance criteria, providing correct-ness, security, and maintainability scores. If the Critic finds a "blocker" issue, the script is considered flawed and goes into a revision state. 

### 5. Ephemeral Fly.io Sandbox (`sandbox.py`)
To prevent the main server environment from executing potentially malicious or broken AI-generated code, the framework wraps the proposed code and tests and sends them to a disposable Fly.io Machine.
- The machine boots up (using the custom `fly-sandbox` Docker image).
- It runs Bandit (security analysis), Mypy (type checking), Ruff (linting), and Pytest (functionality).
- It extracts the logs and output, returning them to the worker and instantly destroying itself.

### 6. GitHub Integration (`pr_creator.py`)
If the Sandbox tests pass and the Critic is satisfied (or conditionally depending on policies), the system creates a feature branch, commits the files, and opens a formal Pull Request on GitHub. 

### 7. The DMZ & Telegram (`dmz/main.py` & `telegram_bot.py`)
The system follows a strict zero-trust inbound policy for the main worker. 
- The worker only makes *outbound* connections to the API providers and the Database.
- A lightweight, public-facing FastAPI service (DMZ) securely processes incoming Telegram callbacks (e.g., when a user clicks "Approve PR" or "Reject PR").
- When an action is taken via the Telegram Bot UI, the DMZ simply updates the PostgreSQL database. The worker will pick up these state changes on its next poll, closing the loop.

## Workflow Path
1. **Creation:** A new objective is inserted into the `jobs` table.
2. **Claiming:** `worker_core` locks the job. 
3. **Execution:** `gsd_executor` designs, writes, and tests the target code.
4. **Validation:** `sandbox` verifies the unit tests; `critic_agent` does the semantic review.
5. **PR & Notify:** A GitHub PR is generated and the Telegram Bot sends a Gate 4 alert to the human owner.
6. **Approval:** The human approves the PR via Telegram.
7. **Resolution:** The DMZ sets the job status to `approved`, the job resolves, and the workflow ends.

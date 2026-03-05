"""
sdr_handler.py — AI SDR reply handler powered by Gemini 2.0 Flash.

Handles incoming email replies from prospects (via Instantly.ai webhook).
Drafts Dutch B2B responses following a conversation playbook, then routes
to Gate 2 for human approval before sending.

Conversation stages:
  1. Initial interest → Propose a call/demo
  2. Objection handling → Address concern, re-propose
  3. Scheduling → Confirm meeting details
  4. Disqualification → Polite close if not a fit

Thread safety:
  Uses SELECT ... FOR UPDATE on leads.reply_locked_by to ensure only one
  worker drafts a reply per lead at a time (P-01: replaces Redis mutex).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import google.genai as genai
from instructor import from_genai, Mode
from pydantic import BaseModel, Field
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config import WORKER_ID
from agency_config import agency_prompt_snippet

log = logging.getLogger(__name__)

# ── Gemini client ────────────────────────────────────────────────────────────

gemini_client = from_genai(
    client=genai.Client(api_key=os.environ.get("GEMINI_API_KEY", "")),
    mode=Mode.GENAI_TOOLS,
)


# ── Reply schema ─────────────────────────────────────────────────────────────

class DraftReply(BaseModel):
    """Structured AI-drafted reply for human review."""
    reply_text: str = Field(
        max_length=2000,
        description="The full email reply text in Dutch",
    )
    conversation_stage: str = Field(
        description="Current stage: 'interest', 'objection', 'scheduling', 'disqualify', 'other'"
    )
    sentiment: str = Field(
        description="Detected sentiment of their reply: 'positive', 'neutral', 'negative'"
    )
    confidence: int = Field(
        ge=0, le=100,
        description="How confident the AI is in this draft (0-100)",
    )
    suggested_action: str = Field(
        description="'send' (auto-sendable), 'edit' (human should tweak), 'escalate' (complex situation)"
    )
    key_points: list[str] = Field(
        default_factory=list,
        description="Key points detected in their reply",
    )
    service_mentioned: str = Field(
        default="",
        description="If reply references a specific service, note which one",
    )
    sequence_step: str = Field(
        default="initial",
        description="'initial', 'follow_up_1', 'follow_up_2', 'break_up' — where we are in the sequence",
    )


# ── Reply generation prompt ──────────────────────────────────────────────────

SDR_SYSTEM_PROMPT = """\
You are a professional B2B sales development representative (SDR) for
Postmaster Digital, a US-based agency.

{agency_context}

## Rules
1. Write in English. Keep tone professional but human — no corporate jargon.
2. Max 120 words per reply.
3. Always propose a concrete next step (call, audit, demo).
4. On objections: acknowledge → short counter → propose call.
5. On disinterest: thank them, leave the door open. One sentence max.
6. NEVER lie about capabilities or pricing.
7. NEVER use high-pressure tactics ("limited time", "last chance").
8. If they mention a specific service or pain, mirror it back.

## Sequence strategy
{sequence_strategy}

## Conversation stages
- interest: They show interest → propose a call/demo
- objection: They push back → acknowledge + counter + call
- scheduling: They want to meet → confirm details
- disqualify: Not a fit → polite close
"""

REPLY_PROMPT = """\
## Bedrijfscontext
{company_context}

## Eerdere berichten
{conversation_history}

## Hun laatste bericht
{their_reply}

Schrijf een passende reply. Bepaal de gespreksfase en een suggested_action.
"""


# ── Reply lock (P-01: replaces Redis mutex) ──────────────────────────────────

def acquire_reply_lock(conn, lead_id: str) -> bool:
    """
    Acquire exclusive lock on a lead's reply thread.
    Uses SELECT ... FOR UPDATE SKIP LOCKED to prevent double-drafting.

    Returns True if lock acquired, False if another worker holds it.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id FROM leads
                   WHERE id = %s
                     AND (reply_locked_by IS NULL
                          OR reply_locked_at < NOW() - INTERVAL '5 minutes')
                   FOR UPDATE SKIP LOCKED""",
                (lead_id,),
            )
            if not cur.fetchone():
                conn.rollback()
                return False

            cur.execute(
                """UPDATE leads
                   SET reply_locked_by = %s, reply_locked_at = NOW()
                   WHERE id = %s""",
                (WORKER_ID, lead_id),
            )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        log.error(f"Reply lock failed for lead {lead_id}: {e}")
        return False


def release_reply_lock(conn, lead_id: str) -> None:
    """Release reply lock after drafting is complete."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE leads
                   SET reply_locked_by = NULL, reply_locked_at = NULL
                   WHERE id = %s AND reply_locked_by = %s""",
                (lead_id, WORKER_ID),
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.error(f"Reply lock release failed for lead {lead_id}: {e}")


# ── Conversation history ─────────────────────────────────────────────────────

def get_conversation_history(conn, lead_id: str, limit: int = 10) -> list[dict]:
    """
    Fetch recent conversation messages for a lead from reply_threads.

    Returns list of {direction, body, sent_at} dicts, oldest first.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT direction, body, sent_at
                   FROM reply_threads
                   WHERE lead_id = %s
                   ORDER BY sent_at DESC
                   LIMIT %s""",
                (lead_id, limit),
            )
            rows = cur.fetchall()
        conn.commit()

        # Reverse to chronological order
        return [
            {
                "direction": row[0],
                "body": row[1],
                "sent_at": row[2].isoformat() if row[2] else "",
            }
            for row in reversed(rows)
        ]
    except Exception as e:
        conn.rollback()
        log.warning(f"Failed to fetch conversation for lead {lead_id}: {e}")
        return []


# ── Draft generation ─────────────────────────────────────────────────────────


def _count_outbound_emails(history: list[dict]) -> int:
    """Count how many outbound emails have been sent in this thread."""
    return sum(1 for m in history if m.get("direction") == "outbound")


def _get_sequence_strategy(outbound_count: int) -> str:
    """Return guidance for where we are in the follow-up sequence."""
    if outbound_count == 0:
        return "This is the FIRST email. Keep it short, personal, and value-led."
    elif outbound_count == 1:
        return "This is follow-up #1. Reference your first email briefly, add a new angle or case study."
    elif outbound_count == 2:
        return "This is follow-up #2. Be shorter. Ask a simple yes/no question."
    else:
        return "This is the BREAK-UP email. Last touch — be respectful, leave the door open."


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=15),
    retry=retry_if_exception_type(Exception),
)
def generate_reply(
    lead: dict,
    their_reply: str,
    conversation_history: list[dict],
) -> DraftReply:
    """
    Generate an AI-drafted reply using Gemini 2.0 Flash.

    Args:
        lead: Lead record with company_name, website, etc.
        their_reply: The prospect's latest message.
        conversation_history: Previous messages in the thread.

    Returns:
        DraftReply with the AI-generated response.
    """
    company_context = json.dumps({
        "company_name": lead.get("company_name", "Unknown"),
        "website": lead.get("website", "N/A"),
        "icp_score": lead.get("icp_score", "N/A"),
        "recommended_service": lead.get("recommended_service", "N/A"),
        "pain_point": lead.get("pain_point", "N/A"),
    }, indent=2)

    history_text = ""
    for msg in conversation_history[-6:]:  # Last 6 messages for context
        direction = "Us" if msg["direction"] == "outbound" else "Them"
        history_text += f"[{direction}] {msg['body'][:300]}\n\n"

    outbound_count = _count_outbound_emails(conversation_history)
    sequence_strategy = _get_sequence_strategy(outbound_count)

    system = SDR_SYSTEM_PROMPT.format(
        agency_context=agency_prompt_snippet(),
        sequence_strategy=sequence_strategy,
    )

    prompt = REPLY_PROMPT.format(
        company_context=company_context,
        conversation_history=history_text or "(first contact)",
        their_reply=their_reply[:1000],
    )

    result = gemini_client.chat.completions.create(
        response_model=DraftReply,
        model="gemini-2.0-flash",
        messages=[
            {"role": "user", "content": system},
            {"role": "user", "content": prompt},
        ],
    )

    return result


# ── Store reply thread ───────────────────────────────────────────────────────

def store_reply(
    conn,
    lead_id: str,
    direction: str,
    body: str,
    draft_id: str | None = None,
) -> str | None:
    """
    Store a message in the reply_threads table.

    Args:
        direction: 'inbound' (from prospect) or 'outbound' (our reply)
        draft_id: If outbound and pending approval, links to draft

    Returns:
        UUID of the stored message, or None on failure.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO reply_threads
                   (lead_id, direction, body, status, sent_at)
                   VALUES (%s, %s, %s, %s, NOW())
                   RETURNING id::text""",
                (
                    lead_id,
                    direction,
                    body,
                    "sent" if direction == "inbound" else "pending_approval",
                ),
            )
            result = cur.fetchone()
        conn.commit()
        return result[0] if result else None
    except Exception as e:
        conn.rollback()
        log.error(f"Failed to store reply for lead {lead_id}: {e}")
        return None


# ── Entry point for worker_core.execute_job ──────────────────────────────────

def run_sdr_reply(conn, job: dict) -> float:
    """
    Execute an sdr_reply job.

    Payload format:
        {
            "lead_id": "uuid",
            "their_reply": "text of prospect's email",
            "instantly_message_id": "optional"
        }

    Pipeline:
        1. Acquire reply lock (P-01)
        2. Store inbound message
        3. Fetch conversation history
        4. Generate AI draft
        5. Store draft as pending_approval
        6. Send Gate 2 Telegram message
        7. Release lock

    Returns:
        Approximate API cost in USD.
    """
    payload = job.get("payload", {})
    lead_id = payload.get("lead_id")
    their_reply = payload.get("their_reply", "")

    if not lead_id or not their_reply:
        log.warning(f"sdr_reply job {job['id']} missing lead_id or their_reply")
        return 0.0

    # Step 1: Acquire reply lock
    if not acquire_reply_lock(conn, lead_id):
        raise RuntimeError(
            f"Could not acquire reply lock for lead {lead_id} — "
            "another worker is processing"
        )

    try:
        # Fetch lead data
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, company_name, website, contact_email,
                          icp_score, status, recommended_service, pain_point
                   FROM leads WHERE id = %s""",
                (lead_id,),
            )
            row = cur.fetchone()
        conn.commit()

        if not row:
            log.warning(f"Lead {lead_id} not found")
            return 0.0

        lead = {
            "id": str(row[0]),
            "company_name": row[1],
            "website": row[2],
            "contact_email": row[3],
            "icp_score": row[4],
            "status": row[5],
            "recommended_service": row[6],
            "pain_point": row[7],
        }

        # Step 2: Store inbound message
        store_reply(conn, lead_id, "inbound", their_reply)

        # Update lead status
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE leads
                   SET status = 'replied', last_contact_date = NOW()
                   WHERE id = %s""",
                (lead_id,),
            )
        conn.commit()

        # Step 3: Fetch conversation history
        history = get_conversation_history(conn, lead_id)

        # Step 4: Generate AI draft
        draft = generate_reply(lead, their_reply, history)

        # Step 5: Store draft
        draft_msg_id = store_reply(conn, lead_id, "outbound", draft.reply_text)

        # Step 6: Send Gate 2 Telegram message
        from telegram_bot import send_reply_approval
        import asyncio

        asyncio.run(send_reply_approval(lead, their_reply, draft.reply_text))

        log.info(
            f"SDR reply drafted for lead {lead_id}. "
            f"Stage: {draft.conversation_stage}, "
            f"Confidence: {draft.confidence}%, "
            f"Action: {draft.suggested_action}"
        )

        # Cost: Gemini 2.0 Flash is very cheap
        return 0.001

    finally:
        # Step 7: Release lock
        release_reply_lock(conn, lead_id)

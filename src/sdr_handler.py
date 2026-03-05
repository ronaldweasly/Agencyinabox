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


# ── Reply generation prompt ──────────────────────────────────────────────────

SDR_SYSTEM_PROMPT = """\
Je bent een professionele Nederlandse B2B sales development representative (SDR).
Je werkt voor een tech-automatiseringsbureau dat AI-gestuurde oplossingen bouwt.

## Regels
1. Schrijf ALTIJD in het Nederlands (tenzij het gesprek in het Engels is).
2. Houd het professioneel maar persoonlijk — geen stijve corporate taal.
3. Maximaal 150 woorden per reply.
4. Noem altijd een concreet volgende stap (call, demo, voorstel).
5. Bij bezwaren: erken het bezwaar, geef een kort tegenargument, stel voor
   om het in een kort gesprek te bespreken.
6. Bij desinteresse: wees beleefd, bedank, en laat de deur open.
7. NOOIT liegen over capabilities of prijzen.
8. NOOIT druk uitoefenen ("last chance", "beperkt aanbod", etc.).

## Gespreksfasen
- interest: Ze tonen interesse → stel een call/demo voor
- objection: Ze hebben een bezwaar → erken + tegenargument + call
- scheduling: Ze willen plannen → bevestig details
- disqualify: Niet een fit → beleefd afsluiten
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
    }, indent=2)

    history_text = ""
    for msg in conversation_history[-6:]:  # Last 6 messages for context
        direction = "Wij" if msg["direction"] == "outbound" else "Zij"
        history_text += f"[{direction}] {msg['body'][:300]}\n\n"

    prompt = REPLY_PROMPT.format(
        company_context=company_context,
        conversation_history=history_text or "(eerste contact)",
        their_reply=their_reply[:1000],
    )

    result = gemini_client.chat.completions.create(
        response_model=DraftReply,
        model="gemini-2.0-flash",
        messages=[
            {"role": "user", "content": SDR_SYSTEM_PROMPT},
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
                          icp_score, status
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

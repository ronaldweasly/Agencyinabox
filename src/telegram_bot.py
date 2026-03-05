"""
telegram_bot.py — Telegram notification & approval messages (4 gates).

The bot is stateless — all state lives in Postgres.
This module only SENDS messages; callbacks are handled by the DMZ (dmz/main.py).

Fixes applied from PROBLEMS.md:
  P-18: Bot sends rich messages with inline keyboards; the DMZ answers callbacks.
"""
from __future__ import annotations

import logging
import os

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

log = logging.getLogger(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# Maximum message length for Telegram (4096, we use 3800 for safety)
MAX_MSG_LEN = 3800


async def _send_chunked(
    text: str,
    keyboard: InlineKeyboardMarkup | None = None,
    parse_mode: str = "Markdown",
) -> None:
    """
    Send a Telegram message, chunking if over MAX_MSG_LEN.
    Keyboard is attached only to the LAST chunk.
    """
    bot = Bot(token=BOT_TOKEN)
    chunks = [text[i : i + MAX_MSG_LEN] for i in range(0, len(text), MAX_MSG_LEN)]
    for i, chunk in enumerate(chunks):
        kb = keyboard if i == len(chunks) - 1 else None
        await bot.send_message(
            chat_id=CHAT_ID,
            text=chunk,
            parse_mode=parse_mode,
            reply_markup=kb,
            disable_web_page_preview=True,
        )


# ── Gate 1: Lead Approval ───────────────────────────────────────────────────

async def send_lead_approval(lead: dict) -> None:
    """
    Gate 1: Send lead approval message with ICP score and AI reasoning.
    Buttons: Approve / Reject
    """
    text = (
        f"*🎯 NEW LEAD — Score: {lead['icp_score']}/100*\n\n"
        f"Company: {lead.get('company_name', 'Unknown')}\n"
        f"Website: {lead.get('website', 'N/A')}\n"
        f"Contact: {lead.get('contact_email', 'N/A')}\n\n"
        f"*AI Reasoning:*\n{lead.get('icp_reasoning', 'N/A')[:400]}"
    )
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Approve", callback_data=f"LEAD_APPROVE:{lead['id']}"
                ),
                InlineKeyboardButton(
                    "❌ Reject", callback_data=f"LEAD_REJECT:{lead['id']}"
                ),
            ]
        ]
    )
    await _send_chunked(text, keyboard)


# ── Gate 2: Reply Approval ───────────────────────────────────────────────────

async def send_reply_approval(lead: dict, their_reply: str, ai_draft: str) -> None:
    """
    Gate 2: Lead replied to cold email. Show their reply + AI-drafted response.
    Buttons: Send / Edit / Reject & Re-draft
    """
    text = (
        f"*💬 REPLY — {lead.get('company_name', 'Unknown')}*\n\n"
        f"*Their message:*\n{their_reply[:500]}\n\n"
        f"*AI draft response:*\n{ai_draft[:500]}"
    )
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Send", callback_data=f"REPLY_SEND:{lead['id']}"
                ),
                InlineKeyboardButton(
                    "✏️ Edit", callback_data=f"REPLY_EDIT:{lead['id']}"
                ),
                InlineKeyboardButton(
                    "❌ Reject", callback_data=f"REPLY_REJECT:{lead['id']}"
                ),
            ]
        ]
    )
    await _send_chunked(text, keyboard)


# ── Gate 3: Deal Brief Approval ─────────────────────────────────────────────

async def send_deal_approval(project: dict) -> None:
    """
    Gate 3: Lead qualified as opportunity. Show structured brief.
    Buttons: Start Build / Modify Brief / Decline
    """
    text = (
        f"*📋 DEAL BRIEF*\n\n"
        f"Deliverable: {project.get('deliverable', 'N/A')}\n"
        f"Tech Stack: {project.get('tech_stack', 'N/A')}\n"
        f"Acceptance Criteria:\n"
    )
    criteria = project.get("acceptance_criteria", [])
    if isinstance(criteria, list):
        for c in criteria[:10]:
            text += f"  • {c}\n"
    elif isinstance(criteria, dict):
        for k, v in list(criteria.items())[:10]:
            text += f"  • {k}: {v}\n"

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Start Build",
                    callback_data=f"DEAL_APPROVE:{project['id']}",
                ),
                InlineKeyboardButton(
                    "❌ Decline",
                    callback_data=f"DEAL_REJECT:{project['id']}",
                ),
            ]
        ]
    )
    await _send_chunked(text, keyboard)


# ── Gate 4: Code Review Approval ────────────────────────────────────────────

async def send_code_review(
    project: dict, pr_url: str, qa_summary: dict
) -> None:
    """
    Gate 4: Code passed all automated QA. Show results + PR link.
    Buttons: Approve & Merge / Reject & Re-roll
    """
    score_emoji = "✅" if qa_summary.get("all_passed") else "⚠️"
    text = (
        f"*{score_emoji} CODE REVIEW READY*\n"
        f"Project: {project.get('deliverable', 'N/A')}\n\n"
        f"*QA Results*\n"
        f"Tests: {qa_summary.get('passed', 0)}/{qa_summary.get('total', 0)} passed\n"
        f"Coverage: {qa_summary.get('coverage', 0):.0f}%\n"
        f"Security: {qa_summary.get('bandit_findings', 0)} findings\n"
        f"Critic: {qa_summary.get('critic_verdict', 'N/A')}\n\n"
        f"*Scores*\n"
        f"Correctness: {qa_summary.get('correctness', 0)}/100\n"
        f"Security: {qa_summary.get('security', 0)}/100\n"
        f"Maintainability: {qa_summary.get('maintainability', 0)}/100\n\n"
        f"[View PR on GitHub]({pr_url})"
    )

    repo = project["github_repo"]
    pr_num = project["github_pr_number"]
    job_id = project["job_id"]

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Approve & Merge",
                    callback_data=f"APPROVE_PR:{repo}:{pr_num}",
                ),
                InlineKeyboardButton(
                    "❌ Reject & Re-roll",
                    callback_data=f"REJECT_PR:{repo}:{pr_num}:{job_id}",
                ),
            ]
        ]
    )
    await _send_chunked(text, keyboard)


# ── Alerts (DLQ, GDPR cron failure, etc.) ────────────────────────────────────

async def send_alert(alert_type: str, message: str) -> None:
    """Send a plain alert notification (no buttons)."""
    emoji = {"DLQ": "🚨", "GDPR": "⚖️", "BUDGET": "💰"}.get(alert_type, "⚠️")
    text = f"*{emoji} {alert_type} ALERT*\n\n{message[:3000]}"
    await _send_chunked(text)

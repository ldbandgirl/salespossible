"""
Email tool — draft and optionally send emails via SMTP.

email_draft: returns a formatted draft for review (no sending)
email_send:  actually sends via aiosmtplib (requires SMTP config in .env)
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

EMAIL_DRAFT_SCHEMA: dict[str, Any] = {
    "name": "email_draft",
    "description": (
        "Draft a professional sales email. Returns the formatted email for review. "
        "Does NOT send — use email_send after user approval."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "to": {
                "type": "string",
                "description": "Recipient email address",
            },
            "subject": {"type": "string"},
            "body": {
                "type": "string",
                "description": "Email body (plain text or Markdown)",
            },
            "tone": {
                "type": "string",
                "enum": ["professional", "warm", "direct", "follow_up"],
                "default": "professional",
            },
            "cc": {"type": "string", "description": "CC addresses (comma-separated)"},
        },
        "required": ["to", "subject", "body"],
    },
}

EMAIL_SEND_SCHEMA: dict[str, Any] = {
    "name": "email_send",
    "description": (
        "Send an email via SMTP. Requires SMTP_* environment variables to be configured. "
        "Only use after explicit user approval."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "to": {"type": "string"},
            "subject": {"type": "string"},
            "body": {"type": "string"},
            "cc": {"type": "string"},
        },
        "required": ["to", "subject", "body"],
    },
}


async def email_draft(inputs: dict[str, Any]) -> str:
    """Format an email draft for review."""
    to = inputs["to"]
    subject = inputs["subject"]
    body = inputs["body"]
    cc = inputs.get("cc", "")
    tone = inputs.get("tone", "professional")

    draft = f"""
EMAIL DRAFT ({tone.upper()})
────────────────────────────────────────
To:      {to}
{f'CC:      {cc}' if cc else ''}
Subject: {subject}
────────────────────────────────────────

{body}

────────────────────────────────────────
[Draft only — not sent. Approve to send with email_send tool.]
""".strip()

    return draft


async def email_send(inputs: dict[str, Any]) -> str:
    """Send an email via SMTP."""
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USERNAME", "")
    smtp_pass = os.environ.get("SMTP_PASSWORD", "")
    smtp_from = os.environ.get("SMTP_FROM", smtp_user)

    if not all([smtp_host, smtp_user, smtp_pass]):
        return (
            "SMTP not configured. Set SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD in .env"
        )

    to = inputs["to"]
    subject = inputs["subject"]
    body = inputs["body"]
    cc = inputs.get("cc", "")

    try:
        import aiosmtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart()
        msg["From"] = smtp_from
        msg["To"] = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc

        msg.attach(MIMEText(body, "plain"))

        recipients = [to] + ([c.strip() for c in cc.split(",")] if cc else [])

        await aiosmtplib.send(
            msg,
            hostname=smtp_host,
            port=smtp_port,
            username=smtp_user,
            password=smtp_pass,
            start_tls=True,
            recipients=recipients,
        )

        logger.info("Email sent to %s: %s", to, subject)
        return f"Email sent successfully to {to}: '{subject}'"

    except ImportError:
        return "aiosmtplib not installed. Run: pip install aiosmtplib"
    except Exception as e:
        logger.error("Email send error: %s", e)
        return f"Email failed: {e}"

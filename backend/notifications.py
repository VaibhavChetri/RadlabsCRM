"""
notifications.py
----------------
Sends the "You have a new lead!" email to a client when a new lead arrives.

Design choices (matching the senior's checklist):
  * Credentials come from .env — never hardcoded.
  * DRY-RUN: if SMTP_USER/SMTP_PASSWORD aren't filled in, we just PRINT the
    email instead of sending. Lets you build/test without real credentials.
  * SAFE: `notify_new_lead()` swallows and logs any error, so a mail failure
    can NEVER break the lead-saving flow.

Configured for Microsoft 365 / Outlook: smtp.office365.com, port 587, STARTTLS.
"""

import os
import smtplib
import logging
from email.message import EmailMessage

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("notifications")

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.office365.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
# Who the email appears to be "from". Defaults to the login user.
SMTP_FROM = os.getenv("SMTP_FROM") or SMTP_USER


def _build_message(to_email: str, lead_name: str, lead_message: str) -> EmailMessage:
    """Compose the actual email object."""
    msg = EmailMessage()
    msg["Subject"] = "You have a new lead!"
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    body = (
        f"You've received a new lead.\n\n"
        f"Name:    {lead_name}\n"
        f"Message: {lead_message or '(no message)'}\n\n"
        f"Log in to your dashboard to see the full details.\n"
        f"— Lead Management System"
    )
    msg.set_content(body)
    return msg


def send_new_lead_email(to_email: str, lead_name: str, lead_message: str) -> None:
    """
    Actually send the email. Raises on failure (caught by notify_new_lead).
    If SMTP credentials aren't configured, runs in DRY-RUN mode and only prints.
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        # ---- DRY RUN: not configured yet, so just show what we WOULD send ----
        # flush=True forces it to appear immediately in the server console.
        print(
            "\n" + "=" * 60 + "\n"
            "[EMAIL DRY-RUN] SMTP not configured (fill .env to send for real)\n"
            f"  To:      {to_email}\n"
            f"  Subject: You have a new lead!\n"
            f"  Lead:    {lead_name} — {lead_message or '(no message)'}\n"
            + "=" * 60,
            flush=True,
        )
        return

    # ---- REAL SEND via Outlook/365 over STARTTLS ----
    msg = _build_message(to_email, lead_name, lead_message)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
        server.starttls()                       # upgrade the connection to encrypted
        server.login(SMTP_USER, SMTP_PASSWORD)  # sign in to the mailbox
        server.send_message(msg)                # deliver it
    print(f"[EMAIL SENT] new-lead notification delivered to {to_email}", flush=True)
    logger.info("New-lead email sent to %s", to_email)


def notify_new_lead(to_email: str, lead_name: str, lead_message: str) -> None:
    """
    SAFE wrapper used by the API. Never raises — if sending fails, it just logs
    the problem so the lead (already saved) is never affected.
    """
    try:
        send_new_lead_email(to_email, lead_name, lead_message)
    except Exception as exc:  # noqa: BLE001 (we deliberately catch everything)
        logger.warning("Could not send new-lead email to %s: %s", to_email, exc)

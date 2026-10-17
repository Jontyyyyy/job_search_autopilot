"""
Connects to Gmail over IMAP (free, no API key -- just your email + an
"App Password") and fetches recent emails for classification.

Setup (free, ~2 minutes):
1. Go to your Google Account -> Security -> 2-Step Verification (turn it on
   if it isn't already -- required for app passwords)
2. Security -> App passwords -> create one for "Mail"
3. Google gives you a 16-character password like "abcd efgh ijkl mnop"
4. Put your email and that app password in .env as GMAIL_ADDRESS and
   GMAIL_APP_PASSWORD -- never use your real Google password here.

This module only reads your inbox (read-only IMAP session). It never
sends, deletes, or modifies anything.
"""
from __future__ import annotations

import imaplib
import logging
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv

from email_tracking.parser import ParsedEmail, parse_raw_email

load_dotenv()

logger = logging.getLogger(__name__)

GMAIL_IMAP_HOST = "imap.gmail.com"


class GmailClient:
    def __init__(self, address: str | None = None, app_password: str | None = None):
        self.address = address or os.environ.get("GMAIL_ADDRESS")
        self.app_password = app_password or os.environ.get("GMAIL_APP_PASSWORD")

    @property
    def is_configured(self) -> bool:
        return bool(self.address) and bool(self.app_password)

    def fetch_recent_emails(self, since_days: int = 1, limit: int = 50) -> list[ParsedEmail]:
        """Fetches emails received in the last `since_days` days, newest
        first, up to `limit`. Returns an empty list (never raises) if not
        configured or the connection fails -- so one Gmail outage never
        crashes the whole agent."""
        if not self.is_configured:
            logger.warning("GMAIL_ADDRESS or GMAIL_APP_PASSWORD not set in .env.")
            return []

        try:
            return self._fetch(since_days, limit)
        except Exception as exc:
            logger.error("Gmail fetch failed: %s", exc)
            return []

    def _fetch(self, since_days: int, limit: int) -> list[ParsedEmail]:
        imap = imaplib.IMAP4_SSL(GMAIL_IMAP_HOST)
        try:
            imap.login(self.address, self.app_password)
            imap.select("INBOX", readonly=True)  # read-only: never modifies your inbox

            since_date = (datetime.now() - timedelta(days=since_days)).strftime("%d-%b-%Y")
            status, data = imap.search(None, f'(SINCE "{since_date}")')
            if status != "OK":
                return []

            message_ids = data[0].split()
            message_ids = message_ids[-limit:]  # most recent `limit` emails

            emails = []
            for msg_id in reversed(message_ids):  # newest first
                status, msg_data = imap.fetch(msg_id, "(RFC822)")
                if status != "OK" or not msg_data or msg_data[0] is None:
                    continue
                raw_bytes = msg_data[0][1]
                emails.append(parse_raw_email(raw_bytes))
            return emails
        finally:
            try:
                imap.close()
            except Exception:
                pass
            imap.logout()

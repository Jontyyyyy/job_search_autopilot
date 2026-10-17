"""
Parses a raw RFC822 email (the bytes IMAP gives you) into a clean,
structured ParsedEmail -- plain text body, subject, sender, date -- so the
classifier and job-linking logic never touch MIME/encoding details.

Uses Python's built-in `email` package (stdlib). This only works correctly
because our own package is named `email_tracking`, not `email` -- naming it
`email` would shadow the standard library module these functions need.
"""
from __future__ import annotations

import email
import re
from dataclasses import dataclass
from email.header import decode_header
from email.message import Message


@dataclass
class ParsedEmail:
    sender: str
    subject: str
    body: str           # plain text, HTML stripped if that's all that was available
    date: str
    message_id: str


def _decode_header_value(raw_value: str | None) -> str:
    if not raw_value:
        return ""
    parts = decode_header(raw_value)
    decoded = []
    for text, encoding in parts:
        if isinstance(text, bytes):
            decoded.append(text.decode(encoding or "utf-8", errors="replace"))
        else:
            decoded.append(text)
    return "".join(decoded)


def _strip_html(html: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_body(msg: Message) -> str:
    """Prefers plain text; falls back to stripped HTML if that's all there is."""
    if msg.is_multipart():
        plain_parts = []
        html_parts = []
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition:
                continue
            try:
                payload = part.get_payload(decode=True)
            except Exception:
                continue
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace")
            if content_type == "text/plain":
                plain_parts.append(text)
            elif content_type == "text/html":
                html_parts.append(text)
        if plain_parts:
            return "\n".join(plain_parts).strip()
        if html_parts:
            return _strip_html("\n".join(html_parts))
        return ""
    else:
        try:
            payload = msg.get_payload(decode=True)
        except Exception:
            payload = None
        if payload is None:
            return str(msg.get_payload())
        charset = msg.get_content_charset() or "utf-8"
        text = payload.decode(charset, errors="replace")
        if msg.get_content_type() == "text/html":
            return _strip_html(text)
        return text.strip()


def parse_raw_email(raw_bytes: bytes) -> ParsedEmail:
    """Parses raw RFC822 email bytes (as returned by IMAP FETCH) into a
    ParsedEmail. Never raises on malformed input -- returns best-effort
    empty fields rather than crashing the whole fetch loop."""
    try:
        msg = email.message_from_bytes(raw_bytes)
    except Exception:
        return ParsedEmail(sender="", subject="", body="", date="", message_id="")

    sender = _decode_header_value(msg.get("From", ""))
    subject = _decode_header_value(msg.get("Subject", ""))
    date = msg.get("Date", "") or ""
    message_id = msg.get("Message-ID", "") or ""
    body = _extract_body(msg)

    return ParsedEmail(sender=sender, subject=subject, body=body, date=date, message_id=message_id)

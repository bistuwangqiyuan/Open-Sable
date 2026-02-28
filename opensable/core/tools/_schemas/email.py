"""
Tool schemas for Email domain.
"""

SCHEMAS = [
    # ── Email tools (SMTP/IMAP) ──────────────────
    {
    "type": "function",
    "function": {
    "name": "email_send",
    "description": "Send an email via SMTP. Requires SMTP_HOST, SMTP_USER, SMTP_PASSWORD in .env",
    "parameters": {
    "type": "object",
    "properties": {
    "to": {"type": "string", "description": "Recipient email address"},
    "subject": {"type": "string", "description": "Email subject line"},
    "body": {"type": "string", "description": "Email body text"},
    "cc": {"type": "string", "description": "CC recipients (comma-separated, optional)"},
    "attachments": {"type": "array", "items": {"type": "string"}, "description": "File paths to attach (optional)"},
    },
    "required": ["to", "subject", "body"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "email_read",
    "description": "Read recent emails via IMAP. Requires IMAP_HOST, IMAP_USER, IMAP_PASSWORD in .env",
    "parameters": {
    "type": "object",
    "properties": {
    "count": {"type": "integer", "description": "Number of recent emails to fetch (default: 5)"},
    "folder": {"type": "string", "description": "Mailbox folder (default: INBOX)"},
    "unread_only": {"type": "boolean", "description": "Only fetch unread emails (default: false)"},
    },
    "required": [],
    },
    },
    },

]

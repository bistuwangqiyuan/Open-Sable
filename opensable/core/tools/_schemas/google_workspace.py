"""
Tool schemas for Google Workspace domain (via gws CLI).
Covers Gmail, Drive, Calendar, Sheets, Docs, Chat, and a raw fallback.
"""

SCHEMAS = [
    # ── Gmail ─────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "gws_gmail_list",
            "description": "List or search Gmail messages. Supports Gmail search syntax (from:, to:, subject:, has:attachment, newer_than:, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Gmail search query (e.g. 'from:boss@company.com is:unread')"},
                    "max_results": {"type": "integer", "description": "Maximum messages to return (default 10)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gws_gmail_get",
            "description": "Read a specific Gmail message by its ID. Returns full headers, body text, and attachment list.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string", "description": "Gmail message ID"},
                    "format": {"type": "string", "enum": ["full", "metadata", "minimal"], "description": "Response detail level"},
                },
                "required": ["message_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gws_gmail_send",
            "description": "Send an email via Gmail. Supports To, CC, BCC, subject, and plain-text body.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string", "description": "Email subject line"},
                    "body": {"type": "string", "description": "Email body (plain text)"},
                    "cc": {"type": "string", "description": "CC recipients (comma-separated)"},
                    "bcc": {"type": "string", "description": "BCC recipients (comma-separated)"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
    # ── Google Drive ──────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "gws_drive_list",
            "description": "List files in Google Drive, optionally filtered. Returns names, types, sizes, and links.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Drive search query (e.g. 'name contains \"report\"')"},
                    "page_size": {"type": "integer", "description": "Max results (default 20)"},
                    "order_by": {"type": "string", "description": "Sort order (default 'modifiedTime desc')"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gws_drive_get",
            "description": "Get metadata for a specific Google Drive file by ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "Google Drive file ID"},
                },
                "required": ["file_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gws_drive_search",
            "description": "Search Google Drive by file name or content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term (matches file name and full text)"},
                    "page_size": {"type": "integer", "description": "Max results (default 20)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gws_drive_upload",
            "description": "Upload a local file to Google Drive.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Absolute path to the local file to upload"},
                    "name": {"type": "string", "description": "Name in Drive (defaults to local filename)"},
                    "parent_id": {"type": "string", "description": "Parent folder ID in Drive"},
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gws_drive_create",
            "description": "Create a new file (Doc, Sheet, Folder, etc.) in Google Drive.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "File name"},
                    "mime_type": {
                        "type": "string",
                        "description": "MIME type (e.g. application/vnd.google-apps.document, application/vnd.google-apps.spreadsheet, application/vnd.google-apps.folder)",
                    },
                    "parent_id": {"type": "string", "description": "Parent folder ID"},
                },
                "required": ["name"],
            },
        },
    },
    # ── Google Calendar ───────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "gws_calendar_list",
            "description": "List upcoming events from Google Calendar. Supports time range filtering.",
            "parameters": {
                "type": "object",
                "properties": {
                    "calendar_id": {"type": "string", "description": "Calendar ID (default: primary)"},
                    "max_results": {"type": "integer", "description": "Max events to return (default 10)"},
                    "time_min": {"type": "string", "description": "Start of time range (ISO 8601, e.g. 2025-01-20T00:00:00Z)"},
                    "time_max": {"type": "string", "description": "End of time range (ISO 8601)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gws_calendar_create",
            "description": "Create a new Google Calendar event with optional attendees and location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Event title"},
                    "start": {"type": "string", "description": "Start datetime (ISO 8601, e.g. 2025-01-20T10:00:00+03:00)"},
                    "end": {"type": "string", "description": "End datetime (ISO 8601)"},
                    "description": {"type": "string", "description": "Event description"},
                    "location": {"type": "string", "description": "Event location"},
                    "attendees": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Email addresses of attendees",
                    },
                    "calendar_id": {"type": "string", "description": "Calendar ID (default: primary)"},
                },
                "required": ["summary", "start", "end"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gws_calendar_delete",
            "description": "Delete a Google Calendar event by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "ID of the event to delete"},
                    "calendar_id": {"type": "string", "description": "Calendar ID (default: primary)"},
                },
                "required": ["event_id"],
            },
        },
    },
    # ── Google Sheets ─────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "gws_sheets_get",
            "description": "Read data from a Google Sheets spreadsheet. Can read the full sheet or a specific range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "spreadsheet_id": {"type": "string", "description": "Spreadsheet ID from the URL"},
                    "range": {"type": "string", "description": "Cell range in A1 notation (e.g. 'Sheet1!A1:D10'). Omit to get spreadsheet metadata."},
                },
                "required": ["spreadsheet_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gws_sheets_write",
            "description": "Write data to a Google Sheets spreadsheet at a specific range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "spreadsheet_id": {"type": "string", "description": "Spreadsheet ID"},
                    "range": {"type": "string", "description": "Target range in A1 notation (e.g. 'Sheet1!A1')"},
                    "values": {
                        "type": "array",
                        "description": "2D array of values — each inner array is a row",
                        "items": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "required": ["spreadsheet_id", "range", "values"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gws_sheets_create",
            "description": "Create a new blank Google Sheets spreadsheet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Spreadsheet title"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gws_sheets_append",
            "description": "Append rows to the end of a Google Sheet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "spreadsheet_id": {"type": "string", "description": "Spreadsheet ID"},
                    "range": {"type": "string", "description": "Target range (e.g. 'Sheet1!A:D')"},
                    "values": {
                        "type": "array",
                        "description": "2D array of values to append",
                        "items": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "required": ["spreadsheet_id", "range", "values"],
            },
        },
    },
    # ── Google Docs ───────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "gws_docs_get",
            "description": "Read the content of a Google Doc by ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {"type": "string", "description": "Google Doc document ID"},
                },
                "required": ["document_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gws_docs_create",
            "description": "Create a new blank Google Doc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Document title"},
                },
                "required": ["title"],
            },
        },
    },
    # ── Google Chat ───────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "gws_chat_send",
            "description": "Send a message to a Google Chat space.",
            "parameters": {
                "type": "object",
                "properties": {
                    "space": {"type": "string", "description": "Space resource name (e.g. spaces/AAAA...)"},
                    "text": {"type": "string", "description": "Message text"},
                },
                "required": ["space", "text"],
            },
        },
    },
    # ── Raw / generic command ─────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "gws_raw_command",
            "description": "Execute any arbitrary Google Workspace CLI command. Use when the specific tool you need isn't available above. The argument is everything after 'gws', e.g. 'admin users list --params {\"domain\":\"example.com\"}'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Full gws CLI arguments (e.g. 'drive files list --params {\"q\":\"...\"}')"},
                },
                "required": ["command"],
            },
        },
    },
    # ── Auth check ────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "gws_auth_status",
            "description": "Check if Google Workspace authentication is configured and valid.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]

"""
Google Workspace Skill — Drive, Gmail, Calendar, Sheets, Docs, Chat via `gws` CLI.

Wraps the Google Workspace CLI (https://github.com/googleworkspace/cli) to give
Sable full access to Google Workspace APIs with structured JSON output.

Setup:
    1. Install the CLI:  npm install -g @googleworkspace/cli
    2. Authenticate:     gws auth setup   (or gws auth login)
    3. (Optional) Set in .env:
         GOOGLE_WORKSPACE_CLI_TOKEN=...       (pre-obtained access token)
         GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE=...  (service account JSON)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class GWSResult:
    """Standardized result from a Google Workspace operation."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    raw: Optional[str] = None

    def to_str(self) -> str:
        if self.success:
            if isinstance(self.data, dict):
                return json.dumps(self.data, indent=2, default=str)
            elif isinstance(self.data, list):
                return json.dumps(self.data, indent=2, default=str)
            return str(self.data) if self.data else "✅ Success"
        return f"❌ {self.error or 'Unknown error'}"


class GoogleWorkspaceSkill:
    """
    Google Workspace API integration via the `gws` CLI.

    Provides typed methods for the most common operations across:
    - Gmail (read, send, search, labels)
    - Google Drive (list, upload, download, share)
    - Google Calendar (list events, create, delete)
    - Google Sheets (read, write, create)
    - Google Docs (create, read)
    - Google Chat (send messages)

    Falls back to subprocess calls; all output is structured JSON.
    """

    def __init__(self, config):
        self.config = config
        self._gws_path: Optional[str] = None
        self._available = False
        self._checked = False

    def is_available(self) -> bool:
        """Check if gws CLI is installed and accessible."""
        if not self._checked:
            self._gws_path = shutil.which("gws")
            self._available = self._gws_path is not None
            self._checked = True
            if not self._available:
                logger.info("gws CLI not found. Install with: npm install -g @googleworkspace/cli")
        return self._available

    async def _run(self, args: List[str], timeout: int = 60) -> GWSResult:
        """Run a gws CLI command and return parsed JSON result."""
        if not self.is_available():
            return GWSResult(
                success=False,
                error="gws CLI not installed. Install with: npm install -g @googleworkspace/cli"
            )

        cmd = [self._gws_path] + args
        logger.info(f"[GWS] Running: gws {' '.join(args)}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )

            stdout_text = stdout.decode("utf-8", errors="replace").strip()
            stderr_text = stderr.decode("utf-8", errors="replace").strip()

            if proc.returncode != 0:
                # gws outputs structured JSON errors too
                error_msg = stderr_text or stdout_text or f"Exit code {proc.returncode}"
                # Try to parse JSON error
                try:
                    err_data = json.loads(error_msg)
                    msg = err_data.get("error", {}).get("message", error_msg)
                    return GWSResult(success=False, error=msg, raw=error_msg)
                except json.JSONDecodeError:
                    return GWSResult(success=False, error=error_msg, raw=error_msg)

            # Parse JSON output (gws always outputs JSON)
            if not stdout_text:
                return GWSResult(success=True, data=None)
            try:
                data = json.loads(stdout_text)
                return GWSResult(success=True, data=data, raw=stdout_text)
            except json.JSONDecodeError:
                # NDJSON (paginated)? Try parsing line-by-line
                lines = stdout_text.strip().splitlines()
                parsed = []
                for line in lines:
                    try:
                        parsed.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
                if parsed:
                    return GWSResult(success=True, data=parsed, raw=stdout_text)
                return GWSResult(success=True, data=stdout_text, raw=stdout_text)

        except asyncio.TimeoutError:
            return GWSResult(success=False, error=f"Command timed out after {timeout}s")
        except FileNotFoundError:
            self._available = False
            return GWSResult(
                success=False,
                error="gws CLI not found. Install with: npm install -g @googleworkspace/cli"
            )
        except Exception as e:
            return GWSResult(success=False, error=str(e))

    # ── Auth ──────────────────────────────────────────────────────────────

    async def auth_status(self) -> GWSResult:
        """Check authentication status."""
        return await self._run(["auth", "status"])

    # ── Gmail ─────────────────────────────────────────────────────────────

    async def gmail_list(
        self,
        query: str = "",
        max_results: int = 10,
        label_ids: Optional[List[str]] = None,
    ) -> GWSResult:
        """List Gmail messages, optionally filtered by query."""
        params: Dict[str, Any] = {"maxResults": max_results}
        if query:
            params["q"] = query
        if label_ids:
            params["labelIds"] = label_ids
        return await self._run([
            "gmail", "users", "messages", "list",
            "--params", json.dumps({"userId": "me", **params}),
        ])

    async def gmail_get(self, message_id: str, format: str = "full") -> GWSResult:
        """Get a specific Gmail message by ID."""
        return await self._run([
            "gmail", "users", "messages", "get",
            "--params", json.dumps({"userId": "me", "id": message_id, "format": format}),
        ])

    async def gmail_send(
        self,
        to: str,
        subject: str,
        body: str,
        cc: str = "",
        bcc: str = "",
    ) -> GWSResult:
        """Send an email via Gmail."""
        import base64
        headers = f"To: {to}\nSubject: {subject}\nContent-Type: text/plain; charset=utf-8\n"
        if cc:
            headers += f"Cc: {cc}\n"
        if bcc:
            headers += f"Bcc: {bcc}\n"
        raw_msg = headers + "\n" + body
        encoded = base64.urlsafe_b64encode(raw_msg.encode("utf-8")).decode("ascii")
        return await self._run([
            "gmail", "users", "messages", "send",
            "--params", json.dumps({"userId": "me"}),
            "--json", json.dumps({"raw": encoded}),
        ])

    async def gmail_search(self, query: str, max_results: int = 10) -> GWSResult:
        """Search Gmail messages."""
        return await self.gmail_list(query=query, max_results=max_results)

    # ── Google Drive ──────────────────────────────────────────────────────

    async def drive_list(
        self,
        query: str = "",
        page_size: int = 20,
        order_by: str = "modifiedTime desc",
    ) -> GWSResult:
        """List files in Google Drive."""
        params: Dict[str, Any] = {
            "pageSize": page_size,
            "orderBy": order_by,
            "fields": "files(id,name,mimeType,modifiedTime,size,webViewLink)",
        }
        if query:
            params["q"] = query
        return await self._run([
            "drive", "files", "list",
            "--params", json.dumps(params),
        ])

    async def drive_get(self, file_id: str) -> GWSResult:
        """Get metadata for a Drive file."""
        return await self._run([
            "drive", "files", "get",
            "--params", json.dumps({
                "fileId": file_id,
                "fields": "id,name,mimeType,modifiedTime,size,webViewLink,owners,permissions",
            }),
        ])

    async def drive_create(
        self,
        name: str,
        mime_type: str = "application/vnd.google-apps.document",
        parent_id: str = "",
        content: str = "",
    ) -> GWSResult:
        """Create a file in Google Drive."""
        body: Dict[str, Any] = {"name": name, "mimeType": mime_type}
        if parent_id:
            body["parents"] = [parent_id]
        args = [
            "drive", "files", "create",
            "--json", json.dumps(body),
        ]
        return await self._run(args)

    async def drive_upload(self, file_path: str, name: str = "", parent_id: str = "") -> GWSResult:
        """Upload a local file to Google Drive."""
        body: Dict[str, Any] = {"name": name or os.path.basename(file_path)}
        if parent_id:
            body["parents"] = [parent_id]
        return await self._run([
            "drive", "files", "create",
            "--json", json.dumps(body),
            "--upload", file_path,
        ], timeout=120)

    async def drive_search(self, query: str, page_size: int = 20) -> GWSResult:
        """Search for files in Google Drive by name or content."""
        # Wrap in Drive query syntax
        drive_query = f"name contains '{query}' or fullText contains '{query}'"
        return await self.drive_list(query=drive_query, page_size=page_size)

    # ── Google Calendar ───────────────────────────────────────────────────

    async def calendar_list_events(
        self,
        calendar_id: str = "primary",
        max_results: int = 10,
        time_min: str = "",
        time_max: str = "",
    ) -> GWSResult:
        """List upcoming calendar events."""
        from datetime import datetime, timezone
        params: Dict[str, Any] = {
            "calendarId": calendar_id,
            "maxResults": max_results,
            "singleEvents": True,
            "orderBy": "startTime",
        }
        if time_min:
            params["timeMin"] = time_min
        else:
            params["timeMin"] = datetime.now(timezone.utc).isoformat()
        if time_max:
            params["timeMax"] = time_max
        return await self._run([
            "calendar", "events", "list",
            "--params", json.dumps(params),
        ])

    async def calendar_create_event(
        self,
        summary: str,
        start: str,
        end: str,
        description: str = "",
        location: str = "",
        calendar_id: str = "primary",
        attendees: Optional[List[str]] = None,
    ) -> GWSResult:
        """Create a calendar event."""
        event: Dict[str, Any] = {
            "summary": summary,
            "start": {"dateTime": start},
            "end": {"dateTime": end},
        }
        if description:
            event["description"] = description
        if location:
            event["location"] = location
        if attendees:
            event["attendees"] = [{"email": e} for e in attendees]
        return await self._run([
            "calendar", "events", "insert",
            "--params", json.dumps({"calendarId": calendar_id}),
            "--json", json.dumps(event),
        ])

    async def calendar_delete_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
    ) -> GWSResult:
        """Delete a calendar event."""
        return await self._run([
            "calendar", "events", "delete",
            "--params", json.dumps({"calendarId": calendar_id, "eventId": event_id}),
        ])

    # ── Google Sheets ─────────────────────────────────────────────────────

    async def sheets_get(self, spreadsheet_id: str, range: str = "") -> GWSResult:
        """Read data from a Google Sheet."""
        if range:
            return await self._run([
                "sheets", "spreadsheets", "values", "get",
                "--params", json.dumps({
                    "spreadsheetId": spreadsheet_id,
                    "range": range,
                }),
            ])
        return await self._run([
            "sheets", "spreadsheets", "get",
            "--params", json.dumps({"spreadsheetId": spreadsheet_id}),
        ])

    async def sheets_create(self, title: str) -> GWSResult:
        """Create a new Google Sheets spreadsheet."""
        return await self._run([
            "sheets", "spreadsheets", "create",
            "--json", json.dumps({"properties": {"title": title}}),
        ])

    async def sheets_write(
        self,
        spreadsheet_id: str,
        range: str,
        values: List[List[str]],
    ) -> GWSResult:
        """Write data to a Google Sheet."""
        return await self._run([
            "sheets", "spreadsheets", "values", "update",
            "--params", json.dumps({
                "spreadsheetId": spreadsheet_id,
                "range": range,
                "valueInputOption": "USER_ENTERED",
            }),
            "--json", json.dumps({"values": values}),
        ])

    async def sheets_append(
        self,
        spreadsheet_id: str,
        range: str,
        values: List[List[str]],
    ) -> GWSResult:
        """Append rows to a Google Sheet."""
        return await self._run([
            "sheets", "spreadsheets", "values", "append",
            "--params", json.dumps({
                "spreadsheetId": spreadsheet_id,
                "range": range,
                "valueInputOption": "USER_ENTERED",
            }),
            "--json", json.dumps({"values": values}),
        ])

    # ── Google Docs ───────────────────────────────────────────────────────

    async def docs_get(self, document_id: str) -> GWSResult:
        """Get a Google Doc's content."""
        return await self._run([
            "docs", "documents", "get",
            "--params", json.dumps({"documentId": document_id}),
        ])

    async def docs_create(self, title: str) -> GWSResult:
        """Create a new Google Doc."""
        return await self._run([
            "docs", "documents", "create",
            "--json", json.dumps({"title": title}),
        ])

    # ── Google Chat ───────────────────────────────────────────────────────

    async def chat_send(self, space: str, text: str) -> GWSResult:
        """Send a message to a Google Chat space."""
        return await self._run([
            "chat", "spaces", "messages", "create",
            "--params", json.dumps({"parent": space}),
            "--json", json.dumps({"text": text}),
        ])

    # ── Generic / raw command ─────────────────────────────────────────────

    async def raw_command(self, args_str: str) -> GWSResult:
        """Execute any arbitrary gws CLI command. The input is the full
        argument string after ``gws``, e.g. ``drive files list --params '{...}'``."""
        import shlex
        try:
            args = shlex.split(args_str)
        except ValueError:
            args = args_str.split()
        return await self._run(args, timeout=120)

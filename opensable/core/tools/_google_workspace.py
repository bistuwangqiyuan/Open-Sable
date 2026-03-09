"""
Google Workspace tools — Gmail, Drive, Calendar, Sheets, Docs, Chat.

Provides tool handlers that delegate to GoogleWorkspaceSkill,
following the same mixin pattern as _github.py, _social.py, etc.
"""

import json
import logging
from typing import Dict

logger = logging.getLogger(__name__)

_NOT_CONFIGURED = (
    "❌ Google Workspace not configured.\n"
    "Install the CLI:  npm install -g @googleworkspace/cli\n"
    "Then authenticate: gws auth setup && gws auth login"
)


class GoogleWorkspaceToolsMixin:
    """Mixin providing Google Workspace tool implementations for ToolRegistry."""

    def _gws_available(self) -> bool:
        return self.gws_skill is not None and self.gws_skill.is_available()

    # ── Gmail ─────────────────────────────────────────────────────────────

    async def _gws_gmail_list_tool(self, params: Dict) -> str:
        if not self._gws_available():
            return _NOT_CONFIGURED
        result = await self.gws_skill.gmail_list(
            query=params.get("query", ""),
            max_results=params.get("max_results", 10),
        )
        if result.success:
            data = result.data
            if isinstance(data, dict):
                messages = data.get("messages", [])
                if not messages:
                    return "📭 No messages found."
                count = data.get("resultSizeEstimate", len(messages))
                lines = [f"📬 {count} messages:"]
                for m in messages[:20]:
                    lines.append(f"  • ID: {m.get('id', '?')} | Thread: {m.get('threadId', '?')}")
                return "\n".join(lines)
            return result.to_str()
        return f"❌ {result.error}"

    async def _gws_gmail_get_tool(self, params: Dict) -> str:
        if not self._gws_available():
            return _NOT_CONFIGURED
        result = await self.gws_skill.gmail_get(
            message_id=params.get("message_id", ""),
            format=params.get("format", "full"),
        )
        if result.success:
            data = result.data
            if isinstance(data, dict):
                headers = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}
                snippet = data.get("snippet", "")
                lines = [
                    f"📧 From: {headers.get('From', '?')}",
                    f"📅 Date: {headers.get('Date', '?')}",
                    f"📝 Subject: {headers.get('Subject', '?')}",
                    f"",
                    snippet[:2000],
                ]
                return "\n".join(lines)
            return result.to_str()
        return f"❌ {result.error}"

    async def _gws_gmail_send_tool(self, params: Dict) -> str:
        if not self._gws_available():
            return _NOT_CONFIGURED
        result = await self.gws_skill.gmail_send(
            to=params.get("to", ""),
            subject=params.get("subject", ""),
            body=params.get("body", ""),
            cc=params.get("cc", ""),
            bcc=params.get("bcc", ""),
        )
        if result.success:
            msg_id = result.data.get("id", "?") if isinstance(result.data, dict) else "?"
            return f"✅ Email sent (ID: {msg_id})"
        return f"❌ {result.error}"

    # ── Google Drive ──────────────────────────────────────────────────────

    async def _gws_drive_list_tool(self, params: Dict) -> str:
        if not self._gws_available():
            return _NOT_CONFIGURED
        result = await self.gws_skill.drive_list(
            query=params.get("query", ""),
            page_size=params.get("page_size", 20),
            order_by=params.get("order_by", "modifiedTime desc"),
        )
        if result.success:
            data = result.data
            if isinstance(data, dict):
                files = data.get("files", [])
                if not files:
                    return "📁 No files found."
                lines = [f"📁 {len(files)} files:"]
                for f in files:
                    size = f.get("size", "?")
                    lines.append(f"  📄 {f.get('name', '?')} ({f.get('mimeType', '?')}, {size} bytes)")
                    if f.get("webViewLink"):
                        lines.append(f"     🔗 {f['webViewLink']}")
                return "\n".join(lines)
            return result.to_str()
        return f"❌ {result.error}"

    async def _gws_drive_get_tool(self, params: Dict) -> str:
        if not self._gws_available():
            return _NOT_CONFIGURED
        result = await self.gws_skill.drive_get(file_id=params.get("file_id", ""))
        if result.success:
            data = result.data
            if isinstance(data, dict):
                lines = [
                    f"📄 {data.get('name', '?')}",
                    f"  Type: {data.get('mimeType', '?')}",
                    f"  Size: {data.get('size', '?')} bytes",
                    f"  Modified: {data.get('modifiedTime', '?')}",
                ]
                if data.get("webViewLink"):
                    lines.append(f"  🔗 {data['webViewLink']}")
                return "\n".join(lines)
            return result.to_str()
        return f"❌ {result.error}"

    async def _gws_drive_search_tool(self, params: Dict) -> str:
        if not self._gws_available():
            return _NOT_CONFIGURED
        result = await self.gws_skill.drive_search(
            query=params.get("query", ""),
            page_size=params.get("page_size", 20),
        )
        if result.success:
            data = result.data
            if isinstance(data, dict):
                files = data.get("files", [])
                if not files:
                    return f"🔍 No files matching '{params.get('query', '')}'"
                lines = [f"🔍 {len(files)} results for '{params.get('query', '')}':"]
                for f in files:
                    lines.append(f"  📄 {f.get('name', '?')} — {f.get('mimeType', '?')}")
                return "\n".join(lines)
            return result.to_str()
        return f"❌ {result.error}"

    async def _gws_drive_upload_tool(self, params: Dict) -> str:
        if not self._gws_available():
            return _NOT_CONFIGURED
        result = await self.gws_skill.drive_upload(
            file_path=params.get("file_path", ""),
            name=params.get("name", ""),
            parent_id=params.get("parent_id", ""),
        )
        if result.success:
            file_id = result.data.get("id", "?") if isinstance(result.data, dict) else "?"
            return f"✅ File uploaded to Drive (ID: {file_id})"
        return f"❌ {result.error}"

    async def _gws_drive_create_tool(self, params: Dict) -> str:
        if not self._gws_available():
            return _NOT_CONFIGURED
        result = await self.gws_skill.drive_create(
            name=params.get("name", ""),
            mime_type=params.get("mime_type", "application/vnd.google-apps.document"),
            parent_id=params.get("parent_id", ""),
        )
        if result.success:
            data = result.data
            file_id = data.get("id", "?") if isinstance(data, dict) else "?"
            return f"✅ Created '{params.get('name', '')}' in Drive (ID: {file_id})"
        return f"❌ {result.error}"

    # ── Google Calendar ───────────────────────────────────────────────────

    async def _gws_calendar_list_tool(self, params: Dict) -> str:
        if not self._gws_available():
            return _NOT_CONFIGURED
        result = await self.gws_skill.calendar_list_events(
            calendar_id=params.get("calendar_id", "primary"),
            max_results=params.get("max_results", 10),
            time_min=params.get("time_min", ""),
            time_max=params.get("time_max", ""),
        )
        if result.success:
            data = result.data
            if isinstance(data, dict):
                events = data.get("items", [])
                if not events:
                    return "📅 No upcoming events."
                lines = [f"📅 {len(events)} events:"]
                for ev in events:
                    start = ev.get("start", {}).get("dateTime", ev.get("start", {}).get("date", "?"))
                    lines.append(f"  🗓️ {ev.get('summary', 'No title')} — {start}")
                    if ev.get("location"):
                        lines.append(f"     📍 {ev['location']}")
                return "\n".join(lines)
            return result.to_str()
        return f"❌ {result.error}"

    async def _gws_calendar_create_tool(self, params: Dict) -> str:
        if not self._gws_available():
            return _NOT_CONFIGURED
        result = await self.gws_skill.calendar_create_event(
            summary=params.get("summary", ""),
            start=params.get("start", ""),
            end=params.get("end", ""),
            description=params.get("description", ""),
            location=params.get("location", ""),
            calendar_id=params.get("calendar_id", "primary"),
            attendees=params.get("attendees"),
        )
        if result.success:
            data = result.data
            link = data.get("htmlLink", "") if isinstance(data, dict) else ""
            return f"✅ Event '{params.get('summary', '')}' created\n🔗 {link}"
        return f"❌ {result.error}"

    async def _gws_calendar_delete_tool(self, params: Dict) -> str:
        if not self._gws_available():
            return _NOT_CONFIGURED
        result = await self.gws_skill.calendar_delete_event(
            event_id=params.get("event_id", ""),
            calendar_id=params.get("calendar_id", "primary"),
        )
        if result.success:
            return f"✅ Event deleted"
        return f"❌ {result.error}"

    # ── Google Sheets ─────────────────────────────────────────────────────

    async def _gws_sheets_get_tool(self, params: Dict) -> str:
        if not self._gws_available():
            return _NOT_CONFIGURED
        result = await self.gws_skill.sheets_get(
            spreadsheet_id=params.get("spreadsheet_id", ""),
            range=params.get("range", ""),
        )
        if result.success:
            data = result.data
            if isinstance(data, dict):
                values = data.get("values", [])
                if values:
                    lines = [f"📊 {len(values)} rows:"]
                    for i, row in enumerate(values[:30]):
                        lines.append(f"  {i+1}. {' | '.join(str(c) for c in row)}")
                    if len(values) > 30:
                        lines.append(f"  ... ({len(values) - 30} more rows)")
                    return "\n".join(lines)
                # Spreadsheet metadata
                title = data.get("properties", {}).get("title", "?")
                sheets = [s.get("properties", {}).get("title", "?") for s in data.get("sheets", [])]
                return f"📊 {title}\n  Sheets: {', '.join(sheets)}"
            return result.to_str()
        return f"❌ {result.error}"

    async def _gws_sheets_write_tool(self, params: Dict) -> str:
        if not self._gws_available():
            return _NOT_CONFIGURED
        result = await self.gws_skill.sheets_write(
            spreadsheet_id=params.get("spreadsheet_id", ""),
            range=params.get("range", ""),
            values=params.get("values", []),
        )
        if result.success:
            data = result.data
            cells = data.get("updatedCells", "?") if isinstance(data, dict) else "?"
            return f"✅ Updated {cells} cells"
        return f"❌ {result.error}"

    async def _gws_sheets_create_tool(self, params: Dict) -> str:
        if not self._gws_available():
            return _NOT_CONFIGURED
        result = await self.gws_skill.sheets_create(title=params.get("title", ""))
        if result.success:
            data = result.data
            sid = data.get("spreadsheetId", "?") if isinstance(data, dict) else "?"
            url = data.get("spreadsheetUrl", "") if isinstance(data, dict) else ""
            return f"✅ Spreadsheet '{params.get('title', '')}' created (ID: {sid})\n🔗 {url}"
        return f"❌ {result.error}"

    async def _gws_sheets_append_tool(self, params: Dict) -> str:
        if not self._gws_available():
            return _NOT_CONFIGURED
        result = await self.gws_skill.sheets_append(
            spreadsheet_id=params.get("spreadsheet_id", ""),
            range=params.get("range", ""),
            values=params.get("values", []),
        )
        if result.success:
            data = result.data
            rows = data.get("updates", {}).get("updatedRows", "?") if isinstance(data, dict) else "?"
            return f"✅ Appended {rows} rows"
        return f"❌ {result.error}"

    # ── Google Docs ───────────────────────────────────────────────────────

    async def _gws_docs_get_tool(self, params: Dict) -> str:
        if not self._gws_available():
            return _NOT_CONFIGURED
        result = await self.gws_skill.docs_get(document_id=params.get("document_id", ""))
        if result.success:
            data = result.data
            if isinstance(data, dict):
                title = data.get("title", "?")
                # Extract plain text from document body
                body = data.get("body", {})
                text_parts = []
                for elem in body.get("content", []):
                    para = elem.get("paragraph", {})
                    for el in para.get("elements", []):
                        tr = el.get("textRun", {})
                        if tr.get("content"):
                            text_parts.append(tr["content"])
                text = "".join(text_parts)[:3000]
                return f"📝 {title}\n\n{text}"
            return result.to_str()
        return f"❌ {result.error}"

    async def _gws_docs_create_tool(self, params: Dict) -> str:
        if not self._gws_available():
            return _NOT_CONFIGURED
        result = await self.gws_skill.docs_create(title=params.get("title", ""))
        if result.success:
            data = result.data
            doc_id = data.get("documentId", "?") if isinstance(data, dict) else "?"
            return f"✅ Doc '{params.get('title', '')}' created (ID: {doc_id})"
        return f"❌ {result.error}"

    # ── Google Chat ───────────────────────────────────────────────────────

    async def _gws_chat_send_tool(self, params: Dict) -> str:
        if not self._gws_available():
            return _NOT_CONFIGURED
        result = await self.gws_skill.chat_send(
            space=params.get("space", ""),
            text=params.get("text", ""),
        )
        if result.success:
            return f"✅ Message sent to {params.get('space', '?')}"
        return f"❌ {result.error}"

    # ── Raw command ───────────────────────────────────────────────────────

    async def _gws_raw_command_tool(self, params: Dict) -> str:
        if not self._gws_available():
            return _NOT_CONFIGURED
        result = await self.gws_skill.raw_command(params.get("command", ""))
        return result.to_str()

    # ── Auth status ───────────────────────────────────────────────────────

    async def _gws_auth_status_tool(self, params: Dict) -> str:
        if not self._gws_available():
            return _NOT_CONFIGURED
        result = await self.gws_skill.auth_status()
        if result.success:
            return f"✅ Google Workspace authenticated\n{result.to_str()}"
        return f"⚠️ Auth issue: {result.error}\nRun: gws auth setup && gws auth login"

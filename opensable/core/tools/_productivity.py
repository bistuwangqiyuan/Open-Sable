"""
Productivity tools — documents, email, calendar, clipboard, OCR
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


class ProductivityToolsMixin:
    """Mixin providing productivity tools — documents, email, calendar, clipboard, ocr tool implementations."""

    # ========== DOCUMENT TOOLS ==========

    async def _create_document_tool(self, params: Dict) -> str:
        """Create a Word document"""
        result = await self.document_skill.create_word(
            filename=params.get("filename", "document.docx"),
            title=params.get("title", ""),
            content=params.get("content", ""),
            paragraphs=params.get("paragraphs"),
            table_data=params.get("table_data"),
            output_dir=params.get("output_dir"),
        )
        if result.get("success"):
            return f"📄 Word document created: **{result['path']}**"
        return f"❌ {result.get('error')}"

    async def _create_spreadsheet_tool(self, params: Dict) -> str:
        """Create an Excel spreadsheet"""
        result = await self.document_skill.create_spreadsheet(
            filename=params.get("filename", "spreadsheet.xlsx"),
            data=params.get("data"),
            headers=params.get("headers"),
            sheets=params.get("sheets"),
            output_dir=params.get("output_dir"),
        )
        if result.get("success"):
            sheets = result.get("sheets", [])
            return f"📊 Spreadsheet created: **{result['path']}** ({len(sheets)} sheet(s))"
        return f"❌ {result.get('error')}"

    async def _create_pdf_tool(self, params: Dict) -> str:
        """Create a PDF document"""
        result = await self.document_skill.create_pdf(
            filename=params.get("filename", "document.pdf"),
            title=params.get("title", ""),
            content=params.get("content", ""),
            paragraphs=params.get("paragraphs"),
            table_data=params.get("table_data"),
            output_dir=params.get("output_dir"),
        )
        if result.get("success"):
            return f"📕 PDF created: **{result['path']}**"
        return f"❌ {result.get('error')}"

    async def _create_presentation_tool(self, params: Dict) -> str:
        """Create a PowerPoint presentation"""
        result = await self.document_skill.create_presentation(
            filename=params.get("filename", "presentation.pptx"),
            title=params.get("title", ""),
            subtitle=params.get("subtitle", ""),
            slides=params.get("slides"),
            output_dir=params.get("output_dir"),
        )
        if result.get("success"):
            count = result.get("slide_count", 0)
            return f"📽️ Presentation created: **{result['path']}** ({count} slides)"
        return f"❌ {result.get('error')}"

    async def _read_document_tool(self, params: Dict) -> str:
        """Read content from a document file"""
        file_path = params.get("file_path", "")
        if not file_path:
            return "⚠️ Please provide a file_path."
        result = await self.document_skill.read_document(file_path)
        if result.get("success"):
            text = result.get("text", "")
            fmt = result.get("format", "unknown")
            # Truncate for LLM context if very long
            if len(text) > 8000:
                text = text[:8000] + f"\n\n... (truncated, {len(result.get('text', ''))} chars total)"
            return f"📄 **{fmt.upper()} content** ({file_path}):\n\n{text}"
        return f"❌ {result.get('error')}"

    async def _open_document_tool(self, params: Dict) -> str:
        """Open a document with the default application"""
        file_path = params.get("file_path", "")
        if not file_path:
            return "⚠️ Please provide a file_path."
        result = await self.document_skill.open_document(file_path)
        if result.get("success"):
            return f"✅ Opened **{result['opened']}** ({result['system']})"
        return f"❌ {result.get('error')}"

    # ========== EMAIL TOOLS (SMTP/IMAP) ==========

    async def _email_send_tool(self, params: Dict) -> str:
        """Send email via SMTP with optional attachments"""
        host = getattr(self.config, "smtp_host", None)
        if not host:
            return (
                "⚠️ SMTP not configured. Add to .env:\n"
                "  SMTP_HOST=smtp.gmail.com\n"
                "  SMTP_USER=you@gmail.com\n"
                "  SMTP_PASSWORD=your-app-password"
            )

        to = params.get("to", "")
        subject = params.get("subject", "(no subject)")
        body = params.get("body", "")
        cc = params.get("cc", "")
        attachments = params.get("attachments", [])

        if not to:
            return "⚠️ Missing 'to' — who should I send the email to?"

        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            from email.mime.base import MIMEBase
            from email import encoders

            msg = MIMEMultipart()
            msg["From"] = getattr(self.config, "smtp_from", None) or self.config.smtp_user
            msg["To"] = to
            msg["Subject"] = subject
            if cc:
                msg["Cc"] = cc
            msg.attach(MIMEText(body, "plain"))

            # Attach files
            for fpath in attachments:
                p = Path(fpath)
                if p.exists():
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(p.read_bytes())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", f"attachment; filename={p.name}")
                    msg.attach(part)

            port = int(getattr(self.config, "smtp_port", 587))
            recipients = [to] + ([c.strip() for c in cc.split(",") if c.strip()] if cc else [])

            with smtplib.SMTP(host, port) as server:
                server.starttls()
                server.login(self.config.smtp_user, self.config.smtp_password)
                server.send_message(msg, to_addrs=recipients)

            att_note = f" ({len(attachments)} attachment(s))" if attachments else ""
            logger.info(f"📧 Email sent to {to}: {subject}")
            return f"✅ Email sent to **{to}**{att_note}\nSubject: {subject}"

        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return f"❌ Failed to send email: {e}"

    async def _email_read_tool(self, params: Dict) -> str:
        """Read emails via IMAP"""
        host = getattr(self.config, "imap_host", None)
        if not host:
            return (
                "⚠️ IMAP not configured. Add to .env:\n"
                "  IMAP_HOST=imap.gmail.com\n"
                "  IMAP_USER=you@gmail.com\n"
                "  IMAP_PASSWORD=your-app-password"
            )

        count = int(params.get("count", 5))
        folder = params.get("folder", "INBOX")
        unread_only = params.get("unread_only", False)

        try:
            import imaplib
            import email as email_lib
            from email.header import decode_header

            port = int(getattr(self.config, "imap_port", 993))
            with imaplib.IMAP4_SSL(host, port) as imap:
                imap.login(
                    getattr(self.config, "imap_user", None) or self.config.smtp_user,
                    getattr(self.config, "imap_password", None) or self.config.smtp_password,
                )
                imap.select(folder, readonly=True)

                search_criteria = "UNSEEN" if unread_only else "ALL"
                _, data = imap.search(None, search_criteria)
                ids = data[0].split()
                if not ids:
                    return f"📧 No {'unread ' if unread_only else ''}emails in {folder}."

                latest = ids[-count:]
                latest.reverse()
                results = []
                for mid in latest:
                    _, msg_data = imap.fetch(mid, "(RFC822)")
                    raw = msg_data[0][1]
                    msg = email_lib.message_from_bytes(raw)
                    subj = ""
                    for part, enc in decode_header(msg["Subject"] or ""):
                        subj += (
                            part.decode(enc or "utf-8")
                            if isinstance(part, bytes)
                            else str(part)
                        )
                    frm = msg["From"] or ""
                    date = msg["Date"] or ""

                    # Extract body snippet
                    snippet = ""
                    if msg.is_multipart():
                        for p in msg.walk():
                            if p.get_content_type() == "text/plain":
                                snippet = p.get_payload(decode=True).decode(errors="replace")[:200]
                                break
                    else:
                        payload = msg.get_payload(decode=True)
                        if payload:
                            snippet = payload.decode(errors="replace")[:200]

                    results.append(
                        f"• **{subj}**\n  From: {frm}\n  Date: {date}\n  Preview: {snippet.strip()}"
                    )

            return f"📧 **Latest {len(results)} emails ({folder}):**\n\n" + "\n\n".join(results)
        except Exception as e:
            logger.error(f"Email read failed: {e}")
            return f"❌ Failed to read email: {e}"

    # ========== CALENDAR TOOLS (LOCAL + GOOGLE) ==========

    async def _calendar_list_events_tool(self, params: Dict) -> str:
        """List calendar events — tries Google Calendar first, falls back to local"""
        source = params.get("source", "auto")
        days = int(params.get("days_ahead", 7))

        # Try Google Calendar
        if source in ("auto", "google") and self.google_calendar_skill.service:
            try:
                events = await self.google_calendar_skill.list_events(
                    days_ahead=days, max_results=15
                )
                if events:
                    result = "📅 **Upcoming Events (Google Calendar):**\n\n"
                    for ev in events:
                        result += f"• **{ev['summary']}**\n"
                        result += f"  📆 {ev['start']}\n"
                        if ev.get("location"):
                            result += f"  📍 {ev['location']}\n"
                        if ev.get("description"):
                            result += f"  📝 {ev['description']}\n"
                        result += f"  ID: {ev['id']}\n\n"
                    return result.strip()
                return "📅 No upcoming events in Google Calendar."
            except Exception as e:
                logger.warning(f"Google Calendar failed, falling back to local: {e}")

        # Fall back to local calendar
        return await self._calendar_tool({"action": "list"})

    async def _calendar_add_event_tool(self, params: Dict) -> str:
        """Add a calendar event — tries Google Calendar first, falls back to local"""
        source = params.get("source", "auto")
        title = params.get("title", "Untitled Event")
        date_str = params.get("date", "")
        duration = int(params.get("duration_minutes", 60))
        description = params.get("description", "")
        location = params.get("location", "")

        if not date_str:
            return "⚠️ Please provide a date/time (e.g., '2026-02-20 15:00')"

        # Try Google Calendar
        if source in ("auto", "google") and self.google_calendar_skill.service:
            try:
                success = await self.google_calendar_skill.add_event(
                    summary=title,
                    start_time=date_str,
                    duration_minutes=duration,
                    description=description,
                    location=location,
                )
                if success:
                    return f"✅ Event added to Google Calendar: **{title}** on {date_str}"
                return "❌ Failed to add event to Google Calendar"
            except Exception as e:
                logger.warning(f"Google Calendar add failed, falling back to local: {e}")

        # Fall back to local
        return await self._calendar_tool({
            "action": "add", "title": title, "date": date_str, "description": description,
        })

    async def _calendar_delete_event_tool(self, params: Dict) -> str:
        """Delete a calendar event"""
        source = params.get("source", "auto")
        event_id = params.get("event_id", "")

        if not event_id:
            return "⚠️ Please provide an event_id to delete."

        # Try Google Calendar
        if source in ("auto", "google") and self.google_calendar_skill.service:
            try:
                success = await self.google_calendar_skill.delete_event(event_id)
                if success:
                    return f"✅ Event {event_id} deleted from Google Calendar"
                return f"❌ Failed to delete event {event_id}"
            except Exception as e:
                logger.warning(f"Google Calendar delete failed, falling back to local: {e}")

        # Fall back to local
        return await self._calendar_tool({"action": "delete", "id": event_id})

    # ========== CLIPBOARD TOOLS ==========

    async def _clipboard_copy_tool(self, params: Dict) -> str:
        """Copy text to clipboard"""
        text = params.get("text", "")
        if not text:
            return "⚠️ No text provided to copy."
        result = await self.clipboard_skill.copy(text)
        if result.get("success"):
            return f"📋 Copied {result['length']} characters to clipboard"
        return f"❌ Clipboard error: {result.get('error')}"

    async def _clipboard_paste_tool(self, params: Dict) -> str:
        """Read from clipboard"""
        result = await self.clipboard_skill.paste()
        if result.get("success"):
            text = result.get("text", "")
            if not text:
                return "📋 Clipboard is empty."
            return f"📋 **Clipboard content** ({result['length']} chars):\n\n{text}"
        return f"❌ Clipboard error: {result.get('error')}"

    # ========== OCR (DOCUMENT SCANNING) ==========

    async def _ocr_extract_tool(self, params: Dict) -> str:
        """Extract text from images or scanned PDFs via OCR"""
        file_path = params.get("file_path", "")
        language = params.get("language", "en")

        if not file_path:
            return "⚠️ Please provide a file_path to an image or PDF."

        result = await self.ocr_skill.extract_text(
            file_path=file_path, language=language
        )
        if result.get("success"):
            text = result.get("text", "")
            engine = result.get("engine", "unknown")
            conf = result.get("confidence")
            conf_str = f" (confidence: {conf:.1%})" if conf else ""

            if len(text) > 8000:
                text = text[:8000] + f"\n\n... (truncated, {len(result.get('text', ''))} chars total)"

            return f"📄 **OCR Result** [{engine}{conf_str}]:\n\n{text}"
        return f"❌ OCR failed: {result.get('error')}"


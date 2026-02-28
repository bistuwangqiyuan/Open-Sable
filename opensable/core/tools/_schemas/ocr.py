"""
Tool schemas for Ocr domain.
"""

SCHEMAS = [
    # ── OCR (document scanning) ───────────────────
    {
    "type": "function",
    "function": {
    "name": "ocr_extract",
    "description": "Extract text from images or scanned PDFs using OCR (Optical Character Recognition)",
    "parameters": {
    "type": "object",
    "properties": {
    "file_path": {"type": "string", "description": "Path to image or PDF file"},
    "language": {"type": "string", "description": "Language code: en, es, fr, de, etc. (default: en)"},
    },
    "required": ["file_path"],
    },
    },
    },

]

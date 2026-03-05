"""
Tool schemas for Documents domain.
"""

SCHEMAS = [
    # ── Document creation tools ───────────────────
    {
    "type": "function",
    "function": {
    "name": "create_document",
    "description": "Create a Word (.docx) document with title, paragraphs, and optional table",
    "parameters": {
    "type": "object",
    "properties": {
    "filename": {"type": "string", "description": "Output filename (e.g. report.docx)"},
    "title": {"type": "string", "description": "Document title / heading"},
    "content": {"type": "string", "description": "Body text (single block). Use 'paragraphs' for multiple sections."},
    "paragraphs": {"type": "array", "items": {"type": "string"}, "description": "List of paragraphs"},
    "table_data": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}, "description": "2D array for a table (first row = headers)"},
    "output_dir": {"type": "string", "description": "Output directory (default: ~/Documents/SableDocs)"},
    },
    "required": ["filename"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "create_spreadsheet",
    "description": "Create an Excel (.xlsx) spreadsheet with data, headers, and multiple sheets",
    "parameters": {
    "type": "object",
    "properties": {
    "filename": {"type": "string", "description": "Output filename (e.g. data.xlsx)"},
    "data": {"type": "array", "items": {"type": "array"}, "description": "2D array of row data"},
    "headers": {"type": "array", "items": {"type": "string"}, "description": "Column headers"},
    "sheets": {"type": "object", "description": "Dict mapping sheet names to 2D data arrays (for multi-sheet)"},
    "output_dir": {"type": "string", "description": "Output directory"},
    },
    "required": ["filename"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "create_pdf",
    "description": "Create a PDF document with title, text content, and optional table",
    "parameters": {
    "type": "object",
    "properties": {
    "filename": {"type": "string", "description": "Output filename (e.g. report.pdf)"},
    "title": {"type": "string", "description": "Document title"},
    "content": {"type": "string", "description": "Body text"},
    "paragraphs": {"type": "array", "items": {"type": "string"}, "description": "List of paragraphs"},
    "table_data": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}, "description": "2D array for a table"},
    "output_dir": {"type": "string", "description": "Output directory"},
    },
    "required": ["filename"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "create_presentation",
    "description": "Create a PowerPoint (.pptx) presentation with title slide and content slides",
    "parameters": {
    "type": "object",
    "properties": {
    "filename": {"type": "string", "description": "Output filename (e.g. deck.pptx)"},
    "title": {"type": "string", "description": "Title slide heading"},
    "subtitle": {"type": "string", "description": "Title slide subtitle"},
    "slides": {
    "type": "array",
    "items": {
    "type": "object",
    "properties": {
    "title": {"type": "string"},
    "content": {"type": "string"},
    "bullets": {"type": "array", "items": {"type": "string"}},
    "layout": {"type": "string", "description": "title, content, bullets, or blank"},
    },
    },
    "description": "List of slide definitions",
    },
    "output_dir": {"type": "string", "description": "Output directory"},
    },
    "required": ["filename"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "read_document",
    "description": "Read and extract text from Word, Excel, PDF, or PowerPoint files",
    "parameters": {
    "type": "object",
    "properties": {
    "file_path": {"type": "string", "description": "Path to the document file"},
    },
    "required": ["file_path"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "open_document",
    "description": "Open a document with the system's default application (cross-platform)",
    "parameters": {
    "type": "object",
    "properties": {
    "file_path": {"type": "string", "description": "Path to the file to open"},
    },
    "required": ["file_path"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "write_in_writer",
    "description": "Open LibreOffice Writer and type text in real-time, character by character, visible on screen. Supports 'live' mode (types in empty document) and 'instant' mode (creates .docx then opens it).",
    "parameters": {
    "type": "object",
    "properties": {
    "text": {"type": "string", "description": "The text content to type in Writer"},
    "title": {"type": "string", "description": "Optional document title (typed first, followed by two newlines)"},
    "mode": {"type": "string", "enum": ["live", "instant"], "description": "'live' = opens empty Writer and types char by char (default). 'instant' = creates .docx then opens it."},
    "typing_speed": {"type": "number", "description": "Seconds between characters in live mode (default: 0.02). Lower = faster."},
    },
    "required": ["text"],
    },
    },
    },

]

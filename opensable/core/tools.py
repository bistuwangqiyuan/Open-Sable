"""
Tool registry for Open-Sable - manages all available actions
"""

import logging
import json
import aiohttp
from typing import Dict, Any, Callable, List
from pathlib import Path
from datetime import datetime

from .computer_tools import ComputerTools
from .vision_tools import VisionTools
from .browser import BrowserEngine
from .skill_creator import SkillCreator

try:
    from ..skills.trading.trading_skill import TradingSkill
except ImportError:
    TradingSkill = None  # type: ignore

try:
    from ..skills import VoiceSkill, ImageSkill, DatabaseSkill, RAGSkill, CodeExecutor, APIClient, XSkill, GrokSkill
except ImportError:
    # Graceful fallback if a skill is not available
    from ..skills import VoiceSkill, DatabaseSkill, RAGSkill, CodeExecutor, APIClient
    from ..skills.image_skill import ImageAnalyzer as ImageSkill  # type: ignore
    XSkill = None  # type: ignore
    GrokSkill = None  # type: ignore

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry of all available tools/actions"""

    # Map tool schema names → security ActionType for RBAC checking
    _TOOL_PERMISSIONS = {
        "execute_command": "system_command",
        "read_file": "file_read",
        "write_file": "file_write",
        "edit_file": "file_write",
        "delete_file": "file_delete",
        "move_file": "file_write",
        "copy_file": "file_write",
        "create_directory": "file_write",
        "browser_search": "browser_navigate",
        "browser_scrape": "browser_navigate",
        "browser_snapshot": "browser_navigate",
        "browser_action": "browser_navigate",
        "execute_code": "system_command",
        "desktop_screenshot": "system_command",
        "desktop_click": "system_command",
        "desktop_type": "system_command",
        "desktop_hotkey": "system_command",
        # Document & email
        "email_send": "email_send",
        "email_read": "email_read",
        "create_document": "file_write",
        "create_spreadsheet": "file_write",
        "create_pdf": "file_write",
        "create_presentation": "file_write",
        "open_document": "system_command",
        "clipboard_copy": "system_command",
        "clipboard_paste": "system_command",
        # Trading tools
        "trading_portfolio": "trading_read",
        "trading_price": "trading_read",
        "trading_analyze": "trading_read",
        "trading_signals": "trading_read",
        "trading_history": "trading_read",
        "trading_risk_status": "trading_read",
        "trading_place_trade": "trading_execute",
        "trading_cancel_order": "trading_execute",
        "trading_start_scan": "trading_execute",
        "trading_stop_scan": "trading_execute",
    }

    def __init__(self, config):
        self.config = config
        self.tools: Dict[str, Callable] = {}
        self._permission_manager = None
        self._custom_schemas: List[Dict[str, Any]] = []  # @function_tool schemas

        # Initialize permission manager for RBAC
        try:
            from .security import PermissionManager

            self._permission_manager = PermissionManager(config)
            self._permission_manager.initialize()
            logger.info("✅ Permission manager loaded for tool RBAC")
        except Exception as e:
            logger.debug(f"Permission manager not available: {e}")

        # Calendar storage
        self.calendar_file = Path.home() / ".opensable" / "calendar.json"
        self.calendar_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.calendar_file.exists():
            self.calendar_file.write_text(json.dumps([], indent=2))

        # Initialize browser engine
        self.browser_engine = BrowserEngine()

        # Initialize computer control tools
        self.computer = ComputerTools(config, sandbox_mode=getattr(config, "sandbox_mode", False))

        # Initialize vision tools (screen understanding + computer control via VLM)
        self.vision = VisionTools(config)

        # Initialize skill creator
        self.skill_creator = SkillCreator(config)

        # Initialize advanced skills
        self.voice = VoiceSkill(config)
        self.image = ImageSkill(config)
        self.database = DatabaseSkill(config)
        self.rag = RAGSkill(config)
        self.code_executor = CodeExecutor(config)
        self.api_client = APIClient(config)

        # X (Twitter) and Grok skills
        self.x_skill = XSkill(config) if XSkill else None
        self.grok_skill = GrokSkill(config) if GrokSkill else None

        # Document, Clipboard, OCR, Calendar (Google) skills
        from ..skills.document_skill import DocumentSkill
        from ..skills.clipboard_skill import ClipboardSkill
        from ..skills.ocr_skill import OCRSkill
        from ..skills.calendar_skill import CalendarSkill as GoogleCalendarSkill
        from ..skills.email_skill import EmailSkill

        self.document_skill = DocumentSkill(config)
        self.clipboard_skill = ClipboardSkill(config)
        self.ocr_skill = OCRSkill(config)
        self.google_calendar_skill = GoogleCalendarSkill(config)
        self.email_skill = EmailSkill(config)

        # Trading skill
        self.trading_skill = None
        if TradingSkill and getattr(config, "trading_enabled", False):
            try:
                self.trading_skill = TradingSkill(config)
            except Exception as e:
                logger.warning(f"Trading skill creation failed: {e}")

    async def initialize(self):
        """Initialize all tools"""
        # Register computer control tools (CRITICAL)
        self.register("execute_command", self._execute_command_tool)
        self.register("read_file", self._read_file_tool)
        self.register("write_file", self._write_file_tool)
        self.register("edit_file", self._edit_file_tool)
        self.register("list_directory", self._list_directory_tool)
        self.register("create_directory", self._create_directory_tool)
        self.register("delete_file", self._delete_file_tool)
        self.register("move_file", self._move_file_tool)
        self.register("copy_file", self._copy_file_tool)
        self.register("search_files", self._search_files_tool)
        self.register("system_info", self._system_info_tool)

        # Register built-in tools
        self.register("email", self._email_tool)
        self.register("calendar", self._calendar_tool)
        self.register("browser", self._browser_tool)
        self.register("web_action", self._web_action_tool)
        self.register("weather", self._weather_tool)

        # Register advanced skills
        self.register("voice_speak", self._voice_speak_tool)
        self.register("voice_listen", self._voice_listen_tool)
        self.register("generate_image", self._generate_image_tool)
        self.register("analyze_image", self._analyze_image_tool)
        self.register("ocr", self._ocr_tool)
        self.register("database_query", self._database_query_tool)
        self.register("vector_search", self._vector_search_tool)
        self.register("execute_code", self._execute_code_tool)
        self.register("api_request", self._api_request_tool)

        # Register document tools
        self.register("create_document", self._create_document_tool)
        self.register("create_spreadsheet", self._create_spreadsheet_tool)
        self.register("create_pdf", self._create_pdf_tool)
        self.register("create_presentation", self._create_presentation_tool)
        self.register("read_document", self._read_document_tool)
        self.register("open_document", self._open_document_tool)

        # Register email tools (schema-mapped)
        self.register("email_send", self._email_send_tool)
        self.register("email_read", self._email_read_tool)

        # Register Google Calendar tools
        self.register("calendar_list_events", self._calendar_list_events_tool)
        self.register("calendar_add_event", self._calendar_add_event_tool)
        self.register("calendar_delete_event", self._calendar_delete_event_tool)

        # Register clipboard tools
        self.register("clipboard_copy", self._clipboard_copy_tool)
        self.register("clipboard_paste", self._clipboard_paste_tool)

        # Register OCR tool (advanced)
        self.register("ocr_extract", self._ocr_extract_tool)

        # Register skill creation
        self.register("create_skill", self._create_skill_tool)
        self.register("list_skills", self._list_skills_tool)

        # Register X (Twitter) tools
        self.register("x_post_tweet", self._x_post_tweet_tool)
        self.register("x_post_thread", self._x_post_thread_tool)
        self.register("x_search", self._x_search_tool)
        self.register("x_get_trends", self._x_get_trends_tool)
        self.register("x_like", self._x_like_tool)
        self.register("x_retweet", self._x_retweet_tool)
        self.register("x_reply", self._x_reply_tool)
        self.register("x_get_user", self._x_get_user_tool)
        self.register("x_get_user_tweets", self._x_get_user_tweets_tool)
        self.register("x_follow", self._x_follow_tool)
        self.register("x_send_dm", self._x_send_dm_tool)
        self.register("x_delete_tweet", self._x_delete_tweet_tool)

        # Register Grok AI tools
        self.register("grok_chat", self._grok_chat_tool)
        self.register("grok_analyze_image", self._grok_analyze_image_tool)
        self.register("grok_generate_image", self._grok_generate_image_tool)

        # Register desktop control tools
        self.register("desktop_screenshot", self._desktop_screenshot_tool)
        self.register("desktop_click", self._desktop_click_tool)
        self.register("desktop_type", self._desktop_type_tool)
        self.register("desktop_hotkey", self._desktop_hotkey_tool)
        self.register("desktop_scroll", self._desktop_scroll_tool)
        self.register("desktop_mouse_move", self._desktop_mouse_move_tool)

        # Register vision / autonomous computer-use tools
        self.register("screen_analyze", self._screen_analyze_tool)
        self.register("screen_find", self._screen_find_tool)
        self.register("screen_click_on", self._screen_click_on_tool)
        self.register("open_app", self._open_app_tool)
        self.register("window_list", self._window_list_tool)
        self.register("window_focus", self._window_focus_tool)

        # Initialize advanced skills
        try:
            await self.voice.initialize()
        except Exception as e:
            logger.warning(f"Voice skill initialization failed: {e}")

        try:
            await self.image.initialize()
        except Exception as e:
            logger.warning(f"Image skill initialization failed: {e}")

        try:
            await self.database.initialize()
        except Exception as e:
            logger.warning(f"Database skill initialization failed: {e}")

        try:
            await self.rag.initialize()
        except Exception as e:
            logger.warning(f"RAG skill initialization failed: {e}")

        # Initialize X (Twitter) skill
        if self.x_skill:
            try:
                await self.x_skill.initialize()
            except Exception as e:
                logger.warning(f"X skill initialization failed: {e}")

        # Initialize Grok skill
        if self.grok_skill:
            try:
                await self.grok_skill.initialize()
            except Exception as e:
                logger.warning(f"Grok skill initialization failed: {e}")

        # Initialize new skills (document, clipboard, OCR, Google Calendar, Email)
        for skill_name, skill_obj in [
            ("Document", self.document_skill),
            ("Clipboard", self.clipboard_skill),
            ("OCR", self.ocr_skill),
            ("Google Calendar", self.google_calendar_skill),
            ("Email", self.email_skill),
        ]:
            try:
                await skill_obj.initialize()
            except Exception as e:
                logger.warning(f"{skill_name} skill initialization failed: {e}")

        # Initialize trading skill
        if self.trading_skill:
            try:
                await self.trading_skill.initialize()
                self.register("trading_portfolio", self._trading_portfolio_tool)
                self.register("trading_price", self._trading_price_tool)
                self.register("trading_analyze", self._trading_analyze_tool)
                self.register("trading_place_trade", self._trading_place_trade_tool)
                self.register("trading_cancel_order", self._trading_cancel_order_tool)
                self.register("trading_history", self._trading_history_tool)
                self.register("trading_signals", self._trading_signals_tool)
                self.register("trading_start_scan", self._trading_start_scan_tool)
                self.register("trading_stop_scan", self._trading_stop_scan_tool)
                self.register("trading_risk_status", self._trading_risk_status_tool)
                logger.info("✅ Trading skill initialized with 10 tools")
            except Exception as e:
                logger.warning(f"Trading skill initialization failed: {e}")

        logger.info(f"Initialized {len(self.tools)} tools")

    def register(self, name: str, func: Callable):
        """Register a new tool"""
        self.tools[name] = func
        logger.debug(f"Registered tool: {name}")

    def list_tools(self) -> List[str]:
        """List all available tools"""
        return list(self.tools.keys())

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return Ollama-compatible tool schemas (OpenAI function calling format)"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "browser_search",
                    "description": "Search the web for information about any topic, person, place, news, etc.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "The search query"},
                            "num_results": {
                                "type": "integer",
                                "description": "Number of results (default 5)",
                                "default": 5,
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_scrape",
                    "description": "Fetch and read the content of a specific web page URL",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "The full URL to scrape (must start with http:// or https://)",
                            }
                        },
                        "required": ["url"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_snapshot",
                    "description": "Take an accessibility snapshot of a web page to see interactive elements (buttons, inputs, links) with stable refs for automation",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "The URL to snapshot"}
                        },
                        "required": ["url"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_action",
                    "description": "Interact with a web page: click buttons, type text, submit forms. Use after browser_snapshot to get refs.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "description": "Action: click, type, hover, select, press, submit, evaluate, wait",
                            },
                            "ref": {
                                "type": "string",
                                "description": "Element ref from snapshot (e.g. 'e3')",
                            },
                            "selector": {
                                "type": "string",
                                "description": "CSS selector (alternative to ref)",
                            },
                            "value": {
                                "type": "string",
                                "description": "Value for type/fill/select actions",
                            },
                            "url": {
                                "type": "string",
                                "description": "URL to navigate to before action (optional)",
                            },
                        },
                        "required": ["action"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "execute_command",
                    "description": "Run a shell command on the system",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The shell command to execute",
                            },
                            "cwd": {
                                "type": "string",
                                "description": "Working directory (optional)",
                            },
                            "timeout": {
                                "type": "integer",
                                "description": "Timeout in seconds (default 30)",
                            },
                        },
                        "required": ["command"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read the contents of a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Absolute or relative file path",
                            }
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write content to a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path"},
                            "content": {"type": "string", "description": "Content to write"},
                            "mode": {
                                "type": "string",
                                "description": "'w' to overwrite (default), 'a' to append",
                            },
                        },
                        "required": ["path", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_directory",
                    "description": "List files and folders in a directory",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Directory path (default '.')",
                            }
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "weather",
                    "description": "Get current weather for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "City name, country, or address",
                            }
                        },
                        "required": ["location"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "calendar",
                    "description": "Manage calendar events: list upcoming events, add new events, or delete events",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string", "description": "list, add, or delete"},
                            "title": {"type": "string", "description": "Event title (for add)"},
                            "date": {
                                "type": "string",
                                "description": "Date/time in YYYY-MM-DD HH:MM format (for add)",
                            },
                            "description": {
                                "type": "string",
                                "description": "Event description (optional)",
                            },
                            "id": {"type": "integer", "description": "Event ID (for delete)"},
                        },
                        "required": ["action"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "execute_code",
                    "description": "Execute Python or other code in a sandbox",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "description": "Code to execute"},
                            "language": {
                                "type": "string",
                                "description": "Programming language (default: python)",
                            },
                        },
                        "required": ["code"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "vector_search",
                    "description": "Semantic search through stored documents and knowledge base",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "top_k": {
                                "type": "integer",
                                "description": "Number of results (default 5)",
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "create_skill",
                    "description": "Create a new dynamic skill/extension for the agent. The skill will be validated, saved, and loaded automatically.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Skill name (snake_case, e.g. 'weather_check')",
                            },
                            "description": {"type": "string", "description": "What the skill does"},
                            "code": {"type": "string", "description": "Python code for the skill"},
                            "author": {
                                "type": "string",
                                "description": "Author name (default: 'sable')",
                            },
                        },
                        "required": ["name", "description", "code"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_skills",
                    "description": "List all custom skills created by the agent",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            # ── File & system tools ─────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "edit_file",
                    "description": "Edit a file by replacing specific text",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path"},
                            "old_content": {"type": "string", "description": "Text to find"},
                            "new_content": {"type": "string", "description": "Replacement text"},
                        },
                        "required": ["path", "old_content", "new_content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "delete_file",
                    "description": "Delete a file or empty directory",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string", "description": "Path to delete"}},
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "move_file",
                    "description": "Move or rename a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source": {"type": "string", "description": "Source path"},
                            "destination": {"type": "string", "description": "Destination path"},
                        },
                        "required": ["source", "destination"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_files",
                    "description": "Search for files by name pattern or content",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "string",
                                "description": "Search pattern (glob or text)",
                            },
                            "path": {
                                "type": "string",
                                "description": "Directory to search in (default '.')",
                            },
                            "content": {
                                "type": "string",
                                "description": "Search inside file contents for this text",
                            },
                        },
                        "required": ["pattern"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "system_info",
                    "description": "Get system information: OS, CPU, memory, disk usage",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            # ── Desktop control tools ─────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "desktop_screenshot",
                    "description": "Take a screenshot of the screen. Returns base64 PNG image and dimensions.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "save_path": {
                                "type": "string",
                                "description": "Optional file path to save the PNG to instead of returning base64",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "desktop_click",
                    "description": "Click the mouse at screen coordinates (x, y)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "integer", "description": "X pixel coordinate"},
                            "y": {"type": "integer", "description": "Y pixel coordinate"},
                            "button": {
                                "type": "string",
                                "description": "'left' (default), 'right', or 'middle'",
                            },
                            "clicks": {
                                "type": "integer",
                                "description": "Number of clicks (2 = double-click)",
                            },
                        },
                        "required": ["x", "y"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "desktop_type",
                    "description": "Type text via the keyboard at the current cursor position",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "The text to type"}
                        },
                        "required": ["text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "desktop_hotkey",
                    "description": "Press a key or key combination (e.g. 'enter', 'ctrl+c', 'alt+f4', 'ctrl+shift+t')",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {
                                "type": "string",
                                "description": "Key or combo like 'enter', 'ctrl+c', 'alt+tab'",
                            }
                        },
                        "required": ["key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "desktop_scroll",
                    "description": "Scroll the mouse wheel. Positive = up, negative = down.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "amount": {
                                "type": "integer",
                                "description": "Scroll amount (positive=up, negative=down)",
                            },
                            "x": {
                                "type": "integer",
                                "description": "Optional X coordinate to scroll at",
                            },
                            "y": {
                                "type": "integer",
                                "description": "Optional Y coordinate to scroll at",
                            },
                        },
                        "required": ["amount"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "desktop_mouse_move",
                    "description": "Move the mouse to screen coordinates (x, y)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "integer", "description": "X pixel coordinate"},
                            "y": {"type": "integer", "description": "Y pixel coordinate"},
                        },
                        "required": ["x", "y"],
                    },
                },
            },
            # ── Vision / autonomous computer-use tools ────────────
            {
                "type": "function",
                "function": {
                    "name": "screen_analyze",
                    "description": (
                        "Take a screenshot and use an AI vision model (Qwen2.5-VL) to understand "
                        "what is on the screen. Returns a detailed description of visible UI elements, "
                        "windows, buttons, text, errors, etc. Use this before clicking to know "
                        "what's there. Optionally ask a specific question about the screen."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question": {
                                "type": "string",
                                "description": "Optional specific question about the screen, e.g. 'Is there an error dialog?' or 'What app is open?'",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "screen_find",
                    "description": (
                        "Find a specific UI element on the screen by visual description. "
                        "Uses AI vision to locate buttons, input fields, links, icons, etc. "
                        "Returns (x, y) pixel coordinates to use with desktop_click. "
                        "Example: screen_find('Login button') → x:640, y:450"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "What to find on screen, e.g. 'the Submit button', 'username input field', 'close X button', 'error message'",
                            },
                        },
                        "required": ["description"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "screen_click_on",
                    "description": (
                        "ONE SHOT: Find a UI element visually on the screen and click it. "
                        "Combines screen_find + desktop_click in one action. "
                        "Use this instead of screen_find + desktop_click when you want to click something. "
                        "Example: screen_click_on('the Login button')"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "What to click, e.g. 'OK button', 'username field', 'X close button', 'Accept button'",
                            },
                            "double": {
                                "type": "boolean",
                                "description": "True for double-click (e.g. to open files), default false",
                            },
                        },
                        "required": ["description"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "open_app",
                    "description": (
                        "Open an application on the computer by name. "
                        "Works with: firefox, chrome, terminal, vscode, spotify, vlc, gimp, "
                        "libreoffice, calculator, files, discord, slack, and any installed program."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Application name or command, e.g. 'firefox', 'terminal', 'vscode', 'spotify'",
                            },
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "window_list",
                    "description": "List all currently open windows on the desktop. Returns window titles and IDs.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "window_focus",
                    "description": "Bring a specific window to the front by its title or partial title. E.g. 'Firefox', 'Terminal', 'Visual Studio Code'",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Window title or partial title to focus",
                            },
                        },
                        "required": ["name"],
                    },
                },
            },
            # ── X (Twitter) tools ─────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "x_post_tweet",
                    "description": "Post a tweet on X (Twitter). Can include text and optional images/video.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "Tweet text (max 280 chars)"},
                            "media_paths": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional list of image/video file paths to attach",
                            },
                            "reply_to": {"type": "string", "description": "Tweet ID to reply to (optional)"},
                        },
                        "required": ["text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "x_post_thread",
                    "description": "Post a thread (multiple connected tweets) on X. Provide a list of tweet texts in order.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tweets": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of tweet texts in thread order",
                            },
                        },
                        "required": ["tweets"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "x_search",
                    "description": "Search for tweets on X by keyword or phrase",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "search_type": {"type": "string", "description": "'Latest', 'Top', 'People', or 'Media' (default: Latest)"},
                            "count": {"type": "integer", "description": "Max results (default 10)"},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "x_get_trends",
                    "description": "Get trending topics on X (Twitter)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string", "description": "'trending', 'news', 'sports', or 'entertainment'"},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "x_like",
                    "description": "Like a tweet on X",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tweet_id": {"type": "string", "description": "Tweet ID to like"},
                        },
                        "required": ["tweet_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "x_retweet",
                    "description": "Retweet a tweet on X",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tweet_id": {"type": "string", "description": "Tweet ID to retweet"},
                        },
                        "required": ["tweet_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "x_reply",
                    "description": "Reply to a tweet on X",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tweet_id": {"type": "string", "description": "Tweet ID to reply to"},
                            "text": {"type": "string", "description": "Reply text"},
                        },
                        "required": ["tweet_id", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "x_get_user",
                    "description": "Get a user's profile information on X (followers, bio, etc.)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "username": {"type": "string", "description": "X username (without @)"},
                        },
                        "required": ["username"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "x_get_user_tweets",
                    "description": "Get recent tweets from a specific X user",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "username": {"type": "string", "description": "X username (without @)"},
                            "tweet_type": {"type": "string", "description": "'Tweets', 'Replies', 'Media', or 'Likes'"},
                            "count": {"type": "integer", "description": "Max tweets to return (default 10)"},
                        },
                        "required": ["username"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "x_follow",
                    "description": "Follow a user on X",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "username": {"type": "string", "description": "X username to follow (without @)"},
                        },
                        "required": ["username"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "x_send_dm",
                    "description": "Send a direct message to a user on X",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string", "description": "User ID (numeric) to DM"},
                            "text": {"type": "string", "description": "Message text"},
                        },
                        "required": ["user_id", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "x_delete_tweet",
                    "description": "Delete one of your own tweets on X",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tweet_id": {"type": "string", "description": "Tweet ID to delete"},
                        },
                        "required": ["tweet_id"],
                    },
                },
            },
            # ── Grok AI tools ─────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "grok_chat",
                    "description": "Chat with Grok AI (free via your X account). Ask questions, get analysis, brainstorm ideas.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string", "description": "Message/prompt to send to Grok"},
                            "conversation_id": {"type": "string", "description": "Continue existing conversation (optional)"},
                        },
                        "required": ["message"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "grok_analyze_image",
                    "description": "Send images to Grok AI for analysis/description (vision capability)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "image_paths": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of image file paths to analyze",
                            },
                            "prompt": {"type": "string", "description": "Question about the images (default: describe them)"},
                        },
                        "required": ["image_paths"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "grok_generate_image",
                    "description": "Generate images using Grok AI",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "prompt": {"type": "string", "description": "Image generation prompt"},
                            "save_path": {"type": "string", "description": "Path to save generated image (optional)"},
                        },
                        "required": ["prompt"],
                    },
                },
            },
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
            # ── Calendar tools (local + Google Calendar) ──
            {
                "type": "function",
                "function": {
                    "name": "calendar_list_events",
                    "description": "List upcoming calendar events (local store or Google Calendar if configured)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "days_ahead": {"type": "integer", "description": "Number of days to look ahead (default: 7)"},
                            "source": {"type": "string", "description": "'local' or 'google' (default: auto-detect)"},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "calendar_add_event",
                    "description": "Add a new calendar event (to local store or Google Calendar)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Event title"},
                            "date": {"type": "string", "description": "Date/time in YYYY-MM-DD HH:MM format"},
                            "duration_minutes": {"type": "integer", "description": "Duration in minutes (default: 60)"},
                            "description": {"type": "string", "description": "Event description (optional)"},
                            "location": {"type": "string", "description": "Event location (optional)"},
                            "source": {"type": "string", "description": "'local' or 'google'"},
                        },
                        "required": ["title", "date"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "calendar_delete_event",
                    "description": "Delete a calendar event by ID",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "event_id": {"type": "string", "description": "Event ID to delete"},
                            "source": {"type": "string", "description": "'local' or 'google'"},
                        },
                        "required": ["event_id"],
                    },
                },
            },
            # ── Clipboard tools ───────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "clipboard_copy",
                    "description": "Copy text to the system clipboard",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "Text to copy to clipboard"},
                        },
                        "required": ["text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clipboard_paste",
                    "description": "Read current text from the system clipboard",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            },
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
            # ── Trading tools ─────────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "trading_portfolio",
                    "description": "Get the current trading portfolio summary — balances, positions, P&L, performance stats",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "trading_price",
                    "description": "Get the current price of a trading pair (crypto, stock, prediction market)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string", "description": "Trading pair, e.g. BTC/USDT, ETH/USDT, AAPL"},
                        },
                        "required": ["symbol"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "trading_analyze",
                    "description": "Analyze a market/asset using all active strategies. Returns trading signals with confidence levels.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string", "description": "Trading pair to analyze, e.g. BTC/USDT"},
                        },
                        "required": ["symbol"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "trading_place_trade",
                    "description": "Place a buy or sell trade. Goes through risk checks and requires approval for large amounts.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string", "description": "Trading pair, e.g. BTC/USDT"},
                            "side": {"type": "string", "enum": ["buy", "sell"], "description": "Buy or sell"},
                            "amount": {"type": "string", "description": "Amount to trade (in base currency)"},
                            "type": {"type": "string", "enum": ["market", "limit"], "description": "Order type (default: market)"},
                            "price": {"type": "string", "description": "Limit price (only for limit orders)"},
                            "exchange": {"type": "string", "description": "Exchange to use: paper, binance, coinbase, alpaca, etc. (default: paper)"},
                        },
                        "required": ["symbol", "side", "amount"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "trading_cancel_order",
                    "description": "Cancel an open order on an exchange",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {"type": "string", "description": "The order ID to cancel"},
                            "exchange": {"type": "string", "description": "Exchange name (default: paper)"},
                            "symbol": {"type": "string", "description": "Trading pair (some exchanges require it)"},
                        },
                        "required": ["order_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "trading_history",
                    "description": "Get recent trade history and execution log",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Number of trades to return (default: 20)"},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "trading_signals",
                    "description": "Scan all assets on the watchlist and return current trading signals from all strategies",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "trading_start_scan",
                    "description": "Start background market scanning — continuously monitors watchlist for trading opportunities",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "trading_stop_scan",
                    "description": "Stop the background market scanning loop",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "trading_risk_status",
                    "description": "Show the current risk manager status — limits, daily P&L, drawdown, emergency halt status",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
        ] + self._custom_schemas  # append @function_tool schemas

    # Tool schema → internal tool name mapping
    _SCHEMA_TO_TOOL = {
        "browser_search": ("browser", lambda a: {"action": "search", **a}),
        "browser_scrape": ("browser", lambda a: {"action": "scrape", **a}),
        "browser_snapshot": ("browser", lambda a: {"action": "snapshot", **a}),
        "browser_action": ("web_action", lambda a: a),
        "execute_command": ("execute_command", lambda a: a),
        "read_file": ("read_file", lambda a: a),
        "write_file": ("write_file", lambda a: a),
        "list_directory": ("list_directory", lambda a: a),
        "weather": ("weather", lambda a: a),
        "calendar": ("calendar", lambda a: a),
        "execute_code": ("execute_code", lambda a: a),
        "vector_search": ("vector_search", lambda a: a),
        "create_skill": ("create_skill", lambda a: a),
        "list_skills": ("list_skills", lambda a: a),
        # File & system tools
        "edit_file": ("edit_file", lambda a: a),
        "delete_file": ("delete_file", lambda a: a),
        "move_file": ("move_file", lambda a: a),
        "search_files": ("search_files", lambda a: a),
        "system_info": ("system_info", lambda a: a),
        # Desktop control
        "desktop_screenshot": ("desktop_screenshot", lambda a: a),
        "desktop_click": ("desktop_click", lambda a: a),
        "desktop_type": ("desktop_type", lambda a: a),
        "desktop_hotkey": ("desktop_hotkey", lambda a: a),
        "desktop_scroll": ("desktop_scroll", lambda a: a),
        "desktop_mouse_move": ("desktop_mouse_move", lambda a: a),
        # Vision / autonomous computer-use
        "screen_analyze": ("screen_analyze", lambda a: a),
        "screen_find": ("screen_find", lambda a: a),
        "screen_click_on": ("screen_click_on", lambda a: a),
        "open_app": ("open_app", lambda a: a),
        "window_list": ("window_list", lambda a: a),
        "window_focus": ("window_focus", lambda a: a),
        # X (Twitter) tools
        "x_post_tweet": ("x_post_tweet", lambda a: a),
        "x_post_thread": ("x_post_thread", lambda a: a),
        "x_search": ("x_search", lambda a: a),
        "x_get_trends": ("x_get_trends", lambda a: a),
        "x_like": ("x_like", lambda a: a),
        "x_retweet": ("x_retweet", lambda a: a),
        "x_reply": ("x_reply", lambda a: a),
        "x_get_user": ("x_get_user", lambda a: a),
        "x_get_user_tweets": ("x_get_user_tweets", lambda a: a),
        "x_follow": ("x_follow", lambda a: a),
        "x_send_dm": ("x_send_dm", lambda a: a),
        "x_delete_tweet": ("x_delete_tweet", lambda a: a),
        # Grok AI tools
        "grok_chat": ("grok_chat", lambda a: a),
        "grok_analyze_image": ("grok_analyze_image", lambda a: a),
        "grok_generate_image": ("grok_generate_image", lambda a: a),
        # Document tools
        "create_document": ("create_document", lambda a: a),
        "create_spreadsheet": ("create_spreadsheet", lambda a: a),
        "create_pdf": ("create_pdf", lambda a: a),
        "create_presentation": ("create_presentation", lambda a: a),
        "read_document": ("read_document", lambda a: a),
        "open_document": ("open_document", lambda a: a),
        # Email tools
        "email_send": ("email_send", lambda a: a),
        "email_read": ("email_read", lambda a: a),
        # Calendar tools
        "calendar_list_events": ("calendar_list_events", lambda a: a),
        "calendar_add_event": ("calendar_add_event", lambda a: a),
        "calendar_delete_event": ("calendar_delete_event", lambda a: a),
        # Clipboard tools
        "clipboard_copy": ("clipboard_copy", lambda a: a),
        "clipboard_paste": ("clipboard_paste", lambda a: a),
        # OCR
        "ocr_extract": ("ocr_extract", lambda a: a),
        # Trading
        "trading_portfolio": ("trading_portfolio", lambda a: a),
        "trading_price": ("trading_price", lambda a: a),
        "trading_analyze": ("trading_analyze", lambda a: a),
        "trading_place_trade": ("trading_place_trade", lambda a: a),
        "trading_cancel_order": ("trading_cancel_order", lambda a: a),
        "trading_history": ("trading_history", lambda a: a),
        "trading_signals": ("trading_signals", lambda a: a),
        "trading_start_scan": ("trading_start_scan", lambda a: a),
        "trading_stop_scan": ("trading_stop_scan", lambda a: a),
        "trading_risk_status": ("trading_risk_status", lambda a: a),
    }

    async def execute_schema_tool(
        self, schema_name: str, arguments: Dict[str, Any], user_id: str = "default"
    ) -> str:
        """Execute a tool by its schema name (as returned by Ollama tool calling)"""
        # Check the static schema mapping first, then fall back to
        # directly registered tools (e.g. from @function_tool).
        if schema_name not in self._SCHEMA_TO_TOOL and schema_name not in self.tools:
            return f"⚠️ Unknown tool: {schema_name}"

        # RBAC check — if a permission manager is loaded and the tool is mapped
        if self._permission_manager and schema_name in self._TOOL_PERMISSIONS:
            from .security import ActionType

            action_str = self._TOOL_PERMISSIONS[schema_name]
            try:
                action = ActionType(action_str)
                allowed = await self._permission_manager.check_permission(
                    user_id, action, {"tool": schema_name, "arguments": arguments}
                )
                if not allowed:
                    logger.warning(f"🔒 RBAC denied {schema_name} for user {user_id}")
                    return f"🔒 Permission denied: {schema_name} requires '{action_str}' permission"
            except Exception as e:
                # Don't block tools if RBAC check itself fails
                logger.debug(f"RBAC check error (allowing): {e}")

        if schema_name in self._SCHEMA_TO_TOOL:
            internal_name, arg_mapper = self._SCHEMA_TO_TOOL[schema_name]
            mapped_args = arg_mapper(arguments)
            return await self.execute(internal_name, mapped_args)

        # Direct-registered tool (e.g. @function_tool)
        return await self.execute(schema_name, arguments)

    async def execute(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """Execute a tool"""
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        logger.info(f"Executing tool: {tool_name}")
        try:
            result = await self.tools[tool_name](tool_input)
            return result
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}")
            raise

    # ========== COMPUTER CONTROL TOOLS ==========

    async def _execute_command_tool(self, params: Dict) -> str:
        """Execute shell command"""
        command = params.get("command", "")
        cwd = params.get("cwd")
        timeout = params.get("timeout", 30)

        result = await self.computer.execute_command(command, cwd=cwd, timeout=timeout)

        if result["success"]:
            output = result["stdout"] if result["stdout"] else "(no output)"
            return f"✅ Command executed successfully\n\n```\n{output}\n```\n\nExit code: {result['exit_code']}"
        else:
            return (
                f"❌ Command failed\n\nError: {result['stderr']}\nExit code: {result['exit_code']}"
            )

    async def _read_file_tool(self, params: Dict) -> str:
        """Read file contents"""
        path = params.get("path", "")

        result = await self.computer.read_file(path)

        if result["success"]:
            content = result["content"]
            # Truncate very long files
            if len(content) > 10000:
                content = content[:10000] + f"\n... (truncated, total size: {result['size']} bytes)"
            return f"📄 File: {result['path']}\n\n```\n{content}\n```"
        else:
            return f"❌ Failed to read file: {result['error']}"

    async def _write_file_tool(self, params: Dict) -> str:
        """Write content to file"""
        path = params.get("path", "")
        content = params.get("content", "")
        mode = params.get("mode", "w")

        result = await self.computer.write_file(path, content, mode=mode)

        if result["success"]:
            return f"✅ Wrote {result['bytes_written']} bytes to {result['path']}"
        else:
            return f"❌ Failed to write file: {result['error']}"

    async def _edit_file_tool(self, params: Dict) -> str:
        """Edit file by replacing content"""
        path = params.get("path", "")
        old_content = params.get("old_content", "")
        new_content = params.get("new_content", "")

        result = await self.computer.edit_file(path, old_content, new_content)

        if result["success"]:
            return f"✅ Made {result['replacements']} replacement(s) in {result['path']}"
        else:
            return f"❌ Failed to edit file: {result['error']}"

    async def _list_directory_tool(self, params: Dict) -> str:
        """List directory contents"""
        path = params.get("path", ".")
        include_hidden = params.get("include_hidden", False)
        recursive = params.get("recursive", False)

        result = await self.computer.list_directory(path, include_hidden, recursive)

        if result["success"]:
            files = result["files"]
            output = f"📁 Directory: {result['path']}\n\n"

            if not files:
                return output + "(empty directory)"

            for f in files[:50]:  # Limit to 50 items
                icon = "📁" if f["type"] == "directory" else "📄"
                size = f"({f['size']} bytes)" if f["type"] == "file" else ""
                output += f"{icon} {f['name']} {size}\n"

            if len(files) > 50:
                output += f"\n... and {len(files) - 50} more items"

            return output
        else:
            return f"❌ Failed to list directory: {result['error']}"

    async def _create_directory_tool(self, params: Dict) -> str:
        """Create directory"""
        path = params.get("path", "")

        result = await self.computer.create_directory(path)

        if result["success"]:
            return f"✅ Created directory: {result['path']}"
        else:
            return f"❌ Failed to create directory: {result['error']}"

    async def _delete_file_tool(self, params: Dict) -> str:
        """Delete file or directory"""
        path = params.get("path", "")

        result = await self.computer.delete_file(path)

        if result["success"]:
            return f"✅ Deleted: {result['path']}"
        else:
            return f"❌ Failed to delete: {result['error']}"

    async def _move_file_tool(self, params: Dict) -> str:
        """Move/rename file"""
        source = params.get("source", "")
        destination = params.get("destination", "")

        result = await self.computer.move_file(source, destination)

        if result["success"]:
            return f"✅ Moved: {result['source']} → {result['destination']}"
        else:
            return f"❌ Failed to move: {result['error']}"

    async def _copy_file_tool(self, params: Dict) -> str:
        """Copy file or directory"""
        source = params.get("source", "")
        destination = params.get("destination", "")

        result = await self.computer.copy_file(source, destination)

        if result["success"]:
            return f"✅ Copied: {result['source']} → {result['destination']}"
        else:
            return f"❌ Failed to copy: {result['error']}"

    async def _search_files_tool(self, params: Dict) -> str:
        """Search for files"""
        path = params.get("path", ".")
        pattern = params.get("pattern", "")
        content_search = params.get("content_search", False)

        result = await self.computer.search_files(path, pattern, content_search)

        if result["success"]:
            matches = result["matches"]
            output = f"🔍 Search results for '{pattern}' in {path}\n\n"

            if not matches:
                return output + "No matches found"

            for m in matches[:20]:  # Limit to 20 results
                output += f"• {m['path']}\n"

            if len(matches) > 20:
                output += f"\n... and {len(matches) - 20} more matches"

            return output
        else:
            return f"❌ Search failed: {result['error']}"

    async def _system_info_tool(self, params: Dict) -> str:
        """Get system information"""
        result = await self.computer.get_system_info()

        if result["success"]:
            return f"""💻 System Information

**Platform:** {result['system']} ({result['platform']})
**Python:** {result['python_version']}

**CPU:**
- Cores: {result['cpu_count']}
- Usage: {result['cpu_percent']}%

**Memory:**
- Total: {result['memory_total'] / (1024**3):.2f} GB
- Available: {result['memory_available'] / (1024**3):.2f} GB
- Usage: {result['memory_percent']}%

**Disk:**
- Total: {result['disk_usage']['total'] / (1024**3):.2f} GB
- Used: {result['disk_usage']['used'] / (1024**3):.2f} GB
- Free: {result['disk_usage']['free'] / (1024**3):.2f} GB
- Usage: {result['disk_usage']['percent']}%
"""
        else:
            return f"❌ Failed to get system info: {result['error']}"

    # ========== ORIGINAL TOOLS ==========

    # Built-in tools (simplified implementations)

    async def _email_tool(self, params: Dict) -> str:
        """Email operations via SMTP/IMAP"""
        action = params.get("action", "read")

        if action == "send":
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
            if not to:
                return "⚠️ Missing 'to' field — who should I send the email to?"

            try:
                import smtplib
                from email.mime.text import MIMEText
                from email.mime.multipart import MIMEMultipart

                msg = MIMEMultipart()
                msg["From"] = getattr(self.config, "smtp_from", None) or self.config.smtp_user
                msg["To"] = to
                msg["Subject"] = subject
                msg.attach(MIMEText(body, "plain"))

                port = int(getattr(self.config, "smtp_port", 587))
                with smtplib.SMTP(host, port) as server:
                    server.starttls()
                    server.login(self.config.smtp_user, self.config.smtp_password)
                    server.send_message(msg)

                logger.info(f"📧 Email sent to {to}: {subject}")
                return f"✅ Email sent to **{to}**\nSubject: {subject}"
            except Exception as e:
                logger.error(f"Email send failed: {e}")
                return f"❌ Failed to send email: {e}"

        elif action == "read":
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
                    _, data = imap.search(None, "ALL")
                    ids = data[0].split()
                    if not ids:
                        return f"📧 No emails in {folder}."

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
                        results.append(f"• **{subj}**\n  From: {frm}\n  Date: {date}")

                return f"📧 **Latest {len(results)} emails ({folder}):**\n\n" + "\n\n".join(results)
            except Exception as e:
                logger.error(f"Email read failed: {e}")
                return f"❌ Failed to read email: {e}"

        else:
            return f"Unknown email action: {action}. Use: send, read"

    async def _calendar_tool(self, params: Dict) -> str:
        """Internal calendar operations (stored locally)"""
        action = params.get("action", "list")

        try:
            # Load calendar events
            events = json.loads(self.calendar_file.read_text())

            if action == "list":
                # Show upcoming events
                now = datetime.now()
                upcoming = [e for e in events if datetime.fromisoformat(e["datetime"]) >= now]
                upcoming.sort(key=lambda x: x["datetime"])

                if not upcoming:
                    return "📅 No upcoming events in your calendar."

                result = "📅 **Upcoming Events:**\n\n"
                for event in upcoming[:10]:  # Show next 10
                    dt = datetime.fromisoformat(event["datetime"])
                    result += f"• **{event['title']}**\n"
                    result += f"  📆 {dt.strftime('%Y-%m-%d %H:%M')}\n"
                    if event.get("description"):
                        result += f"  📝 {event['description']}\n"
                    result += "\n"
                return result.strip()

            elif action == "add":
                title = params.get("title", "Untitled Event")
                date_str = params.get("date", "")
                description = params.get("description", "")

                if not date_str:
                    return "⚠️ Please provide a date/time (e.g., '2026-02-20 15:00' or 'tomorrow at 3pm')"

                # Parse date (simple ISO format support)
                try:
                    # Try ISO format first
                    event_dt = datetime.fromisoformat(date_str)
                except ValueError:
                    # Try common formats
                    for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%d", "%m/%d/%Y %H:%M", "%m/%d/%Y"]:
                        try:
                            event_dt = datetime.strptime(date_str, fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        return f"⚠️ Could not parse date '{date_str}'. Use format: YYYY-MM-DD HH:MM"

                # Add event
                new_event = {
                    "id": len(events) + 1,
                    "title": title,
                    "datetime": event_dt.isoformat(),
                    "description": description,
                    "created_at": datetime.now().isoformat(),
                }
                events.append(new_event)

                # Save
                self.calendar_file.write_text(json.dumps(events, indent=2))

                return f"✅ Event added: **{title}** on {event_dt.strftime('%Y-%m-%d %H:%M')}"

            elif action == "delete":
                event_id = params.get("id")
                if not event_id:
                    return "⚠️ Please provide event ID to delete"

                events = [e for e in events if e["id"] != int(event_id)]
                self.calendar_file.write_text(json.dumps(events, indent=2))
                return f"✅ Event {event_id} deleted"

            else:
                return f"Unknown calendar action: {action}. Use: list, add, delete"

        except Exception as e:
            logger.error(f"Calendar error: {e}")
            return f"⚠️ Calendar error: {str(e)}"

    async def _browser_tool(self, params: Dict) -> str:
        """Browser automation and web scraping using Playwright"""
        action = params.get("action", "scrape")

        if action == "snapshot":
            url = params.get("url", "")
            format_type = params.get("format", "aria")

            result = await self.browser_engine.snapshot(url, format_type)
            if result.get("success"):
                refs_text = f"📸 Snapshot of {result.get('url')}\n"
                refs_text += f"Found {result.get('count', 0)} interactive elements:\n\n"

                for ref_data in result.get("refs", [])[:20]:  # Limit to first 20
                    ref_text = f"{ref_data['ref']}: {ref_data['role']}"
                    if ref_data.get("name"):
                        ref_text += f" '{ref_data['name']}'"
                    refs_text += ref_text + "\n"

                if result.get("count", 0) > 20:
                    refs_text += f"\n... and {result.get('count') - 20} more elements"

                return refs_text
            else:
                return f"❌ Snapshot failed: {result.get('error', 'Unknown error')}"

        elif action == "scrape":
            url = params.get("url")
            result = await self.browser_engine.scrape_page(url)

            if not result.get("success"):
                return f"⚠️ {result.get('error', 'Unknown error')}"

            return f"🌐 **{result['title']}**\n\nURL: {result['url']}\n\n{result['content']}"

        elif action == "search":
            query = params.get("query")
            if not query:
                return "⚠️ Please provide a search query"

            logger.info(f"🔍 Searching web for: '{query}'")
            num_results = params.get("num_results", 5)
            result = await self.browser_engine.search_web(query, num_results)

            logger.info(
                f"Search returned: success={result.get('success')}, count={result.get('count', 0)}"
            )

            if not result.get("success"):
                return f"⚠️ {result.get('error', 'Unknown error')}"

            # Check if we got results
            results_list = result.get("results", [])
            if not results_list or len(results_list) == 0:
                logger.warning(f"No search results found for '{query}'")
                return f"🔍 No search results found for '{query}'. The search engine returned 0 results."

            # Format results
            response = f"🔍 **Search Results for: {query}**\n\n"
            for i, res in enumerate(results_list, 1):
                response += f"**{i}. {res.get('title', 'Untitled')}**\n"
                response += f"{res.get('snippet', 'No description')}\n"
                response += f"🔗 {res.get('url', '')}\n\n"

            return response.strip()

        elif action == "screenshot":
            url = params.get("url")
            if not url:
                return "⚠️ Please provide a URL for screenshot"

            result = await self.browser_engine.get_page_screenshot(url)

            if not result.get("success"):
                return f"⚠️ {result.get('error', 'Unknown error')}"

            return f"📸 Screenshot saved: {result['path']}"

        else:
            return f"Unknown browser action: {action}. Available: scrape, search, screenshot"

    async def _web_action_tool(self, params: Dict) -> str:
        """Execute interactive web actions using refs or selectors

        Actions: click, type, hover, drag, select, fill, press, evaluate, wait, submit
        Use refs from snapshot for stable automation
        """
        url = params.get("url")
        action = params.get("action", "")
        ref = params.get("ref")
        selector = params.get("selector")
        value = params.get("value")

        if not action:
            return "⚠️ Missing action parameter"

        try:
            result = await self.browser_engine.execute_action(
                url=url, action=action, ref=ref, selector=selector, value=value
            )

            if result.get("success"):
                action_name = result.get("action", action).capitalize()
                details = ""

                if "value" in result:
                    details = f": '{result['value']}'"
                elif "key" in result:
                    details = f": {result['key']}"
                elif "result" in result:
                    details = f" -> {result['result']}"

                return f"✅ {action_name}{details}"
            else:
                return f"❌ {result.get('error', 'Unknown error')}"
        except Exception as e:
            return f"❌ Error: {str(e)}"

    async def _file_tool(self, params: Dict) -> str:
        """
        DEPRECATED: Use specific file tools instead
        (read_file, write_file, edit_file, list_directory, etc.)
        """
        action = params.get("action", "list")

        if action == "list":
            return await self._list_directory_tool({"path": params.get("path", ".")})
        elif action == "read":
            return await self._read_file_tool({"path": params.get("path", "")})
        else:
            return "⚠️ Use specific file tools: read_file, write_file, edit_file, list_directory"

    async def _weather_tool(self, params: Dict) -> str:
        """Weather information using wttr.in (no API key required)"""
        location = params.get("location", "")

        if not location:
            # Use IP-based auto-detection
            location = ""

        try:
            # Call wttr.in API (free, no API key needed)
            async with aiohttp.ClientSession() as session:
                # Format: ?format=j1 for JSON, ?m for metric
                url = f"https://wttr.in/{location}?format=j1&m"
                headers = {"User-Agent": "curl/7.68.0"}  # wttr.in prefers curl user agent

                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        # Parse weather data
                        current = data["current_condition"][0]
                        location_info = data["nearest_area"][0]

                        temp = current["temp_C"]
                        feels_like = current["FeelsLikeC"]
                        humidity = current["humidity"]
                        description = current["weatherDesc"][0]["value"]
                        wind_speed = current["windspeedKmph"]
                        city_name = location_info.get("areaName", [{}])[0].get(
                            "value", location or "Your location"
                        )

                        # Weather emoji mapping
                        weather_code = int(current["weatherCode"])
                        weather_emojis = {
                            113: "☀️",  # Clear/Sunny
                            116: "⛅",  # Partly cloudy
                            119: "☁️",  # Cloudy
                            122: "☁️",  # Overcast
                            143: "🌫️",  # Mist
                            176: "🌦️",  # Patchy rain possible
                            200: "⛈️",  # Thundery outbreaks possible
                            248: "🌫️",  # Fog
                            263: "🌧️",  # Patchy light drizzle
                            266: "🌧️",  # Light drizzle
                            281: "🌧️",  # Freezing drizzle
                            284: "🌧️",  # Heavy freezing drizzle
                            293: "🌧️",  # Patchy light rain
                            296: "🌧️",  # Light rain
                            299: "🌧️",  # Moderate rain at times
                            302: "🌧️",  # Moderate rain
                            305: "🌧️",  # Heavy rain at times
                            308: "🌧️",  # Heavy rain
                            311: "🌧️",  # Light freezing rain
                            314: "🌧️",  # Moderate or heavy freezing rain
                            317: "🌨️",  # Light sleet
                            320: "🌨️",  # Moderate or heavy sleet
                            323: "❄️",  # Patchy light snow
                            326: "❄️",  # Light snow
                            329: "❄️",  # Patchy moderate snow
                            332: "❄️",  # Moderate snow
                            335: "❄️",  # Patchy heavy snow
                            338: "❄️",  # Heavy snow
                            350: "🌨️",  # Ice pellets
                            353: "🌧️",  # Light rain shower
                            356: "🌧️",  # Moderate or heavy rain shower
                            359: "🌧️",  # Torrential rain shower
                            362: "🌨️",  # Light sleet showers
                            365: "🌨️",  # Moderate or heavy sleet showers
                            368: "❄️",  # Light snow showers
                            371: "❄️",  # Moderate or heavy snow showers
                            374: "🌨️",  # Light showers of ice pellets
                            377: "🌨️",  # Moderate or heavy showers of ice pellets
                            386: "⛈️",  # Patchy light rain with thunder
                            389: "⛈️",  # Moderate or heavy rain with thunder
                            392: "⛈️",  # Patchy light snow with thunder
                            395: "⛈️",  # Moderate or heavy snow with thunder
                        }

                        emoji = weather_emojis.get(weather_code, "🌤️")

                        return (
                            f"{emoji} **Weather in {city_name}**\n"
                            f"🌡️ Temperature: {temp}°C (feels like {feels_like}°C)\n"
                            f"💧 Humidity: {humidity}%\n"
                            f"💨 Wind: {wind_speed} km/h\n"
                            f"📝 Conditions: {description}"
                        )
                    else:
                        return f"⚠️ Weather service error: {resp.status}"
        except Exception as e:
            logger.error(f"Weather API error: {e}")
            return f"⚠️ Failed to fetch weather data: {str(e)}"

    # ========== VOICE TOOLS ==========

    async def _voice_speak_tool(self, params: Dict) -> str:
        """Text-to-speech conversion"""
        text = params.get("text", "")
        output_file = params.get("output_file")

        try:
            audio_path = await self.voice.speak(text, output_file=output_file)
            return f"🔊 Audio generated: {audio_path}"
        except Exception as e:
            return f"❌ TTS failed: {str(e)}"

    async def _voice_listen_tool(self, params: Dict) -> str:
        """Speech-to-text conversion"""
        audio_file = params.get("audio_file")

        try:
            text = await self.voice.listen(audio_file=audio_file)
            return f"📝 Transcription:\n{text}"
        except Exception as e:
            return f"❌ STT failed: {str(e)}"

    # ========== IMAGE TOOLS ==========

    async def _generate_image_tool(self, params: Dict) -> str:
        """Generate images from text prompts"""
        prompt = params.get("prompt", "")
        model = params.get("model", "dall-e-3")
        size = params.get("size", "1024x1024")
        output_path = params.get("output_path", "generated_image.png")

        try:
            result = await self.image.generate(
                prompt=prompt, model=model, size=size, output_path=output_path
            )

            if result.get("success"):
                return f"🎨 Image generated: {result.get('path')}\nPrompt: {prompt}"
            else:
                return f"❌ Generation failed: {result.get('error')}"
        except Exception as e:
            return f"❌ Image generation error: {str(e)}"

    async def _analyze_image_tool(self, params: Dict) -> str:
        """Analyze image content"""
        image_path = params.get("image_path", "")

        try:
            result = await self.image.analyze(image_path)

            if result.get("success"):
                labels = ", ".join(result.get("labels", []))
                description = result.get("description", "No description")

                return f"🔍 Image Analysis:\n{description}\n\nDetected: {labels}"
            else:
                return f"❌ Analysis failed: {result.get('error')}"
        except Exception as e:
            return f"❌ Image analysis error: {str(e)}"

    async def _ocr_tool(self, params: Dict) -> str:
        """Extract text from images"""
        image_path = params.get("image_path", "")
        language = params.get("language", "eng")

        try:
            result = await self.image.ocr(image_path, language=language)

            if result.get("success"):
                text = result.get("text", "")
                confidence = result.get("confidence", 0)

                return f"📄 OCR Results (confidence: {confidence}%):\n\n{text}"
            else:
                return f"❌ OCR failed: {result.get('error')}"
        except Exception as e:
            return f"❌ OCR error: {str(e)}"

    # ========== DATABASE TOOLS ==========

    async def _database_query_tool(self, params: Dict) -> str:
        """Execute database queries"""
        query = params.get("query", "")
        db_type = params.get("db_type", "sqlite")
        database = params.get("database", "default.db")

        try:
            result = await self.database.execute(query=query, db_type=db_type, database=database)

            if result.get("success"):
                rows = result.get("rows", [])
                row_count = len(rows)

                return f"✅ Query executed successfully\nRows returned: {row_count}\n\n{json.dumps(rows[:10], indent=2)}"
            else:
                return f"❌ Query failed: {result.get('error')}"
        except Exception as e:
            return f"❌ Database error: {str(e)}"

    # ========== RAG TOOLS ==========

    async def _vector_search_tool(self, params: Dict) -> str:
        """Semantic search using vector database, falls back to web search if unavailable"""
        query = params.get("query", "")
        collection = params.get("collection", "default")
        top_k = int(params.get("top_k", 5))  # ensure int, not string

        try:
            results = await self.rag.search(query=query, collection=collection, top_k=top_k)

            if results:
                formatted = "\n\n".join(
                    [
                        f"**Result {i+1}** (score: {r.get('score', 0):.2f}):\n{r.get('content', '')}"
                        for i, r in enumerate(results)
                    ]
                )
                return f"🔍 Found {len(results)} results:\n\n{formatted}"
            else:
                # Local knowledge base is empty — fall back to web search
                logger.info(f"Vector DB empty for '{query}', falling back to browser_search")
                return await self._browser_tool(
                    {"action": "search", "query": query, "num_results": int(top_k)}
                )
        except Exception as e:
            # Embedding model not available — fall back to web search
            logger.warning(f"Vector search unavailable ({e}), falling back to browser_search")
            return await self._browser_tool({"action": "search", "query": query, "num_results": 5})

    # ========== CODE EXECUTION TOOLS ==========

    async def _execute_code_tool(self, params: Dict) -> str:
        """Execute code in sandbox"""
        code = params.get("code", "")
        language = params.get("language", "python")
        timeout = params.get("timeout", 30)

        try:
            result = await self.code_executor.execute(code=code, language=language, timeout=timeout)

            if result.get("success"):
                output = result.get("output", "")
                return f"✅ Code executed successfully:\n\n```\n{output}\n```"
            else:
                error = result.get("error", "Unknown error")
                return f"❌ Execution failed:\n{error}"
        except Exception as e:
            return f"❌ Code execution error: {str(e)}"

    # ========== API CLIENT TOOLS ==========

    async def _api_request_tool(self, params: Dict) -> str:
        """Make HTTP API requests"""
        url = params.get("url", "")
        method = params.get("method", "GET")
        headers = params.get("headers", {})
        data = params.get("data")

        try:
            result = await self.api_client.request(
                url=url, method=method, headers=headers, data=data
            )

            if result.get("success"):
                response_data = result.get("data", "")
                status_code = result.get("status_code", 200)

                return f"✅ API request successful (status: {status_code}):\n\n{json.dumps(response_data, indent=2)[:500]}"
            else:
                return f"❌ API request failed: {result.get('error')}"
        except Exception as e:
            return f"❌ API request error: {str(e)}"

    # ========== SKILL CREATION TOOLS ==========

    async def _create_skill_tool(self, params: Dict) -> str:
        """Create a new dynamic skill"""
        name = params.get("name", "")
        description = params.get("description", "")
        code = params.get("code", "")
        author = params.get("author", "sable")

        metadata = {"author": author, "created_at": datetime.utcnow().isoformat()}

        try:
            result = await self.skill_creator.create_skill(name, description, code, metadata)

            if result.get("success"):
                return f"✅ Skill '{name}' created successfully!\n\nPath: {result.get('path')}\n\nThe skill has been validated and is ready to use."
            else:
                return f"❌ Failed to create skill: {result.get('error')}"
        except Exception as e:
            return f"❌ Skill creation error: {str(e)}"

    async def _list_skills_tool(self, params: Dict) -> str:
        """List all custom skills"""
        try:
            skills = await self.skill_creator.list_skills()

            if not skills:
                return (
                    "📦 No custom skills created yet.\n\nUse create_skill to add new functionality!"
                )

            formatted = "\n".join(
                [
                    f"• **{s['name']}** - {s['description']}\n  Status: {'✅ Enabled' if s.get('enabled', True) else '❌ Disabled'}\n  Author: {s.get('metadata', {}).get('author', 'unknown')}"
                    for s in skills
                ]
            )

            return f"📦 Custom Skills ({len(skills)}):\n\n{formatted}"
        except Exception as e:
            return f"❌ Error listing skills: {str(e)}"

    # ========== DESKTOP CONTROL TOOLS ==========

    async def _desktop_screenshot_tool(self, params: Dict) -> str:
        """Take a screenshot and optionally auto-analyze with vision AI"""
        save_path = params.get("save_path")
        analyze = params.get("analyze", True)  # Auto-analyze by default
        result = await self.computer.screenshot(save_path=save_path)
        if result.get("success"):
            w, h = result.get("width"), result.get("height")
            if result.get("path"):
                base = f"📸 Screenshot saved: {result['path']} ({w}x{h})"
            else:
                base = f"📸 Screenshot captured ({w}x{h})"

            # Auto-analyze with vision AI so the LLM knows what's on screen
            if analyze and not save_path:
                vision_result = await self.vision.screen_analyze()
                if vision_result.get("success"):
                    return f"{base}\n\n👁️ **What's on screen:**\n{vision_result['description']}"
            return base
        return f"❌ Screenshot failed: {result.get('error')}"

    async def _desktop_click_tool(self, params: Dict) -> str:
        """Click mouse at coordinates"""
        x = params.get("x", 0)
        y = params.get("y", 0)
        button = params.get("button", "left")
        clicks = params.get("clicks", 1)
        result = await self.computer.mouse_click(x, y, button=button, clicks=clicks)
        if result.get("success"):
            return f"🖱️ Clicked ({button} x{clicks}) at ({x}, {y})"
        return f"❌ Click failed: {result.get('error')}"

    async def _desktop_type_tool(self, params: Dict) -> str:
        """Type text via keyboard"""
        text = params.get("text", "")
        result = await self.computer.keyboard_type(text)
        if result.get("success"):
            return f"⌨️ Typed {result.get('length', len(text))} characters"
        return f"❌ Type failed: {result.get('error')}"

    async def _desktop_hotkey_tool(self, params: Dict) -> str:
        """Press key or key combination"""
        key = params.get("key", "")
        result = await self.computer.keyboard_press(key)
        if result.get("success"):
            return f"⌨️ Pressed: {key}"
        return f"❌ Hotkey failed: {result.get('error')}"

    async def _desktop_scroll_tool(self, params: Dict) -> str:
        """Scroll the mouse wheel"""
        amount = params.get("amount", 0)
        x = params.get("x")
        y = params.get("y")
        result = await self.computer.mouse_scroll(amount, x=x, y=y)
        if result.get("success"):
            return f"🖱️ Scrolled {amount}"
        return f"❌ Scroll failed: {result.get('error')}"

    async def _desktop_mouse_move_tool(self, params: Dict) -> str:
        """Move mouse to coordinates"""
        x = params.get("x", 0)
        y = params.get("y", 0)
        result = await self.computer.mouse_move(x, y)
        if result.get("success"):
            return f"🖱️ Mouse moved to ({x}, {y})"
        return f"❌ Move failed: {result.get('error')}"

    # ========== VISION / AUTONOMOUS COMPUTER-USE TOOLS ==========

    async def _screen_analyze_tool(self, params: Dict) -> str:
        """Screenshot → Ollama VLM → describe what's on screen"""
        question = params.get("question")
        result = await self.vision.screen_analyze(question=question)
        if result.get("success"):
            model = result.get("model", "VLM")
            desc = result["description"]
            return f"👁️ **Screen Analysis** (via {model}):\n{desc}"
        return f"❌ Screen analysis failed: {result.get('error')}"

    async def _screen_find_tool(self, params: Dict) -> str:
        """Find a UI element on screen by description, return coordinates"""
        description = params.get("description", "")
        result = await self.vision.screen_find(description)
        if result.get("success"):
            return (
                f"👁️ Found '{description}' at coordinates ({result['x']}, {result['y']}). "
                f"Use desktop_click with x={result['x']}, y={result['y']} to click it."
            )
        return f"❌ '{description}' not found on screen: {result.get('error')}"

    async def _screen_click_on_tool(self, params: Dict) -> str:
        """Find element visually and click it"""
        description = params.get("description", "")
        double = params.get("double", False)
        result = await self.vision.screen_click_on(description, double=double)
        if result.get("success"):
            return f"🖱️ {result['message']}"
        return f"❌ Could not click '{description}': {result.get('error')}"

    async def _open_app_tool(self, params: Dict) -> str:
        """Open an application by name"""
        name = params.get("name", "")
        result = await self.vision.open_app(name)
        if result.get("success"):
            return f"🚀 {result['message']}"
        return f"❌ {result.get('error')}"

    async def _window_list_tool(self, params: Dict) -> str:
        """List all open windows"""
        result = await self.vision.window_list()
        if result.get("success"):
            windows = result.get("windows", [])
            if not windows:
                return "📋 No windows found"
            lines = [f"  [{w['id']}] {w['title']}" for w in windows]
            return f"📋 Open windows ({result['count']}):\n" + "\n".join(lines)
        return f"❌ {result.get('error')}"

    async def _window_focus_tool(self, params: Dict) -> str:
        """Bring a window to front by title"""
        name = params.get("name", "")
        result = await self.vision.window_focus(name)
        if result.get("success"):
            return f"🪟 {result['message']}"
        return f"❌ {result.get('error')}"

    # ========== X (TWITTER) TOOLS ==========

    async def _x_post_tweet_tool(self, params: Dict) -> str:
        """Post a tweet on X"""
        if not self.x_skill or not self.x_skill.is_available():
            return "❌ X skill not initialized. Set X_USERNAME, X_EMAIL, X_PASSWORD in .env"
        text = params.get("text", "")
        media_paths = params.get("media_paths")
        reply_to = params.get("reply_to")
        result = await self.x_skill.post_tweet(text, media_paths=media_paths, reply_to=reply_to)
        if result.get("success"):
            url = result.get("url", "")
            return f"✅ Tweet posted!\n📝 {text[:100]}{'...' if len(text)>100 else ''}\n🔗 {url}"
        return f"❌ Failed to post tweet: {result.get('error')}"

    async def _x_post_thread_tool(self, params: Dict) -> str:
        """Post a thread on X"""
        if not self.x_skill or not self.x_skill.is_available():
            return "❌ X skill not initialized. Set X_USERNAME, X_EMAIL, X_PASSWORD in .env"
        tweets = params.get("tweets", [])
        if not tweets:
            return "❌ No tweets provided for thread"
        result = await self.x_skill.post_thread(tweets)
        if result.get("success"):
            url = result.get("thread_url", "")
            return f"✅ Thread posted ({result['thread_length']} tweets)\n🔗 {url}"
        return f"❌ Thread failed: {result.get('error')}"

    async def _x_search_tool(self, params: Dict) -> str:
        """Search tweets on X"""
        if not self.x_skill or not self.x_skill.is_available():
            return "❌ X skill not initialized."
        query = params.get("query", "")
        search_type = params.get("search_type", "Latest")
        count = params.get("count", 10)
        result = await self.x_skill.search_tweets(query, search_type=search_type, count=count)
        if result.get("success"):
            tweets = result.get("tweets", [])
            if not tweets:
                return f"🔍 No tweets found for '{query}'"
            lines = []
            for t in tweets:
                lines.append(f"  @{t.get('username', '?')}: {t.get('text', '')[:120]}")
                lines.append(f"    ❤️ {t.get('likes', 0)} | 🔁 {t.get('retweets', 0)}")
            return f"🔍 Search results for '{query}' ({len(tweets)}):\n" + "\n".join(lines)
        return f"❌ Search failed: {result.get('error')}"

    async def _x_get_trends_tool(self, params: Dict) -> str:
        """Get trending topics on X"""
        if not self.x_skill or not self.x_skill.is_available():
            return "❌ X skill not initialized."
        category = params.get("category", "trending")
        result = await self.x_skill.get_trends(category)
        if result.get("success"):
            trends = result.get("trends", [])
            lines = [f"  {i+1}. {t.get('name', '?')}" for i, t in enumerate(trends)]
            return f"📈 Trending on X ({category}):\n" + "\n".join(lines)
        return f"❌ Trends failed: {result.get('error')}"

    async def _x_like_tool(self, params: Dict) -> str:
        """Like a tweet"""
        if not self.x_skill or not self.x_skill.is_available():
            return "❌ X skill not initialized."
        result = await self.x_skill.like_tweet(params.get("tweet_id", ""))
        return f"❤️ Tweet liked!" if result.get("success") else f"❌ {result.get('error')}"

    async def _x_retweet_tool(self, params: Dict) -> str:
        """Retweet a tweet"""
        if not self.x_skill or not self.x_skill.is_available():
            return "❌ X skill not initialized."
        result = await self.x_skill.retweet(params.get("tweet_id", ""))
        return f"🔁 Retweeted!" if result.get("success") else f"❌ {result.get('error')}"

    async def _x_reply_tool(self, params: Dict) -> str:
        """Reply to a tweet"""
        if not self.x_skill or not self.x_skill.is_available():
            return "❌ X skill not initialized."
        result = await self.x_skill.reply(params.get("tweet_id", ""), params.get("text", ""))
        if result.get("success"):
            return f"💬 Reply posted! {result.get('url', '')}"
        return f"❌ Reply failed: {result.get('error')}"

    async def _x_get_user_tool(self, params: Dict) -> str:
        """Get user profile"""
        if not self.x_skill or not self.x_skill.is_available():
            return "❌ X skill not initialized."
        result = await self.x_skill.get_user(params.get("username", ""))
        if result.get("success"):
            return (
                f"👤 @{result.get('username')}\n"
                f"   Name: {result.get('name')}\n"
                f"   Bio: {result.get('bio', 'N/A')}\n"
                f"   Followers: {result.get('followers', 0):,}\n"
                f"   Following: {result.get('following', 0):,}\n"
                f"   Tweets: {result.get('tweets_count', 0):,}"
            )
        return f"❌ {result.get('error')}"

    async def _x_get_user_tweets_tool(self, params: Dict) -> str:
        """Get a user's tweets"""
        if not self.x_skill or not self.x_skill.is_available():
            return "❌ X skill not initialized."
        username = params.get("username", "")
        tweet_type = params.get("tweet_type", "Tweets")
        count = params.get("count", 10)
        result = await self.x_skill.get_user_tweets(username, tweet_type=tweet_type, count=count)
        if result.get("success"):
            tweets = result.get("tweets", [])
            lines = [f"  - {t.get('text', '')[:140]}" for t in tweets]
            return f"📜 @{username} tweets ({len(tweets)}):\n" + "\n".join(lines)
        return f"❌ {result.get('error')}"

    async def _x_follow_tool(self, params: Dict) -> str:
        """Follow a user"""
        if not self.x_skill or not self.x_skill.is_available():
            return "❌ X skill not initialized."
        result = await self.x_skill.follow_user(params.get("username", ""))
        return f"✅ Followed @{params.get('username')}" if result.get("success") else f"❌ {result.get('error')}"

    async def _x_send_dm_tool(self, params: Dict) -> str:
        """Send a DM"""
        if not self.x_skill or not self.x_skill.is_available():
            return "❌ X skill not initialized."
        result = await self.x_skill.send_dm(params.get("user_id", ""), params.get("text", ""))
        return f"✉️ DM sent!" if result.get("success") else f"❌ {result.get('error')}"

    async def _x_delete_tweet_tool(self, params: Dict) -> str:
        """Delete a tweet"""
        if not self.x_skill or not self.x_skill.is_available():
            return "❌ X skill not initialized."
        result = await self.x_skill.delete_tweet(params.get("tweet_id", ""))
        return f"🗑️ Tweet deleted!" if result.get("success") else f"❌ {result.get('error')}"

    # ========== GROK AI TOOLS ==========

    async def _grok_chat_tool(self, params: Dict) -> str:
        """Chat with Grok AI"""
        if not self.grok_skill:
            return "❌ Grok skill not initialized. Set X_USERNAME, X_EMAIL, X_PASSWORD in .env"
        message = params.get("message", "")
        conversation_id = params.get("conversation_id")
        result = await self.grok_skill.chat(message, conversation_id=conversation_id)
        if result.get("success"):
            conv_id = result.get("conversation_id", "")
            return f"🤖 **Grok**: {result['response']}\n\n_Conversation: {conv_id}_"
        return f"❌ Grok error: {result.get('error')}"

    async def _grok_analyze_image_tool(self, params: Dict) -> str:
        """Analyze images with Grok"""
        if not self.grok_skill:
            return "❌ Grok skill not initialized."
        image_paths = params.get("image_paths", [])
        prompt = params.get("prompt", "Please describe these images in detail.")
        result = await self.grok_skill.analyze_image(image_paths, prompt)
        if result.get("success"):
            return f"👁️ **Grok Vision**: {result['response']}"
        return f"❌ Grok image analysis error: {result.get('error')}"

    async def _grok_generate_image_tool(self, params: Dict) -> str:
        """Generate images with Grok"""
        if not self.grok_skill:
            return "❌ Grok skill not initialized."
        prompt = params.get("prompt", "")
        save_path = params.get("save_path")
        result = await self.grok_skill.generate_image(prompt, save_path=save_path)
        if result.get("success"):
            images = result.get("images", [])
            return f"🎨 **Grok Image**: Generated {len(images)} image(s)\n" + "\n".join(f"  📁 {p}" for p in images)
        return f"❌ Grok image generation error: {result.get('error')}"

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

    # ========== TRADING TOOLS ==========

    async def _trading_portfolio_tool(self, params: Dict) -> str:
        """Get portfolio summary"""
        if not self.trading_skill:
            return "⚠️ Trading is not enabled. Set TRADING_ENABLED=true in your environment."
        return await self.trading_skill.get_portfolio(params)

    async def _trading_price_tool(self, params: Dict) -> str:
        """Get current price"""
        if not self.trading_skill:
            return "⚠️ Trading is not enabled."
        return await self.trading_skill.get_price(params)

    async def _trading_analyze_tool(self, params: Dict) -> str:
        """Analyze market"""
        if not self.trading_skill:
            return "⚠️ Trading is not enabled."
        return await self.trading_skill.analyze_market(params)

    async def _trading_place_trade_tool(self, params: Dict) -> str:
        """Place a trade"""
        if not self.trading_skill:
            return "⚠️ Trading is not enabled."
        return await self.trading_skill.place_trade(params)

    async def _trading_cancel_order_tool(self, params: Dict) -> str:
        """Cancel an order"""
        if not self.trading_skill:
            return "⚠️ Trading is not enabled."
        return await self.trading_skill.cancel_order(params)

    async def _trading_history_tool(self, params: Dict) -> str:
        """Get trade history"""
        if not self.trading_skill:
            return "⚠️ Trading is not enabled."
        return await self.trading_skill.get_trade_history(params)

    async def _trading_signals_tool(self, params: Dict) -> str:
        """Get current signals"""
        if not self.trading_skill:
            return "⚠️ Trading is not enabled."
        return await self.trading_skill.get_signals(params)

    async def _trading_start_scan_tool(self, params: Dict) -> str:
        """Start background scanning"""
        if not self.trading_skill:
            return "⚠️ Trading is not enabled."
        return await self.trading_skill.start_scanning(params)

    async def _trading_stop_scan_tool(self, params: Dict) -> str:
        """Stop background scanning"""
        if not self.trading_skill:
            return "⚠️ Trading is not enabled."
        return await self.trading_skill.stop_scanning(params)

    async def _trading_risk_status_tool(self, params: Dict) -> str:
        """Get risk status"""
        if not self.trading_skill:
            return "⚠️ Trading is not enabled."
        return await self.trading_skill.get_risk_status(params)

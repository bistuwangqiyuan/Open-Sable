"""
Tool registry for Open-Sable - manages all available actions
"""

import logging
import json
import aiohttp
from typing import Dict, Any, Callable, List
from pathlib import Path
from datetime import datetime

from ..computer_tools import ComputerTools
from ..vision_tools import VisionTools
from ..browser import BrowserEngine
from ..skill_creator import SkillCreator

try:
    from ...skills.trading.trading_skill import TradingSkill
except ImportError:
    TradingSkill = None  # type: ignore

try:
    from ...skills import VoiceSkill, ImageSkill, DatabaseSkill, RAGSkill, CodeExecutor, APIClient, XSkill, GrokSkill
    from ...skills import InstagramSkill, FacebookSkill, LinkedInSkill, TikTokSkill, YouTubeSkill
except ImportError:
    # Graceful fallback if a skill is not available
    from ...skills import VoiceSkill, DatabaseSkill, RAGSkill, CodeExecutor, APIClient
    from ...skills.media.image_skill import ImageAnalyzer as ImageSkill  # type: ignore
    XSkill = None  # type: ignore
    GrokSkill = None  # type: ignore
    InstagramSkill = None  # type: ignore
    FacebookSkill = None  # type: ignore
    LinkedInSkill = None  # type: ignore
    TikTokSkill = None  # type: ignore
    YouTubeSkill = None  # type: ignore

logger = logging.getLogger(__name__)

# Tool implementation mixins (split for maintainability)
from ._core_tools import CoreToolsMixin
from ._desktop_vision import DesktopVisionToolsMixin
from ._social import SocialToolsMixin
from ._productivity import ProductivityToolsMixin
from ._trading import TradingToolsMixin
from ._marketplace import MarketplaceToolsMixin
from ._mobile import MobileToolsMixin



class ToolRegistry(
    CoreToolsMixin,
    DesktopVisionToolsMixin,
    SocialToolsMixin,
    ProductivityToolsMixin,
    TradingToolsMixin,
    MarketplaceToolsMixin,
    MobileToolsMixin,
):
    """Registry of all available tools/actions.

    Tool implementations are organized into mixin classes:
    - CoreToolsMixin: file system, commands, browser, media, code, skills
    - DesktopVisionToolsMixin: desktop control, vision, autonomous computer-use
    - SocialToolsMixin: X/Twitter, Grok, Instagram, Facebook, LinkedIn, TikTok, YouTube
    - ProductivityToolsMixin: documents, email, calendar, clipboard, OCR
    - TradingToolsMixin: trading portfolio, prices, orders, analysis
    - MobileToolsMixin: phone notification, reminders, geofence, location, device status
    """

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
        # Instagram tools
        "ig_upload_photo": "social_write",
        "ig_upload_reel": "social_write",
        "ig_upload_story": "social_write",
        "ig_search_users": "social_read",
        "ig_search_hashtags": "social_read",
        "ig_get_user_info": "social_read",
        "ig_get_timeline": "social_read",
        "ig_like_media": "social_write",
        "ig_comment": "social_write",
        "ig_follow_user": "social_write",
        "ig_send_dm": "social_write",
        "ig_get_media_comments": "social_read",
        # Facebook tools
        "fb_post": "social_write",
        "fb_upload_photo": "social_write",
        "fb_get_feed": "social_read",
        "fb_like_post": "social_write",
        "fb_comment": "social_write",
        "fb_get_profile": "social_read",
        "fb_search": "social_read",
        # LinkedIn tools
        "linkedin_get_profile": "social_read",
        "linkedin_search_people": "social_read",
        "linkedin_search_companies": "social_read",
        "linkedin_search_jobs": "social_read",
        "linkedin_post_update": "social_write",
        "linkedin_send_message": "social_write",
        "linkedin_send_connection": "social_write",
        "linkedin_get_feed": "social_read",
        # TikTok tools (read-only)
        "tiktok_trending": "social_read",
        "tiktok_search_videos": "social_read",
        "tiktok_search_users": "social_read",
        "tiktok_get_user_info": "social_read",
        "tiktok_get_user_videos": "social_read",
        "tiktok_get_hashtag_videos": "social_read",
        # YouTube tools
        "yt_search_videos": "social_read",
        "yt_search_channels": "social_read",
        "yt_get_channel": "social_read",
        "yt_get_channel_videos": "social_read",
        "yt_get_video": "social_read",
        "yt_get_comments": "social_read",
        "yt_comment": "social_write",
        "yt_get_playlist": "social_read",
        "yt_rate_video": "social_write",
        "yt_subscribe": "social_write",
        "yt_trending": "social_read",
        "yt_upload_video": "social_write",
        # Skills Marketplace
        "marketplace_search": "marketplace_read",
        "marketplace_info": "marketplace_read",
        "marketplace_install": "marketplace_install",
        "marketplace_review": "marketplace_write",
        # Mobile phone tools
        "phone_notify": "mobile_write",
        "phone_reminder": "mobile_write",
        "phone_geofence": "mobile_write",
        "phone_location": "mobile_read",
        "phone_device": "mobile_read",
    }

    def __init__(self, config):
        self.config = config
        self.tools: Dict[str, Callable] = {}
        self._permission_manager = None
        self._custom_schemas: List[Dict[str, Any]] = []  # @function_tool schemas

        # Initialize permission manager for RBAC
        try:
            from ..security import PermissionManager

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

        # Social media skills (Instagram, Facebook, LinkedIn, TikTok)
        self.instagram_skill = InstagramSkill(config) if InstagramSkill else None
        self.facebook_skill = FacebookSkill(config) if FacebookSkill else None
        self.linkedin_skill = LinkedInSkill(config) if LinkedInSkill else None
        self.tiktok_skill = TikTokSkill(config) if TikTokSkill else None
        self.youtube_skill = YouTubeSkill(config) if YouTubeSkill else None

        # Document, Clipboard, OCR, Calendar (Google) skills
        from ...skills.data.document_skill import DocumentSkill
        from ...skills.data.clipboard_skill import ClipboardSkill
        from ...skills.media.ocr_skill import OCRSkill
        from ...skills.automation.calendar_skill import CalendarSkill as GoogleCalendarSkill
        from ...skills.automation.email_skill import EmailSkill

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

        # Register Skills Marketplace tools (SAGP gateway)
        self.register("marketplace_search", self._marketplace_search_tool)
        self.register("marketplace_info", self._marketplace_info_tool)
        self.register("marketplace_install", self._marketplace_install_tool)
        self.register("marketplace_review", self._marketplace_review_tool)

        # Register Mobile phone tools (SETP/1.0 encrypted tunnel)
        self.register("phone_notify", self._phone_notify_tool)
        self.register("phone_reminder", self._phone_reminder_tool)
        self.register("phone_geofence", self._phone_geofence_tool)
        self.register("phone_location", self._phone_location_tool)
        self.register("phone_device", self._phone_device_tool)

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

        # Register Instagram tools
        self.register("ig_upload_photo", self._ig_upload_photo_tool)
        self.register("ig_upload_reel", self._ig_upload_reel_tool)
        self.register("ig_upload_story", self._ig_upload_story_tool)
        self.register("ig_search_users", self._ig_search_users_tool)
        self.register("ig_search_hashtags", self._ig_search_hashtags_tool)
        self.register("ig_get_user_info", self._ig_get_user_info_tool)
        self.register("ig_get_timeline", self._ig_get_timeline_tool)
        self.register("ig_like_media", self._ig_like_media_tool)
        self.register("ig_comment", self._ig_comment_tool)
        self.register("ig_follow_user", self._ig_follow_user_tool)
        self.register("ig_send_dm", self._ig_send_dm_tool)
        self.register("ig_get_media_comments", self._ig_get_media_comments_tool)

        # Register Facebook tools
        self.register("fb_post", self._fb_post_tool)
        self.register("fb_upload_photo", self._fb_upload_photo_tool)
        self.register("fb_get_feed", self._fb_get_feed_tool)
        self.register("fb_like_post", self._fb_like_post_tool)
        self.register("fb_comment", self._fb_comment_tool)
        self.register("fb_get_profile", self._fb_get_profile_tool)
        self.register("fb_search", self._fb_search_tool)

        # Register LinkedIn tools
        self.register("linkedin_get_profile", self._linkedin_get_profile_tool)
        self.register("linkedin_search_people", self._linkedin_search_people_tool)
        self.register("linkedin_search_companies", self._linkedin_search_companies_tool)
        self.register("linkedin_search_jobs", self._linkedin_search_jobs_tool)
        self.register("linkedin_post_update", self._linkedin_post_update_tool)
        self.register("linkedin_send_message", self._linkedin_send_message_tool)
        self.register("linkedin_send_connection", self._linkedin_send_connection_tool)
        self.register("linkedin_get_feed", self._linkedin_get_feed_tool)

        # Register TikTok tools (read-only)
        self.register("tiktok_trending", self._tiktok_trending_tool)
        self.register("tiktok_search_videos", self._tiktok_search_videos_tool)
        self.register("tiktok_search_users", self._tiktok_search_users_tool)
        self.register("tiktok_get_user_info", self._tiktok_get_user_info_tool)
        self.register("tiktok_get_user_videos", self._tiktok_get_user_videos_tool)
        self.register("tiktok_get_hashtag_videos", self._tiktok_get_hashtag_videos_tool)

        # Register YouTube tools
        self.register("yt_search_videos", self._yt_search_videos_tool)
        self.register("yt_search_channels", self._yt_search_channels_tool)
        self.register("yt_get_channel", self._yt_get_channel_tool)
        self.register("yt_get_channel_videos", self._yt_get_channel_videos_tool)
        self.register("yt_get_video", self._yt_get_video_tool)
        self.register("yt_get_comments", self._yt_get_comments_tool)
        self.register("yt_comment", self._yt_comment_tool)
        self.register("yt_get_playlist", self._yt_get_playlist_tool)
        self.register("yt_rate_video", self._yt_rate_video_tool)
        self.register("yt_subscribe", self._yt_subscribe_tool)
        self.register("yt_trending", self._yt_trending_tool)
        self.register("yt_upload_video", self._yt_upload_video_tool)

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
        self.register("open_url", self._open_url_tool)
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

        # Initialize social media skills
        if self.instagram_skill:
            try:
                await self.instagram_skill.initialize()
            except Exception as e:
                logger.warning(f"Instagram skill initialization failed: {e}")

        if self.facebook_skill:
            try:
                await self.facebook_skill.initialize()
            except Exception as e:
                logger.warning(f"Facebook skill initialization failed: {e}")

        if self.linkedin_skill:
            try:
                await self.linkedin_skill.initialize()
            except Exception as e:
                logger.warning(f"LinkedIn skill initialization failed: {e}")

        if self.tiktok_skill:
            try:
                await self.tiktok_skill.initialize()
            except Exception as e:
                logger.warning(f"TikTok skill initialization failed: {e}")

        if self.youtube_skill:
            try:
                await self.youtube_skill.initialize()
            except Exception as e:
                logger.warning(f"YouTube skill initialization failed: {e}")

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

    # Social-media tool name prefixes that require a testing-purposes disclaimer
    _SOCIAL_PREFIXES = ("x_", "grok_", "ig_", "fb_", "linkedin_", "tiktok_", "yt_")
    _SOCIAL_DISCLAIMER = " [⚠️ For testing/educational purposes only — respect each platform's ToS]"

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return Ollama-compatible tool schemas (OpenAI function calling format)"""
        schemas = [
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
            # ── Skills Marketplace tools (SAGP gateway) ─────
            {
                "type": "function",
                "function": {
                    "name": "marketplace_search",
                    "description": "Search the SableCore Skills Marketplace for skills to extend your capabilities. The marketplace contains community and official skills you can install. Use this when the user asks about available skills, wants new functionality, or you need a capability you don't have.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query (e.g. 'weather', 'calculator', 'crypto', 'automation')",
                            },
                            "category": {
                                "type": "string",
                                "description": "Optional category filter: productivity, communication, automation, data_analysis, entertainment, education, development, system, ai_ml, custom",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results (default 10)",
                                "default": 10,
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "marketplace_info",
                    "description": "Get detailed information about a specific skill from the SableCore Skills Marketplace, including description, author, rating, downloads, dependencies, and version.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "skill_id": {
                                "type": "string",
                                "description": "The skill ID/slug (e.g. 'weather_checker', 'smart_calculator')",
                            },
                        },
                        "required": ["skill_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "marketplace_install",
                    "description": "Install a skill from the SableCore Skills Marketplace. This downloads and installs the skill package securely via the SAGP agent gateway. IMPORTANT: This requires user approval before execution.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "skill_id": {
                                "type": "string",
                                "description": "The skill ID/slug to install (e.g. 'weather_checker')",
                            },
                        },
                        "required": ["skill_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "marketplace_review",
                    "description": "Post a review on a skill you have used from the marketplace. Use this after installing and testing a skill to help other users and agents.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "skill_id": {
                                "type": "string",
                                "description": "The skill ID/slug to review",
                            },
                            "rating": {
                                "type": "integer",
                                "description": "Rating from 1 to 5 stars",
                                "minimum": 1,
                                "maximum": 5,
                            },
                            "title": {
                                "type": "string",
                                "description": "Short review title",
                            },
                            "content": {
                                "type": "string",
                                "description": "Detailed review content",
                            },
                        },
                        "required": ["skill_id", "rating", "title", "content"],
                    },
                },
            },
            # ── Mobile phone tools ──────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "phone_notify",
                    "description": "Send a push notification to the user's phone. Use this to alert the user about important events, trade signals, task completions, or any information they should see immediately.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Notification title (short)",
                            },
                            "body": {
                                "type": "string",
                                "description": "Notification body/message",
                            },
                            "channel": {
                                "type": "string",
                                "description": "Notification channel: 'agent-chat', 'trade-alerts', 'reminders', 'system'",
                                "default": "agent-chat",
                            },
                            "urgency": {
                                "type": "string",
                                "description": "Urgency level: 'low', 'normal', 'high', 'critical'",
                                "default": "normal",
                            },
                        },
                        "required": ["title", "body"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "phone_reminder",
                    "description": "Create a smart reminder on the user's phone. Can be time-based (triggers at a specific time) or geo-fenced (triggers when the user enters a location area). Use 'geo' type for location-based reminders like 'remind me to buy medicine when I'm near a pharmacy'.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Reminder title",
                            },
                            "body": {
                                "type": "string",
                                "description": "Reminder details/description",
                            },
                            "type": {
                                "type": "string",
                                "description": "Reminder type: 'time' (triggers at a time), 'geo' (triggers at a location), 'manual' (user dismisses)",
                                "default": "manual",
                            },
                            "trigger_at": {
                                "type": "string",
                                "description": "For time-based: ISO 8601 timestamp when to trigger (e.g. '2025-01-15T09:00:00')",
                            },
                            "latitude": {
                                "type": "number",
                                "description": "For geo-based: latitude of the target location",
                            },
                            "longitude": {
                                "type": "number",
                                "description": "For geo-based: longitude of the target location",
                            },
                            "radius": {
                                "type": "integer",
                                "description": "For geo-based: radius in meters (default 200)",
                                "default": 200,
                            },
                            "location_name": {
                                "type": "string",
                                "description": "Human-readable name of the location (e.g. 'Walgreens on 5th Ave')",
                            },
                        },
                        "required": ["title"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "phone_geofence",
                    "description": "Set a geofence that triggers when the user enters a specific area. Use this for location-based alerts, check-ins, or context-aware actions. The phone will monitor the area in the background.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Geofence name (e.g. 'Office', 'Pharmacy', 'Gym')",
                            },
                            "latitude": {
                                "type": "number",
                                "description": "Latitude of the geofence center",
                            },
                            "longitude": {
                                "type": "number",
                                "description": "Longitude of the geofence center",
                            },
                            "radius": {
                                "type": "integer",
                                "description": "Radius in meters (default 200)",
                                "default": 200,
                            },
                            "action_title": {
                                "type": "string",
                                "description": "Notification title when geofence is entered",
                            },
                            "action_body": {
                                "type": "string",
                                "description": "Notification body when geofence is entered",
                            },
                            "max_triggers": {
                                "type": "integer",
                                "description": "Max times to trigger (default 1, set higher for recurring geofences)",
                                "default": 1,
                            },
                        },
                        "required": ["name", "latitude", "longitude"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "phone_location",
                    "description": "Get the user's current phone location (GPS coordinates and address). Use this to provide location-aware responses or set up geo-fences near the user.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "phone_device",
                    "description": "Get the user's phone device status including battery level, charging state, and network connectivity. Use this to adapt behavior (e.g. reduce notifications when battery is low).",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    },
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
                        "Pass ONLY the application name — never a search query or sentence. "
                        "To open a URL in the browser, use open_url instead. "
                        "Examples: 'terminal', 'vscode', 'spotify', 'vlc', 'gimp', "
                        "'libreoffice', 'calculator', 'files', 'discord', 'slack'. "
                        "NEVER use 'firefox' — always use open_url for web browsing."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "App executable name ONLY. NEVER 'firefox'. Use open_url for websites.",
                            },
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "open_url",
                    "description": (
                        "Open a URL or website in Chromium browser. "
                        "ALWAYS use this instead of open_app when the user wants to visit a website or URL. "
                        "Automatically prepends https:// if no scheme is given. "
                        "Examples: 'https://opensable.com', 'google.com', 'https://youtube.com/watch?v=abc'."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "The URL or domain to open (e.g. 'opensable.com' or 'https://google.com').",
                            },
                        },
                        "required": ["url"],
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
            # ── Instagram tools ───────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "ig_upload_photo",
                    "description": "Upload a photo to Instagram with caption",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "photo_path": {"type": "string", "description": "Path to the photo file"},
                            "caption": {"type": "string", "description": "Photo caption text"},
                        },
                        "required": ["photo_path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "ig_upload_reel",
                    "description": "Upload a reel (short video) to Instagram with caption",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "video_path": {"type": "string", "description": "Path to the video file"},
                            "caption": {"type": "string", "description": "Reel caption text"},
                        },
                        "required": ["video_path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "ig_upload_story",
                    "description": "Upload a story (photo or video) to Instagram",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string", "description": "Path to photo or video file"},
                            "caption": {"type": "string", "description": "Story caption/sticker text (optional)"},
                        },
                        "required": ["file_path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "ig_search_users",
                    "description": "Search for Instagram users by query string",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "count": {"type": "integer", "description": "Max results (default: 10)"},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "ig_search_hashtags",
                    "description": "Search Instagram hashtags",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Hashtag search query"},
                            "count": {"type": "integer", "description": "Max results (default: 10)"},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "ig_get_user_info",
                    "description": "Get detailed info about an Instagram user by username",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "username": {"type": "string", "description": "Instagram username"},
                        },
                        "required": ["username"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "ig_get_timeline",
                    "description": "Get the authenticated user's Instagram timeline/feed",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "count": {"type": "integer", "description": "Number of posts to fetch (default: 20)"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "ig_like_media",
                    "description": "Like an Instagram post by its media ID or URL",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "media_id": {"type": "string", "description": "Media ID or Instagram post URL"},
                        },
                        "required": ["media_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "ig_comment",
                    "description": "Comment on an Instagram post",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "media_id": {"type": "string", "description": "Media ID or Instagram post URL"},
                            "text": {"type": "string", "description": "Comment text"},
                        },
                        "required": ["media_id", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "ig_follow_user",
                    "description": "Follow an Instagram user by username",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "username": {"type": "string", "description": "Instagram username to follow"},
                        },
                        "required": ["username"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "ig_send_dm",
                    "description": "Send a direct message to an Instagram user",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "username": {"type": "string", "description": "Instagram username to DM"},
                            "text": {"type": "string", "description": "Message text"},
                        },
                        "required": ["username", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "ig_get_media_comments",
                    "description": "Get comments on an Instagram post",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "media_id": {"type": "string", "description": "Media ID or Instagram post URL"},
                            "count": {"type": "integer", "description": "Max comments to fetch (default: 20)"},
                        },
                        "required": ["media_id"],
                    },
                },
            },
            # ── Facebook tools ────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "fb_post",
                    "description": "Publish a text post to Facebook (your timeline or page)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string", "description": "Post text content"},
                            "link": {"type": "string", "description": "URL to attach (optional)"},
                        },
                        "required": ["message"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fb_upload_photo",
                    "description": "Upload a photo to Facebook with caption",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "photo_path": {"type": "string", "description": "Path to the photo file"},
                            "caption": {"type": "string", "description": "Photo caption text (optional)"},
                        },
                        "required": ["photo_path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fb_get_feed",
                    "description": "Get recent posts from your Facebook feed or a page's feed",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "count": {"type": "integer", "description": "Number of posts (default: 10)"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fb_like_post",
                    "description": "Like a Facebook post by its ID",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "post_id": {"type": "string", "description": "Facebook post ID"},
                        },
                        "required": ["post_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fb_comment",
                    "description": "Comment on a Facebook post",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "post_id": {"type": "string", "description": "Facebook post ID"},
                            "message": {"type": "string", "description": "Comment text"},
                        },
                        "required": ["post_id", "message"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fb_get_profile",
                    "description": "Get Facebook profile information for a user or page",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string", "description": "User/page ID or 'me' (default: me)"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fb_search",
                    "description": "Search Facebook for pages, people, groups, etc.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "search_type": {"type": "string", "description": "Type: page, user, group, event (default: page)"},
                            "count": {"type": "integer", "description": "Max results (default: 10)"},
                        },
                        "required": ["query"],
                    },
                },
            },
            # ── LinkedIn tools ────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "linkedin_get_profile",
                    "description": "Get a LinkedIn user's profile by their public ID or URL",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "username": {"type": "string", "description": "LinkedIn public profile ID or vanity URL"},
                        },
                        "required": ["username"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linkedin_search_people",
                    "description": "Search for people on LinkedIn by keywords, location, company, etc.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keywords": {"type": "string", "description": "Search keywords"},
                            "limit": {"type": "integer", "description": "Max results (default: 10)"},
                        },
                        "required": ["keywords"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linkedin_search_companies",
                    "description": "Search for companies on LinkedIn",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keywords": {"type": "string", "description": "Search keywords"},
                            "limit": {"type": "integer", "description": "Max results (default: 10)"},
                        },
                        "required": ["keywords"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linkedin_search_jobs",
                    "description": "Search for jobs on LinkedIn",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keywords": {"type": "string", "description": "Job search keywords"},
                            "location": {"type": "string", "description": "Job location (optional)"},
                            "limit": {"type": "integer", "description": "Max results (default: 10)"},
                        },
                        "required": ["keywords"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linkedin_post_update",
                    "description": "Publish a post/update on LinkedIn",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "Post text content"},
                        },
                        "required": ["text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linkedin_send_message",
                    "description": "Send a message to a LinkedIn connection",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "profile_id": {"type": "string", "description": "LinkedIn profile public ID of recipient"},
                            "message": {"type": "string", "description": "Message text"},
                        },
                        "required": ["profile_id", "message"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linkedin_send_connection",
                    "description": "Send a connection request on LinkedIn",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "profile_id": {"type": "string", "description": "LinkedIn public profile ID"},
                            "message": {"type": "string", "description": "Connection request message (optional)"},
                        },
                        "required": ["profile_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linkedin_get_feed",
                    "description": "Get recent posts from your LinkedIn feed",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "count": {"type": "integer", "description": "Number of posts (default: 10)"},
                        },
                    },
                },
            },
            # ── TikTok tools (read-only) ──────────────────
            {
                "type": "function",
                "function": {
                    "name": "tiktok_trending",
                    "description": "Get trending TikTok videos. Note: TikTok API is read-only, cannot post content.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "count": {"type": "integer", "description": "Number of videos (default: 10)"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "tiktok_search_videos",
                    "description": "Search TikTok videos by keyword",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "count": {"type": "integer", "description": "Max results (default: 10)"},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "tiktok_search_users",
                    "description": "Search TikTok users by keyword",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "count": {"type": "integer", "description": "Max results (default: 10)"},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "tiktok_get_user_info",
                    "description": "Get information about a TikTok user",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "username": {"type": "string", "description": "TikTok username"},
                        },
                        "required": ["username"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "tiktok_get_user_videos",
                    "description": "Get videos posted by a TikTok user",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "username": {"type": "string", "description": "TikTok username"},
                            "count": {"type": "integer", "description": "Max videos (default: 10)"},
                        },
                        "required": ["username"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "tiktok_get_hashtag_videos",
                    "description": "Get videos under a TikTok hashtag",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "hashtag": {"type": "string", "description": "Hashtag name (without #)"},
                            "count": {"type": "integer", "description": "Max videos (default: 10)"},
                        },
                        "required": ["hashtag"],
                    },
                },
            },
            # ── YouTube tools ─────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "yt_search_videos",
                    "description": "Search YouTube videos by keyword",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "count": {"type": "integer", "description": "Max results (default: 10)"},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "yt_search_channels",
                    "description": "Search YouTube channels by keyword",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "count": {"type": "integer", "description": "Max results (default: 10)"},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "yt_get_channel",
                    "description": "Get detailed info about a YouTube channel (subscribers, videos, description)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_id": {"type": "string", "description": "YouTube channel ID"},
                        },
                        "required": ["channel_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "yt_get_channel_videos",
                    "description": "Get recent videos from a YouTube channel",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_id": {"type": "string", "description": "YouTube channel ID"},
                            "count": {"type": "integer", "description": "Max videos (default: 10)"},
                        },
                        "required": ["channel_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "yt_get_video",
                    "description": "Get detailed info about a YouTube video (views, likes, duration, description)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "video_id": {"type": "string", "description": "YouTube video ID"},
                        },
                        "required": ["video_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "yt_get_comments",
                    "description": "Get top comments on a YouTube video",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "video_id": {"type": "string", "description": "YouTube video ID"},
                            "count": {"type": "integer", "description": "Max comments (default: 20)"},
                        },
                        "required": ["video_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "yt_comment",
                    "description": "Post a comment on a YouTube video (requires OAuth access token)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "video_id": {"type": "string", "description": "YouTube video ID"},
                            "text": {"type": "string", "description": "Comment text"},
                        },
                        "required": ["video_id", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "yt_get_playlist",
                    "description": "Get videos in a YouTube playlist",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "playlist_id": {"type": "string", "description": "YouTube playlist ID"},
                            "count": {"type": "integer", "description": "Max items (default: 20)"},
                        },
                        "required": ["playlist_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "yt_rate_video",
                    "description": "Like or dislike a YouTube video (requires OAuth access token)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "video_id": {"type": "string", "description": "YouTube video ID"},
                            "rating": {"type": "string", "description": "'like', 'dislike', or 'none'"},
                        },
                        "required": ["video_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "yt_subscribe",
                    "description": "Subscribe to a YouTube channel (requires OAuth access token)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_id": {"type": "string", "description": "YouTube channel ID"},
                        },
                        "required": ["channel_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "yt_trending",
                    "description": "Get trending YouTube videos by region",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "region_code": {"type": "string", "description": "ISO country code (default: US)"},
                            "count": {"type": "integer", "description": "Max videos (default: 10)"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "yt_upload_video",
                    "description": "Upload a video to YouTube (requires OAuth access token). Defaults to private.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string", "description": "Path to video file"},
                            "title": {"type": "string", "description": "Video title"},
                            "description": {"type": "string", "description": "Video description"},
                            "tags": {"type": "array", "items": {"type": "string"}, "description": "Video tags"},
                            "privacy": {"type": "string", "description": "'private', 'public', or 'unlisted'"},
                        },
                        "required": ["file_path", "title"],
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

        # Append testing-purposes disclaimer to all social-media tool descriptions
        for schema in schemas:
            name = schema.get("function", {}).get("name", "")
            if any(name.startswith(p) for p in self._SOCIAL_PREFIXES):
                schema["function"]["description"] += self._SOCIAL_DISCLAIMER

        return schemas

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
        # Skills Marketplace
        "marketplace_search": ("marketplace_search", lambda a: a),
        "marketplace_info": ("marketplace_info", lambda a: a),
        "marketplace_install": ("marketplace_install", lambda a: a),
        "marketplace_review": ("marketplace_review", lambda a: a),
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
        "open_url": ("open_url", lambda a: a),
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
        # Benchmark users get unrestricted access to all tools
        is_benchmark = user_id.startswith("benchmark_")
        if self._permission_manager and schema_name in self._TOOL_PERMISSIONS and not is_benchmark:
            from ..security import ActionType

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


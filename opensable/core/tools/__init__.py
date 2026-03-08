"""
Tool registry for Open-Sable — manages all available actions.

This is the central orchestrator that:
  - Initializes all skills (voice, image, database, social, trading, etc.)
  - Registers tool handlers from domain-specific mixin classes
  - Provides tool schemas (from per-domain _schemas/ modules)
  - Dispatches schema calls through the _dispatch.py mapping
  - Enforces RBAC via _permissions.py

Architecture:
  Tool implementations  → _core_tools.py, _desktop_vision.py, _social.py, etc. (mixins)
  Tool schemas          → _schemas/ package (one module per domain)
  RBAC permissions      → _permissions.py
  Schema→tool dispatch  → _dispatch.py
"""

import logging
import json
from typing import Dict, Any, Callable, List
from pathlib import Path
from datetime import datetime

from ..computer_tools import ComputerTools
from ..vision_tools import VisionTools
from ..browser import BrowserEngine
from ..skill_creator import SkillCreator
from ..paths import opensable_home

try:
    from ...skills.trading.trading_skill import TradingSkill
except ImportError:
    TradingSkill = None  # type: ignore

try:
    from ...skills import VoiceSkill, ImageSkill, DatabaseSkill, RAGSkill, CodeExecutor, APIClient, XSkill, GrokSkill
    from ...skills import InstagramSkill, FacebookSkill, LinkedInSkill, TikTokSkill, YouTubeSkill
except ImportError:
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

# ── Domain modules ────────────────────────────────────────────────────────────
from ._core_tools import CoreToolsMixin
from ._desktop_vision import DesktopVisionToolsMixin
from ._social import SocialToolsMixin
from ._productivity import ProductivityToolsMixin
from ._trading import TradingToolsMixin
from ._marketplace import MarketplaceToolsMixin
from ._mobile import MobileToolsMixin
from ._github import GitHubToolsMixin
from ._arena import ArenaToolsMixin

from ._permissions import TOOL_PERMISSIONS
from ._dispatch import SCHEMA_TO_TOOL
from ._schemas import get_all_schemas


class ToolRegistry(
    CoreToolsMixin,
    DesktopVisionToolsMixin,
    SocialToolsMixin,
    ProductivityToolsMixin,
    TradingToolsMixin,
    MarketplaceToolsMixin,
    MobileToolsMixin,
    GitHubToolsMixin,
    ArenaToolsMixin,
):
    """Registry of all available tools/actions.

    Tool implementations are organized into mixin classes:
    - CoreToolsMixin: file system, commands, browser, media, code, skills
    - DesktopVisionToolsMixin: desktop control, vision, autonomous computer-use
    - SocialToolsMixin: X/Twitter, Grok, Instagram, Facebook, LinkedIn, TikTok, YouTube
    - ProductivityToolsMixin: documents, email, calendar, clipboard, OCR
    - TradingToolsMixin: trading portfolio, prices, orders, analysis
    - MarketplaceToolsMixin: skills marketplace (SAGP)
    - MobileToolsMixin: phone notification, reminders, geofence, location, device status
    - GitHubToolsMixin: issues, PRs, repos, branches, code search, releases
    - ArenaToolsMixin: fighting-game arena (SAGP auth + WebSocket combat)
    """

    # RBAC permissions (imported from _permissions.py)
    _TOOL_PERMISSIONS = TOOL_PERMISSIONS

    # Schema → internal tool dispatch (imported from _dispatch.py)
    _SCHEMA_TO_TOOL = SCHEMA_TO_TOOL

    # ── Constructor ───────────────────────────────────────────────────────────

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
        self.calendar_file = opensable_home() / "calendar.json"
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

        # Social media skills
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
        from ...skills.automation.news_reader_skill import NewsReaderSkill
        try:
            from ...skills.media.genelia_skill import GeneliaSkill
        except ImportError:
            GeneliaSkill = None

        self.document_skill = DocumentSkill(config)
        self.clipboard_skill = ClipboardSkill(config)
        self.ocr_skill = OCRSkill(config)
        self.google_calendar_skill = GoogleCalendarSkill(config)
        self.email_skill = EmailSkill(config)
        self.news_reader_skill = NewsReaderSkill(config)
        self.genelia_skill = GeneliaSkill(config) if GeneliaSkill else None

        # Trading skill (conditional)
        self.trading_skill = None
        if TradingSkill and getattr(config, "trading_enabled", False):
            try:
                self.trading_skill = TradingSkill(config)
            except Exception as e:
                logger.warning(f"Trading skill creation failed: {e}")

        # GitHub skill (conditional)
        self.github_skill = None
        try:
            from ...skills.automation.github_skill import GitHubSkill
            self.github_skill = GitHubSkill(config)
        except Exception as e:
            logger.debug(f"GitHub skill not available: {e}")

        # Arena Fighter skill (conditional)
        self.arena_skill = None
        try:
            from ...skills.gaming.arena_fighter import ArenaFighterSkill
            self.arena_skill = ArenaFighterSkill(config)
        except Exception as e:
            logger.debug(f"Arena skill not available: {e}")

    # ── Initialization ────────────────────────────────────────────────────────

    async def initialize(self):
        """Initialize all tools: register handlers, initialize skills."""

        # ── File / System ─────────────────────────────────────────────────────
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

        # ── Built-in ─────────────────────────────────────────────────────────
        self.register("email", self._email_tool)
        self.register("calendar", self._calendar_tool)
        self.register("browser", self._browser_tool)
        self.register("web_action", self._web_action_tool)
        self.register("weather", self._weather_tool)

        # ── Advanced skills ───────────────────────────────────────────────────
        self.register("voice_speak", self._voice_speak_tool)
        self.register("voice_listen", self._voice_listen_tool)
        self.register("generate_image", self._generate_image_tool)
        self.register("analyze_image", self._analyze_image_tool)
        self.register("ocr", self._ocr_tool)
        self.register("database_query", self._database_query_tool)
        self.register("vector_search", self._vector_search_tool)
        self.register("execute_code", self._execute_code_tool)
        self.register("api_request", self._api_request_tool)

        # ── Documents ─────────────────────────────────────────────────────────
        self.register("create_document", self._create_document_tool)
        self.register("create_spreadsheet", self._create_spreadsheet_tool)
        self.register("create_pdf", self._create_pdf_tool)
        self.register("create_presentation", self._create_presentation_tool)
        self.register("read_document", self._read_document_tool)
        self.register("open_document", self._open_document_tool)
        self.register("write_in_writer", self._write_in_writer_tool)

        # ── Email (schema-mapped) ────────────────────────────────────────────
        self.register("email_send", self._email_send_tool)
        self.register("email_read", self._email_read_tool)

        # ── Google Calendar ───────────────────────────────────────────────────
        self.register("calendar_list_events", self._calendar_list_events_tool)
        self.register("calendar_add_event", self._calendar_add_event_tool)
        self.register("calendar_delete_event", self._calendar_delete_event_tool)

        # ── News Reader ───────────────────────────────────────────────────
        self.register("news_get_world_news", self._news_get_world_news_tool)
        self.register("news_search", self._news_search_tool)
        self.register("news_country_brief", self._news_country_brief_tool)
        self.register("news_get_conflicts", self._news_get_conflicts_tool)
        self.register("news_get_macro_signals", self._news_get_macro_signals_tool)
        self.register("news_get_market_quotes", self._news_get_market_quotes_tool)
        self.register("news_get_crypto_quotes", self._news_get_crypto_quotes_tool)
        self.register("news_digest", self._news_digest_tool)

        # ── Genelia v2 (Image Generation) ───────────────────────────────────
        if self.genelia_skill:
            self.register("genelia_generate", self._genelia_generate_tool)
            self.register("genelia_status", self._genelia_status_tool)
            self.register("genelia_list_images", self._genelia_list_images_tool)

        # ── Clipboard ─────────────────────────────────────────────────────────
        self.register("clipboard_copy", self._clipboard_copy_tool)
        self.register("clipboard_paste", self._clipboard_paste_tool)

        # ── OCR ───────────────────────────────────────────────────────────────
        self.register("ocr_extract", self._ocr_extract_tool)

        # ── Skill creation ────────────────────────────────────────────────────
        self.register("create_skill", self._create_skill_tool)
        self.register("list_skills", self._list_skills_tool)

        # ── Meta-tool: lazy schema loading ────────────────────────────────────
        self.register("load_tool_details", self._load_tool_details)

        # ── Skills Marketplace (SAGP gateway) ─────────────────────────────────
        self.register("marketplace_search", self._marketplace_search_tool)
        self.register("marketplace_info", self._marketplace_info_tool)
        self.register("marketplace_install", self._marketplace_install_tool)
        self.register("marketplace_review", self._marketplace_review_tool)

        # ── Mobile phone (SETP/1.0 encrypted tunnel) ─────────────────────────
        self.register("phone_notify", self._phone_notify_tool)
        self.register("phone_reminder", self._phone_reminder_tool)
        self.register("phone_geofence", self._phone_geofence_tool)
        self.register("phone_location", self._phone_location_tool)
        self.register("phone_device", self._phone_device_tool)
        # ── GitHub ───────────────────────────────────────────────────────────────
        self.register("github_create_issue", self._github_create_issue_tool)
        self.register("github_list_issues", self._github_list_issues_tool)
        self.register("github_comment_issue", self._github_comment_issue_tool)
        self.register("github_close_issue", self._github_close_issue_tool)
        self.register("github_create_pr", self._github_create_pr_tool)
        self.register("github_list_prs", self._github_list_prs_tool)
        self.register("github_merge_pr", self._github_merge_pr_tool)
        self.register("github_repo_info", self._github_repo_info_tool)
        self.register("github_list_repos", self._github_list_repos_tool)
        self.register("github_create_branch", self._github_create_branch_tool)
        self.register("github_search_code", self._github_search_code_tool)
        self.register("github_get_file", self._github_get_file_tool)
        self.register("github_create_release", self._github_create_release_tool)

        # Initialize GitHub skill
        if self.github_skill:
            try:
                await self.github_skill.initialize()
            except Exception as e:
                logger.debug(f"GitHub skill init failed: {e}")

        # ── Arena Fighter ─────────────────────────────────────────────────────
        self.register("arena_fight", self._arena_fight_tool)
        self.register("arena_status", self._arena_status_tool)
        self.register("arena_history", self._arena_history_tool)
        self.register("arena_disconnect", self._arena_disconnect_tool)

        # Initialize arena skill
        if self.arena_skill:
            try:
                await self.arena_skill.initialize()
            except Exception as e:
                logger.debug(f"Arena skill init failed: {e}")

        # ── X (Twitter) ──────────────────────────────────────────────────────
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

        # ── Grok AI ──────────────────────────────────────────────────────────
        self.register("grok_chat", self._grok_chat_tool)
        self.register("grok_analyze_image", self._grok_analyze_image_tool)
        self.register("grok_generate_image", self._grok_generate_image_tool)

        # ── Instagram ─────────────────────────────────────────────────────────
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

        # ── Facebook ──────────────────────────────────────────────────────────
        self.register("fb_post", self._fb_post_tool)
        self.register("fb_upload_photo", self._fb_upload_photo_tool)
        self.register("fb_get_feed", self._fb_get_feed_tool)
        self.register("fb_like_post", self._fb_like_post_tool)
        self.register("fb_comment", self._fb_comment_tool)
        self.register("fb_get_profile", self._fb_get_profile_tool)
        self.register("fb_search", self._fb_search_tool)

        # ── LinkedIn ──────────────────────────────────────────────────────────
        self.register("linkedin_get_profile", self._linkedin_get_profile_tool)
        self.register("linkedin_search_people", self._linkedin_search_people_tool)
        self.register("linkedin_search_companies", self._linkedin_search_companies_tool)
        self.register("linkedin_search_jobs", self._linkedin_search_jobs_tool)
        self.register("linkedin_post_update", self._linkedin_post_update_tool)
        self.register("linkedin_send_message", self._linkedin_send_message_tool)
        self.register("linkedin_send_connection", self._linkedin_send_connection_tool)
        self.register("linkedin_get_feed", self._linkedin_get_feed_tool)

        # ── TikTok (read-only) ────────────────────────────────────────────────
        self.register("tiktok_trending", self._tiktok_trending_tool)
        self.register("tiktok_search_videos", self._tiktok_search_videos_tool)
        self.register("tiktok_search_users", self._tiktok_search_users_tool)
        self.register("tiktok_get_user_info", self._tiktok_get_user_info_tool)
        self.register("tiktok_get_user_videos", self._tiktok_get_user_videos_tool)
        self.register("tiktok_get_hashtag_videos", self._tiktok_get_hashtag_videos_tool)

        # ── YouTube ───────────────────────────────────────────────────────────
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

        # ── Desktop control ───────────────────────────────────────────────────
        self.register("desktop_screenshot", self._desktop_screenshot_tool)
        self.register("desktop_click", self._desktop_click_tool)
        self.register("desktop_type", self._desktop_type_tool)
        self.register("desktop_hotkey", self._desktop_hotkey_tool)
        self.register("desktop_scroll", self._desktop_scroll_tool)
        self.register("desktop_mouse_move", self._desktop_mouse_move_tool)

        # ── Vision / autonomous computer-use ──────────────────────────────────
        self.register("screen_analyze", self._screen_analyze_tool)
        self.register("screen_find", self._screen_find_tool)
        self.register("screen_click_on", self._screen_click_on_tool)
        self.register("open_app", self._open_app_tool)
        self.register("open_url", self._open_url_tool)
        self.register("window_list", self._window_list_tool)
        self.register("window_focus", self._window_focus_tool)

        # ── Skill initialization ──────────────────────────────────────────────
        _skills_to_init = [
            ("Voice", self.voice),
            ("Image", self.image),
            ("Database", self.database),
            ("RAG", self.rag),
        ]
        for name, skill in _skills_to_init:
            try:
                await skill.initialize()
            except Exception as e:
                logger.warning(f"{name} skill initialization failed: {e}")

        # Social skills (optional)
        _optional_skills = [
            ("X", self.x_skill),
            ("Grok", self.grok_skill),
            ("Instagram", self.instagram_skill),
            ("Facebook", self.facebook_skill),
            ("LinkedIn", self.linkedin_skill),
            ("TikTok", self.tiktok_skill),
            ("YouTube", self.youtube_skill),
        ]
        for name, skill in _optional_skills:
            if skill:
                try:
                    await skill.initialize()
                except Exception as e:
                    logger.warning(f"{name} skill initialization failed: {e}")

        # Productivity skills
        _productivity_skills = [
            ("Document", self.document_skill),
            ("Clipboard", self.clipboard_skill),
            ("OCR", self.ocr_skill),
            ("Google Calendar", self.google_calendar_skill),
            ("Email", self.email_skill),
            ("News Reader", self.news_reader_skill),
        ]
        if self.genelia_skill:
            _productivity_skills.append(("Genelia v2", self.genelia_skill))
        for name, skill in _productivity_skills:
            try:
                await skill.initialize()
            except Exception as e:
                logger.warning(f"{name} skill initialization failed: {e}")

        # Trading (conditional)
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

        # ── Profile tool filtering ─────────────────────────────────────────
        try:
            from .profile import get_active_profile
            profile = get_active_profile()
            if profile and profile.tools.mode != "all":
                before = len(self.tools)
                self.tools = {
                    name: func
                    for name, func in self.tools.items()
                    if profile.tools.is_allowed(name)
                }
                after = len(self.tools)
                if before != after:
                    logger.info(
                        f"[Profile:{profile.name}] tool filter ({profile.tools.mode}): "
                        f"{before} → {after} tools"
                    )
        except ImportError:
            pass  # profile module not available
        except Exception as exc:
            logger.debug(f"Profile tool filter error: {exc}")

        logger.info(f"Initialized {len(self.tools)} tools")

    # ── Tool registry API ─────────────────────────────────────────────────────

    def register(self, name: str, func: Callable):
        """Register a new tool."""
        self.tools[name] = func
        logger.debug(f"Registered tool: {name}")

    def list_tools(self) -> List[str]:
        """List all available tools."""
        return list(self.tools.keys())

    # ── Schema generation ─────────────────────────────────────────────────────

    # Social-media tool name prefixes that require a testing-purposes disclaimer
    _SOCIAL_PREFIXES = ("x_", "grok_", "ig_", "fb_", "linkedin_", "tiktok_", "yt_")
    _SOCIAL_DISCLAIMER = " [⚠️ For testing/educational purposes only — respect each platform's ToS]"

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return Ollama-compatible tool schemas (OpenAI function calling format).

        Schemas are loaded from per-domain modules in _schemas/ for maintainability.
        """
        schemas = get_all_schemas() + self._custom_schemas

        # Append social media disclaimer to relevant schemas
        for schema in schemas:
            fn = schema.get("function", {})
            name = fn.get("name", "")
            if any(name.startswith(p) for p in self._SOCIAL_PREFIXES):
                fn["description"] = fn.get("description", "") + self._SOCIAL_DISCLAIMER

        return schemas

    # ── Execution ─────────────────────────────────────────────────────────────

    async def execute_schema_tool(
        self, schema_name: str, arguments: Dict[str, Any], user_id: str = "default"
    ) -> str:
        """Execute a tool by its schema name (as returned by Ollama tool calling)."""
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
        """Execute a tool by internal name."""
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        logger.info(f"Executing tool: {tool_name}")
        try:
            result = await self.tools[tool_name](tool_input)
            return result
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}")
            raise

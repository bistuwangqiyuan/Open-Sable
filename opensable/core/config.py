"""
Core configuration management for Open-Sable
"""

import os
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, Field
from dotenv import load_dotenv


class OpenSableConfig(BaseModel):
    """Main configuration for Open-Sable"""

    # Interface Mode
    cli_enabled: bool = False

    # Disable external APIs and web servers
    enable_gateway: bool = False  # Disable FastAPI/uvicorn web server
    enable_api: bool = False  # Disable REST API endpoints
    enable_websocket: bool = False  # Disable WebSocket server

    # LLM Settings
    ollama_base_url: str = "http://localhost:11434"
    default_model: str = "llama3.1:8b"
    auto_select_model: bool = True
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    together_api_key: Optional[str] = None
    xai_api_key: Optional[str] = None
    mistral_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    cohere_api_key: Optional[str] = None
    kimi_api_key: Optional[str] = None
    qwen_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    openwebui_api_key: Optional[str] = None
    openwebui_api_url: Optional[str] = None
    openwebui_model: Optional[str] = None

    # Chat Platforms
    telegram_bot_token: Optional[str] = None
    telegram_allowed_users: List[str] = Field(default_factory=list)

    # Telegram Userbot
    telegram_userbot_enabled: bool = False
    telegram_api_id: Optional[int] = None
    telegram_api_hash: Optional[str] = None
    telegram_phone_number: Optional[str] = None
    telegram_session_name: str = "opensable_session"
    userbot_auto_respond: bool = True

    discord_bot_token: Optional[str] = None
    discord_guild_id: Optional[str] = None
    whatsapp_enabled: bool = False

    # X (Twitter) / Grok
    x_username: Optional[str] = None
    x_email: Optional[str] = None
    x_password: Optional[str] = None
    x_enabled: bool = False
    x_language: str = "en-US"
    x_action_delay: int = 2  # seconds between actions (rate limit safety)
    grok_enabled: bool = False

    # X Autoposter
    x_autoposter_enabled: bool = False
    x_post_interval: int = 1800  # seconds between posts (default 30 min)
    x_topics: str = "geopolitics,tech,ai"
    x_style: str = "analyst"  # analyst, news, meme, thread
    x_max_daily_posts: int = 20
    x_max_daily_engagements: int = 100
    x_dry_run: bool = False
    x_custom_feeds: str = ""  # comma-separated RSS URLs
    x_engage_interval: int = 300  # seconds between engagement sessions
    x_accounts_to_watch: str = ""  # comma-separated usernames
    x_reply_probability: float = 0.3
    x_like_probability: float = 0.6
    x_retweet_probability: float = 0.2
    x_follow_probability: float = 0.1
    x_quote_probability: float = 0.1
    x_bookmark_probability: float = 0.15

    slack_bot_token: Optional[str] = None
    slack_app_token: Optional[str] = None
    slack_signing_secret: Optional[str] = None
    slack_allowed_users: Optional[list] = None

    # Email & Calendar
    gmail_enabled: bool = True
    gmail_credentials_path: Path = Path("./config/gmail_credentials.json")
    calendar_enabled: bool = True
    calendar_credentials_path: Path = Path("./config/calendar_credentials.json")
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None
    imap_host: Optional[str] = None
    imap_port: int = 993
    imap_user: Optional[str] = None
    imap_password: Optional[str] = None

    # Security
    enable_sandbox: bool = True
    allowed_domains: List[str] = Field(
        default_factory=lambda: ["*.google.com", "*.booking.com", "*.airbnb.com"]
    )
    max_file_size_mb: int = 100

    # Agent Behavior
    agent_name: str = "Sable"
    agent_personality: str = "helpful"  # professional, sarcastic, meme-aware, helpful
    heartbeat_interval: int = 300  # seconds
    max_retries: int = 3

    # Memory
    memory_retention_days: int = 90
    vector_db_path: Path = Path("./data/vectordb")

    # Logging
    log_level: str = "INFO"
    log_file: Path = Path("./logs/opensable.log")

    # Voice
    tts_provider: str = "local"
    stt_provider: str = "local"
    tts_voice_gender: str = "female"
    tts_rate: int = 150
    tts_volume: float = 0.9
    elevenlabs_api_key: Optional[str] = None
    elevenlabs_voice_id: Optional[str] = None
    elevenlabs_model: str = "eleven_multilingual_v2"
    whisper_model_size: str = "base"

    @property
    def tts_engine(self) -> str:
        """Alias so core/voice.py can read config.tts_engine."""
        return self.tts_provider

    # Image
    image_provider: str = "none"
    openai_image_api_key: Optional[str] = None

    # Mobile relay
    # Sable generates a QR code on first run; the mobile app scans it once.
    # The relay listens on 127.0.0.1 ONLY (never 0.0.0.0) — safe on a VPS.
    # For remote access: either use Tailscale, or expose via Tor hidden service.
    mobile_relay_enabled: bool = False  # disabled until mobile app exists
    mobile_relay_host: str = "127.0.0.1"  # loopback only — never 0.0.0.0
    mobile_relay_port: int = 7891  # arbitrary high port
    mobile_relay_secret: Optional[str] = None  # auto-generated if None
    mobile_relay_tor_enabled: bool = False  # expose via Tor hidden service
    mobile_relay_tailscale: bool = False  # log Tailscale IP on startup

    # Browser WebChat (served by Gateway on loopback TCP)
    webchat_host: str = "127.0.0.1"  # loopback only
    webchat_port: int = 8789  # open http://127.0.0.1:8789
    webchat_token: Optional[str] = None  # if set, URL must include ?token=<value>
    webchat_tailscale: bool = False  # also bind on Tailscale IP (100.x.x.x)

    # ── Trading Bot ──────────────────────────────────────────────
    trading_enabled: bool = False
    trading_paper_mode: bool = True  # SAFETY: paper trade by default
    trading_auto_trade: bool = False  # autonomous trading in autonomous mode
    trading_scan_interval: int = 60  # seconds between market scans

    # Exchange API keys
    binance_api_key: Optional[str] = None
    binance_api_secret: Optional[str] = None
    binance_testnet: bool = True

    coinbase_api_key: Optional[str] = None
    coinbase_api_secret: Optional[str] = None

    alpaca_api_key: Optional[str] = None
    alpaca_api_secret: Optional[str] = None
    alpaca_paper: bool = True

    polymarket_private_key: Optional[str] = None
    polymarket_funder: Optional[str] = None

    hyperliquid_private_key: Optional[str] = None
    hyperliquid_testnet: bool = True

    jupiter_private_key: Optional[str] = None
    jupiter_rpc_url: str = "https://api.mainnet-beta.solana.com"

    # Risk limits
    trading_max_position_pct: float = 5.0
    trading_max_daily_loss_pct: float = 2.0
    trading_max_drawdown_pct: float = 10.0
    trading_max_open_positions: int = 10
    trading_max_order_usd: float = 10000.0
    trading_require_approval_above_usd: float = 100.0
    trading_banned_assets: str = ""  # comma-separated

    # Strategy settings
    trading_strategies: str = "momentum,mean_reversion,sentiment"  # comma-separated
    trading_watchlist: str = "BTC/USDT,ETH/USDT,SOL/USDT"  # comma-separated

    # Misc compat
    Config_alias: Optional[str] = None

    def exists(self) -> bool:
        """Check if config file exists (compat)"""
        return True

    class Config:
        extra = "ignore"  # silently drop unknown fields (catches env var typos)


def load_config() -> OpenSableConfig:
    """Load configuration from environment variables"""
    load_dotenv()

    config_data = {
        "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        "default_model": os.getenv("DEFAULT_MODEL", "llama3.1:8b"),
        "auto_select_model": os.getenv("AUTO_SELECT_MODEL", "true").lower() == "true",
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY"),
        "deepseek_api_key": os.getenv("DEEPSEEK_API_KEY"),
        "groq_api_key": os.getenv("GROQ_API_KEY"),
        "together_api_key": os.getenv("TOGETHER_API_KEY"),
        "xai_api_key": os.getenv("XAI_API_KEY"),
        "mistral_api_key": os.getenv("MISTRAL_API_KEY"),
        "gemini_api_key": os.getenv("GEMINI_API_KEY"),
        "cohere_api_key": os.getenv("COHERE_API_KEY"),
        "kimi_api_key": os.getenv("KIMI_API_KEY") or os.getenv("MOONSHOT_API_KEY"),
        "qwen_api_key": os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY"),
        "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
        "openwebui_api_key": os.getenv("OPENWEBUI_API_KEY"),
        "openwebui_api_url": os.getenv("OPENWEBUI_API_URL"),
        "openwebui_model": os.getenv("OPENWEBUI_MODEL"),
        "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN"),
        "telegram_allowed_users": [
            u.strip() for u in os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",") if u.strip()
        ],
        "telegram_userbot_enabled": os.getenv("TELEGRAM_USERBOT_ENABLED", "false").lower()
        == "true",
        "telegram_api_id": (
            int(os.getenv("TELEGRAM_API_ID", "0")) if os.getenv("TELEGRAM_API_ID") else None
        ),
        "telegram_api_hash": os.getenv("TELEGRAM_API_HASH"),
        "telegram_phone_number": os.getenv("TELEGRAM_PHONE_NUMBER"),
        "telegram_session_name": os.getenv("TELEGRAM_SESSION_NAME", "opensable_session"),
        "userbot_auto_respond": os.getenv("USERBOT_AUTO_RESPOND", "true").lower() == "true",
        "discord_bot_token": os.getenv("DISCORD_BOT_TOKEN"),
        "discord_guild_id": os.getenv("DISCORD_GUILD_ID"),
        "whatsapp_enabled": os.getenv("WHATSAPP_ENABLED", "false").lower() == "true",
        # X (Twitter) / Grok
        "x_username": os.getenv("X_USERNAME"),
        "x_email": os.getenv("X_EMAIL"),
        "x_password": os.getenv("X_PASSWORD"),
        "x_enabled": os.getenv("X_ENABLED", "false").lower() == "true",
        "x_language": os.getenv("X_LANGUAGE", "en-US"),
        "x_action_delay": int(os.getenv("X_ACTION_DELAY", "2")),
        "grok_enabled": os.getenv("GROK_ENABLED", "false").lower() == "true",
        # X Autoposter
        "x_autoposter_enabled": os.getenv("X_AUTOPOSTER_ENABLED", "false").lower() == "true",
        "x_post_interval": int(os.getenv("X_POST_INTERVAL", "1800")),
        "x_topics": os.getenv("X_TOPICS", "geopolitics,tech,ai"),
        "x_style": os.getenv("X_STYLE", "analyst"),
        "x_max_daily_posts": int(os.getenv("X_MAX_DAILY_POSTS", "20")),
        "x_max_daily_engagements": int(os.getenv("X_MAX_DAILY_ENGAGEMENTS", "100")),
        "x_dry_run": os.getenv("X_DRY_RUN", "false").lower() == "true",
        "x_custom_feeds": os.getenv("X_CUSTOM_FEEDS", ""),
        "x_engage_interval": int(os.getenv("X_ENGAGE_INTERVAL", "300")),
        "x_accounts_to_watch": os.getenv("X_ACCOUNTS_TO_WATCH", ""),
        "x_reply_probability": float(os.getenv("X_REPLY_PROBABILITY", "0.3")),
        "x_like_probability": float(os.getenv("X_LIKE_PROBABILITY", "0.6")),
        "x_retweet_probability": float(os.getenv("X_RETWEET_PROBABILITY", "0.2")),
        "x_follow_probability": float(os.getenv("X_FOLLOW_PROBABILITY", "0.1")),
        "x_quote_probability": float(os.getenv("X_QUOTE_PROBABILITY", "0.1")),
        "x_bookmark_probability": float(os.getenv("X_BOOKMARK_PROBABILITY", "0.15")),
        "slack_bot_token": os.getenv("SLACK_BOT_TOKEN"),
        "slack_app_token": os.getenv("SLACK_APP_TOKEN"),
        "slack_signing_secret": os.getenv("SLACK_SIGNING_SECRET"),
        "slack_allowed_users": [
            u.strip() for u in os.getenv("SLACK_ALLOWED_USERS", "").split(",") if u.strip()
        ],
        "gmail_enabled": os.getenv("GMAIL_ENABLED", "true").lower() == "true",
        "gmail_credentials_path": Path(
            os.getenv("GMAIL_CREDENTIALS_PATH", "./config/gmail_credentials.json")
        ),
        "smtp_host": os.getenv("SMTP_HOST"),
        "smtp_port": int(os.getenv("SMTP_PORT", "587")),
        "smtp_user": os.getenv("SMTP_USER"),
        "smtp_password": os.getenv("SMTP_PASSWORD"),
        "smtp_from": os.getenv("SMTP_FROM") or os.getenv("SMTP_USER"),
        "imap_host": os.getenv("IMAP_HOST"),
        "imap_port": int(os.getenv("IMAP_PORT", "993")),
        "imap_user": os.getenv("IMAP_USER") or os.getenv("SMTP_USER"),
        "imap_password": os.getenv("IMAP_PASSWORD") or os.getenv("SMTP_PASSWORD"),
        "calendar_enabled": os.getenv("CALENDAR_ENABLED", "true").lower() == "true",
        "calendar_credentials_path": Path(
            os.getenv("CALENDAR_CREDENTIALS_PATH", "./config/calendar_credentials.json")
        ),
        "enable_sandbox": os.getenv("ENABLE_SANDBOX", "true").lower() == "true",
        "allowed_domains": [
            d.strip()
            for d in os.getenv("ALLOWED_DOMAINS", "*.google.com,*.booking.com,*.airbnb.com").split(
                ","
            )
        ],
        "max_file_size_mb": int(os.getenv("MAX_FILE_SIZE_MB", "100")),
        "agent_name": os.getenv("AGENT_NAME", "Sable"),
        "agent_personality": os.getenv("AGENT_PERSONALITY", "helpful"),
        "heartbeat_interval": int(os.getenv("HEARTBEAT_INTERVAL", "300")),
        "max_retries": int(os.getenv("MAX_RETRIES", "3")),
        "memory_retention_days": int(os.getenv("MEMORY_RETENTION_DAYS", "90")),
        "vector_db_path": Path(os.getenv("VECTOR_DB_PATH", "./data/vectordb")),
        "cli_enabled": os.getenv("CLI_ENABLED", "false").lower() == "true",
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "log_file": Path(os.getenv("LOG_FILE", "./logs/opensable.log")),
        # Mobile relay
        "mobile_relay_enabled": os.getenv("MOBILE_RELAY_ENABLED", "false").lower() == "true",
        "mobile_relay_host": os.getenv("MOBILE_RELAY_HOST", "127.0.0.1"),
        "mobile_relay_port": int(os.getenv("MOBILE_RELAY_PORT", "7891")),
        "mobile_relay_secret": os.getenv("MOBILE_RELAY_SECRET"),
        "mobile_relay_tor_enabled": os.getenv("MOBILE_RELAY_TOR", "false").lower() == "true",
        "mobile_relay_tailscale": os.getenv("MOBILE_RELAY_TAILSCALE", "false").lower() == "true",
        # Browser WebChat
        "webchat_host": os.getenv("WEBCHAT_HOST", "127.0.0.1"),
        "webchat_port": int(os.getenv("WEBCHAT_PORT", "8789")),
        "webchat_token": os.getenv("WEBCHAT_TOKEN") or None,
        "webchat_tailscale": os.getenv("WEBCHAT_TAILSCALE", "false").lower() == "true",
        # Voice / TTS / STT
        "tts_provider": os.getenv("TTS_PROVIDER", "local"),
        "stt_provider": os.getenv("STT_PROVIDER", "local"),
        "tts_voice_gender": os.getenv("TTS_VOICE_GENDER", "female"),
        "tts_rate": int(os.getenv("TTS_RATE", "150")),
        "tts_volume": float(os.getenv("TTS_VOLUME", "0.9")),
        "elevenlabs_api_key": os.getenv("ELEVENLABS_API_KEY"),
        "elevenlabs_voice_id": os.getenv("ELEVENLABS_VOICE_ID"),
        "elevenlabs_model": os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2"),
        "whisper_model_size": os.getenv("WHISPER_MODEL_SIZE", "base"),
        # ── Trading Bot ──────────────────────────────────────────
        "trading_enabled": os.getenv("TRADING_ENABLED", "false").lower() == "true",
        "trading_paper_mode": os.getenv("TRADING_PAPER_MODE", "true").lower() == "true",
        "trading_auto_trade": os.getenv("TRADING_AUTO_TRADE", "false").lower() == "true",
        "trading_scan_interval": int(os.getenv("TRADING_SCAN_INTERVAL", "60")),
        # Exchange keys
        "binance_api_key": os.getenv("BINANCE_API_KEY"),
        "binance_api_secret": os.getenv("BINANCE_API_SECRET"),
        "binance_testnet": os.getenv("BINANCE_TESTNET", "true").lower() == "true",
        "coinbase_api_key": os.getenv("COINBASE_API_KEY"),
        "coinbase_api_secret": os.getenv("COINBASE_API_SECRET"),
        "alpaca_api_key": os.getenv("ALPACA_API_KEY"),
        "alpaca_api_secret": os.getenv("ALPACA_API_SECRET"),
        "alpaca_paper": os.getenv("ALPACA_PAPER", "true").lower() == "true",
        "polymarket_private_key": os.getenv("POLYMARKET_PRIVATE_KEY"),
        "polymarket_funder": os.getenv("POLYMARKET_FUNDER"),
        "hyperliquid_private_key": os.getenv("HYPERLIQUID_PRIVATE_KEY"),
        "hyperliquid_testnet": os.getenv("HYPERLIQUID_TESTNET", "true").lower() == "true",
        "jupiter_private_key": os.getenv("JUPITER_PRIVATE_KEY"),
        "jupiter_rpc_url": os.getenv("JUPITER_RPC_URL", "https://api.mainnet-beta.solana.com"),
        # Risk limits
        "trading_max_position_pct": float(os.getenv("TRADING_MAX_POSITION_PCT", "5.0")),
        "trading_max_daily_loss_pct": float(os.getenv("TRADING_MAX_DAILY_LOSS_PCT", "2.0")),
        "trading_max_drawdown_pct": float(os.getenv("TRADING_MAX_DRAWDOWN_PCT", "10.0")),
        "trading_max_open_positions": int(os.getenv("TRADING_MAX_OPEN_POSITIONS", "10")),
        "trading_max_order_usd": float(os.getenv("TRADING_MAX_ORDER_USD", "10000")),
        "trading_require_approval_above_usd": float(os.getenv("TRADING_REQUIRE_APPROVAL_ABOVE_USD", "100")),
        "trading_banned_assets": os.getenv("TRADING_BANNED_ASSETS", ""),
        # Strategy & watchlist
        "trading_strategies": os.getenv("TRADING_STRATEGIES", "momentum,mean_reversion,sentiment"),
        "trading_watchlist": os.getenv("TRADING_WATCHLIST", "BTC/USDT,ETH/USDT,SOL/USDT"),
    }

    return OpenSableConfig(**config_data)


# Alias so older modules that import 'Config' still work
Config = OpenSableConfig

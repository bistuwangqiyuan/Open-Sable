"""Interfaces package for Open-Sable,  chat platform integrations."""

__all__ = [
    "TelegramBot",
    "DiscordBot",
    "WhatsAppBot",
    "SlackBot",
    "MatrixBot",
    "IRCBot",
    "EmailBot",
    "VoiceCall",
    "CLIInterface",
    "MobileAPI",
]


def __getattr__(name: str):
    """Lazy imports so missing optional deps don't crash the package."""
    _map = {
        "TelegramBot": ".telegram_bot",
        "DiscordBot": ".discord_bot",
        "WhatsAppBot": ".whatsapp_bot",
        "SlackBot": ".slack_bot",
        "MatrixBot": ".matrix_bot",
        "IRCBot": ".irc_bot",
        "EmailBot": ".email_bot",
        "VoiceCall": ".voice_call",
        "CLIInterface": ".cli_interface",
        "MobileAPI": ".mobile_api",
    }
    module_path = _map.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    mod = importlib.import_module(module_path, __name__)
    return getattr(mod, name)

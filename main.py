"""
Open-Sable Main Entry Point
"""

import asyncio
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

from opensable.core.agent import SableAgent
from opensable.core.config import load_config

console = Console()


def setup_logging(log_level: str = "INFO"):
    """Configure logging with rich output"""
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


async def main():
    """Main entry point for Open-Sable"""
    console.print("[bold cyan]🚀 Starting Open-Sable...[/bold cyan]")

    # Load configuration
    config = load_config()
    setup_logging(config.log_level)

    logger = logging.getLogger("opensable")
    logger.info("Configuration loaded successfully")

    # ── Startup wizard: check for missing config ───────────────────
    from opensable.core.startup_wizard import run_startup_wizard

    can_proceed = await run_startup_wizard(config)
    if not can_proceed:
        console.print("[bold red]❌ Cannot start — fix the issues above and try again.[/bold red]")
        return

    # Reload config in case the wizard wrote new values to .env
    config = load_config()

    # Initialize core agent
    agent = SableAgent(config)
    await agent.initialize()
    logger.info("Core agent initialized")

    # ── Start Gateway + WebChat (always, so browser chat works) ─────────
    gateway = None
    try:
        from opensable.core.gateway import Gateway

        gateway = Gateway(agent, config)
        await gateway.start()
        webchat_port = int(getattr(config, "webchat_port", 8789))
        console.print("[bold green]🔌 Gateway running[/bold green]")
        console.print(f"[bold cyan]🌐 WebChat → http://127.0.0.1:{webchat_port}[/bold cyan]")
        console.print(
            f"[dim]Remote access: ssh -L {webchat_port}:127.0.0.1:{webchat_port} user@host[/dim]"
        )
    except Exception as e:
        logger.warning(f"Gateway failed to start: {e}")

    # ── Pixel-Bridge (Pixel Agents VS Code extension) ─────────────────────
    _bridge_proc = None
    if getattr(config, "pixel_bridge_enabled", False):
        try:
            import uuid as _uuid
            _bridge_script = Path(__file__).resolve().parent / "scripts" / "pixel-bridge.py"
            if _bridge_script.exists():
                _sid = f"sable-{_uuid.uuid4().hex[:8]}"
                _ws_url = f"ws://127.0.0.1:{getattr(config, 'webchat_port', 8789)}"
                _bridge_proc = await asyncio.create_subprocess_exec(
                    sys.executable, str(_bridge_script),
                    "--session-id", _sid,
                    "--gateway-url", _ws_url,
                )
                logger.info(f"Pixel-Bridge started (session: {_sid}, pid: {_bridge_proc.pid})")
                console.print(f"[bold magenta]🎮 Pixel-Bridge running (session: {_sid})[/bold magenta]")
            else:
                logger.warning(f"Pixel-Bridge script not found at {_bridge_script}")
        except Exception as e:
            logger.warning(f"Pixel-Bridge failed to start: {e}")

    # Check if autonomous mode is enabled
    autonomous_enabled = getattr(config, "autonomous_mode", False)

    if autonomous_enabled:
        console.print("[bold yellow]🤖 AUTONOMOUS MODE ENABLED[/bold yellow]")
        console.print("[dim]Agent will run continuously and take actions independently[/dim]")

        from opensable.core.autonomous_mode import AutonomousMode

        autonomous = AutonomousMode(agent, config)

        # Start autonomous operation
        await autonomous.start()
        return

    # Start interfaces
    interfaces = []

    # CLI (terminal chat)
    if getattr(config, "cli_enabled", False):
        from opensable.interfaces.cli_interface import CLIInterface

        cli = CLIInterface(agent, config)
        logger.info("CLI interface enabled")
        # CLI runs solo - don't start other interfaces
        console.print("[bold green]✅ Starting CLI mode[/bold green]")
        await cli.start()
        return

    # Telegram bot
    if config.telegram_bot_token:
        try:
            from opensable.interfaces.telegram_bot import TelegramInterface

            telegram = TelegramInterface(agent, config)
            interfaces.append(telegram)
            logger.info("Telegram bot enabled")
        except Exception as e:
            logger.error(f"Telegram init failed: {e}")

    # Telegram userbot
    if config.telegram_userbot_enabled:
        try:
            from opensable.interfaces.telegram_userbot import HybridTelegramInterface

            userbot = HybridTelegramInterface(agent, config)
            interfaces.append(userbot)
            logger.info("Telegram userbot enabled")
        except Exception as e:
            logger.error(f"Telegram userbot init failed: {e}")

    # Discord
    if config.discord_bot_token:
        try:
            from opensable.interfaces.discord_bot import DiscordInterface

            discord = DiscordInterface(agent, config)
            interfaces.append(discord)
            logger.info("Discord interface enabled")
        except Exception as e:
            logger.error(f"Discord init failed: {e}")

    # WhatsApp
    if getattr(config, "whatsapp_enabled", False):
        from opensable.interfaces.whatsapp_bot import WhatsAppBot

        whatsapp = WhatsAppBot(config, agent)
        interfaces.append(whatsapp)
        logger.info("WhatsApp bot enabled")

    # Slack
    if getattr(config, "slack_bot_token", None) and getattr(config, "slack_app_token", None):
        try:
            from opensable.interfaces.slack_bot import SlackInterface

            slack = SlackInterface(agent, config)
            interfaces.append(slack)
            logger.info("Slack interface enabled")
        except Exception as e:
            logger.error(f"Slack init failed: {e}")

    platform_count = len(interfaces)
    if platform_count > 0:
        console.print(
            f"[bold green]✅ Open-Sable is running with {platform_count} interface(s) + WebChat[/bold green]"
        )
    elif gateway:
        console.print("[bold green]✅ Open-Sable is running with WebChat only[/bold green]")
        console.print("[dim]Add tokens to .env for Telegram, Discord, WhatsApp, Slack[/dim]")
    else:
        console.print("[yellow]⚠️  No chat interfaces started.[/yellow]")
        return

    console.print(
        f"[dim]Agent: {config.agent_name} | Personality: {config.agent_personality}[/dim]"
    )
    console.print("[dim]Type Ctrl+C to stop[/dim]")

    # Run all interfaces (+ keep alive for WebChat if no platforms)
    try:
        if interfaces:
            await asyncio.gather(*[interface.start() for interface in interfaces])
        else:
            # No platform interfaces — just keep the WebChat running
            await asyncio.Event().wait()
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down gracefully...[/yellow]")
        if _bridge_proc and _bridge_proc.returncode is None:
            _bridge_proc.terminate()
        for interface in interfaces:
            await interface.stop()
        if gateway:
            await gateway.stop()
        await agent.shutdown()
        console.print("[bold green]✅ Open-Sable stopped[/bold green]")


if __name__ == "__main__":
    asyncio.run(main())

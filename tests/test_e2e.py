"""
End-to-End tests for SableCore.

These tests spin up real components (Gateway, Config, ToolRegistry)
and verify they work together — not just mocked unit behavior.

Run:
    pytest tests/test_e2e.py -v
    pytest tests/test_e2e.py -m e2e -v
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from opensable.core.config import OpenSableConfig, load_config
from opensable.core.gateway import Gateway, GatewayServer, SOCKET_PATH, GATEWAY_VER, _clean_gateway_reply


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def config():
    """Create a test config with a random high port to avoid collisions."""
    import random
    port = random.randint(19000, 19999)
    return OpenSableConfig(
        webchat_host="127.0.0.1",
        webchat_port=port,
        webchat_token=None,
        webchat_tailscale=False,
    )


@pytest.fixture
def config_with_token():
    """Config with token auth enabled."""
    import random
    port = random.randint(19000, 19999)
    return OpenSableConfig(
        webchat_host="127.0.0.1",
        webchat_port=port,
        webchat_token="test-secret-token-42",
        webchat_tailscale=False,
    )


@pytest.fixture
def mock_agent():
    """A mock agent with all the methods Gateway expects."""
    agent = MagicMock()
    agent.tools = MagicMock()
    agent.tools.list_tools = MagicMock(return_value=["browser_search", "system_run", "email_send"])
    agent.llm = MagicMock()
    agent.llm.current_model = "test-model-7b"
    agent.monitor_subscribe = MagicMock()

    async def mock_process(user_id, text, history=None, progress_callback=None):
        if progress_callback:
            await progress_callback("Thinking...")
        return f"Echo: {text}"

    agent.process_message = AsyncMock(side_effect=mock_process)
    return agent


@pytest.fixture
async def gateway(mock_agent, config):
    """Start a real Gateway instance, yield it, stop after test."""
    gw = Gateway(mock_agent, config)
    await gw.start()
    yield gw
    await gw.stop()


@pytest.fixture
async def gateway_with_token(mock_agent, config_with_token):
    """Start a Gateway with token auth."""
    gw = Gateway(mock_agent, config_with_token)
    await gw.start()
    yield gw
    await gw.stop()


# ─── Config Validation E2E ────────────────────────────────────────────────────


class TestConfigValidation:
    """Test that config validators catch real-world misconfigurations."""

    @pytest.mark.e2e
    def test_valid_default_config(self):
        """Default config should always be valid."""
        c = OpenSableConfig()
        assert c.webchat_port == 8789
        assert c.log_level == "INFO"
        assert c.ollama_base_url == "http://localhost:11434"

    @pytest.mark.e2e
    def test_invalid_port_rejected(self):
        with pytest.raises(Exception, match="Port must be 1-65535"):
            OpenSableConfig(webchat_port=70000)

    @pytest.mark.e2e
    def test_invalid_url_rejected(self):
        with pytest.raises(Exception, match="must start with http"):
            OpenSableConfig(ollama_base_url="ftp://invalid:1234")

    @pytest.mark.e2e
    def test_invalid_probability_rejected(self):
        with pytest.raises(Exception, match="Probability must be 0.0-1.0"):
            OpenSableConfig(x_reply_probability=2.0)

    @pytest.mark.e2e
    def test_invalid_log_level_rejected(self):
        with pytest.raises(Exception, match="log_level must be one of"):
            OpenSableConfig(log_level="VERBOSE")

    @pytest.mark.e2e
    def test_url_trailing_slash_stripped(self):
        c = OpenSableConfig(ollama_base_url="http://localhost:11434/")
        assert c.ollama_base_url == "http://localhost:11434"

    @pytest.mark.e2e
    def test_volume_clamped(self):
        c = OpenSableConfig(tts_volume=5.0)
        assert c.tts_volume == 1.0

    @pytest.mark.e2e
    def test_negative_retention_rejected(self):
        with pytest.raises(Exception, match="must be >= 1"):
            OpenSableConfig(memory_retention_days=0)

    @pytest.mark.e2e
    def test_extra_fields_ignored(self):
        """Unknown fields should not crash (extra='ignore')."""
        c = OpenSableConfig(nonexistent_field="hello")
        assert not hasattr(c, "nonexistent_field")

    @pytest.mark.e2e
    def test_load_config_from_env(self, monkeypatch):
        """load_config() should read env vars and return valid config."""
        monkeypatch.setenv("DEFAULT_MODEL", "test-model-3b")
        monkeypatch.setenv("WEBCHAT_PORT", "9999")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        c = load_config()
        assert c.default_model == "test-model-3b"
        assert c.webchat_port == 9999
        assert c.log_level == "DEBUG"

    @pytest.mark.e2e
    def test_percentage_bounds(self):
        with pytest.raises(Exception, match="Percentage must be 0-100"):
            OpenSableConfig(trading_max_position_pct=150.0)

    @pytest.mark.e2e
    def test_positive_intervals(self):
        with pytest.raises(Exception, match="must be >= 1"):
            OpenSableConfig(heartbeat_interval=0)


# ─── Gateway Reply Cleaning E2E ──────────────────────────────────────────────


class TestReplyClean:
    """Test the thinking-block removal that runs on every gateway reply."""

    @pytest.mark.e2e
    def test_strips_think_tags(self):
        assert _clean_gateway_reply("<think>internal</think>Hello!") == "Hello!"

    @pytest.mark.e2e
    def test_strips_orphan_think(self):
        assert _clean_gateway_reply("<think>forever thinking...") == ""

    @pytest.mark.e2e
    def test_strips_reasoning_preamble(self):
        text = "I need to help the user.\nLet me think about this.\n\nHere is your answer."
        result = _clean_gateway_reply(text)
        assert "Here is your answer" in result
        assert "I need to" not in result

    @pytest.mark.e2e
    def test_preserves_normal_text(self):
        assert _clean_gateway_reply("Just a normal reply.") == "Just a normal reply."

    @pytest.mark.e2e
    def test_empty_input(self):
        assert _clean_gateway_reply("") == ""
        assert _clean_gateway_reply(None) is None


# ─── Tools Registry E2E ──────────────────────────────────────────────────────


class TestToolsRegistry:
    """Test that the refactored tools registry still works correctly."""

    @pytest.mark.e2e
    def test_schemas_load(self):
        from opensable.core.tools._schemas import get_all_schemas

        schemas = get_all_schemas()
        assert len(schemas) >= 100  # should be ~125
        # Every schema must have the OpenAI function-call structure
        for s in schemas:
            assert s.get("type") == "function", f"Missing type: {s.get('function', {}).get('name')}"
            fn = s.get("function", {})
            assert "name" in fn, f"Schema missing name: {s}"
            assert "parameters" in fn, f"Schema missing parameters: {fn.get('name')}"

    @pytest.mark.e2e
    def test_permissions_load(self):
        from opensable.core.tools._permissions import TOOL_PERMISSIONS

        assert len(TOOL_PERMISSIONS) >= 80  # should be ~90
        for tool_name, action in TOOL_PERMISSIONS.items():
            assert isinstance(tool_name, str)
            assert isinstance(action, str)
            assert action  # non-empty

    @pytest.mark.e2e
    def test_dispatch_load(self):
        from opensable.core.tools._dispatch import SCHEMA_TO_TOOL

        assert len(SCHEMA_TO_TOOL) >= 100  # should be ~125
        for tool_name, (method_name, arg_mapper) in SCHEMA_TO_TOOL.items():
            assert isinstance(tool_name, str)
            assert isinstance(method_name, str)
            assert callable(arg_mapper)

    @pytest.mark.e2e
    def test_schema_dispatch_alignment(self):
        """Every schema should have a corresponding dispatch entry."""
        from opensable.core.tools._schemas import get_all_schemas
        from opensable.core.tools._dispatch import SCHEMA_TO_TOOL

        schema_names = {s["function"]["name"] for s in get_all_schemas()}
        dispatch_names = set(SCHEMA_TO_TOOL.keys())
        missing = schema_names - dispatch_names
        assert not missing, f"Schemas without dispatch: {missing}"


# ─── Gateway WebSocket E2E ────────────────────────────────────────────────────


@pytest.mark.e2e
class TestGatewayWebSocket:
    """Real WebSocket tests against a running Gateway."""

    @pytest.mark.asyncio
    async def test_connect_and_receive_connected(self, gateway, config):
        """Connecting via WS should receive a 'connected' message."""
        url = f"http://127.0.0.1:{config.webchat_port}/ws"
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(url) as ws:
                raw = await asyncio.wait_for(ws.receive_json(), timeout=5)
                assert raw["type"] == "connected"
                assert "version" in raw
                assert "ts" in raw

    @pytest.mark.asyncio
    async def test_ping_pong(self, gateway, config):
        url = f"http://127.0.0.1:{config.webchat_port}/ws"
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(url) as ws:
                await ws.receive_json()  # connected
                await ws.send_json({"type": "ping"})
                resp = await asyncio.wait_for(ws.receive_json(), timeout=5)
                assert resp["type"] == "pong"
                assert "ts" in resp

    @pytest.mark.asyncio
    async def test_status(self, gateway, config):
        url = f"http://127.0.0.1:{config.webchat_port}/ws"
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(url) as ws:
                await ws.receive_json()  # connected
                await ws.send_json({"type": "status"})
                resp = await asyncio.wait_for(ws.receive_json(), timeout=5)
                assert resp["type"] == "status"
                assert resp["running"] is True
                assert "uptime_sec" in resp
                assert "clients" in resp

    @pytest.mark.asyncio
    async def test_tools_list(self, gateway, config):
        url = f"http://127.0.0.1:{config.webchat_port}/ws"
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(url) as ws:
                await ws.receive_json()  # connected
                await ws.send_json({"type": "tools.list"})
                resp = await asyncio.wait_for(ws.receive_json(), timeout=5)
                assert resp["type"] == "tools.list.result"
                assert "browser_search" in resp["tools"]

    @pytest.mark.asyncio
    async def test_message_flow(self, gateway, config, mock_agent):
        """Send a message -> receive message.start + progress + message.done."""
        url = f"http://127.0.0.1:{config.webchat_port}/ws"
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(url) as ws:
                await ws.receive_json()  # connected
                await ws.send_json({
                    "type": "message",
                    "session_id": "test-sid",
                    "user_id": "e2e-user",
                    "text": "Hello agent!",
                })

                # Collect responses
                msgs = []
                for _ in range(10):
                    try:
                        resp = await asyncio.wait_for(ws.receive_json(), timeout=10)
                        msgs.append(resp)
                        if resp.get("type") == "message.done":
                            break
                    except asyncio.TimeoutError:
                        break

                types = [m["type"] for m in msgs]
                assert "message.start" in types
                assert "message.done" in types

                done = next(m for m in msgs if m["type"] == "message.done")
                assert "Echo: Hello agent!" in done["text"]

    @pytest.mark.asyncio
    async def test_invalid_json(self, gateway, config):
        url = f"http://127.0.0.1:{config.webchat_port}/ws"
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(url) as ws:
                await ws.receive_json()  # connected
                await ws.send_str("not valid json{{{")
                resp = await asyncio.wait_for(ws.receive_json(), timeout=5)
                assert resp["type"] == "error"
                assert "Invalid JSON" in resp["text"]

    @pytest.mark.asyncio
    async def test_unknown_type(self, gateway, config):
        url = f"http://127.0.0.1:{config.webchat_port}/ws"
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(url) as ws:
                await ws.receive_json()
                await ws.send_json({"type": "nonexistent.type"})
                resp = await asyncio.wait_for(ws.receive_json(), timeout=5)
                assert resp["type"] == "error"
                assert "Unknown type" in resp["text"]

    @pytest.mark.asyncio
    async def test_ws_on_root_path(self, gateway, config):
        """Frontends connect to ws://host/ (root) — must work."""
        url = f"http://127.0.0.1:{config.webchat_port}/"
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(url) as ws:
                raw = await asyncio.wait_for(ws.receive_json(), timeout=5)
                assert raw["type"] == "connected"


# ─── Gateway Token Auth E2E ──────────────────────────────────────────────────


@pytest.mark.e2e
class TestGatewayTokenAuth:
    """Verify token authentication on the gateway."""

    @pytest.mark.asyncio
    async def test_no_token_returns_401(self, gateway_with_token, config_with_token):
        """Request without token should get 401."""
        port = config_with_token.webchat_port
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://127.0.0.1:{port}/") as resp:
                assert resp.status == 401

    @pytest.mark.asyncio
    async def test_wrong_token_returns_401(self, gateway_with_token, config_with_token):
        port = config_with_token.webchat_port
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://127.0.0.1:{port}/?token=wrong") as resp:
                assert resp.status == 401

    @pytest.mark.asyncio
    async def test_correct_token_returns_200(self, gateway_with_token, config_with_token):
        port = config_with_token.webchat_port
        token = config_with_token.webchat_token
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://127.0.0.1:{port}/?token={token}") as resp:
                assert resp.status == 200

    @pytest.mark.asyncio
    async def test_ws_with_correct_token(self, gateway_with_token, config_with_token):
        port = config_with_token.webchat_port
        token = config_with_token.webchat_token
        url = f"http://127.0.0.1:{port}/ws?token={token}"
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(url) as ws:
                raw = await asyncio.wait_for(ws.receive_json(), timeout=5)
                assert raw["type"] == "connected"


# ─── Gateway HTTP Routes E2E ─────────────────────────────────────────────────


@pytest.mark.e2e
class TestGatewayHTTPRoutes:
    """Verify HTTP route handlers return correct responses."""

    @pytest.mark.asyncio
    async def test_root_serves_html(self, gateway, config):
        port = config.webchat_port
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://127.0.0.1:{port}/") as resp:
                assert resp.status == 200
                assert "text/html" in resp.content_type

    @pytest.mark.asyncio
    async def test_chat_route(self, gateway, config):
        port = config.webchat_port
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://127.0.0.1:{port}/chat") as resp:
                assert resp.status == 200
                assert "text/html" in resp.content_type

    @pytest.mark.asyncio
    async def test_monitor_route(self, gateway, config):
        port = config.webchat_port
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://127.0.0.1:{port}/monitor") as resp:
                assert resp.status == 200
                assert "text/html" in resp.content_type

    @pytest.mark.asyncio
    async def test_favicon_route(self, gateway, config):
        port = config.webchat_port
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://127.0.0.1:{port}/favicon.ico") as resp:
                assert resp.status in (200, 204)


# ─── Gateway Compat ──────────────────────────────────────────────────────────


@pytest.mark.e2e
class TestGatewayCompat:
    """Verify backward-compatible exports."""

    def test_gateway_server_alias(self):
        assert GatewayServer is Gateway

    def test_socket_path(self):
        assert SOCKET_PATH == Path("/tmp/sable.sock")

    def test_version(self):
        assert isinstance(GATEWAY_VER, str)
        assert GATEWAY_VER.count(".") == 2  # semver

    @pytest.mark.asyncio
    async def test_gateway_status_dict(self, gateway, config):
        status = gateway.status()
        assert status["running"] is True
        assert isinstance(status["uptime_sec"], float)
        assert isinstance(status["clients"], int)
        assert isinstance(status["nodes"], list)

    @pytest.mark.asyncio
    async def test_gateway_broadcast(self, gateway, config):
        """broadcast() should not error when no clients connected."""
        await gateway.broadcast({"type": "test", "data": "hello"})


# ─── Rate Limiting E2E ────────────────────────────────────────────────────────


@pytest.mark.e2e
class TestRateLimiting:
    """Verify the gateway rate limiter on real WebSocket connections."""

    @pytest.mark.asyncio
    async def test_rate_limit_kicks_in(self, gateway, config, mock_agent):
        """Sending >30 messages in 60s should trigger rate limit."""
        url = f"http://127.0.0.1:{config.webchat_port}/ws"
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(url) as ws:
                await ws.receive_json()  # connected

                # Send 31 rapid messages (rate limit = 30/60s)
                for i in range(31):
                    await ws.send_json({
                        "type": "message",
                        "session_id": f"rate-test-{i}",
                        "text": f"msg {i}",
                    })

                # Drain all responses, look for a rate limit error
                found_rate_error = False
                for _ in range(100):
                    try:
                        resp = await asyncio.wait_for(ws.receive_json(), timeout=3)
                        if resp.get("type") == "error" and "Rate limit" in resp.get("text", ""):
                            found_rate_error = True
                            break
                    except asyncio.TimeoutError:
                        break

                assert found_rate_error, "Expected rate limit error after 31 rapid messages"

"""
MCP Client,  Connect to Model Context Protocol servers.

Allows Open-Sable to consume tools from any MCP-compliant server,
giving it access to the entire MCP ecosystem (databases, APIs, file systems,
GitHub, Slack, etc.) without writing custom integrations.

Usage:
    from opensable.core.mcp import MCPClient

    # Connect to a stdio-based MCP server
    client = MCPClient.stdio("npx", ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"])
    await client.connect()

    tools = await client.list_tools()         # OpenAI-format schemas
    result = await client.call_tool("read_file", {"path": "/tmp/hello.txt"})

    await client.disconnect()

    # Or use as a context manager:
    async with MCPClient.stdio("npx", ["-y", "@modelcontextprotocol/server-github"]) as mcp:
        tools = await mcp.list_tools()
        result = await mcp.call_tool("search_repositories", {"query": "opensable"})

    # SSE transport for remote servers:
    async with MCPClient.sse("https://mcp.example.com/sse") as mcp:
        tools = await mcp.list_tools()

References:
    - MCP Specification: https://spec.modelcontextprotocol.io
    - MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """A tool exposed by an MCP server."""
    name: str
    description: str
    input_schema: Dict[str, Any]

    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert to the OpenAI function-calling format used everywhere in Open-Sable."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


@dataclass
class MCPResource:
    """A resource exposed by an MCP server."""
    uri: str
    name: str
    description: str = ""
    mime_type: str = "text/plain"


class MCPClient:
    """
    Client for connecting to MCP (Model Context Protocol) servers.

    Supports two transports:
      - stdio: Launch a subprocess and communicate via stdin/stdout JSON-RPC
      - sse:   Connect to a remote server via Server-Sent Events (HTTP)
    """

    def __init__(self, transport: str, **kwargs):
        self._transport = transport
        self._kwargs = kwargs
        self._process: Optional[asyncio.subprocess.Process] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._request_id = 0
        self._pending: Dict[int, asyncio.Future] = {}
        self._tools: List[MCPTool] = []
        self._resources: List[MCPResource] = []
        self._connected = False
        self._read_task: Optional[asyncio.Task] = None
        self._server_info: Dict[str, Any] = {}

    # ── Factory methods ──────────────────────────────────────────────────

    @classmethod
    def stdio(cls, command: str, args: List[str] | None = None, env: Dict[str, str] | None = None) -> "MCPClient":
        """Create an MCP client using stdio transport (subprocess)."""
        return cls("stdio", command=command, args=args or [], env=env)

    @classmethod
    def sse(cls, url: str, headers: Dict[str, str] | None = None) -> "MCPClient":
        """Create an MCP client using SSE transport (HTTP)."""
        return cls("sse", url=url, headers=headers or {})

    # ── Context manager ──────────────────────────────────────────────────

    async def __aenter__(self) -> "MCPClient":
        await self.connect()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.disconnect()

    # ── Connection lifecycle ─────────────────────────────────────────────

    async def connect(self) -> None:
        """Establish connection to the MCP server."""
        if self._transport == "stdio":
            await self._connect_stdio()
        elif self._transport == "sse":
            await self._connect_sse()
        else:
            raise ValueError(f"Unknown transport: {self._transport}")

        # Initialize protocol
        result = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {"listChanged": True},
            },
            "clientInfo": {
                "name": "opensable",
                "version": "0.1.0",
            },
        })
        self._server_info = result or {}

        # Send initialized notification
        await self._send_notification("notifications/initialized", {})

        self._connected = True
        server_name = self._server_info.get("serverInfo", {}).get("name", "unknown")
        logger.info(f"✅ MCP connected to: {server_name}")

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except (asyncio.CancelledError, Exception):
                pass

        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()
            self._process = None

        self._connected = False
        logger.info("MCP disconnected")

    # ── Public API ───────────────────────────────────────────────────────

    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        List tools from the MCP server, returned as OpenAI-format schemas.

        These can be directly appended to the agent's tool_schemas.
        """
        result = await self._send_request("tools/list", {})
        tools = result.get("tools", []) if result else []
        self._tools = [
            MCPTool(
                name=t["name"],
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {"type": "object", "properties": {}}),
            )
            for t in tools
        ]
        return [t.to_openai_schema() for t in self._tools]

    async def call_tool(self, name: str, arguments: Dict[str, Any] | None = None) -> str:
        """Call a tool on the MCP server and return the text result."""
        result = await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments or {},
        })
        if not result:
            return f"❌ MCP tool '{name}' returned no result"

        # MCP returns content as a list of content blocks
        content = result.get("content", [])
        text_parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif block.get("type") == "image":
                    text_parts.append(f"[image: {block.get('mimeType', 'image/png')}]")
                else:
                    text_parts.append(str(block))
            else:
                text_parts.append(str(block))

        return "\n".join(text_parts) if text_parts else str(result)

    async def list_resources(self) -> List[MCPResource]:
        """List resources from the MCP server."""
        result = await self._send_request("resources/list", {})
        resources = result.get("resources", []) if result else []
        self._resources = [
            MCPResource(
                uri=r["uri"],
                name=r.get("name", r["uri"]),
                description=r.get("description", ""),
                mime_type=r.get("mimeType", "text/plain"),
            )
            for r in resources
        ]
        return self._resources

    async def read_resource(self, uri: str) -> str:
        """Read a resource by URI."""
        result = await self._send_request("resources/read", {"uri": uri})
        contents = result.get("contents", []) if result else []
        parts = []
        for c in contents:
            if isinstance(c, dict):
                parts.append(c.get("text", str(c)))
            else:
                parts.append(str(c))
        return "\n".join(parts)

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def server_info(self) -> Dict[str, Any]:
        return self._server_info

    # ── Stdio transport ──────────────────────────────────────────────────

    async def _connect_stdio(self) -> None:
        """Launch subprocess and wire up stdin/stdout."""
        cmd = self._kwargs["command"]
        args = self._kwargs.get("args", [])
        env = self._kwargs.get("env")

        import os
        full_env = {**os.environ, **(env or {})}

        self._process = await asyncio.create_subprocess_exec(
            cmd, *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=full_env,
        )

        # Start background reader
        self._read_task = asyncio.create_task(self._stdio_reader())

    async def _stdio_reader(self) -> None:
        """Read JSON-RPC messages from subprocess stdout."""
        assert self._process and self._process.stdout
        buffer = b""
        while True:
            try:
                chunk = await self._process.stdout.read(4096)
                if not chunk:
                    break
                buffer += chunk

                # Process complete JSON-RPC messages (newline-delimited)
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        self._handle_message(msg)
                    except json.JSONDecodeError:
                        logger.debug(f"MCP: non-JSON line: {line[:100]}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"MCP reader error: {e}")
                break

    # ── SSE transport ────────────────────────────────────────────────────

    async def _connect_sse(self) -> None:
        """Connect to an MCP server via SSE (Server-Sent Events)."""
        # SSE transport is more complex,  simplified implementation
        # that posts JSON-RPC via HTTP
        self._sse_url = self._kwargs["url"]
        self._sse_headers = self._kwargs.get("headers", {})
        logger.info(f"MCP SSE connecting to {self._sse_url}")

    # ── JSON-RPC helpers ─────────────────────────────────────────────────

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _send_request(self, method: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send a JSON-RPC request and wait for the response."""
        req_id = self._next_id()
        msg = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }

        if self._transport == "stdio":
            return await self._stdio_send(msg, req_id)
        elif self._transport == "sse":
            return await self._sse_send(msg, req_id)
        return None

    async def _send_notification(self, method: str, params: Dict[str, Any]) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        msg = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        if self._transport == "stdio" and self._process and self._process.stdin:
            data = json.dumps(msg) + "\n"
            self._process.stdin.write(data.encode())
            await self._process.stdin.drain()

    async def _stdio_send(self, msg: Dict, req_id: int) -> Optional[Dict]:
        """Send request via stdio and wait for response."""
        if not self._process or not self._process.stdin:
            raise ConnectionError("MCP stdio process not running")

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[req_id] = future

        data = json.dumps(msg) + "\n"
        self._process.stdin.write(data.encode())
        await self._process.stdin.drain()

        try:
            result = await asyncio.wait_for(future, timeout=30)
            return result
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            logger.error(f"MCP request timed out: {msg.get('method')}")
            return None

    async def _sse_send(self, msg: Dict, req_id: int) -> Optional[Dict]:
        """Send request via HTTP POST to SSE endpoint."""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    self._sse_url,
                    json=msg,
                    headers={**self._sse_headers, "Content-Type": "application/json"},
                    timeout=30,
                )
                return resp.json().get("result")
        except Exception as e:
            logger.error(f"MCP SSE request failed: {e}")
            return None

    def _handle_message(self, msg: Dict) -> None:
        """Handle an incoming JSON-RPC message."""
        msg_id = msg.get("id")
        if msg_id is not None and msg_id in self._pending:
            future = self._pending.pop(msg_id)
            if "error" in msg:
                error = msg["error"]
                logger.error(f"MCP error: {error.get('message', error)}")
                future.set_result(None)
            else:
                future.set_result(msg.get("result"))
        elif "method" in msg:
            # Server-initiated notification
            logger.debug(f"MCP notification: {msg['method']}")


def connect_mcp_tools(
    agent_tools,  # ToolRegistry instance
    mcp_tools: List[Dict[str, Any]],
    mcp_client: MCPClient,
) -> None:
    """
    Wire MCP tools into an Open-Sable ToolRegistry so the agent can call them.

    Args:
        agent_tools: The ToolRegistry instance from the agent
        mcp_tools: List of OpenAI-format schemas from mcp.list_tools()
        mcp_client: The connected MCPClient
    """
    for schema in mcp_tools:
        fn = schema.get("function", schema)
        name = fn["name"]

        # Create a handler that delegates to the MCP server
        async def _handler(params: Dict, _name=name) -> str:
            return await mcp_client.call_tool(_name, params)

        agent_tools.register(name, _handler)
        agent_tools._custom_schemas.append(schema)

    logger.info(f"✅ Registered {len(mcp_tools)} MCP tools")

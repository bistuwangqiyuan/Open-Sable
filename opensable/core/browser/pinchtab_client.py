"""
PinchTab client — HTTP adapter for the PinchTab browser control server.

PinchTab provides token-efficient, stealth-capable browser automation via a
lightweight HTTP API.  This module wraps its REST endpoints so BrowserEngine
can transparently delegate to PinchTab when available, falling back to
Playwright when it isn't.

Ref: https://github.com/pinchtab/pinchtab
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

# Default PinchTab server
_DEFAULT_URL = "http://127.0.0.1:9867"
_HEALTH_TIMEOUT = 3  # seconds to wait for health check
_NAV_TIMEOUT = 20  # seconds to wait for navigation


def _find_pinchtab_binary() -> Optional[str]:
    """Locate the pinchtab binary (project bin/ first, then PATH)."""
    project_bin = Path(__file__).resolve().parents[3] / "bin" / "pinchtab"
    if project_bin.exists() and os.access(str(project_bin), os.X_OK):
        return str(project_bin)
    which = shutil.which("pinchtab")
    return which


class PinchTabClient:
    """Async HTTP client for a PinchTab server.

    Lifecycle:
        1. ``await connect()`` — check if server is reachable (or auto-start it)
        2. Use ``navigate()``, ``snapshot()``, ``text()``, ``click()``, etc.
        3. ``await shutdown()`` — stop the managed server (if we started it)
    """

    def __init__(self, base_url: Optional[str] = None, auto_start: bool = True):
        self.base_url = (
            base_url
            or os.environ.get("PINCHTAB_URL")
            or _DEFAULT_URL
        ).rstrip("/")
        self._auto_start = auto_start
        self._process: Optional[subprocess.Popen] = None
        self._connected = False
        self._instance_id: Optional[str] = None
        self._default_tab: Optional[str] = None
        # aiohttp session (lazy)
        self._session = None

    # ── Connection ────────────────────────────────────────────────────────

    async def _get_session(self):
        """Lazy aiohttp session creation."""
        if self._session is None or self._session.closed:
            import aiohttp
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return self._session

    async def connect(self) -> bool:
        """Check PinchTab reachability; auto-start if configured."""
        if self._connected:
            return True

        # 1. Check if already running
        if await self._health_check():
            self._connected = True
            await self._ensure_instance()
            logger.info(f"✅ PinchTab connected at {self.base_url}")
            return True

        # 2. Auto-start if we can
        if self._auto_start:
            binary = _find_pinchtab_binary()
            if binary:
                return await self._start_server(binary)

        logger.debug("PinchTab not available")
        return False

    async def _health_check(self) -> bool:
        """Ping the PinchTab server."""
        try:
            session = await self._get_session()
            async with session.get(
                f"{self.base_url}/health",
                timeout=_HEALTH_TIMEOUT,
            ) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def _start_server(self, binary: str) -> bool:
        """Start PinchTab server as a subprocess."""
        logger.info(f"Starting PinchTab server: {binary}")
        try:
            self._process = subprocess.Popen(
                [binary],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid,
            )
            # Wait up to 8s for it to be ready
            for _ in range(16):
                await asyncio.sleep(0.5)
                if await self._health_check():
                    self._connected = True
                    await self._ensure_instance()
                    logger.info(f"✅ PinchTab server started (PID {self._process.pid})")
                    return True

            logger.warning("PinchTab started but not responding in time")
            self._kill_server()
            return False
        except Exception as e:
            logger.warning(f"Failed to start PinchTab: {e}")
            return False

    async def _ensure_instance(self):
        """Create a default headless instance if none exists."""
        try:
            session = await self._get_session()
            # Check existing instances
            async with session.get(f"{self.base_url}/instances") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    instances = data if isinstance(data, list) else data.get("instances", [])
                    if instances:
                        self._instance_id = instances[0].get("id") or instances[0].get("instanceId")
                        logger.debug(f"PinchTab: reusing instance {self._instance_id}")
                        return

            # Launch new headless instance
            async with session.post(
                f"{self.base_url}/instances/launch",
                json={"name": "sable", "mode": "headless"},
            ) as resp:
                if resp.status in (200, 201):
                    data = await resp.json()
                    self._instance_id = data.get("id") or data.get("instanceId")
                    logger.info(f"PinchTab: created instance {self._instance_id}")
        except Exception as e:
            logger.debug(f"PinchTab instance setup: {e}")

    # ── Core API ──────────────────────────────────────────────────────────

    async def navigate(self, url: str) -> Dict[str, Any]:
        """Navigate to a URL, return tab info."""
        try:
            session = await self._get_session()
            if self._instance_id:
                async with session.post(
                    f"{self.base_url}/instances/{self._instance_id}/tabs/open",
                    json={"url": url},
                    timeout=_NAV_TIMEOUT,
                ) as resp:
                    if resp.status in (200, 201):
                        data = await resp.json()
                        self._default_tab = data.get("tabId") or data.get("id")
                        return {"success": True, "tabId": self._default_tab, "url": url}
            # Fallback: CLI-style nav endpoint
            async with session.post(
                f"{self.base_url}/nav",
                json={"url": url},
                timeout=_NAV_TIMEOUT,
            ) as resp:
                data = await resp.json()
                return {"success": resp.status == 200, **data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def snapshot(self, tab_id: Optional[str] = None, filter_type: str = "interactive") -> Dict[str, Any]:
        """Get accessibility snapshot (element refs) for a tab."""
        tid = tab_id or self._default_tab
        if not tid:
            return {"success": False, "error": "No active tab"}
        try:
            session = await self._get_session()
            async with session.get(
                f"{self.base_url}/tabs/{tid}/snapshot",
                params={"filter": filter_type},
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {"success": True, **data}
                return {"success": False, "error": f"HTTP {resp.status}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def text(self, tab_id: Optional[str] = None) -> Dict[str, Any]:
        """Extract page text (token-efficient, ~800 tokens/page)."""
        tid = tab_id or self._default_tab
        if not tid:
            return {"success": False, "error": "No active tab"}
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/tabs/{tid}/text") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {"success": True, **data}
                # Some versions return plain text
                body = await resp.text()
                return {"success": True, "text": body}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def click(self, ref: str, tab_id: Optional[str] = None) -> Dict[str, Any]:
        """Click an element by ref."""
        tid = tab_id or self._default_tab
        if not tid:
            return {"success": False, "error": "No active tab"}
        try:
            session = await self._get_session()
            async with session.post(
                f"{self.base_url}/tabs/{tid}/action",
                json={"kind": "click", "ref": ref},
            ) as resp:
                data = await resp.json()
                return {"success": resp.status == 200, **data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def fill(self, ref: str, value: str, tab_id: Optional[str] = None) -> Dict[str, Any]:
        """Fill an input field by ref."""
        tid = tab_id or self._default_tab
        if not tid:
            return {"success": False, "error": "No active tab"}
        try:
            session = await self._get_session()
            async with session.post(
                f"{self.base_url}/tabs/{tid}/action",
                json={"kind": "fill", "ref": ref, "value": value},
            ) as resp:
                data = await resp.json()
                return {"success": resp.status == 200, **data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def press(self, ref: str, key: str, tab_id: Optional[str] = None) -> Dict[str, Any]:
        """Press a key on an element."""
        tid = tab_id or self._default_tab
        if not tid:
            return {"success": False, "error": "No active tab"}
        try:
            session = await self._get_session()
            async with session.post(
                f"{self.base_url}/tabs/{tid}/action",
                json={"kind": "press", "ref": ref, "key": key},
            ) as resp:
                data = await resp.json()
                return {"success": resp.status == 200, **data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def screenshot(self, tab_id: Optional[str] = None) -> Optional[bytes]:
        """Take screenshot, return PNG bytes."""
        tid = tab_id or self._default_tab
        if not tid:
            return None
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/tabs/{tid}/screenshot") as resp:
                if resp.status == 200:
                    return await resp.read()
        except Exception:
            pass
        return None

    async def close_tab(self, tab_id: Optional[str] = None) -> bool:
        """Close a tab."""
        tid = tab_id or self._default_tab
        if not tid:
            return False
        try:
            session = await self._get_session()
            async with session.delete(f"{self.base_url}/tabs/{tid}") as resp:
                if tid == self._default_tab:
                    self._default_tab = None
                return resp.status == 200
        except Exception:
            return False

    # ── Lifecycle ─────────────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        return self._connected

    def _kill_server(self):
        """Kill the managed PinchTab process."""
        if self._process:
            try:
                os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
            except (OSError, ProcessLookupError):
                pass
            self._process = None

    async def shutdown(self):
        """Shutdown: close session and kill managed server."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
        self._kill_server()
        self._connected = False
        self._instance_id = None
        self._default_tab = None

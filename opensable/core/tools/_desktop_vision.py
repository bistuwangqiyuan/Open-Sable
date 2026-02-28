"""
Desktop control and vision/autonomous computer-use tools
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


class DesktopVisionToolsMixin:
    """Mixin providing desktop control and vision/autonomous computer-use tools tool implementations."""

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

    async def _open_url_tool(self, params: Dict) -> str:
        """Open a URL directly in Chromium"""
        url = params.get("url", "")
        result = await self.vision.open_url(url)
        if result.get("success"):
            return f"🌐 Opened {result['url']} in {result['browser']} (PID {result.get('pid')})"
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


"""
Vision Tools — autonomous screen understanding and computer control.

Uses Ollama vision models (Qwen2.5-VL, LLaVA, chat-gph-vision) to "see"
the screen, find UI elements by description and interact with them.

New tools added to the agent:
  screen_analyze   — screenshot + VLM → describe what's on screen
  screen_find      — find UI element by text description → (x, y) coords
  screen_click_on  — one shot: "click on Login button" → find → click
  open_app         — open an application by name (Firefox, terminal, etc.)
  window_list      — list all open windows
  window_focus     — bring a window to front by title
"""

import asyncio
import base64
import logging
import re
import subprocess
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Vision model priority order — best first
# The user has qwen2.5-vl-7b (redule26) and chat-gph-vision already installed
_VISION_MODEL_PRIORITY = [
    "redule26/huihui_ai_qwen2.5-vl-7b-abliterated",
    "mskimomadto/chat-gph-vision",
    "qwen2.5vl",
    "qwen2-vl",
    "qwenvl",
    "llava",
    "minicpm-v",
    "moondream",
    "bakllava",
]


class VisionTools:
    """
    Gives the agent eyes — screenshot → VLM → understand → act.

    All methods return {success: bool, ...} dicts, same pattern as ComputerTools.
    """

    def __init__(self, config):
        self.config = config
        self.ollama_url = getattr(config, "ollama_base_url", "http://localhost:11434")
        self._vision_model: Optional[str] = None
        self._client = None
        self._screen_w: Optional[int] = None
        self._screen_h: Optional[int] = None

    # ─────────────────────────────────────────────────────────────────────
    #  Internal helpers
    # ─────────────────────────────────────────────────────────────────────

    async def _get_client(self):
        """Lazy-init: detect the best available Ollama vision model."""
        if self._client is not None:
            return self._client, self._vision_model

        try:
            import ollama  # type: ignore

            client = ollama.AsyncClient(host=self.ollama_url)
            models_resp = await client.list()

            # Support both old dict API and new Pydantic ListResponse object
            if hasattr(models_resp, "models"):
                available = [m.model for m in models_resp.models if hasattr(m, "model")]
            else:
                available = [m["name"] for m in models_resp.get("models", [])]

            chosen = None
            for pref in _VISION_MODEL_PRIORITY:
                for m in available:
                    if pref.lower() in m.lower():
                        chosen = m
                        break
                if chosen:
                    break

            # Fallback: any model with vision keywords
            if not chosen:
                for m in available:
                    if any(k in m.lower() for k in ["llava", "vl", "vision", "moondream", "minicpm"]):
                        chosen = m
                        break

            if chosen:
                self._vision_model = chosen
                self._client = client
                logger.info(f"👁️ Vision model selected: {chosen}")
            else:
                logger.warning(
                    "👁️ No vision model found in Ollama. "
                    "Run: ollama pull llava:7b  (or qwen2.5-vl)"
                )

        except Exception as e:
            logger.warning(f"VisionTools: Ollama unavailable: {e}")

        return self._client, self._vision_model

    async def _screen_size(self):
        """Get screen dimensions, cache result."""
        if self._screen_w:
            return self._screen_w, self._screen_h
        try:
            import pyautogui  # type: ignore

            self._screen_w, self._screen_h = pyautogui.size()
        except Exception:
            self._screen_w, self._screen_h = 1920, 1080
        return self._screen_w, self._screen_h

    async def _screenshot_b64(self, region: Optional[Dict] = None) -> Optional[str]:
        """Take a screenshot, resize for VLM efficiency, return base64 PNG."""
        try:
            import pyautogui  # type: ignore
            from PIL import Image  # type: ignore
            import io

            if region:
                img = pyautogui.screenshot(
                    region=(region["x"], region["y"], region["width"], region["height"])
                )
            else:
                img = pyautogui.screenshot()

            # Resize to max 1280px wide — keeps VLM fast but readable
            w, h = img.size
            if w > 1280:
                scale = 1280 / w
                img = img.resize((1280, int(h * scale)), Image.LANCZOS)

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode()

        except ImportError as e:
            logger.error(f"Missing dep for screenshot: {e}. Run: pip install pyautogui Pillow")
            return None
        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────
    #  Public tools
    # ─────────────────────────────────────────────────────────────────────

    async def screen_analyze(
        self,
        question: Optional[str] = None,
        region: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Screenshot → Ollama VLM → text description of the screen.

        Args:
            question: Optional specific question ("What app is open?", "Is there an error?")
            region:   Optional {x,y,width,height} to analyze a sub-region only.

        Returns:
            {success, description, model}
        """
        client, model = await self._get_client()
        if not client or not model:
            return {
                "success": False,
                "error": (
                    "No vision model available. "
                    "Run: ollama pull llava:7b"
                ),
            }

        img_b64 = await self._screenshot_b64(region)
        if not img_b64:
            return {
                "success": False,
                "error": "Screenshot failed. Install: pip install pyautogui Pillow",
            }

        prompt = question or (
            "Describe what you see on this screen in detail. "
            "List the main UI elements visible (buttons, text fields, menus, windows, dialogs, errors). "
            "For each important element, mention its approximate position: "
            "top/center/bottom and left/center/right. "
            "Be concise and specific."
        )

        try:
            response = await client.chat(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [img_b64],
                    }
                ],
            )
            description = response["message"]["content"]
            logger.info(f"👁️ Screen analyzed ({model}): {description[:100]}...")
            return {
                "success": True,
                "description": description,
                "model": model,
            }

        except Exception as e:
            logger.error(f"VLM chat error: {e}")
            return {"success": False, "error": str(e)}

    async def screen_find(self, description: str) -> Dict[str, Any]:
        """
        Find a UI element on screen by visual description.
        Returns pixel (x, y) of its center so you can click it.

        Args:
            description: What to find, e.g. "Login button", "search input field",
                         "error message", "close button"

        Returns:
            {success, x, y, description}  — (x,y) are pixel coordinates
        """
        client, model = await self._get_client()
        if not client or not model:
            return {"success": False, "error": "No vision model available"}

        img_b64 = await self._screenshot_b64()
        if not img_b64:
            return {"success": False, "error": "Screenshot failed"}

        sw, sh = await self._screen_size()

        prompt = (
            f"I need to find '{description}' on this screen.\n"
            f"Screen resolution: {sw}x{sh} pixels.\n\n"
            "Instructions:\n"
            "1. Look carefully at the screenshot.\n"
            f"2. Find '{description}'.\n"
            "3. If found, reply ONLY with this exact format:\n"
            "   FOUND: x,y\n"
            "   (where x and y are the PIXEL coordinates of the CENTER of the element)\n"
            "4. If NOT found, reply ONLY with:\n"
            "   NOT_FOUND\n"
            "Do not include any explanation, just FOUND: x,y or NOT_FOUND."
        )

        try:
            response = await client.chat(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [img_b64],
                    }
                ],
            )
            text = response["message"]["content"].strip()
            logger.info(f"👁️ screen_find('{description}'): {text[:80]}")

            # Parse pixel coords: FOUND: 640,450 or FOUND: 640, 450
            m = re.search(r"FOUND[:\s]+(\d+)[,\s]+(\d+)", text, re.IGNORECASE)
            if m:
                x, y = int(m.group(1)), int(m.group(2))
                return {"success": True, "x": x, "y": y, "description": description}

            # Some models return percentages — convert to pixels
            pm = re.search(r"(\d+(?:\.\d+)?)\s*%[,\s]+(\d+(?:\.\d+)?)\s*%", text)
            if pm:
                x = int(float(pm.group(1)) / 100 * sw)
                y = int(float(pm.group(2)) / 100 * sh)
                return {"success": True, "x": x, "y": y, "description": description}

            return {
                "success": False,
                "error": f"'{description}' not found on screen",
                "model_response": text,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def screen_click_on(self, description: str, double: bool = False) -> Dict[str, Any]:
        """
        ONE SHOT: Find a UI element visually and click it.
        Combines screen_find + mouse_click in one action.

        Args:
            description: What to click, e.g. "OK button", "username field", "X close button"
            double:      True for double-click

        Returns:
            {success, message, x, y}
        """
        result = await self.screen_find(description)
        if not result.get("success"):
            return result

        x, y = result["x"], result["y"]
        try:
            import pyautogui  # type: ignore

            clicks = 2 if double else 1
            pyautogui.click(x=x, y=y, clicks=clicks)
            action = "Double-clicked" if double else "Clicked"
            logger.info(f"🖱️ {action} on '{description}' at ({x}, {y})")
            return {
                "success": True,
                "message": f"{action} on '{description}' at ({x}, {y})",
                "x": x,
                "y": y,
            }
        except ImportError:
            return {
                "success": False,
                "error": "pyautogui not installed. Run: pip install pyautogui",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def open_app(self, name: str) -> Dict[str, Any]:
        """
        Open an application by name or command.
        Tries direct executable → common aliases → xdg-open.

        Examples: "firefox", "terminal", "vscode", "gnome-calculator", "spotify"
        """
        # Common app name → executable mappings
        # NOTE: Firefox is intentionally excluded — always use Chromium/Chrome.
        _ALIASES = {
            "browser":  ["chromium-browser", "chromium", "google-chrome"],
            "chrome":   ["chromium-browser", "chromium", "google-chrome"],
            "chromium": ["chromium-browser", "chromium", "google-chrome"],
            # Redirect any request for firefox → chromium instead
            "firefox":  ["chromium-browser", "chromium", "google-chrome"],
            "mozilla":  ["chromium-browser", "chromium", "google-chrome"],
            "opera":    ["chromium-browser", "chromium", "google-chrome"],
            "terminal": ["gnome-terminal", "xterm", "konsole", "xfce4-terminal", "alacritty"],
            "files": ["nautilus", "thunar", "dolphin", "nemo"],
            "text editor": ["gedit", "mousepad", "kate", "xed"],
            "calculator": ["gnome-calculator", "kcalc", "xcalc"],
            "vscode": ["code"],
            "vs code": ["code"],
            "spotify": ["spotify"],
            "discord": ["discord"],
            "slack": ["slack"],
            "vlc": ["vlc"],
            "gimp": ["gimp"],
            "libreoffice": ["libreoffice", "soffice"],
        }

        # Separate app name from any accidental extra words / URLs the model may pass.
        # e.g. "firefox the news" → app="firefox", extra_args=["the", "news"]
        # e.g. "firefox https://example.com" → app="firefox", extra_args=["https://.."]
        # Multi-word known aliases ("vs code", "text editor") are kept intact.
        name_lower = name.lower().strip()
        alias_hits = _ALIASES.get(name_lower, [])
        if alias_hits or name_lower in _ALIASES:
            # Known multi-word alias → use as-is
            app_name = name
            extra_args: list = []
        else:
            # Split on first space: first token = executable, rest = optional args
            tokens = name.split(None, 1)
            app_name = tokens[0]
            extra_args = tokens[1].split() if len(tokens) > 1 else []
            # Reject non-URL extra_args (user probably meant a search query, not launch args)
            # Keep args that look like URLs, file paths, flags, or bare domains (e.g. youtube.com)
            import re as _re
            _domain_re = _re.compile(r'^[\w.-]+\.[a-z]{2,}(/\S*)?$', _re.IGNORECASE)
            def _looks_like_arg(s):
                return s.startswith(("-", "/", "http", "file:")) or bool(_domain_re.match(s))
            if extra_args and not any(_looks_like_arg(a) for a in extra_args):
                logger.debug(f"open_app: ignoring non-arg text '{' '.join(extra_args)}' — open '{app_name}' only")
                extra_args = []
            # Prepend https:// to bare domains so Chrome opens them as URLs
            extra_args = [
                ("https://" + a) if _domain_re.match(a) and not a.startswith(("http", "/", "-")) else a
                for a in extra_args
            ]

        # For browser aliases, use the alias list only (don't try the raw name first
        # e.g. don't try "firefox" before chromium)
        _BROWSER_KEYS = {"browser", "chrome", "chromium", "firefox", "mozilla", "opera"}
        if app_name.lower() in _BROWSER_KEYS:
            candidates = _ALIASES.get(app_name.lower(), [app_name])
        else:
            candidates = [app_name] + _ALIASES.get(app_name.lower(), [])

        for cmd in candidates:
            try:
                argv = [cmd] + extra_args if extra_args else cmd.split()
                proc = subprocess.Popen(
                    argv,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                await asyncio.sleep(0.4)
                if proc.poll() is None:
                    return {
                        "success": True,
                        "message": f"Opened '{app_name}' (PID {proc.pid})",
                    }
            except FileNotFoundError:
                continue
            except Exception as e:
                logger.debug(f"open_app '{cmd}' failed: {e}")

        # Last resort: for URLs always prefer chromium over xdg-open (avoids Firefox)
        _is_url = name.startswith(("http://", "https://", "www.")) or (
            "." in name and name.replace(".", "").replace("-", "").replace("/", "").isalnum()
        )
        if _is_url:
            for _cmd in ("chromium-browser", "chromium", "google-chrome", "xdg-open"):
                try:
                    subprocess.Popen(
                        [_cmd, name],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                    return {"success": True, "message": f"Opened '{name}' via {_cmd}"}
                except FileNotFoundError:
                    continue
        else:
            try:
                subprocess.Popen(
                    ["xdg-open", name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                return {"success": True, "message": f"Opened '{name}' via xdg-open"}
            except Exception:
                pass

        return {
            "success": False,
            "error": f"Could not open '{name}'. Try installing it or use the full command.",
        }

    async def open_url(self, url: str) -> Dict[str, Any]:
        """
        Open a URL in Chromium (always — never Firefox or other browsers).
        Prepends https:// if no scheme is given.
        """
        if not url.startswith(("http://", "https://", "file://")):
            url = "https://" + url
        for cmd in ("chromium-browser", "chromium", "google-chrome"):
            try:
                proc = subprocess.Popen(
                    [cmd, url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                await asyncio.sleep(0.4)
                if proc.poll() is None:
                    return {"success": True, "url": url, "browser": cmd, "pid": proc.pid}
            except FileNotFoundError:
                continue
            except Exception as e:
                logger.debug(f"open_url '{cmd}' failed: {e}")
        return {"success": False, "error": "Chromium/Chrome not found. Install chromium-browser."}

    async def window_list(self) -> Dict[str, Any]:
        """
        List all open windows on the desktop.
        Uses xdotool (preferred) or wmctrl as fallback.
        """
        # Try xdotool first
        try:
            result = subprocess.run(
                ["xdotool", "search", "--name", ""],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                wids = [w for w in result.stdout.strip().split("\n") if w]
                windows = []
                for wid in wids[:25]:
                    nr = subprocess.run(
                        ["xdotool", "getwindowname", wid],
                        capture_output=True, text=True, timeout=2,
                    )
                    title = nr.stdout.strip()
                    if title:
                        windows.append({"id": wid, "title": title})
                if windows:
                    return {"success": True, "windows": windows, "count": len(windows)}
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.debug(f"xdotool window_list: {e}")

        # Fallback: wmctrl -l
        try:
            result = subprocess.run(
                ["wmctrl", "-l"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                windows = []
                for line in result.stdout.strip().split("\n"):
                    parts = line.split(None, 3)
                    if len(parts) >= 4:
                        windows.append({"id": parts[0], "title": parts[3]})
                return {"success": True, "windows": windows, "count": len(windows)}
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.debug(f"wmctrl window_list: {e}")

        return {
            "success": False,
            "error": "Install xdotool or wmctrl: sudo apt install xdotool wmctrl",
        }

    async def window_focus(self, name: str) -> Dict[str, Any]:
        """
        Bring a window to the front by its title or partial title.

        Args:
            name: Window title or partial title, e.g. "Firefox", "Terminal", "VS Code"
        """
        # Try xdotool
        try:
            result = subprocess.run(
                ["xdotool", "search", "--name", name, "windowactivate", "--sync"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return {"success": True, "message": f"Focused window: '{name}'"}
        except FileNotFoundError:
            pass
        except Exception:
            pass

        # Try wmctrl
        try:
            result = subprocess.run(
                ["wmctrl", "-a", name],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return {"success": True, "message": f"Focused window: '{name}'"}
            return {"success": False, "error": f"Window '{name}' not found"}
        except FileNotFoundError:
            return {
                "success": False,
                "error": "Install xdotool or wmctrl: sudo apt install xdotool wmctrl",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

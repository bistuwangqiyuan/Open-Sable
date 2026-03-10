"""
Clipboard skill for Open-Sable
Cross-platform clipboard operations (copy, paste, clear).
Works on Windows, macOS, and Linux.
"""

import logging
import platform
import subprocess
import shutil
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ClipboardSkill:
    """Read from and write to the system clipboard.
    
    Supports text content on all platforms.
    Tries pyperclip first; falls back to native commands (xclip/xsel, pbcopy, clip.exe).
    """

    def __init__(self, config):
        self.config = config
        self._backend: Optional[str] = None  # "pyperclip" | "native"
        self._system = platform.system()

    async def initialize(self) -> bool:
        """Detect available clipboard backend."""
        # Try pyperclip (cross-platform, handles edge cases)
        try:
            import pyperclip
            pyperclip.paste()  # quick sanity check
            self._backend = "pyperclip"
            logger.info("ClipboardSkill initialized (pyperclip backend)")
            return True
        except Exception:
            pass

        # Fallback to native commands
        if self._system == "Darwin":
            if shutil.which("pbcopy") and shutil.which("pbpaste"):
                self._backend = "native"
                logger.info("ClipboardSkill initialized (pbcopy/pbpaste backend)")
                return True
        elif self._system == "Windows":
            # clip.exe is always available on modern Windows
            self._backend = "native"
            logger.info("ClipboardSkill initialized (clip.exe/PowerShell backend)")
            return True
        else:
            # Linux,  try xclip, xsel, or wl-copy (Wayland)
            for tool in ("xclip", "xsel", "wl-copy"):
                if shutil.which(tool):
                    self._backend = "native"
                    logger.info(f"ClipboardSkill initialized ({tool} backend)")
                    return True

        logger.warning(
            "ClipboardSkill: no clipboard backend found. "
            "Install pyperclip (pip install pyperclip) "
            "or xclip/xsel (apt install xclip)."
        )
        return False

    async def copy(self, text: str) -> Dict[str, Any]:
        """Copy text to the system clipboard."""
        if not self._backend:
            return {"success": False, "error": "No clipboard backend available"}

        try:
            if self._backend == "pyperclip":
                import pyperclip
                pyperclip.copy(text)
            else:
                self._native_copy(text)

            logger.info(f"Copied {len(text)} chars to clipboard")
            return {"success": True, "length": len(text)}

        except Exception as e:
            logger.error(f"Clipboard copy failed: {e}")
            return {"success": False, "error": str(e)}

    async def paste(self) -> Dict[str, Any]:
        """Read current text from the system clipboard."""
        if not self._backend:
            return {"success": False, "error": "No clipboard backend available"}

        try:
            if self._backend == "pyperclip":
                import pyperclip
                text = pyperclip.paste()
            else:
                text = self._native_paste()

            return {"success": True, "text": text, "length": len(text)}

        except Exception as e:
            logger.error(f"Clipboard paste failed: {e}")
            return {"success": False, "error": str(e)}

    async def clear(self) -> Dict[str, Any]:
        """Clear the clipboard contents."""
        return await self.copy("")

    # ------------------------------------------------------------------
    # Native backends
    # ------------------------------------------------------------------

    def _native_copy(self, text: str) -> None:
        if self._system == "Darwin":
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        elif self._system == "Windows":
            subprocess.run(["clip.exe"], input=text.encode("utf-16le"), check=True)
        else:
            # Linux
            if shutil.which("xclip"):
                subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=text.encode("utf-8"), check=True,
                )
            elif shutil.which("xsel"):
                subprocess.run(
                    ["xsel", "--clipboard", "--input"],
                    input=text.encode("utf-8"), check=True,
                )
            elif shutil.which("wl-copy"):
                subprocess.run(["wl-copy"], input=text.encode("utf-8"), check=True)
            else:
                raise RuntimeError("No clipboard tool found (xclip, xsel, wl-copy)")

    def _native_paste(self) -> str:
        if self._system == "Darwin":
            result = subprocess.run(["pbpaste"], capture_output=True, check=True)
            return result.stdout.decode("utf-8")
        elif self._system == "Windows":
            result = subprocess.run(
                ["powershell.exe", "-Command", "Get-Clipboard"],
                capture_output=True, check=True,
            )
            return result.stdout.decode("utf-8").strip()
        else:
            if shutil.which("xclip"):
                result = subprocess.run(
                    ["xclip", "-selection", "clipboard", "-o"],
                    capture_output=True, check=True,
                )
            elif shutil.which("xsel"):
                result = subprocess.run(
                    ["xsel", "--clipboard", "--output"],
                    capture_output=True, check=True,
                )
            elif shutil.which("wl-paste"):
                result = subprocess.run(
                    ["wl-paste"], capture_output=True, check=True,
                )
            else:
                raise RuntimeError("No clipboard tool found (xclip, xsel, wl-paste)")
            return result.stdout.decode("utf-8")

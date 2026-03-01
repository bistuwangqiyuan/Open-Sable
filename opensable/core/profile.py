"""
Agent Profile Loader — multi-agent profile management.

Each profile lives in ``agents/<name>/`` and contains:
  - ``soul.md``      — the agent's immutable identity
  - ``profile.env``  — env-var overrides (merged on top of root ``.env``)
  - ``tools.json``   — allowlist / denylist of tool names
  - ``data/``        — profile-specific memory, consciousness, checkpoints

Usage::

    from opensable.core.profile import load_profile, get_active_profile

    profile = load_profile("my_agent")
    profile.apply_env()           # merges profile.env into os.environ
    config = load_config()        # now reflects profile overrides
    soul_text = profile.soul      # the profile's soul.md text
    tool_filter = profile.tools   # {"mode": "all|allowlist|denylist", "tools": [...]}
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Resolve project root relative to this file: opensable/core/profile.py → ../../
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_AGENTS_DIR = _PROJECT_ROOT / "agents"

# Global active profile (set once at startup)
_active_profile: Optional["AgentProfile"] = None


@dataclass
class ToolFilter:
    """Describes which tools a profile is allowed to use."""

    mode: str = "all"  # "all", "allowlist", "denylist"
    tools: List[str] = field(default_factory=list)

    def is_allowed(self, tool_name: str) -> bool:
        """Return True if *tool_name* passes the filter."""
        if self.mode == "all":
            return True
        elif self.mode == "allowlist":
            return tool_name in self.tools
        elif self.mode == "denylist":
            return tool_name not in self.tools
        return True  # unknown mode → permit


@dataclass
class AgentProfile:
    """Represents a loaded agent profile."""

    name: str
    profile_dir: Path
    soul: str = ""
    env_overrides: Dict[str, str] = field(default_factory=dict)
    tools: ToolFilter = field(default_factory=ToolFilter)
    data_dir: Path = field(default_factory=lambda: Path("data"))

    # Profile-specific socket path (so profiles don't collide)
    @property
    def socket_path(self) -> str:
        return f"/tmp/sable-{self.name}.sock"

    @property
    def pid_file(self) -> str:
        return str(_PROJECT_ROOT / f".sable-{self.name}.pid")

    @property
    def log_file(self) -> str:
        return str(_PROJECT_ROOT / "logs" / f"sable-{self.name}.log")

    def apply_env(self) -> None:
        """Merge profile.env overrides into ``os.environ``.

        Call this *before* ``load_config()`` so the Pydantic config picks up
        the overridden values.
        """
        if not self.env_overrides:
            return
        for key, value in self.env_overrides.items():
            os.environ[key] = value
            logger.debug(f"[Profile:{self.name}] env override: {key}={value[:20]}{'…' if len(value)>20 else ''}")
        logger.info(f"[Profile:{self.name}] applied {len(self.env_overrides)} env overrides")

        # Also override the socket path via env so gateway.py can read it
        os.environ["_SABLE_PROFILE"] = self.name
        os.environ["_SABLE_PROFILE_DIR"] = str(self.profile_dir)
        os.environ["_SABLE_DATA_DIR"] = str(self.data_dir)
        os.environ["_SABLE_SOCKET_PATH"] = self.socket_path


def _parse_env_file(path: Path) -> Dict[str, str]:
    """Parse a simple KEY=VALUE env file (ignores comments and empty lines)."""
    overrides: Dict[str, str] = {}
    if not path.exists():
        return overrides
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Strip surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        overrides[key] = value
    return overrides


def _load_tools_json(path: Path) -> ToolFilter:
    """Load tools.json and return a ToolFilter."""
    if not path.exists():
        return ToolFilter()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ToolFilter(
            mode=data.get("mode", "all"),
            tools=data.get("tools", []),
        )
    except Exception as exc:
        logger.warning(f"Failed to parse {path}: {exc}")
        return ToolFilter()


def list_profiles() -> List[str]:
    """Return names of all available profiles (excluding _template)."""
    if not _AGENTS_DIR.exists():
        return []
    return sorted(
        d.name
        for d in _AGENTS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith("_") and not d.name.startswith(".")
    )


# Default profile name — used when no --profile is specified
DEFAULT_PROFILE = "sable"


def load_profile(name: str | None = None) -> AgentProfile:
    """Load a profile by name.

    ALL agents live in ``agents/<name>/``.  If *name* is ``None`` or empty,
    the default profile (``sable``) is loaded automatically.
    """
    global _active_profile

    if not name:
        name = DEFAULT_PROFILE

    profile_dir = _AGENTS_DIR / name
    if not profile_dir.exists():
        raise FileNotFoundError(
            f"Profile '{name}' not found at {profile_dir}\n"
            f"Available profiles: {', '.join(list_profiles()) or '(none)'}\n"
            f"Create one with: cp -r agents/_template agents/{name}"
        )

    # Soul
    soul_path = profile_dir / "soul.md"
    soul_text = ""
    if soul_path.exists():
        soul_text = soul_path.read_text(encoding="utf-8").strip()
        logger.info(f"[Profile:{name}] Soul loaded ({len(soul_text)} chars)")
    else:
        logger.warning(f"[Profile:{name}] No soul.md — agent will run without a soul")

    # Env overrides
    env_overrides = _parse_env_file(profile_dir / "profile.env")

    # Tools filter
    tool_filter = _load_tools_json(profile_dir / "tools.json")

    # Data directory (profile-specific)
    data_dir = profile_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    profile = AgentProfile(
        name=name,
        profile_dir=profile_dir,
        soul=soul_text,
        env_overrides=env_overrides,
        tools=tool_filter,
        data_dir=data_dir,
    )
    _active_profile = profile
    logger.info(
        f"[Profile:{name}] loaded — "
        f"soul={bool(soul_text)}, "
        f"env_overrides={len(env_overrides)}, "
        f"tools_mode={tool_filter.mode}"
    )
    return profile


def get_active_profile() -> Optional[AgentProfile]:
    """Return the currently active profile (set by ``load_profile``)."""
    return _active_profile


def get_default_profile_name() -> str:
    """Return the default profile name."""
    return DEFAULT_PROFILE

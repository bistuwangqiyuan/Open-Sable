"""Per-profile path helpers.

Every module that stores data under ``~/.opensable/`` should use
:func:`opensable_home` instead of hard-coding
``Path.home() / ".opensable"``.  When a profile is active the function
returns ``~/.opensable/<profile>/``, keeping each agent's data isolated.
"""

import os
from pathlib import Path


def opensable_home() -> Path:
    """Return the profile-specific opensable home directory.

    * With ``_SABLE_PROFILE`` set → ``~/.opensable/<profile>/``
    * Without                     → ``~/.opensable/``
    """
    base = Path.home() / ".opensable"
    profile = os.environ.get("_SABLE_PROFILE", "")
    if profile:
        return base / profile
    return base

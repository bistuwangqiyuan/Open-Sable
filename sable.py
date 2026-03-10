#!/usr/bin/env python3
"""
DEPRECATED,  This file is kept for backward compatibility only.

Use instead:
  python main.py          # Start the agent (all interfaces)
  python -m opensable     # Same as above
  opensable chat "hello"  # CLI one-shot
"""

import sys
import warnings

warnings.warn(
    "sable.py is deprecated. Use 'python main.py' or 'python -m opensable' instead.",
    DeprecationWarning,
    stacklevel=1,
)

if __name__ == "__main__":
    from main import main
    import asyncio
    asyncio.run(main())

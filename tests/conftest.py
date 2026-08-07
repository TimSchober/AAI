"""
Shared pytest setup.

The application modules import from the repository root (``config``, ``backend``,
``core_functions``), so the root has to be on ``sys.path`` no matter where pytest
was started from.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

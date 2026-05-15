"""Make the pathd package importable from these tests."""
from __future__ import annotations

import sys
from pathlib import Path

_INFRA = Path(__file__).resolve().parents[2]
_CORE = _INFRA.parent / ".laia-core"
for p in (_INFRA, _CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

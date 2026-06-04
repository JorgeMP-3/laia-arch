"""Contract tests for tools/env_probe.py (ported verbatim from upstream Hermes).

The probe inspects the local Python toolchain (PEP 668, pip/python mismatches,
uv) and returns ONE compact line for the system prompt — or an empty string
when nothing is anomalous. The contract LAIA relies on (see the injection in
run_agent.py::_build_system_prompt): it returns str, it NEVER raises, and the
result is cached between calls. Deterministic: no network, no live services
(only short subprocess probes of local binaries, which is the tool's purpose).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

LAIA_CORE = Path(__file__).resolve().parents[1] / ".laia-core"
if not (LAIA_CORE / "tools" / "env_probe.py").exists():
    pytest.skip(
        ".laia-core/tools/env_probe.py not present in this checkout",
        allow_module_level=True,
    )
sys.path.insert(0, str(LAIA_CORE))

from tools.env_probe import (  # noqa: E402
    _reset_cache_for_tests,
    get_environment_probe_line,
)


def test_returns_str_and_never_raises() -> None:
    _reset_cache_for_tests()
    line = get_environment_probe_line()
    assert isinstance(line, str)


def test_result_is_cached_between_calls() -> None:
    _reset_cache_for_tests()
    first = get_environment_probe_line()
    second = get_environment_probe_line()
    assert second == first


def test_force_refresh_recomputes_without_raising() -> None:
    _reset_cache_for_tests()
    get_environment_probe_line()
    line = get_environment_probe_line(force_refresh=True)
    assert isinstance(line, str)

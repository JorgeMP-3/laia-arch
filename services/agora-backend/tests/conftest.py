import os
import shutil
import tempfile

# Must run BEFORE any app imports
_test_dir = tempfile.mkdtemp(prefix="agora_test_")
os.environ["AGORA_ENV"] = "dev"
os.environ["AGORA_DATA_DIR"] = _test_dir
os.environ["AGORA_DEV_DATA_DIR"] = _test_dir
# Tests don't need the background tick loop and the asyncio task can leak
# across test files. The scheduler exposes its public helpers without
# needing the loop, so unit tests call them directly.
os.environ["AGORA_DISABLE_SCHEDULER"] = "1"

import atexit
atexit.register(lambda: shutil.rmtree(_test_dir, ignore_errors=True))


# The in-memory login rate limiter trips after 10 attempts/minute per IP.
# Tests share a single TestClient → all login attempts come from "testserver",
# which means a suite with many login-using tests blows the budget and later
# tests get HTTP 429 spuriously. Wipe the store between tests so each starts
# fresh.
import pytest


@pytest.fixture(autouse=True)
def _reset_login_rate_limit():
    try:
        from app import security  # noqa: WPS433 — late import (env vars first)
        security._rate_store.clear()
    except Exception:
        pass
    yield

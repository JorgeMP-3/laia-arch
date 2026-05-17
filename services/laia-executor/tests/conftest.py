"""Pytest fixtures for laia-executor tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from laia_executor.api import build_app
from laia_executor.config import ExecutorConfig


@pytest.fixture
def test_config(tmp_path) -> ExecutorConfig:
    return ExecutorConfig(
        bind_host="127.0.0.1",
        bind_port=9091,
        token="test-token-abc",
        slug="test-slug",
        workspace_root=str(tmp_path / "workspace"),
        plugins_root=str(tmp_path / "plugins"),
    )


@pytest.fixture
def client(test_config) -> TestClient:
    app = build_app(test_config)
    return TestClient(app)


@pytest.fixture
def auth_headers(test_config) -> dict[str, str]:
    return {"Authorization": f"Bearer {test_config.token}"}

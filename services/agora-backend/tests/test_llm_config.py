"""Tests for the LLM provider catalog (parity with LAIA ARCH)."""

from __future__ import annotations

from app.llm_config import (
    determine_api_mode,
    get_provider,
    list_providers,
    mask_api_key,
)


def test_catalog_includes_major_providers():
    ids = {p.id for p in list_providers()}
    # Parity with ARCH — these are the canonical IDs exposed by
    # `.laia-core/laia_cli/auth.py:PROVIDER_REGISTRY`. ARCH does not list
    # a bare "openai" id; OpenAI chat completions go through OpenRouter
    # (aggregator) or a custom base_url. The only "openai-*" id is
    # `openai-codex` (Responses API). Match exactly what ARCH offers.
    for required in ("anthropic", "openai-codex", "deepseek", "openrouter",
                     "xai", "bedrock", "google-gemini-cli", "lmstudio"):
        assert required in ids, f"missing provider in catalog: {required}"


def test_catalog_has_at_least_15_providers():
    # Plan target: 30+. Fallback catalog ships >25; live catalog from .laia-core
    # has 30+. Even in stripped-down test envs we expect at least 15.
    assert len(list_providers()) >= 15


def test_get_provider_round_trip():
    p = get_provider("anthropic")
    assert p is not None
    assert p.transport == "anthropic_messages"
    assert get_provider("does-not-exist") is None


def test_openai_codex_has_default_models():
    """openai-codex is the org-wide default — its model list must be populated
    so /api/llm/providers/{id}/models returns something useful for the UI."""
    p = get_provider("openai-codex")
    assert p is not None
    # gpt-5.5 is the backend's hardcoded default (main.py POST /api/users).
    assert "gpt-5.5" in p.default_models, \
        "openai-codex must list gpt-5.5 since main.py uses it as default"
    # Sanity: at least 3 models so the UI has something to choose from.
    assert len(p.default_models) >= 3


def test_determine_api_mode_by_url():
    assert determine_api_mode("openrouter", "https://api.anthropic.com") == "anthropic_messages"
    assert determine_api_mode("custom", "https://api.x.ai/v1") == "codex_responses"
    assert determine_api_mode("custom", "https://bedrock-runtime.us-east-1.amazonaws.com") == "bedrock_converse"


def test_determine_api_mode_by_provider_transport():
    assert determine_api_mode("anthropic", "") == "anthropic_messages"
    assert determine_api_mode("deepseek", "") == "chat_completions"
    assert determine_api_mode("bedrock", "") == "bedrock_converse"


def test_mask_api_key():
    assert mask_api_key(None) is None
    assert mask_api_key("") is None
    assert mask_api_key("abcd") == "***"
    assert mask_api_key("sk-1234567890abcd") == "sk-1...abcd"

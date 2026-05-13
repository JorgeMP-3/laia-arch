"""Tests for the Nous-LAIA-3/4 non-agentic warning detector.

Prior to this check, the warning fired on any model whose name contained
``"laia"`` anywhere (case-insensitive). That false-positived on unrelated
local Modelfiles such as ``laia-brain:qwen3-14b-ctx16k`` — a tool-capable
Qwen3 wrapper that happens to live under the "laia" tag namespace.

``is_nous_laia_non_agentic`` should only match the actual Nous Research
LAIA-3 / LAIA-4 chat family.
"""

from __future__ import annotations

import pytest

from laia_cli.model_switch import (
    _LAIA_MODEL_WARNING,
    _check_laia_model_warning,
    is_nous_laia_non_agentic,
)


@pytest.mark.parametrize(
    "model_name",
    [
        "NousResearch/LAIA-3-Llama-3.1-70B",
        "NousResearch/LAIA-3-Llama-3.1-405B",
        "laia-3",
        "LAIA-3",
        "laia-4",
        "laia-4-405b",
        "laia_4_70b",
        "openrouter/laia3:70b",
        "openrouter/nousresearch/laia-4-405b",
        "NousResearch/LAIA3",
        "laia-3.1",
    ],
)
def test_matches_real_nous_laia_chat_models(model_name: str) -> None:
    assert is_nous_laia_non_agentic(model_name), (
        f"expected {model_name!r} to be flagged as Nous LAIA 3/4"
    )
    assert _check_laia_model_warning(model_name) == _LAIA_MODEL_WARNING


@pytest.mark.parametrize(
    "model_name",
    [
        # Kyle's local Modelfile — qwen3:14b under a custom tag
        "laia-brain:qwen3-14b-ctx16k",
        "laia-brain:qwen3-14b-ctx32k",
        "laia-honcho:qwen3-8b-ctx8k",
        # Plain unrelated models
        "qwen3:14b",
        "qwen3-coder:30b",
        "qwen2.5:14b",
        "claude-opus-4-6",
        "anthropic/claude-sonnet-4.5",
        "gpt-5",
        "openai/gpt-4o",
        "google/gemini-2.5-flash",
        "deepseek-chat",
        # Non-chat LAIA models we don't warn about
        "laia-llm-2",
        "laia2-pro",
        "nous-laia-2-mistral",
        # Edge cases
        "",
        "laia",  # bare "laia" isn't the 3/4 family
        "laia-brain",
        "brain-laia-3-impostor",  # "3" not preceded by /: boundary
    ],
)
def test_does_not_match_unrelated_models(model_name: str) -> None:
    assert not is_nous_laia_non_agentic(model_name), (
        f"expected {model_name!r} NOT to be flagged as Nous LAIA 3/4"
    )
    assert _check_laia_model_warning(model_name) == ""


def test_none_like_inputs_are_safe() -> None:
    assert is_nous_laia_non_agentic("") is False
    # Defensive: the helper shouldn't crash on None-ish falsy input either.
    assert _check_laia_model_warning("") == ""

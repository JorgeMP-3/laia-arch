"""LLM provider configuration with parity to LAIA ARCH.

This module exposes the same set of providers and models that LAIA ARCH
supports (defined in `.laia-core/laia_cli/providers.py`). Users of AGORA
should be able to plug in any provider that works in ARCH, with no curated
subset.

Two operating modes:

1. **Full parity mode**: if `.laia-core/laia_cli/providers.py` is importable
   (PYTHONPATH includes `.laia-core`), we use `LAIA_OVERLAYS` and
   `determine_api_mode()` directly from ARCH. This is the production mode
   inside the laia-agora container.

2. **Fallback mode**: a hardcoded subset of well-known providers used for
   tests and dev environments where `.laia-core` isn't on the path. The
   list is intentionally generous (matches the catalog in the plan).

`[PENDIENTE]`: encryption-at-rest for `llm_api_key` is stored plain right now;
the redesign plan calls for Fernet with a master key in `AGORA_FERNET_KEY`.
Adding it is a one-pass change in this module + storage.py once we pick the
key rotation policy.
"""

from __future__ import annotations

import logging
from typing import Iterable

from .models import LLMProviderInfo


logger = logging.getLogger(__name__)


# Fallback catalog — used when .laia-core is not importable.
# Matches the 30+ providers documented in the redesign plan and in
# .laia-core/laia_cli/providers.py:LAIA_OVERLAYS.
_FALLBACK_PROVIDERS: list[LLMProviderInfo] = [
    LLMProviderInfo(id="anthropic", label="Anthropic",
                    transport="anthropic_messages", base_url="https://api.anthropic.com",
                    default_models=["claude-opus-4-7", "claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5"]),
    LLMProviderInfo(id="openai", label="OpenAI",
                    transport="openai_chat", base_url="https://api.openai.com/v1",
                    default_models=["gpt-5.4", "gpt-5.4-mini", "gpt-4o", "gpt-4o-mini"]),
    LLMProviderInfo(id="openai-codex", label="OpenAI Codex",
                    transport="codex_responses",
                    base_url="https://chatgpt.com/backend-api/codex",
                    auth_type="oauth_external",
                    # Mirrors ARCH's .laia-core/laia_cli/codex_models.py:DEFAULT_CODEX_MODELS.
                    # Models NOT accepted via ChatGPT-account OAuth (api-only) are
                    # intentionally excluded so the UI doesn't offer broken choices.
                    default_models=[
                        "gpt-5.5", "gpt-5.4-mini", "gpt-5.4",
                        "gpt-5.3-codex", "gpt-5.2-codex",
                        "gpt-5.1-codex-max", "gpt-5.1-codex-mini",
                    ]),
    LLMProviderInfo(id="deepseek", label="DeepSeek",
                    transport="openai_chat", base_url="https://api.deepseek.com",
                    default_models=["deepseek-chat", "deepseek-reasoner"]),
    LLMProviderInfo(id="openrouter", label="OpenRouter",
                    transport="openai_chat", base_url="https://openrouter.ai/api/v1",
                    is_aggregator=True, default_models=[]),
    LLMProviderInfo(id="xai", label="xAI Grok",
                    transport="codex_responses", base_url="https://api.x.ai/v1",
                    default_models=["grok-4.20", "grok-4-fast", "grok-code-fast"]),
    LLMProviderInfo(id="bedrock", label="AWS Bedrock",
                    transport="bedrock_converse", auth_type="aws_sdk",
                    default_models=["us.anthropic.claude-sonnet-4-6", "us.anthropic.claude-opus-4-6"]),
    LLMProviderInfo(id="google-gemini-cli", label="Google Gemini (Code Assist OAuth)",
                    transport="openai_chat", auth_type="oauth_external",
                    base_url="cloudcode-pa://google"),
    LLMProviderInfo(id="nous", label="Nous Research",
                    transport="openai_chat", auth_type="oauth_device_code",
                    base_url="https://inference-api.nousresearch.com/v1"),
    LLMProviderInfo(id="zai", label="Z.AI (GLM)",
                    transport="openai_chat", default_models=[]),
    LLMProviderInfo(id="kimi-for-coding", label="Kimi (Moonshot) for Coding",
                    transport="openai_chat"),
    LLMProviderInfo(id="stepfun", label="StepFun",
                    transport="openai_chat", base_url="https://api.stepfun.ai/step_plan/v1"),
    LLMProviderInfo(id="minimax", label="MiniMax (Anthropic-compatible)",
                    transport="anthropic_messages"),
    LLMProviderInfo(id="minimax-cn", label="MiniMax CN",
                    transport="anthropic_messages"),
    LLMProviderInfo(id="alibaba", label="Alibaba DashScope (Qwen)",
                    transport="openai_chat", base_url="https://dashscope.aliyuncs.com"),
    LLMProviderInfo(id="alibaba-coding-plan", label="Alibaba Coding Plan",
                    transport="openai_chat"),
    LLMProviderInfo(id="nvidia", label="NVIDIA NIM",
                    transport="openai_chat", base_url="https://integrate.api.nvidia.com/v1"),
    LLMProviderInfo(id="xiaomi", label="Xiaomi MiMo",
                    transport="openai_chat"),
    LLMProviderInfo(id="arcee", label="Arcee AI",
                    transport="openai_chat", base_url="https://api.arcee.ai/api/v1"),
    LLMProviderInfo(id="tencent-tokenhub", label="Tencent TokenHub",
                    transport="openai_chat"),
    LLMProviderInfo(id="huggingface", label="HuggingFace Inference",
                    transport="openai_chat", base_url="https://huggingface.co/api/inference"),
    LLMProviderInfo(id="vercel", label="Vercel AI Gateway",
                    transport="openai_chat", is_aggregator=True),
    LLMProviderInfo(id="opencode", label="OpenCode Zen",
                    transport="openai_chat", is_aggregator=True),
    LLMProviderInfo(id="opencode-go", label="OpenCode Go",
                    transport="openai_chat", is_aggregator=True),
    LLMProviderInfo(id="kilo", label="KiloCode",
                    transport="openai_chat", is_aggregator=True),
    LLMProviderInfo(id="ollama-cloud", label="Ollama Cloud",
                    transport="openai_chat"),
    LLMProviderInfo(id="lmstudio", label="LM Studio (local)",
                    transport="openai_chat", base_url="http://127.0.0.1:1234/v1",
                    base_url_env_var="LM_BASE_URL"),
    LLMProviderInfo(id="azure-foundry", label="Azure AI Foundry",
                    transport="openai_chat"),
    LLMProviderInfo(id="github-copilot", label="GitHub Copilot",
                    transport="openai_chat", auth_type="oauth_external"),
    LLMProviderInfo(id="copilot-acp", label="Copilot ACP (process)",
                    transport="codex_responses", auth_type="external_process"),
    LLMProviderInfo(id="qwen-oauth", label="Qwen (OAuth)",
                    transport="openai_chat", auth_type="oauth_external",
                    base_url="https://portal.qwen.ai/v1"),
    LLMProviderInfo(id="custom", label="Custom (user-defined endpoint)",
                    transport="openai_chat", base_url_env_var="LAIA_CUSTOM_BASE_URL"),
]


def _load_from_laia_core() -> list[LLMProviderInfo] | None:
    """Try to import the live overlay map from .laia-core; return None on failure."""
    try:
        # The laia-core providers module lives in laia_cli; PYTHONPATH must include
        # .laia-core/ for this import to resolve.
        from laia_cli.providers import LAIA_OVERLAYS  # type: ignore[import-not-found]
    except Exception as exc:
        logger.debug("falling back to local provider catalog: %s", exc)
        return None

    # Provider id → curated default model list. ARCH knows openai-codex's models
    # in laia_cli/codex_models.py; we import it lazily so a checkout without that
    # module still loads (just with an empty model list for openai-codex).
    extra_models: dict[str, list[str]] = {}
    try:
        from laia_cli.codex_models import DEFAULT_CODEX_MODELS  # type: ignore[import-not-found]
        extra_models["openai-codex"] = list(DEFAULT_CODEX_MODELS)
    except Exception:
        pass
    # Fall back to the hardcoded catalog for default_models we know about
    # but ARCH doesn't enumerate (anthropic, openai, deepseek, …).
    for fp in _FALLBACK_PROVIDERS:
        if fp.default_models and fp.id not in extra_models:
            extra_models[fp.id] = list(fp.default_models)

    out: list[LLMProviderInfo] = []
    for provider_id, overlay in LAIA_OVERLAYS.items():
        out.append(LLMProviderInfo(
            id=provider_id,
            label=provider_id.replace("-", " ").title(),
            transport=getattr(overlay, "transport", "openai_chat"),
            base_url=getattr(overlay, "base_url_override", "") or None,
            base_url_env_var=getattr(overlay, "base_url_env_var", "") or None,
            is_aggregator=getattr(overlay, "is_aggregator", False),
            auth_type=getattr(overlay, "auth_type", "api_key"),
            default_models=extra_models.get(provider_id, []),
        ))
    return out


_CACHED: list[LLMProviderInfo] | None = None


def list_providers() -> list[LLMProviderInfo]:
    """Return the full list of supported LLM providers (parity with ARCH)."""
    global _CACHED
    if _CACHED is not None:
        return _CACHED
    live = _load_from_laia_core()
    _CACHED = live if live else _FALLBACK_PROVIDERS
    return _CACHED


def get_provider(provider_id: str) -> LLMProviderInfo | None:
    """Look up a single provider by id."""
    for p in list_providers():
        if p.id == provider_id:
            return p
    return None


def determine_api_mode(provider_id: str, base_url: str = "") -> str:
    """Return the api_mode (chat_completions | anthropic_messages | codex_responses | bedrock_converse)
    for a given provider, optionally adjusted by the base URL."""
    # Auto-detect by URL hostname first (matches ARCH behavior).
    if base_url:
        host = base_url.lower()
        if "anthropic.com" in host:
            return "anthropic_messages"
        if "chatgpt.com/backend-api/codex" in host or "api.x.ai" in host:
            return "codex_responses"
        if "bedrock-runtime" in host and "amazonaws.com" in host:
            return "bedrock_converse"
    # Fall back to provider transport.
    p = get_provider(provider_id)
    if p is None:
        return "chat_completions"
    return p.transport if p.transport in {
        "chat_completions", "anthropic_messages", "codex_responses", "bedrock_converse"
    } else "chat_completions"


def mask_api_key(key: str | None) -> str | None:
    """Return a display-safe masked version of an API key. E.g. 'sk-abc...wxyz'."""
    if not key:
        return None
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


__all__ = [
    "list_providers",
    "get_provider",
    "determine_api_mode",
    "mask_api_key",
]

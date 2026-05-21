"""LLM pricing table (USD per 1M tokens).

Values are best-effort and may drift; operators can override the table by
writing ``${AGORA_DATA_DIR}/pricing.yaml`` with the same shape — that file
is reloaded lazily.

Each entry is ``(input_per_1m, output_per_1m)``. Unknown (provider, model)
returns ``None`` from ``cost_for`` — the call is still tracked, but with
``cost_usd = NULL`` (the budget enforcement then can't apply a $ cap to
that call; an admin can configure a token-only cap via
``budget_tokens_daily`` as a fallback).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


# Static baseline. Keys lowercase. Update as providers change pricing.
PRICING: dict[tuple[str, str], tuple[float, float]] = {
    # Anthropic
    ("anthropic", "claude-opus-4-7"):    (15.00, 75.00),
    ("anthropic", "claude-opus-4-6"):    (15.00, 75.00),
    ("anthropic", "claude-sonnet-4-6"):  (3.00, 15.00),
    ("anthropic", "claude-haiku-4-5"):   (0.80,  4.00),
    # OpenAI (chat completions / responses)
    ("openai", "gpt-4o"):                (2.50, 10.00),
    ("openai", "gpt-4o-mini"):           (0.15,  0.60),
    ("openai", "gpt-5.5"):               (10.00, 30.00),
    ("openai", "gpt-5.4"):               (8.00, 24.00),
    ("openai", "gpt-5.4-mini"):          (1.00,  4.00),
    # OpenAI Codex (ChatGPT OAuth, "free" for the user — we estimate at the
    # nominal GPT-5 prices for budget accounting purposes).
    ("openai-codex", "gpt-5.5"):         (10.00, 30.00),
    ("openai-codex", "gpt-5.4-mini"):    (1.00,  4.00),
    ("openai-codex", "gpt-5.3-codex"):   (5.00, 15.00),
    # DeepSeek
    ("deepseek", "deepseek-chat"):       (0.27,  1.10),
    ("deepseek", "deepseek-reasoner"):   (0.55,  2.19),
    # xAI Grok
    ("xai", "grok-4.20"):                (5.00, 15.00),
    ("xai", "grok-4-fast"):              (0.30,  1.00),
    # Generic / aggregator entries — operator should override per-model.
    ("openrouter", ""):                  (1.00,  3.00),
    ("vercel", ""):                      (1.00,  3.00),
}


_OVERRIDES_CACHE: dict[tuple[str, str], tuple[float, float]] | None = None
_OVERRIDES_MTIME: float = 0.0


def _maybe_load_overrides() -> dict[tuple[str, str], tuple[float, float]]:
    """Load pricing overrides from YAML if present; cache by mtime."""
    global _OVERRIDES_CACHE, _OVERRIDES_MTIME
    try:
        from .config import settings
        path = settings.data_dir / "pricing.yaml"
    except Exception:
        return {}
    if not path.exists():
        _OVERRIDES_CACHE = {}
        _OVERRIDES_MTIME = 0.0
        return {}
    mtime = path.stat().st_mtime
    if _OVERRIDES_CACHE is not None and mtime == _OVERRIDES_MTIME:
        return _OVERRIDES_CACHE
    try:
        import yaml  # type: ignore[import-untyped]
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        logger.warning("pricing: failed to load %s: %s", path, exc)
        _OVERRIDES_CACHE = {}
        _OVERRIDES_MTIME = mtime
        return {}
    out: dict[tuple[str, str], tuple[float, float]] = {}
    # Expected YAML shape:
    #   anthropic:
    #     claude-opus-4-7: [15.0, 75.0]
    if isinstance(data, dict):
        for prov, models in data.items():
            if not isinstance(models, dict):
                continue
            for model, pair in models.items():
                if isinstance(pair, (list, tuple)) and len(pair) == 2:
                    out[(str(prov).lower(), str(model))] = (float(pair[0]), float(pair[1]))
    _OVERRIDES_CACHE = out
    _OVERRIDES_MTIME = mtime
    return out


def cost_for(provider: str, model: str,
             tokens_in: int, tokens_out: int) -> float | None:
    """Return USD cost for a call; ``None`` if pricing not configured."""
    if not provider:
        return None
    prov = provider.lower()
    overrides = _maybe_load_overrides()
    key_specific = (prov, model or "")
    key_wildcard = (prov, "")
    pi_po = overrides.get(key_specific) or PRICING.get(key_specific) \
            or overrides.get(key_wildcard) or PRICING.get(key_wildcard)
    if pi_po is None:
        return None
    pi, po = pi_po
    return (max(0, tokens_in) * pi + max(0, tokens_out) * po) / 1_000_000.0


__all__ = ["PRICING", "cost_for"]

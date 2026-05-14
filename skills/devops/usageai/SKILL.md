---
name: usageai
description: "Report Codex and Claude Code usage/status for Hermes. Shows Codex usage summaries, host Claude auth/status, Docker Maribel Claude auth/status, and OpenClaw gateway usage when available. Triggered with /usageai."
triggers:
  - "/usageai"
  - "usageai"
  - "usage ai"
  - "codex usage"
  - "claude usage"
---

# /usageai

Use the local command `~/.local/bin/usageai` to report current AI usage/status.

## What it shows
- Codex usage summary for Codex/OpenAI
- Claude Code auth status for **Jorge** on the host
- Claude Code auth status for **Maribel** in Docker
- OpenClaw gateway usage if the gateway RPC is available
- A clear note when detailed usage is not exposed by the available tools

## How to use

```bash
~/.local/bin/usageai
```

## Telegram / gateway note
- A Hermes skill trigger like `/usageai` does **not** automatically create a Telegram slash command.
- If Telegram says `Unknown command /usageai`, the command must be registered in the OpenClaw/gateway/plugin command layer.
- Treat the skill trigger and the Telegram slash command as related but separate surfaces.

## Important interpretation rules
- **Auth status** confirms which account is active.
- **Usage summaries** are status/consumption signals, not billing totals and not a claim about money owed.
- For subscription tools like Codex and Claude Code, prefer language like *usage*, *consumption*, or *status* instead of *billing* or *charges* unless the provider explicitly exposes billing.
- **Provider-level usage** may be shared across accounts depending on how the logs are recorded; auth status is still shown separately for Jorge and Maribel.
- **Detailed usage / remaining context** may not be available if the OpenClaw gateway is down or if the provider does not expose it.
- Treat Maribel as a shared account and monitor usage conservatively.

## Output expectations
Keep the output concise and practical:
- account email / plan
- last 30 days usage summary
- latest day usage if available
- gateway usage details when available
- short note if detailed usage is unavailable
- match the spirit of a CLI `/status` screen: quick, factual, and not framed as billing

---
name: sclaude-persistent-sessions
description: Fix for sclaude sessions not persisting across container restarts
---

# sclaude — persistent sessions fix

## Problem
`sclaude` launches Claude Code inside `claude-secondary` Docker container with `-w` mapped directory. Sessions were not persisted — each new run showed "no previous sessions."

## Root Cause
- Claude Code sessions stored in `~/.claude/` **inside container** at `/home/claude/.claude/`
- `/home/claude/` is a bind mount to an ephemeral/unpopulated host path
- Sessions stored in container-local storage are lost on container restart

## Solution
Add to `/home/familiamp/bin/sclaude` before the `docker exec` call:

```bash
# Ensure persistent session storage via ~/.hermes/.claude
docker exec claude-secondary mkdir -p /home/claude/.hermes/.claude
docker exec claude-secondary ln -sfn /home/claude/.hermes/.claude /home/claude/.claude
```

## Script location
`/home/familiamp/bin/sclaude`

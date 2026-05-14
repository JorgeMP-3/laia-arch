---
name: claude-code-accounts
description: "How to choose and use Claude Code accounts in this environment: Jorge on host, Maribel in Docker. Includes conservation rules and workflow."
triggers:
  - "Claude Code"
  - "claude code"
  - "Maribel"
  - "Jorge"
  - "cuenta de claude"
  - "usar claude"
  - "agente claude"
---

# Claude Code Accounts

This skill defines how to use Claude Code safely and consistently in this environment.

## Goal

Pick the right Claude Code account, avoid mixing identities, and conserve usage — especially on the shared Maribel account.

---

## Accounts

### Jorge
- **Where:** host
- **Role:** personal/host-side tasks
- **Use for:** local analysis, host-level work, general tasks outside Docker
- **Budget:** use with care, but not as restricted as Maribel

### Maribel
- **Where:** Docker
- **Role:** containerized/isolation tasks
- **Use for:** Docker projects, isolated repo analysis, parallel work
- **Important:** shared account with another person
- **Budget:** be very conservative with usage; avoid spending prompts on long, low-value, or repetitive tasks

---

## Core rules

1. **Do not mix accounts.**
2. **Host → Jorge. Docker → Maribel.**
3. **If the task is ambiguous, identify the execution environment first.**
4. **Prefer analysis-first prompts before any changes.**
5. **Use Maribel sparingly.** Reserve it for high-value work.

---

## When to use each account

### Use Jorge when
- the work happens on the host
- the task is small or local
- the user wants a quick inspection outside Docker
- the task does not need container isolation

### Use Maribel when
- the work is inside Docker
- the project lives in a containerized workspace
- the task benefits from isolation or parallelization
- you need to inspect a Docker project without touching the host

---

## Maribel usage policy

Because Maribel is shared:

- avoid burning prompts on broad exploration
- avoid looping on low-value iterations
- prefer one well-scoped prompt over many small ones
- stop once the key context is found
- do not use it for work that could be answered from existing memory or a quick local check

Think of Maribel as a **precious shared resource**.

---

## Recommended workflow

### Step 1: decide environment
Ask:
- Is this host or Docker?
- Which account matches that environment?

### Step 2: define a narrow goal
Good goals:
- identify key files
- find risks before changing anything
- summarize architecture
- extract only context worth keeping

Bad goals:
- "look around"
- "analyze everything"
- "fix it all"

### Step 2b: map host paths cleanly into Docker
When Claude Code runs inside the `claude-secondary` container and needs Hermes context:
- mount the host's `/home/familiamp/.hermes` directly into `/home/claude/.hermes`
- do **not** rely on a broad `/home/familiamp -> /home/claude/host_home` mount for Hermes access
- after changing mounts, recreate the container before testing the path

Example:
```yaml
volumes:
  - /home/familiamp/.hermes:/home/claude/.hermes:rw
```

Then use:
```bash
docker exec -it claude-secondary bash -lc 'cd /home/claude/.hermes && claude'
```

### Step 3: request analysis first
Ask Claude Code to:
- read structure
- identify important files
- flag risky areas
- summarize useful context
- avoid making changes unless explicitly requested

### Step 4: decide whether to spend more
If the first result is enough, stop.
If not, refine once. Avoid repeated broad probes, especially on Maribel.

---

## Practical host-directory mapping for `sclaude`

When launching Claude Code inside `claude-secondary`, the container should be run in the same directory as the host shell.

### Bind mounts needed
- `/home/familiamp/.hermes` → `/home/claude/.hermes`
- `/home/familiamp` → `/home/claude/host_home`

### Working-directory mapping
Use `docker exec -w` and translate the host path to the container path:
- `cd /home/familiamp/.hermes/...` on host becomes `/home/claude/.hermes/...`
- other paths under `/home/familiamp/...` become `/home/claude/host_home/...`

### Useful wrapper behavior
A robust `sclaude` wrapper should:
- detect the host cwd with `pwd -P`
- map it into the container
- fail clearly if the cwd is outside `/home/familiamp`
- use `docker exec -it -w "$CONTAINER_PWD" claude-secondary claude "$@"`

### Pitfall discovered
`/home/claude/host_home/.hermes` may exist as a path name but still be empty if the host home mount is not present or not the intended source. Mount the actual `.hermes` directory directly when that is the target.

---

## Prompt template

> Analyze this project and tell me which information is worth keeping for Hermes. Focus on:
> - key files
> - architecture
> - risks before touching anything
> - what to read first
> Do not modify files.

For changes:

> Review the project, propose the minimum safe change, and tell me what backup or validation is needed before touching anything.

---

## Safety checklist

Before using Claude Code:

- confirm the correct account
- confirm the correct environment
- confirm the project path
- confirm whether the task is worth spending a prompt on
- prefer read-only analysis first
- back up before any sensitive change

---

## Red lines

- Do not use Maribel casually
- Do not spend prompts on low-value broad exploration
- Do not mix Jorge and Maribel contexts
- Do not start with changes if analysis is enough
- Do not touch production without a backup and a clear plan

---

## Output preference

When Claude Code returns results, keep only:
- what matters for Hermes
- what is risky
- what to do next
- what to avoid

Discard noise.

---

## Related reference

- `references/usage-examples.md` — practical examples and decision table for Jorge vs Maribel
- Related stable context: `/home/familiamp/memory/servidor-docker.md`
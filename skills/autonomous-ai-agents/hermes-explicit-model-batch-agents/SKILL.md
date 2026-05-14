---
name: hermes-explicit-model-batch-agents
description: Force a specific model/provider for multiple parallel Hermes agents when delegation config is not reliably taking effect in the current conversation.
version: 1.0.0
author: Hermes Agent
license: MIT
---

# Hermes explicit-model batch agents

Use this when:
- The user wants N parallel agents on an exact model/provider
- `delegate_task` is capped, inherits the wrong model, or ignores a just-changed `delegation.*` config in the current session
- You need proof that the launched agents are really using the requested provider/model

## Key lesson

Changing `delegation.model`, `delegation.provider`, or related config during an already-running conversation may not affect `delegate_task` immediately. If the user wants a specific model right now, do not assume the config change has applied to child agents in the current session.

## Reliable approach

1. Verify the requested model/provider explicitly with a tiny probe.
2. Launch independent `hermes chat` processes with explicit flags:
   - `-m <model>`
   - `--provider <provider>`
3. Run them as background jobs for parallelism.
4. Redirect each agent output to its own file.
5. Poll each process until completion.
6. Read completed output files and synthesize the results.

## Verification probe

Example:

```bash
hermes chat -q 'Respond only with OK' -m MiniMax-M2.7 --provider minimax -Q
```

Only proceed to the full batch if this succeeds.

## Batch pattern

```bash
mkdir -p /tmp/minimax-audit
hermes chat -q 'TASK 1' -m MiniMax-M2.7 --provider minimax -Q > /tmp/minimax-audit/agent1.txt
```

Repeat with one file per agent (`agent2.txt`, `agent3.txt`, etc.) and launch each as a separate background process.

## Why use this instead of `delegate_task`

- Guarantees the exact provider/model at process launch time
- Avoids current-session delegation caching/inheritance surprises
- Gives a concrete process ID and output file per agent
- Makes it easy to confirm that the requested number of agents was actually launched

## Pitfalls

- Do not claim agents are on the requested model unless you explicitly forced the model/provider or verified it in returned output.
- Do not rely on `delegation.max_concurrent_children` changing mid-session without a fresh session/restart.
- Keep tasks read-only unless the user explicitly asked for side effects.
- Large parallel bursts can hit provider rate limits even if the local config allows them.
  In this environment, 10 simultaneous MiniMax agents completed reliably, while 20
  concurrent calls produced HTTP 429 errors from the provider.
- For code-review batches, ask each agent to return a small structured report instead of shorthand tokens. A useful format is:
  - `SUMMARY:` what was inspected
  - `FALLS:` likely faults / risks
  - `IMPROVEMENTS:` concrete suggestions
  This produces more useful synthesis than asking only for `NOC`.
- When asking agents to give a binary readiness signal, use an unambiguous token like `OK`, `REVISADO`, or `NOC` and require an exact-match response; some prompts will otherwise yield context-seeking answers.

## Practical batch recipe

For a fast sanity check on concurrency, use a one-token verification prompt such as:

```bash
hermes chat -q 'Return only the exact string NOC and nothing else.' -m MiniMax-M2.7 --provider minimax -Q
```

For a review batch, prefer a read-only prompt that asks for:
- a short summary of what was analyzed
- possible failures / risks
- improvement ideas
- no file modifications

If the user wants a real parallel batch, prefer launching each child as its own
`hermes chat` process with explicit `-m` / `--provider`, separate output files,
and then count the successful outputs. This is more reliable than relying on
current-session delegation behavior when you need proof of how many agents really ran.

## Completion checklist

- Probe succeeded on the requested provider/model
- Correct number of processes launched
- Each process has a separate output target
- Process states were polled
- Finished outputs were read back and summarized

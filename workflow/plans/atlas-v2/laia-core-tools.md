# Atlas v2 — .laia-core/tools/

## Real code hardcodes (should migrate)
*No real code hardcodes found.* All matches were in comments/docstrings.

| File | Line | Value | Type | In atlas.yaml? | Should atlas.get()? |

## Comment/docstring hardcodes (leave as-is)

| File | Line | Value | Note |
|---|---|---|---|
| `tools/file_tools.py` | 462 | `/opt/laia/agent` | Comment describing sandbox blocking paths (not code) |
| `tools/browser_tool.py` | 2735 | `/opt/laia/.playwright` | Comment describing Docker env-var default (Playwright browser path docs) |
| `tools/environments/file_sync.py` | 49 | `/home/user` | Comment giving example user home paths (e.g. `/home/daytona, /home/user`) |

## /home/user note
`/home/user` in `file_sync.py:49` is a **docstring example** of bind-mounted user homes inside containers. These are user homes, NOT system paths — **OK to leave**.

## New refs needed
No new Atlas v2 references are required for `.laia-core/tools/`. All path/directory references found are either:
- In comments describing sandboxing behavior
- In docstrings describing Playwright browser lookup order
- In docstrings giving container home examples

No runtime code in `.laia-core/tools/` currently reads `/opt/laia`, `/srv/laia`, `laia-agora`, `agent-jorge`, or `/home/user` directly.

---

*Generated: investigation only — no code modified.*
*Patterns searched: `/opt/laia`, `/srv/laia`, `laia-agora`, `agent-jorge`, `/home/user`*
* atlas.yaml checked: `opt_laia`, `srv_laia`, `agora_container`, `jorge_container`, `executor_api`, `agora_api` are all defined.

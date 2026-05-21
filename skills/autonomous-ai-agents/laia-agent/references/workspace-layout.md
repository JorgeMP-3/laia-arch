# Workspace layout in this environment

Use these paths when asked where LAIA workspaces live.

- Workspace root: `/home/laia-hermes/LAIA/workspaces/`
- Active workspaces can be discovered with `workspace_list_workspaces`
- Typical per-workspace DB: `/home/laia-hermes/LAIA/workspaces/<workspace>/workspace.db`
- Typical per-workspace code root: `/home/laia-hermes/LAIA/workspaces/<workspace>/code/`
- AGORA backend is separate: `/home/laia-hermes/LAIA/services/agora-backend/data/workspace/workspace.db`

Notes:
- The active workspace is not inferred from filesystem naming alone; confirm it with `workspace_list_workspaces`.
- The loaded/editable set in a session may be smaller than the full directory listing under `/workspaces/`.
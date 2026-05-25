# laia-executor — Microservicio en Container de Usuario

## Metadata

- ID: `202`
- Slug: `agora-executor`
- Kind: `doc`
- Status: `active`
- Filename: `agora-executor.md`
- Parent: `agora`
- Source kind: `manual`
- Created at: `2026-05-18T11:03:34.631276+00:00`
- Updated at: `2026-05-19T11:30:41.075116+00:00`
- Aliases: `agora-executor`

## Summary

FastAPI (~300 LOC) en cada container. POST /exec, 22 tools, root libre, sin .laia-core/, sin sandbox. Auth Bearer token. Bind mounts persistentes.

## Body

# laia-executor

## Proposito: servidor HTTP minimal en cada container LXD de usuario. Recibe tool calls, las ejecuta como root, devuelve resultado.

## Endpoints
GET /health -> {"status":"ok"}
GET /profile (Bearer) -> metadata: slug, version, uptime, tools[]
POST /exec (Bearer) -> {"tool":"write_file","args":{},"request_id":"..."} -> {"ok":true,"result":"..."}
GET /workspace/files?path= (Bearer) -> lista directorio

## 22 Tools
Filesystem: read_file, write_file, apply_patch, list_dir, grep, delete_file
Shell: bash (sin blacklist, usuario es root)
Workspace privado: private_workspace_search, private_workspace_add_node, private_workspace_get_node, private_workspace_list_nodes, private_workspace_delete_node
Runtime seguro: python_exec, process_start/stop/status/list/logs, cron_add/remove/list
Utilidad: ping

## Seguridad: Bearer token (/etc/laia/executor-token 0600), body size limit 10MB, container LXD unprivileged, sin acceso a .laia-core/
## Systemd: laia-executor.service, puerto 9091, user laia-agent

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agora` (AGORA — Plataforma de usuarios) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# laia-executor — Microservicio en Container de Usuario

# laia-executor

## Proposito: servidor HTTP minimal en cada container LXD de usuario. Recibe tool calls, las ejecuta como root, devuelve resultado.

## Endpoints
GET /health -> {"status":"ok"}
GET /profile (Bearer) -> metadata: slug, version, uptime, tools[]
POST /exec (Bearer) -> {"tool":"write_file","args":{},"request_id":"..."} -> {"ok":true,"result":"..."}
GET /workspace/files?path= (Bearer) -> lista directorio

## 22 Tools
Filesystem: read_file, write_file, apply_patch, list_dir, grep, delete_file
Shell: bash (sin blacklist, usuario es root)
Workspace privado: private_workspace_search, private_workspace_add_node, private_workspace_get_node, private_workspace_list_nodes, private_workspace_delete_node
Runtime seguro: python_exec, process_start/stop/status/list/logs, cron_add/remove/list
Utilidad: ping

## Seguridad: Bearer token (/etc/laia/executor-token 0600), body size limit 10MB, container LXD unprivileged, sin acceso a .laia-core/
## Systemd: laia-executor.service, puerto 9091, user laia-agent

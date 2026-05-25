# AGORA Control Center — API Admin

## Metadata

- ID: `205`
- Slug: `agora-control-center`
- Kind: `doc`
- Status: `active`
- Filename: `agora-control-center.md`
- Parent: `agora`
- Source kind: `manual`
- Created at: `2026-05-18T11:03:34.672947+00:00`
- Updated at: `2026-05-18T11:03:34.672947+00:00`
- Aliases: `agora-control-center`

## Summary

/api/admin/*: status del sistema, gestion de usuarios/containers, logs, auditoria, self-heal fixes (4), test runner async. Jobs. 197 tests.

## Body

# AGORA Control Center

## Endpoints
GET /api/admin/status — dashboard completo
GET /api/admin/logs/{name} — journalctl
GET /api/admin/audit/tools — auditoria tool calls (cursor-pagination)
GET /api/admin/image/freshness — drift imagen vs git
POST /api/admin/users/provision — crear usuario (async job)
DELETE /api/admin/users/{slug} — eliminar usuario
POST /api/admin/containers/{name}/restart — reiniciar container
POST /api/admin/containers/{name}/snapshot — snapshot
POST /api/admin/containers/{name}/restore — restaurar

## Self-Heal Fixes: auth-json-push, pip-reinstall-laia-core, pm2-stop-respawner, chmod-laia-dir

## Tests: POST /api/admin/tests/run (async job), GET /api/admin/tests/status

## Jobs async: tabla admin_jobs, ThreadPoolExecutor, GET /api/admin/jobs

## Seguridad: require_roles("agora_admin"), rate limit 30 mutaciones/60s

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agora` (AGORA — Plataforma de usuarios) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# AGORA Control Center — API Admin

# AGORA Control Center

## Endpoints
GET /api/admin/status — dashboard completo
GET /api/admin/logs/{name} — journalctl
GET /api/admin/audit/tools — auditoria tool calls (cursor-pagination)
GET /api/admin/image/freshness — drift imagen vs git
POST /api/admin/users/provision — crear usuario (async job)
DELETE /api/admin/users/{slug} — eliminar usuario
POST /api/admin/containers/{name}/restart — reiniciar container
POST /api/admin/containers/{name}/snapshot — snapshot
POST /api/admin/containers/{name}/restore — restaurar

## Self-Heal Fixes: auth-json-push, pip-reinstall-laia-core, pm2-stop-respawner, chmod-laia-dir

## Tests: POST /api/admin/tests/run (async job), GET /api/admin/tests/status

## Jobs async: tabla admin_jobs, ThreadPoolExecutor, GET /api/admin/jobs

## Seguridad: require_roles("agora_admin"), rate limit 30 mutaciones/60s

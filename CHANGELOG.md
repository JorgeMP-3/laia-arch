# CHANGELOG

All notable changes to the LAIA ecosystem.

## [2.0.0] — 2026-05-13

### Security
- **CRITICAL**: All API keys, tokens, and secrets moved from `~/LAIA/` to `~/.laia/` (chmod 600)
- **CRITICAL**: `config.yaml` hardcoded keys (15 instances) replaced with `${ENV_VAR}` references
- **CRITICAL**: 18 session files sanitized, 21 backup files removed (contained plaintext API keys)
- Old Telegram bot token revoked and removed from migration backups
- `state.db` and `response_store.db` permissions changed from 644 to 600

### Architecture
- `.laia-core/` created as independent fork from Hermes 0.11.0 (1,602 commits ahead of upstream)
- 1,244 files: all `hermes`/`HERMES`/`Hermes` references renamed to `laia`/`LAIA`
- `~/.hermes/` → `~/.laia/` as new runtime home directory
- `HERMES_HOME` → `LAIA_HOME` environment variable
- `workspace-ui` → `laia-ui-server` integrated into core
- Removed: Tauri desktop UI, Homebrew packaging, Nix, website, Docker, optional-skills

### Cleanup
- 21 legacy/duplicate entries removed from root (70 → 17 directories)
- Workspaces renamed to consistent hyphen convention (`laia_arch` → `laia-arch`, `servidor_jmp` → `servidor-jmp`)
- `services/laia-agent-runtime` → `services/laia-runtime`
- 11 stale `.bak` files removed from workspaces
- `.gitignore` rewritten (organized, no typos)

### Backend (AGORA)
- Auth: JWT with pbkdf2_hmac password hashing (stdlib, no external dependencies)
- SQLite storage replacing flat JSON files (WAL mode, foreign keys)
- CRUD user management with roles (`agora_admin`, `employee`, `agent`)
- Coordinator (LAIA AGORA): monitor loop, task assignment, alert generation
- WebSocket: real-time push for coordinator alerts
- Observability: structured JSON logging, request metrics, health check
- FleetMonitor: background health daemon with state change detection
- Rate limiting on login endpoint
- 30+ REST endpoints, 69 tests

### Infra (laiactl)
- Fleet operations: `provision-agent`, `fleet-status`, `upgrade-all`, `--all` flags
- 8 CLI tools: `laia status`, `laia health`, `laia service`, `laia logs`, `laia backup`, `laia deploy`, `laia watch`
- New systemd units: `laia-gateway.service`, `laia-ui-server.service`

### Runtime (laia-runtime)
- Plugin system: `PluginRegistry` with dynamic loading from `/opt/laia/plugins/`
- New task types: `delete_file`, `list_dir`, `workspace_delete_node`
- Health HTTP endpoint on `:9090/health`

### Frontend
- ARCH UI: Fleet dashboard (`/fleet`) with agent table, start/stop/restart actions
- ARCH UI: AgentDetail (`/fleet/:slug`) with Info/Logs/Snapshots tabs
- AGORA UI: MiAgente (editable profile), MisTareas, Marketplace, Actividad
- AGORA UI: Role-based navigation (admin vs employee views)
- Auto-refresh JWT tokens on 401
- NeuralBackground unified to teal brand palette

### Documentation
- `docs/ARCHITECTURE.md` — official architecture (was `ARCHITECTURA_OFICIAL.md`)
- `docs/SERVER_CONTEXT.md` — server provisioning guide
- `services/agora-backend/README.md` — complete API reference
- `infra/docs/AGORA_DEPLOYMENT.md` — deployment runbook
- `PLAN_MEJORA_BACKEND.md` — 7-phase backend improvement plan (complete)
- `PLAN_MEJORA_BACKEND.md` — backend improvement plan (7 phases, all complete)

---

## [1.0.0] — 2026-05-11

### Initial
- `.laia-arch/` — Hermes Agent 0.11.0 fork with LAIA branding
- `services/agora-backend/` — initial FastAPI skeleton
- `infra/laiactl` — LXD orchestration CLI
- `laia-ui/` — pnpm monorepo with `arch-app` and `agora-app`
- `workspaces/` — DB-first knowledge workspaces
- LXD agent runtime with profile management

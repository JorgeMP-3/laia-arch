# LAIA CLI Tools Reference

## Terminal Toolkit (`laia`)

All tools live in `infra/bin/`. Add to PATH: `export PATH="$HOME/LAIA/infra/bin:$PATH"`

### System Management

| Command | Description |
|---|---|
| `laia status` | Full system overview: services, LXD agents, ports, disk, RAM |
| `laia health` | 20+ health checks (services, APIs, disk, LXD) |
| `laia service <action> <svc\|all>` | start/stop/restart/status/logs of systemd services |
| `laia logs <component> [-f] [-n N]` | Tail logs: `nginx`, `postgres`, `hermes`, `workspace`, `agora`, `agent <name>` |
| `laia watch [interval]` | Live resource monitor (CPU, RAM, disk, connections) |

### Deployment

| Command | Description |
|---|---|
| `laia deploy agora-frontend` | Build and deploy AGORA frontend to `/srv/laia/agora/frontend/dist` |
| `laia deploy agora-backend` | Restart AGORA backend service |
| `laia deploy agora-all` | Frontend + backend together |
| `laia deploy arch-frontend` | Build and deploy ARCH admin UI |
| `laia deploy runtime` | Upgrade runtime on all LXD agents |
| `laia deploy status` | Show deployment state |

### Backups

| Command | Description |
|---|---|
| `laia backup db` | PostgreSQL dump (arete) |
| `laia backup workspaces` | Copy all workspace.db files |
| `laia backup agents` | LXD snapshots of all agents |
| `laia backup agora` | AGORA database backup |
| `laia backup all` | Everything above |
| `laia backup list` | List existing backups |
| `laia backup clean N` | Delete backups older than N days |

### Path Registry

| Command | Description |
|---|---|
| `laia-path resolve <alias>` | Resolve a single path alias |
| `laia-path list` | List all 32 path aliases |
| `laia-path status` | Daemon status and uptime |
| `laia-path doctor` | Validate all registered paths exist |
| `laia-path reload` | Force reload from config.yaml |
| `laia-path pending-restarts` | Show queued service restarts |
| `laia-path apply-restarts [--yes]` | Apply pending restarts with confirmation |

---

## Fleet Management (`laiactl`)

CLI for managing LXD agent containers. Lives at `infra/laiactl`.

### Fleet Operations

| Command | Description |
|---|---|
| `laiactl fleet-status` | Table of all agents with LXD state, IP, service, runtime |
| `laiactl list-agents` | List LXD containers (laia-* prefix) |
| `laiactl provision-agent <slug>` | Create + install runtime + init workspace + profile + verify (all in one) |
| `laiactl upgrade-all [--rolling N]` | Upgrade runtime on all agents |
| `laiactl restart-agent --all` | Restart all agent services |

### Single Agent

| Command | Description |
|---|---|
| `laiactl create-agent <slug>` | Create LXD container |
| `laiactl install-agent-runtime <slug>` | Push runtime code into container |
| `laiactl init-agent-workspace <slug>` | Initialize personal workspace.db |
| `laiactl init-agent-profile <slug>` | Create default profile files |
| `laiactl verify-agent <slug>` | Run 12-point health verification |
| `laiactl start-agent / stop-agent / restart-agent <slug>` | Service control |
| `laiactl agent-status <slug>` | Runtime status and recent logs |
| `laiactl snapshot-agent <slug> <name>` | Create LXD snapshot |
| `laiactl restore-agent <slug> <name> --yes` | Restore from snapshot |
| `laiactl delete-agent <slug> --yes --force` | Delete container |

### Agent Profile

| Command | Description |
|---|---|
| `laiactl agent-profile <slug>` | Read full profile as JSON |
| `laiactl set-agent-persona <slug> <file>` | Replace persona.md |
| `laiactl set-agent-instructions <slug> <file>` | Replace instructions.md |
| `laiactl enable-agent-skill <slug> <id>` | Enable a skill |
| `laiactl disable-agent-skill <slug> <id>` | Disable a skill |

### Setup

| Command | Description |
|---|---|
| `laiactl doctor` | Check host requirements (lxc, LXD, pool, network) |
| `laiactl setup-lxd` | Create LXD defaults and apply LAIA profile |
| `laiactl build-agent-image [--force]` | Build `laia-agent` base image from Ubuntu 22.04 |
| `laiactl verify` | Verify LXD setup + all agents |

---

## Makefile Targets

Run from `~/LAIA/`:

| Target | Description |
|---|---|
| `make install` | Install all dependencies (AGORA venv + UI pnpm) |
| `make test` | Run backend tests + TypeScript check |
| `make deploy-agora` | Build + deploy AGORA (frontend + backend) |
| `make deploy-arch` | Build + deploy ARCH admin UI |
| `make backup` | Full backup (workspaces, config, DB) |
| `make clean` | Clean build artifacts and caches |
| `make status` | Show system status |
| `make health` | Run health check |
| `make logs` | Recent logs from all services |
| `make watch` | Live resource monitor |

---

## Agent CLI (`laia-arch`)

The LAIA agent interactive CLI:

| Command | Description |
|---|---|
| `laia-arch` | Interactive chat |
| `laia-arch -z "prompt"` | One-shot query |
| `laia-arch --resume <session>` | Resume a session |
| `laia-arch gateway run` | Start messaging gateway |
| `laia-arch setup` | Setup wizard |
| `laia-arch status` | Show all components status |
| `laia-arch doctor` | Check configuration |
| `laia-arch config` | View/edit configuration |
| `laia-arch skills` | Manage skills |
| `laia-arch sessions` | Manage session history |
| `laia-arch logs` | View log files |
| `laia-arch update` | Update to latest version |

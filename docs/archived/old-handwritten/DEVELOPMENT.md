# Development Guide

> 📅 Actualizado: 2026-05-19

## Setup

```bash
# Clone
git clone <repo-url> ~/LAIA
cd ~/LAIA

# LAIA-AGORA Backend
cd services/agora-backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8088 --reload

# LAIA Core
cd ../../.laia-core
python3 -m venv venv
venv/bin/pip install -e .
venv/bin/pip install uvicorn fastapi python-dotenv watchdog

# Frontend UI
cd ../laia-ui
pnpm install
pnpm dev  # starts dev servers
```

## Project Structure

```
~/LAIA/
├── .laia-core/          AI Engine (agent loop, tools, gateway, memory)
├── laia-ui/             Frontend monorepo (pnpm workspaces)
│   ├── packages/arch-app/    LAIA-ARCH admin dashboard
│   ├── packages/agora-app/   AGORA user platform
│   ├── packages/ui/          Shared design system
│   └── packages/shared/      Shared API types
├── services/
│   ├── agora-backend/        AGORA platform API (FastAPI, 69 tests)
│   └── laia-runtime/         Per-container agent runtime
├── infra/
│   ├── laiactl               LXD fleet management CLI
│   ├── bin/                  Terminal tools (laia, laia-path, etc.)
│   ├── pathd/                Atlas — Path Registry daemon
│   ├── orchestrator/         Python LXD orchestration
│   ├── nginx/                Reverse proxy configs
│   ├── lxd/                  LXD profiles and scripts
│   └── systemd/              Service unit files
├── workspace_store/          Shared WorkspaceStore library
├── plugins/                  Host-level plugins (source)
├── workspaces/               Workspace data (DB-first)
├── docs/                     Documentation
├── skills/                   Agent skill marketplace
└── scripts/                  Utility scripts

~/.laia/                      Runtime data (LAIA_HOME)
├── config.yaml               Agent + project configuration
├── .env                      Secrets (API keys, tokens)
├── .env.paths                Path registry snapshot (auto-generated)
├── atlas/                    Symlink farm (32 symlinks)
├── plugins/                  Installed plugins (workspace-context)
├── workspace_store/          WorkspaceStore vendored for plugin
├── state.db                  Session database
└── sessions/                 Session trajectories

/srv/laia/                    Production data (outside repo)
├── agora/
├── state/
└── backups/
```

## Running Tests

```bash
# All tests
make test

# Backend only
cd services/agora-backend
.venv/bin/python -m pytest tests/ -v

# Path resolver
cd .laia-core
venv/bin/python -m pytest tests/test_laia_paths.py -v

# Path daemon
cd ..
.laia-core/venv/bin/python -m pytest infra/pathd/tests/ -v

# Frontend type check
cd laia-ui
npx tsc --noEmit -p packages/arch-app/tsconfig.json
npx tsc --noEmit -p packages/agora-app/tsconfig.json
```

## Development Workflow

1. Create a feature branch
2. Write code and tests
3. Run `make test` to verify
4. Commit with conventional commit message
5. Push and create PR

## Code Standards

### Python
- Follow PEP 8 with type hints (`from __future__ import annotations`)
- Use `pydantic` for data validation
- Use `sqlite3` from stdlib for storage (no ORM)
- Paths: use `laia_paths.get_path()` or `laia_constants.get_laia_home()` — never hardcode

### TypeScript/React
- Functional components with hooks
- CSS custom properties from design system (`var(--d-*)`)
- Shared components from `@laia/ui`
- HTTP via `lib/api.ts` (arch-app) or `lib/agoraApi.ts` (agora-app)

### Shell
- `#!/usr/bin/env bash` with `set -euo pipefail`
- Source `~/.laia/.env.paths` for paths — never hardcode
- Test with `bash -n` before committing

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `LAIA_HOME` | `~/.laia` | Runtime data directory |
| `LAIA_ROOT` | `~/LAIA` | Project root |
| `AGORA_ENV` | `dev` | Backend environment (`dev` / `prod`) |
| `AGORA_DATA_DIR` | `/srv/laia/agora` | Production data |
| `AGORA_JWT_SECRET` | random | JWT signing secret |

## Commit Messages

Follow conventional commits:
- `feat:` new feature
- `fix:` bug fix
- `refactor:` code restructuring
- `security:` security-related changes
- `docs:` documentation
- `chore:` maintenance
- `cleanup:` removing legacy code

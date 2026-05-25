# Contributing to LAIA

## Getting Started

```bash
git clone <repo-url> ~/LAIA
cd ~/LAIA

# Install AGORA backend
cd services/agora-backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Install UI
cd ../../laia-ui
pnpm install

# Run tests
make test
```

## Project Structure

```
~/LAIA/
├── .laia-core/       LAIA Core AI engine (forked from Hermes 0.11.0)
├── laia-ui/          Frontend monorepo (pnpm workspaces)
├── services/         Backend services
│   ├── agora-backend/   AGORA platform API (FastAPI)
│   └── laia-runtime/    Per-container agent runtime
├── infra/            Infrastructure as Code
│   ├── laiactl          CLI entry point
│   ├── bin/             Terminal tools
│   ├── orchestrator/    Python LXD orchestration
│   ├── nginx/           Reverse proxy configs
│   ├── lxd/             LXD profiles and scripts
│   └── systemd/         Service unit files
├── workspace-store/  Shared WorkspaceStore library
├── plugins/          Host-level plugins
├── workspaces/       Workspace data (DB-first)
├── docs/             Documentation
├── scripts/          Utility scripts
├── skills/           Agent skill marketplace
└── Makefile          Standard targets
```

Runtime data lives in `~/.laia/` (not in the repo).

## Development Workflow

1. Create a feature branch from `main`
2. Write code and tests
3. Run `make test` to verify everything passes
4. Commit with descriptive message
5. Submit a pull request

## Code Standards

### Python
- Follow PEP 8
- Use type hints (`from __future__ import annotations`)
- Use `pydantic` models for data validation
- Use `sqlite3` from stdlib for storage (no ORM)
- Run `make test` before pushing

### TypeScript/React
- Use functional components with hooks
- Use CSS custom properties from the design system (`--d-*` tokens)
- Use shared components from `@laia/ui`
- Run `npx tsc --noEmit` before pushing

### Shell
- Use `#!/usr/bin/env bash`
- Use `set -euo pipefail`
- Follow Google Shell Style Guide

## Testing

```bash
# Backend tests
cd services/agora-backend
.venv/bin/python -m pytest tests/ -v

# Frontend type check
cd laia-ui
npx tsc --noEmit -p packages/arch-app/tsconfig.json
npx tsc --noEmit -p packages/agora-app/tsconfig.json
```

## Commit Messages

Follow conventional commits:
- `feat:` new feature
- `fix:` bug fix
- `refactor:` code restructuring
- `security:` security-related changes
- `docs:` documentation
- `chore:` maintenance

## Questions?

Refer to `docs/ARCHITECTURE.md` for the system architecture.

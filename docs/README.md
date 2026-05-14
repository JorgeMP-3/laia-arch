# LAIA Documentation

## Current State — v2.0 (2026-05-14)

LAIA is an AI agent ecosystem with a parent agent operating in two permission contexts (ARCH admin, AGORA coordinator) and personal agent children per user in LXD containers.

## Quick Links

| Document | Description |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture and directory structure |
| [API.md](API.md) | AGORA Backend API reference (30+ endpoints) |
| [CLI.md](CLI.md) | Terminal tools: `laia`, `laiactl`, `laia-path` |
| [PATH_REGISTRY.md](PATH_REGISTRY.md) | Atlas — DNS for files (Path Resolver) |
| [DEPLOY.md](DEPLOY.md) | Deployment guide for AGORA and ARCH |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Development setup and workflow |
| [SERVIDOR_CONTEXTO.md](SERVIDOR_CONTEXTO.md) | Server provisioning context |

## Tech Stack

- **OS:** Ubuntu 24.04 LTS
- **Backend:** Python 3.12+ / FastAPI / SQLite
- **Frontend:** React 19 / Vite / TypeScript / pnpm
- **Containers:** LXD (system containers) + Docker (WordPress only)
- **Auth:** JWT HS256 / PBKDF2-HMAC-SHA256 (stdlib, zero dependencies)
- **Network:** Cloudflare Tunnel → nginx → services

## Running Services (systemd)

| Service | Port | Status |
|---|---|---|
| `laia-gateway` | — | AI agent gateway (Telegram, Discord, CLI) |
| `agora-backend` | 8088 | AGORA platform API + SPA frontend |
| `workspace-ui` | 8077 | ARCH admin dashboard |

## Tests

- **Backend:** 69 tests in `services/agora-backend/tests/`
- **Path Resolver:** 62 tests in `infra/pathd/tests/` + `.laia-core/tests/test_laia_paths.py`
- **Run:** `make test`

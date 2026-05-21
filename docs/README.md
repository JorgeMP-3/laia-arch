# LAIA Documentation

> &#x1F4C5; v2.5 — 2026-05-19

LAIA is an AI agent ecosystem: LAIA-ARCH (personal admin assistant in host) + AGORA (centralized brain serving N personal agents in LXD containers per user).

## Quick Links

| Document | Description |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture and directory structure |
| [API.md](API.md) | LAIA-AGORA Backend API reference (80+ endpoints) |
| [CLI.md](CLI.md) | Terminal tools: `laia`, `laia-marketplace`, `laia-init` |
| [PATH_REGISTRY.md](PATH_REGISTRY.md) | Atlas — Path Resolver (32 aliases) |
| [DEPLOY.md](DEPLOY.md) | Deployment guide for LAIA-AGORA and LAIA-ARCH |
| [OPERATIONS.md](OPERATIONS.md) | Operations: preflight, smoke, state files, recovery |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Development setup and workflow |
| [AGORA_AGENTS.md](AGORA_AGENTS.md) | Agora Agents — architecture, provisioning, APIs |
| [MARKETPLACE.md](MARKETPLACE.md) | AGORA Marketplace v0.1 — plugins, skills, MCP |
| [INTEGRATIONS.md](INTEGRATIONS.md) | Open-source integrations research (50+ repos) |
| [SERVIDOR_CONTEXTO.md](SERVIDOR_CONTEXTO.md) | Server context and hardware |

## Tech Stack

- **OS:** Ubuntu 24.04 LTS
- **Backend:** Python 3.12+ / FastAPI / SQLite (agora.db, 15+ tables)
- **Frontend:** React 19 / Vite / TypeScript / pnpm
- **Containers:** LXD (system containers) — `laia-agora` (brain), `agent-{slug}` (users)
- **Auth:** JWT HS256 / PBKDF2-HMAC-SHA256 (stdlib)
- **Network:** LXD bridge (lxdbr0) + Cloudflare Tunnel → nginx → services

## Architecture at a Glance

```
HOST (LAIA-ARCH — intacto)
├── .laia-core/              ← motor LAIA para admin
├── LXD hypervisor
│   ├── laia-agora (brain)   ← .laia-core/ + LAIA-AGORA Backend + AgentPool
│   │   Port :8000 (proxy host :8088)
│   └── agent-jorge-dev       ← executor :9091 (root libre, sin .laia-core)
│   └── agent-maria            ← executor :9091
│   └── ...
└── laia-jorge (STOPPED)     ← sprint 2 legacy, preservado
```

## Running Services

| Service | Port | Location | Description |
|---|---|---|---|
| `laia-gateway` | — | Host | AI agent gateway (Telegram, Discord, CLI) |
| `laia-agora` (LAIA-AGORA Backend) | `:8000` | LXD container | Brain: AgentPool, chat, marketplace, admin API |
| `laia-agora proxy` | `:8088` | Host → container | LXD proxy device |
| `laia-executor` | `:9091` | LXD container (user) | Tool executor, root libre |
| `laia-agent daemon` | `:9090` | LXD container (user) | Task processor (heartbeat 5s) |
| `laia-pathd` | socket | Host | Atlas Path Registry daemon |
| `workspace-ui` | `:8077` | Host | LAIA-ARCH admin dashboard |

## Tests

| Suite | Count | Location |
|---|---|---|
| **Backend** | 342 | `services/agora-backend/tests/` |
| **Executor** | 53 | `services/laia-executor/tests/` |
| **Forwarder** | 25 | `.laia-core/plugins/agora-executor-forwarder/tests/` |
| **Shell** | 11 | `tests/` (preflight, smoke, marketplace_cli, etc.) |
| **TOTAL** | **431** | |

## Key Endpoints

| Group | Prefix | Examples |
|-------|--------|----------|
| Auth | `/api/login`, `/api/refresh`, `/api/me` | JWT HS256, PBKDF2 |
| Users | `/api/users` (admin) | CRUD + LLM config + budget |
| Agents | `/api/agents` (admin), `/api/agents/me/chat`, `/api/agent/profile` | Fleet + chat SSE |
| Control Center | `/api/admin/*` | Status, containers, logs, audit, fixes, tests, jobs |
| Marketplace | `/api/me/plugins/*`, `/api/plugins/catalog`, `/api/admin/marketplace/*` | Publish, approve, install |
| Agent Area | `/api/me/agent-area` | Soul, instructions, preferences |
| LAIA Coordinator | `/api/laia/inbox-count`, `/api/laia/chat` | Admin chat with LAIA |
| Secrets | `/api/agents/{slug}/secrets` | Bootstrap token → LLM key |
| Webhooks | `/api/wh/{slug}` | External triggers per user |

## Git

- **Repo:** `feat/agora-redesign-centralized-brain`
- **Commits:** 15 (36f7263 → e2b8ea5)
- **Tags:** 10 (sprint2-snapshot, redesign-v1-functional, redesign-v2.0-deployed, control-center-v0.2-polished)
- **URLs:** AGORA API `http://localhost:8088` | Workspace UI `http://100.73.36.92:8077`

> &#x1F4C5; v2.5 — 2026-05-19

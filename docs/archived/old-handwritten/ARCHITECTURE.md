# LAIA — System Architecture

> &#x1F4C5; v2.5 — 2026-05-19

## Architecture Overview

```
HOST (LAIA-ARCH — admin assistant, intacto)
│
├── ARCH (.laia-core/ en host) — asistente personal del admin
│
├── LXD hypervisor
│   │
│   ├── 🧠 laia-agora (container) — CEREBRO CENTRALIZADO
│   │   ├── .laia-core/ + LAIA-AGORA Backend (:8000)
│   │   ├── AgentPool — 1 AIAgent por sesion, TTL 60min, LRU
│   │   ├── Tool Forwarder Plugin — filesystem/bash → executor
│   │   ├── Control Center — /api/admin/*
│   │   ├── Marketplace — plugins, skills, MCP
│   │   ├── LAIA Coordinator — chat admin + inbox
│   │   ├── Scheduler — cron jobs + decay de aprendizajes
│   │   ├── Webhooks — HMAC triggers por usuario
│   │   ├── Usage Ledger — tracking tokens + coste USD
│   │   └── agora.db — 15+ tablas (users, agents, agent_areas,
│   │       plugin_registry, skill_registry, usage_ledger...)
│   │
│   └── 🖥️ agent-{slug} (containers) — EXECUTORS POR USUARIO
│       ├── laia-executor (:9091) — POST /exec, 22 tools
│       ├── laia-agent daemon (:9090) — task processor
│       ├── root libre — sin sandbox
│       └── bind mounts persistentes (/srv/laia/users/{slug}/)
│
└── laia-jorge (STOPPED) — sprint 2 legacy, preservado
```

## Key Rules

1. **ARCH** — host admin assistant. Not modified. Has `.laia-core/` for admin use.
2. **AGORA** — centralized brain in `laia-agora` container. Inherits LAIA technology from ARCH.
3. **Executors** — user containers (`agent-{slug}`). No `.laia-core/`, no LLM, no sandbox. User is root.
4. **Data persistence** — via bind mounts (`/srv/laia/users/{slug}/ → /home/user`).
5. **All paths** — resolved via Atlas Path Registry (`config.yaml → paths:`).
6. **All secrets** — in `~/.laia/` with `chmod 600`, never in repo.
7. **Runtime data** — in `~/.laia/`. Code in `~/LAIA/`. Production data in `/srv/laia/`.

## Directory Structure

```
~/LAIA/                              # Project root
├── .laia-core/                       # AI Engine
│   ├── run_agent.py                  # Core agent loop (~13k LOC)
│   ├── agent/                        # Agent internals (memory, caching, providers)
│   ├── gateway/                      # Multi-platform gateway (20+ adapters)
│   ├── tools/                        # 71 built-in tools
│   ├── plugins/                      # Core plugins
│   │   ├── agora-executor-forwarder/ # Tool call forwarder plugin
│   │   ├── memory/                   # Memory providers (workspace-context)
│   │   └── ...
│   ├── skills/                       # Built-in agent skills
│   ├── laia_cli/                     # CLI commands, profiles, skin engine
│   ├── laia_paths.py                 # Atlas Path Registry module
│   ├── laia_constants.py             # Path resolution (LAIA_HOME)
│   └── venv/                         # Python virtual environment
│
├── services/                         # Backend services
│   ├── agora-backend/                # AGORA platform API (FastAPI)
│   │   ├── app/
│   │   │   ├── main.py               # 80+ endpoints + SPA fallback + WS
│   │   │   ├── admin.py              # Control Center API (1,518 LOC)
│   │   │   ├── agent_pool.py         # AIAgent pool (TTL 60min, LRU, marketplace)
│   │   │   ├── chat_engine.py        # SSE chat + forwarder integration
│   │   │   ├── marketplace.py        # Marketplace HTTP layer (22 endpoints)
│   │   │   ├── marketplace_storage.py# Plugin/skill CRUD + per-user materialize
│   │   │   ├── agent_identity.py     # Container naming helpers (agent-* vs laia-*)
│   │   │   ├── laia_chat.py          # LAIA Coordinator admin chat
│   │   │   ├── laia_identity.py      # LAIA canonical soul/instructions
│   │   │   ├── scheduler.py          # Cron jobs + learning decay
│   │   │   ├── webhooks.py           # HMAC-SHA256 webhook receiver
│   │   │   ├── child_profiles.py     # Ephemeral sub-agent profiles
│   │   │   ├── pricing.py            # LLM cost estimation (USD)
│   │   │   ├── auto_import/          # External data import framework
│   │   │   ├── agent_client.py       # HTTPX async client for executors
│   │   │   ├── orchestrator.py       # LXD agent orchestration
│   │   │   ├── coordinator.py        # Fleet monitor loop (30s)
│   │   │   ├── storage.py            # AgoraStore (SQLite)
│   │   │   ├── database.py           # Schema + migrations (15+ tables)
│   │   │   ├── models.py             # Pydantic models
│   │   │   └── auth.py               # JWT HS256 + PBKDF2
│   │   ├── tests/                    # 342 tests
│   │   └── .venv/                    # Virtual environment
│   │
│   └── laia-executor/                # Per-container executor
│       └── src/laia_executor/
│           ├── api.py                # FastAPI (:9091): POST /exec, 22 tools
│           └── ...
│
├── infra/                            # Infrastructure as Code
│   ├── dev/                          # Development & operations scripts
│   │   ├── preflight.sh              # Operational diagnostics (288 LOC)
│   │   ├── smoke-test.sh             # E2E verification (164 LOC)
│   │   ├── rebuild-state.sh          # State file regeneration (147 LOC)
│   │   ├── laia-marketplace.py       # Marketplace CLI (470 LOC)
│   │   ├── laia-init.sh              # Installation wizard (8 steps)
│   │   ├── chat-with-deployed.sh     # Chat client for deployed agents
│   │   └── ctl/                      # Control Center TUI v2 (Textual, 14 tabs)
│   ├── lxd/                          # LXD profiles, scripts, image builds
│   │   ├── profiles/                 # laia-employee.yaml, laia-agora.yaml
│   │   ├── scripts/                  # rebuild-{1,2,3,4}.sh, create-agent.sh
│   │   └── image-build/              # build-base-image.sh, build-agora-image.sh
│   ├── orchestrator/                 # Python LXD orchestration library
│   ├── systemd/                      # Service unit files
│   └── nginx/                        # Reverse proxy configs
│
├── workspace_store/                  # Shared WorkspaceStore library (SQLite + FTS5)
├── laia-ui/                          # Frontend monorepo (pnpm, React + Vite)
├── docs/                             # Documentation (12 documents)
├── examples/marketplace/             # Example plugins + skills
├── skills/                           # Agent skill marketplace
├── workspaces/                       # Workspace data (DB-first)
├── scripts/                          # Utility scripts
├── archived/                         # Legacy versions (archived)
├── Makefile                          # Standard dev/deploy targets
├── CHANGELOG.md                      # Version history
├── CONTRIBUTING.md                   # Developer onboarding
├── SECURITY.md                       # Security policy
└── .gitignore                        # Clean, organized

~/.laia/                             # Runtime data (LAIA_HOME)
├── config.yaml                       # Agent + project configuration
├── .env                              # Environment secrets
├── auth.json                         # Provider credentials
├── agora.db                          # AGORA production database
├── state/                            # Persistent state files
│   ├── laia-agora-state.json
│   └── laia-state-{slug}.json
├── workspaces/                       # 7 workspaces DB-first
├── plugins/                          # Installed plugins
├── atlas/                            # Symlink farm (32 symlinks)
├── pathd.sock                        # Atlas daemon Unix socket
├── logs/                             # Agent + gateway logs
├── backups/                          # Automated backups
├── cache/                            # Model + media caches
└── sessions/                         # Session trajectories

/srv/laia/                           # Production data (outside repo)
├── agora/                            # AGORA platform data
│   ├── agora.db
│   ├── auth.json
│   ├── plugin-store/                 # Approved plugin blobs
│   ├── skill-store/                  # Approved skill blobs
│   └── workspace.db (colectivo)
├── users/{slug}/                     # Per-user persistent data
│   ├── home/                         # User files (bind mount → /home/user)
│   ├── workspace/                    # Private workspace DB
│   └── plugins/                      # User plugins
├── state/                            # Production state
└── backups/                          # Production backups
```

## Networking

```
Internet
  │
  ▼
Cloudflare (DNS + SSL + WAF + Tunnel)
  │
  ▼
nginx :80 (reverse proxy)
  │
  ├── laiajmp.org → arete-backend :8000 (Node/PM2)
  ├── app.laiajmp.org → arete-backend :8000
  ├── tienda.laiajmp.org → WordPress Docker :9000
  └── agora.laiajmp.org → /srv/laia/agora/frontend/dist
                             /api/* → host:8088 → laia-agora:8000 (LXD proxy)

Internal services:
  laia-gateway (multi-platform, host network)
  workspace-ui :8077 (LAIA-ARCH admin, FastAPI)
  laia-agora :8000 (LAIA-AGORA Backend, inside LXD container)
  laia-executor :9091 (per-user executor, inside LXD container)
```

## Database Schema (agora.db — 15+ tables)

| Table | Purpose |
|-------|---------|
| `users` | User accounts: id, username, role, agent_id, password, llm_provider, llm_api_key, budget caps, mcp_servers |
| `agents` | Agent records: id, user_id, container_name, container_ip, api_token, status |
| `tasks` | Task queue: id, title, assignee_id, priority, status |
| `events` | Audit trail: id, event_type, actor_id, summary, payload |
| `conversations` | Chat history: session_id, user_id, agent_slug, messages_json |
| `telegram_links` | Telegram OAuth: telegram_user_id, agora_user_id |
| `admin_jobs` | Background jobs: id, kind, actor_id, status, params, log |
| `agent_areas` | Agent personality: soul_md, instructions_md, behavior_prefs, memory_prefs |
| `plugin_registry` | Marketplace plugins: slug, version, manifest, blob, status |
| `plugin_installs` | Per-user plugin installs: user_id, plugin_id, active |
| `skill_registry` | Marketplace skills: slug, manifest_md, blob, status |
| `skill_installs` | Per-user skill installs: user_id, skill_id, active |
| `agent_learnings` | Persistent learning: user_id, kind, title, content_md, confidence |
| `agent_scheduled_jobs` | Cron jobs: user_id, cron_expr, prompt, deliver, status |
| `webhook_subscriptions` | Webhooks: user_id, slug, secret, prompt |
| `auto_imports` | External imports: user_id, provider, config, cron |
| `agent_child_runs` | Sub-agent executions: parent_user_id, profile, response |
| `usage_ledger` | Token/cost tracking: user_id, provider, model, tokens, cost_usd |
| `coordinator_messages` | LAIA inbox: user_id, from_role, text, severity, read |

## Container Architecture

```
laia-agora (brain container)
└── /opt/agora/
    ├── app/                     ← code (image)
    │   ├── .laia-core/          ← AI engine + plugins
    │   ├── services/agora-backend/app/  ← backend FastAPI
    │   └── workspace_store/
    ├── venv/                    ← Python venv
    └── data/                    ← bind mount → /srv/laia/agora/
        ├── agora.db
        ├── auth.json
        ├── plugin-store/
        ├── skill-store/
        ├── installed-plugins/{user}/
        └── installed-skills/{user}/

agent-{slug} (user container)
└── /opt/laia/
    ├── agent/src/laia_executor/ ← executor code
    ├── runtime/venv/            ← Python venv
    ├── data/                    ← tasks inbox/done/failed, profile, status
    ├── workspaces/personal/     ← private workspace.db
    └── plugins/                 ← user plugins
    └── /home/user               ← bind mount → /srv/laia/users/{slug}/home/
```

## Tests

| Suite | Count | Path |
|-------|-------|------|
| Backend | 342 | `services/agora-backend/tests/` |
| Executor | 53 | `services/laia-executor/tests/` |
| Forwarder | 25 | `.laia-core/plugins/agora-executor-forwarder/tests/` |
| Shell | 11 | `tests/test_*.sh` |
| **Total** | **431** | |

## Git History

- **Branch:** `feat/agora-redesign-centralized-brain`
- **Commits:** 15 (36f7263 → e2b8ea5)
- **Tags:** sprint2-snapshot, sprint2-final, pre-redesign-backup, redesign-v1-functional, redesign-v1.1-functional, redesign-v1.2-secure, redesign-v1.3-user-runtime, redesign-v2.0-deployed, control-center-v0.1, control-center-v0.2-polished

> &#x1F4C5; v2.5 — 2026-05-19

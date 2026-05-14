# LAIA — System Architecture

## v2.0 (2026-05-14)

## Architecture Overview

```
LAIA (parent agent)
├── Context ARCH (host, admin total)
│   └── Visible only by admin (Jorge)
└── Context AGORA (container: laia-agora, coordinator)
    └── Visible by all users via AGORA platform
        │
        ├── Agent "Nombrix" (child, laia-jorge)
        ├── Agent "MariaBot" (child, laia-maria)
        └── Agent "CarlosAI" (child, laia-carlos)
```

## Directory Structure

```
~/LAIA/                              # Project root
├── .laia-core/                       # AI Engine (forked from Hermes 0.11.0)
│   ├── laia                          # CLI entry point
│   ├── laia_constants.py             # Path resolution (LAIA_HOME)
│   ├── laia_paths.py                 # Path Registry module
│   ├── laia_cli/                     # CLI subcommands
│   ├── agent/                        # Agent internals (providers, memory, caching)
│   ├── gateway/                      # Multi-platform messaging gateway
│   │   └── run.py                    # Gateway orchestrator
│   ├── tools/                        # 71 built-in tools
│   ├── skills/                       # Built-in agent skills
│   ├── plugins/                      # Core plugins (memory providers)
│   ├── laia-ui-server/               # ARCH admin UI backend
│   └── venv/                         # Python virtual environment
│
├── laia-ui/                          # Frontend monorepo (pnpm workspaces)
│   ├── packages/arch-app/            # ARCH admin dashboard (React + Vite)
│   ├── packages/agora-app/           # AGORA user platform (React + Vite)
│   ├── packages/ui/                  # Shared design system
│   └── packages/shared/              # Shared API types
│
├── services/                         # Backend services
│   ├── agora-backend/                # AGORA platform API (FastAPI)
│   │   ├── app/
│   │   │   ├── main.py               # 30+ endpoints, serves SPA frontend
│   │   │   ├── auth.py               # JWT + pbkdf2_hmac authentication
│   │   │   ├── storage.py            # SQLite storage (agora.db)
│   │   │   ├── coordinator.py        # LAIA AGORA monitor loop
│   │   │   ├── monitor.py            # FleetMonitor health daemon
│   │   │   ├── websocket.py          # Real-time push manager
│   │   │   ├── orchestrator.py       # LXD agent orchestration
│   │   │   ├── security.py           # Password hashing + JWT (stdlib)
│   │   │   ├── database.py           # SQLite connection manager
│   │   │   ├── logging.py            # JSON structured logging
│   │   │   └── metrics.py            # Request counters
│   │   └── tests/                    # 69 tests
│   └── laia-runtime/                 # Per-container agent runtime
│       └── src/laia_agent/
│           ├── daemon.py             # Main loop + signal handling
│           ├── tasks.py              # Task queue (13+ types)
│           ├── profile.py            # Editable agent profile
│           ├── workspace.py          # Personal workspace.db
│           ├── plugins.py            # Plugin system
│           └── health.py             # HTTP :9090/health
│
├── infra/                            # Infrastructure as Code
│   ├── laiactl                       # CLI entry point (25+ commands)
│   ├── bin/                          # Terminal toolkit (8 scripts)
│   ├── pathd/                        # Atlas — Path Registry Daemon
│   ├── orchestrator/                 # Python LXD orchestration
│   ├── nginx/                        # Reverse proxy configs
│   ├── lxd/                          # LXD profiles and scripts
│   ├── systemd/                      # Service unit files
│   ├── scripts/                      # Deploy and maintenance scripts
│   └── docs/                         # Infrastructure docs
│
├── workspace_store/                  # Shared WorkspaceStore library
├── plugins/                          # Host-level plugins (source)
│   ├── workspace-context/            # DB-first memory provider
│   └── README.md
├── workspaces/                       # Workspace data (DB-first)
│   ├── laia-ecosystem/               # This workspace
│   ├── laia-arch/                    # Architecture docs
│   ├── arete/                        # Arete project
│   ├── doyouwin/                     # DoYouWin project
│   ├── pixelcore/                    # PixelCore project
│   ├── servidor-jmp/                 # Server docs
│   └── demo-completo/                # Demo workspace
├── skills/                           # Agent skill marketplace
├── docs/                             # Documentation (API, CLI, Architecture, etc.)
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
├── .env.paths                        # Path registry snapshot (auto-generated)
├── atlas/                            # Symlink farm (32 symlinks)
├── plugins/                          # Installed plugins (workspace-context)
├── workspace_store/                  # Vendored WorkspaceStore
├── state.db                          # SQLite session database
├── response_store.db                 # Response cache
├── pathd.sock                        # Atlas daemon Unix socket
├── sessions/                         # Session trajectories
├── logs/                             # Agent + gateway logs
├── backups/                          # Automated backups
├── cache/                            # Model + media caches
├── skills → ../LAIA/skills           # Symlink to repo skills
└── state/                            # Daemon state (path-cache.json)

/srv/laia/                           # Production data (outside repo)
├── agora/                            # AGORA platform data
│   ├── app-data/
│   └── frontend/dist/                # Built AGORA SPA
├── state/                            # Production state
├── agents/                           # Agent registry
└── backups/                          # Production backups
```

## Network Architecture

```
Internet
    │
    ▼
Cloudflare (DNS + SSL + WAF)
    │ Cloudflare Tunnel
    ▼
cloudflared (host)
    │
    ▼
nginx :80 (reverse proxy)
    │
    ├── laiajmp.org ──────► arete-backend :8000 (Node/PM2)
    ├── app.laiajmp.org ──► arete-backend :8000
    ├── tienda.laiajmp.org ► WordPress Docker :9000
    └── agora.laiajmp.org ► /srv/laia/agora/frontend/dist
                             /api/* → agora-backend :8088

Internal services:
    workspace-ui :8077 (ARCH admin, FastAPI)
    laia-gateway (multi-platform, host network)
    postgresql :5432
```

## Key Rules

1. **LAIA** is the parent agent. Not duplicated.
2. **No agent** may be named "LAIA" (reserved for coordinator).
3. **LAIA AGORA** monitors but does NOT modify user containers.
4. **Child agents** do NOT see host plugins.
5. **Child agents** do NOT see LAIA ARCH.
6. **All paths** resolved through Atlas Path Registry (`config.yaml → paths:`).
7. **All secrets** in `~/.laia/` with `chmod 600`, never in repo.
8. **Runtime data** in `~/.laia/`, production data in `/srv/laia/`.

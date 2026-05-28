<p align="center">
  <img src=".laia-core/assets/banner.png" alt="LAIA" width="100%">
</p>

<h1 align="center">LAIA — Personal AI Agent Ecosystem</h1>

<p align="center">
  <a href="https://github.com/JorgeMP-3/laia-arch/blob/main/.laia-core/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License: MIT"></a>
  <a href="https://discord.gg/nousresearch"><img src="https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord"></a>
  <a href="https://laia-agent.nousresearch.com/docs/"><img src="https://img.shields.io/badge/Docs-laia--agent.nousresearch.com-FFD700?style=for-the-badge" alt="Documentation"></a>
</p>

---

## What is LAIA?

LAIA is an **open-source ecosystem of personal AI agents** built for self-hosted deployment. It consists of two layers:

| Layer | Description |
|---|---|
| **LAIA-AGORA** | Multi-user platform — a centralized brain that coordinates all personal agents, handles auth, chat, a marketplace, and a control center. Runs in its own container. |
| **PA-AGORA** | Personal Agent — each user has their own agent running in a private container (root, no sandbox). Agents execute tools in their user's container on behalf of the LLM running in LAIA-AGORA. |
| **LAIA-ARCH** | Host administrator — Jorge Miralles' operational layer for managing infrastructure (LXD, nginx, systemd, deploy). Invisible to users. |

The core agent runtime is **LAIA Agent** — the open-source project built by [Nous Research](https://nousresearch.com). The platform layer (AGORA + executor) is what turns a single agent into a multi-user product.

> **This repo is the development workspace for the LAIA ecosystem.**
> The canonical LAIA Agent product code lives in [`.laia-core/`](.laia-core/).

---

## Repository Layout

```
LAIA/
├── .laia-core/              ← LAIA Agent (MIT, Nous Research)
│   ├── README.md            ← Product overview, install, quick start
│   ├── CONTRIBUTING.md      ← Dev setup, architecture, code style
│   ├── run_agent.py         ← AIAgent class — core conversation loop
│   ├── tools/               ← Self-registering tool implementations
│   ├── gateway/             ← Messaging platform gateway (Telegram, Discord, …)
│   ├── skills/              ← Bundled skills
│   └── agent/               ← Provider adapters, memory, compression, display
│
├── services/                ← Platform layer
│   ├── agora-backend/       ← FastAPI backend (auth, chat, users, marketplace)
│   └── laia-executor/       ← Tool executor (runs in user containers)
│
├── infra/                   ← Infrastructure
│   ├── installer/           ← laia-install, laia-clone
│   ├── orchestrator/        ← Container orchestration (LXD)
│   └── pathd/               ← Path resolution daemon (Atlas v2)
│
├── docs/                    ← Architecture docs and diagrams
├── workflow/                ← Internal changelog, coordination, plans
└── workspace_store/         ← Shared workspace library (SQLite + FTS5)
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  HOST                                                           │
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  LAIA-AGORA — Centralized brain (container)               │  │
│  │  • .laia-core/ (agent motor)                              │  │
│  │  • Backend / REST API                                      │  │
│  │  • LLM instance per chat session                           │  │
│  │  • Marketplace + Control Center                            │  │
│  │  • agora.db (users, agents, config)                       │  │
│  └────────────────────────────┬───────────────────────────────┘  │
│                                │ HTTP (Tool Forwarder)            │
│  ┌────────────────────────────▼───────────────────────────────┐  │
│  │  PA-AGORA — Per-user containers                            │  │
│  │  agent-jorge: "Nombrix"    agent-maria: "MariaBot"        │  │
│  │  • laia-executor (tool execution, root)                    │  │
│  │  • User files, workspace, plugins                          │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  LAIA-ARCH — Host admin (Jorge only)                       │  │
│  │  • Manages LXD, nginx, systemd, deploy                     │  │
│  │  • Invisible to users                                      │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Use the product

```bash
# Install LAIA Agent (single-user, runs anywhere)
curl -fsSL https://raw.githubusercontent.com/NousResearch/laia-agent/main/scripts/install.sh | bash
laia              # start chatting
laia model        # choose your LLM
laia gateway      # connect Telegram, Discord, Slack, …
```

See [.laia-core/README.md](.laia-core/README.md) for the full product documentation.

### Develop the ecosystem

This repo is the development workspace. Clone and explore:

```bash
git clone https://github.com/JorgeMP-3/laia-arch.git
cd laia-arch
ls .laia-core/           # LAIA Agent product code
ls services/             # agora-backend, laia-executor
ls infra/                # installer, orchestrator, pathd
```

---

## Documentation

| What you need | Where to look |
|---|---|
| **What LAIA is** | [`LAIA_ECOSYSTEM.md`](LAIA_ECOSYSTEM.md) — canonical vision (in Spanish) |
| **LAIA Agent product** | [`.laia-core/README.md`](.laia-core/README.md) — install, features, quick start |
| **Develop LAIA Agent** | [`.laia-core/CONTRIBUTING.md`](.laia-core/CONTRIBUTING.md) — dev setup, architecture, code style |
| **Platform (AGORA) development** | [`services/agora-backend/`](services/agora-backend/) — FastAPI backend |
| **Architecture & ADRs** | [`workflow/arch-layout.md`](workflow/arch-layout.md) — disk layout, migration contract |
| **System diagrams** | [`docs/map.svg`](docs/map.svg) — visual architecture |
| **Auto-generated reference** | [`docs/db-export/`](docs/db-export/) — technical detail per subsystem (do not edit) |

---

## Contributing

Contributions are welcome. See the relevant guide for what you're working on:

- **LAIA Agent** (`.laia-core/`): [.laia-core/CONTRIBUTING.md](.laia-core/CONTRIBUTING.md)
- **AGORA platform** (`services/agora-backend/`): open an issue to discuss before submitting PRs

Bug reports, feature requests, and questions are all welcome via GitHub Issues.

---

## License

LAIA Agent (.laia-core/) is [MIT licensed](.laia-core/LICENSE), built by [Nous Research](https://nousresearch.com).

The platform layer and infrastructure scripts in this workspace are private to the LAIA ecosystem project.

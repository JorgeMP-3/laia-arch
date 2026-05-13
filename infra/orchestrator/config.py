from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    laia_root: Path
    infra_root: Path
    state_root: Path
    agents_state: Path
    agent_runtime_root: Path


def discover_paths() -> Paths:
    infra_root = Path(__file__).resolve().parents[1]
    laia_root = infra_root.parent
    state_root = Path(os.environ.get("LAIA_STATE_ROOT", laia_root / ".laia" / "state"))
    return Paths(
        laia_root=laia_root,
        infra_root=infra_root,
        state_root=state_root,
        agents_state=state_root / "agents.json",
        agent_runtime_root=laia_root / "services" / "laia-agent-runtime",
    )


DEFAULT_IMAGE_ALIAS = "laia-agent"
DEFAULT_PROFILE = "laia-employee"
DEFAULT_NETWORK = "lxdbr0"
DEFAULT_POOL = "default"
DEFAULT_BRIDGE_SUBNET = "10.99.0.0/24"

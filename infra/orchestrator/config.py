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
    # Layout v2: agents.json is AGORA-platform orchestration state, not ARCH
    # runtime — it lives at the top-level /srv/laia/state (see arch-layout.md
    # §2.2), NOT under /srv/laia/arch (which is ARCH-only: config, secrets,
    # resolver state). The agora backend passes LAIA_STATE_ROOT explicitly
    # (its config.py → /srv/laia/state); this default covers standalone
    # invocations and stays aligned with agora-backend.service, atlas srv_state
    # and setup-prod-dirs.sh. (Decision 2026-05-29, reconciling the C1 touch-point.)
    state_root = Path(os.environ.get("LAIA_STATE_ROOT", "/srv/laia/state"))
    return Paths(
        laia_root=laia_root,
        infra_root=infra_root,
        state_root=state_root,
        agents_state=state_root / "agents.json",
        agent_runtime_root=laia_root / "services" / "laia-runtime",
    )


DEFAULT_IMAGE_ALIAS = "laia-agent"
DEFAULT_PROFILE = "laia-employee"
DEFAULT_NETWORK = "lxdbr0"
DEFAULT_POOL = "default"
DEFAULT_BRIDGE_SUBNET = "10.99.0.0/24"

# LAIA Orchestrator

`laiactl` is the CLI entrypoint for reproducible LAIA infrastructure operations.

Current scope:

- verify LXD host setup;
- create default LXD pool/network/profile;
- build or verify the `laia-agent` image;
- create personal agent containers;
- install the runtime inside a container;
- start, stop, restart and inspect the runtime service;
- snapshot, restore and delete agent containers;
- verify agent runtime health;
- keep a local JSON state file for future backend/UI integration.

## Commands

```bash
infra/laiactl doctor
infra/laiactl setup-lxd
infra/laiactl build-agent-image
infra/laiactl create-agent jorge
infra/laiactl install-agent-runtime jorge
infra/laiactl init-agent-workspace jorge
infra/laiactl init-agent-profile jorge
infra/laiactl agent-profile jorge
infra/laiactl set-agent-persona jorge /ruta/persona.md
infra/laiactl set-agent-instructions jorge /ruta/instructions.md
infra/laiactl enable-agent-skill jorge planning.deep
infra/laiactl disable-agent-skill jorge tasks.basic
infra/laiactl verify-agent jorge
infra/laiactl agent-status jorge
infra/laiactl restart-agent jorge
infra/laiactl snapshot-agent jorge runtime-installed
infra/laiactl restore-agent jorge runtime-installed --yes
infra/laiactl delete-agent jorge --yes --force
infra/laiactl list-agents
infra/laiactl verify
infra/laiactl state-path
```

If container egress is broken after host reboot or firewall changes:

```bash
sudo infra/lxd/scripts/fix-egress-root.sh
```

## State

Development state defaults to:

```text
LAIA/.laia/state/agents.json
```

Override with:

```bash
LAIA_STATE_ROOT=/srv/laia/state infra/laiactl verify-agent jorge
```

## Design

The CLI is intentionally a thin interface over reusable Python modules.

Boundary:

- `laiactl` belongs to the ARCH/admin side;
- it is the control interface for LXD, runtime installation and fleet operations;
- AGORA must not expose these global commands to end users;
- AGORA should only use filtered ownership-aware operations for the authenticated user's own agent.

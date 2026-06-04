# LAIA-ARCH console (laia-ui-server)

Operator-only web console for LAIA-ARCH: workspaces, agent sessions, the
Command Center (PTY terminals on the host) and the context engine. **Only Jorge
uses it** — users never reach ARCH (`LAIA_ECOSYSTEM.md`).

## Security posture (non-negotiable)

- **Loopback bind only.** Backend defaults to `127.0.0.1` (`LAIA_UI_HOST`); the
  systemd unit pins `--host 127.0.0.1`. Remote operator access goes through
  **Tailscale on the host** — never a `laia-edge` vhost, never `0.0.0.0`.
- **Runs as the operator user, not root** (`laia-ui-server.service.tmpl`). No
  systemd sandbox: the Command Center spawns PTYs + bwrap, which lockdowns
  break (and the snap pitfall, 2026-06-03).
- Containment = non-root user + loopback. The console has the operator's reach
  by design; the threat model is *who can reach it*, answered at the network
  layer (UFW + Tailscale).

## Stack

- Backend: FastAPI + uvicorn (`backend/`, deps `backend/requirements.txt`,
  capped per supply-chain Tier 1).
- Frontend: Vite + React 19 + TS + Tailwind 4 (`frontend/`).

## Build (reproducible, supply-chain-checked)

No Node on the host (host-minimal): build inside the dev VM `laia-dev` via
`dev-run ui-arch build`, or manually on any trusted box. **pnpm** is the LAIA
convention (corepack ships it with Node 22):

```bash
cd frontend
pnpm install --ignore-scripts --frozen-lockfile  # lock integrity; no lifecycle scripts
pnpm audit                                       # must be 0 vulnerabilities
pnpm run build                                   # -> frontend/dist (served by the backend)
```

The committed `pnpm-lock.yaml` pins every transitive dep with integrity
hashes. `dist/` is a build artifact (not committed); it is produced at build
time and shipped to `/opt/laia/.laia-core/laia-ui-server/frontend/dist` on
deploy.

> History (2026-06-04): the old npm lockfile carried two phantom package names
> (`laia-parser`, `laia-estree`) — collateral of the wholesale `hermes`→`laia`
> rename of the fork, pointing at non-existent npm packages (fail-safe, not an
> attack). Replaced wholesale by a fresh pnpm resolution from package.json
> (audit-clean, `react-router` 7.16.0 clearing a DoS advisory that was not
> reachable here anyway — SPA, no SSR `__manifest`).

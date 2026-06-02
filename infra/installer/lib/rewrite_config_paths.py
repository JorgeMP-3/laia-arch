#!/usr/bin/env python3
"""Rewrite the path anchors in a cloned LAIA-ARCH config.yaml.

Used by clone_phase_h_rewrite_config_paths (infra/installer/lib/clone.sh) during
`laia-clone`. Replaces the old line-based `sed` rewrite, which anchored the
key-substitution rules to `^[[:space:]]*<key>:` and therefore also matched
*structural* keys that happen to share a name with a path anchor —
`plugins:` (mapping), `workspaces:` (list), `skills:` (mapping) — appending a
path to them and producing invalid YAML that orphaned the following block.

This version applies the key rewrites ONLY inside the top-level `paths:` mapping.
Absolute-path literals (~/.laia, /home/<user>/LAIA) are normalised everywhere.
The rewrite is line-oriented, so comments and formatting are preserved.

Usage: rewrite_config_paths.py <config.yaml> <live_home_expr>
  live_home_expr e.g. '${LAIA_HOME:-/home/laia-arch/LAIA-ARCH}'
"""
from __future__ import annotations

import re
import sys


def rewrite(text: str, live: str) -> str:
    """Return *text* with path anchors rewritten. Pure; no I/O."""
    # Layout v2 (slice C1) split — the core is volatility + sensitivity:
    #   - INTERACTIVE mesa viva (laia_home, workspaces, memories, skills,
    #     plugins) → the live LAIA_HOME (~/LAIA-ARCH).
    #   - OPERATIONAL runtime state (state_db, response_store) → /srv/laia/arch,
    #     the ARCH runtime home, alongside config.yaml/.env.paths/state.
    # This reverses the earlier T.14.1 decision (everything → LAIA_HOME), which
    # the 2026-05-29 v2 lock superseded — see ~/laia-developers/workflow-main/arch-data-layout.md.
    arch = "/srv/laia/arch"
    key_value = {
        "laia_root":         "/opt/laia",
        "agora_data":        "/srv/laia/agora/agora.db",
        "laia_home":         live,
        "workspaces":        f"{live}/workspaces",
        "memories":          f"{live}/memories",
        "skills":            f"{live}/skills",
        "plugins":           f"{live}/plugins",
        "state_db":          f"{arch}/state.db",
        "response_store":    f"{arch}/response_store.db",
        "response_store_db": f"{arch}/response_store.db",
    }

    def sweep(line: str) -> str:
        # Normalise absolute-path literals anywhere on the line. Replacement
        # callables keep `live` literal (no backref/escape interpretation).
        line = re.sub(r"~/\.laia/", lambda _m: live + "/", line)
        line = re.sub(r'/home/[^/\s"]+/\.laia/', lambda _m: live + "/", line)
        line = re.sub(r'/home/[^/\s"]+/\.laia(?=[\s"]|$)', lambda _m: live, line)
        line = re.sub(r'/home/[^/\s"]+/LAIA/', "/opt/laia/", line)
        line = re.sub(r'/home/[^/\s"]+/LAIA(?=[\s"]|$)', "/opt/laia", line)
        return line

    out: list[str] = []
    in_paths = False
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\n")
        nl = "\n" if line.endswith("\n") else ""

        # The top-level `paths:` mapping opens the scoped region; the next
        # top-level (non-indented) key closes it.
        if re.match(r"^paths:\s*$", body):
            in_paths = True
            out.append(sweep(line))
            continue
        if in_paths and re.match(r"^\S", body):
            in_paths = False

        if in_paths:
            m = re.match(r"^(\s+)([A-Za-z0-9_]+):", body)
            if m and m.group(2) in key_value:
                out.append(f"{m.group(1)}{m.group(2)}: {key_value[m.group(2)]}{nl}")
                continue

        out.append(sweep(line))

    return "".join(out)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: rewrite_config_paths.py <config.yaml> <live_home_expr>",
              file=sys.stderr)
        return 2
    cfg, live = argv[1], argv[2]
    with open(cfg, "r") as fh:
        text = fh.read()
    new = rewrite(text, live)
    if new != text:
        with open(cfg, "w") as fh:
            fh.write(new)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

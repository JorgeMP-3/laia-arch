"""Regression tests for the laia-clone config.yaml path rewrite.

Guards against the bug where line-based sed clobbered structural keys
(plugins:/workspaces:/skills:) that share a name with a `paths:` anchor,
producing invalid YAML. See infra/installer/lib/rewrite_config_paths.py.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
_HELPER = _REPO_ROOT / "infra" / "installer" / "lib" / "rewrite_config_paths.py"

_loader = importlib.machinery.SourceFileLoader("rewrite_config_paths", str(_HELPER))
_spec = importlib.util.spec_from_loader("rewrite_config_paths", _loader)
rcp = importlib.util.module_from_spec(_spec)
_loader.exec_module(rcp)

LIVE = "${LAIA_HOME:-/home/laia-arch/LAIA-ARCH}"

# A config that exercises the collision: plugins/workspaces/skills appear BOTH
# as path anchors (under paths:) AND as structural keys elsewhere.
SAMPLE = """\
platforms:
  api_server:
    enabled: true
plugins:
  workspace-context:
    workspace: laia-ecosystem
    workspaces:
    - laia-ecosystem
    - arete
skills:
  creation_nudge_interval: 15
  external_dirs: []
paths:
  laia_root: /home/laia-hermes/LAIA
  laia_home: ${LAIA_HOME:-/home/laia-hermes/.laia}
  agora_data: ${paths.laia_home}/agora.db
  workspaces: ${paths.laia_home}/workspaces
  memories: ${paths.laia_home}/memories
  skills: ${paths.laia_root}/skills
  plugins: ${paths.laia_home}/plugins
security:
  redact_pii: false
"""


def _rw(text: str = SAMPLE) -> str:
    return rcp.rewrite(text, LIVE)


def test_output_is_valid_yaml() -> None:
    yaml.safe_load(_rw())  # must not raise


def test_structural_plugins_mapping_preserved() -> None:
    data = yaml.safe_load(_rw())
    # The top-level plugins: mapping (NOT the paths anchor) keeps its children.
    assert isinstance(data["plugins"], dict)
    assert data["plugins"]["workspace-context"]["workspace"] == "laia-ecosystem"


def test_structural_workspaces_list_preserved() -> None:
    data = yaml.safe_load(_rw())
    wc = data["plugins"]["workspace-context"]
    assert wc["workspaces"] == ["laia-ecosystem", "arete"]


def test_structural_skills_mapping_preserved() -> None:
    data = yaml.safe_load(_rw())
    assert isinstance(data["skills"], dict)
    assert data["skills"]["creation_nudge_interval"] == 15


def test_paths_anchors_rewritten() -> None:
    data = yaml.safe_load(_rw())
    p = data["paths"]
    assert p["laia_root"] == "/opt/laia"
    assert p["agora_data"] == "/srv/laia/agora/agora.db"
    assert p["laia_home"] == LIVE
    assert p["workspaces"] == f"{LIVE}/workspaces"
    assert p["skills"] == f"{LIVE}/skills"
    assert p["plugins"] == f"{LIVE}/plugins"


def test_legacy_home_literals_normalised() -> None:
    text = "paths:\n  laia_root: /home/laia-hermes/LAIA\nmisc:\n  note: /home/x/.laia/auth.json\n"
    out = _rw(text)
    assert "/home/laia-hermes" not in out
    assert "/opt/laia" in out
    assert LIVE in out  # ~/.laia-style literal swept to live home


def test_idempotent() -> None:
    once = _rw()
    twice = rcp.rewrite(once, LIVE)
    assert once == twice


def test_no_paths_block_leaves_structural_keys_untouched() -> None:
    # The original bug fired even without a paths: block. Here there is none,
    # so the structural plugins:/skills: must be returned verbatim.
    text = "plugins:\n  foo:\n    bar: 1\nskills:\n  baz: 2\n"
    out = _rw(text)
    assert out == text
    yaml.safe_load(out)

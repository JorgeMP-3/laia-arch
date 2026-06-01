# LAIA integrity regression suite

Track T turns the old D2 integrity gate into a runner-driven regression suite.
It follows a pyramid: many fast unit checks, fewer medium integration checks,
and a couple of heavy e2e flows. Every test declares `# integrity:` metadata so
the runner can select the right subset per environment and report machine-
readable results. The slices:

| Slice | What | Where it runs |
|---|---|---|
| **T1** | Runner + taxonomy + JSON report + exit codes (`run_integrity.sh`, `lib/integrity_runner.py`). | everywhere |
| **T2** | One invariant module per core layer (host, lxd, agora, executor, data, atlas, backups). | VM/host (CI for the fixture-backed ones) |
| **T3** | Golden-path e2e: provision → tool-call in the user's container → deprovision (`e2e/golden`). | golden VM only |
| **T4** | Cross-consistency reconciler DB↔FS↔containers (`lib/reconcile.py`, `unit/cross`, `integration/cross`). | CI (fixture) + VM (live) |
| **T5** | One regression guard per `resolved` bug in `problems.md` (`regression/`, see its README). | CI + VM |
| **T6** | Load smoke: N concurrent agents without exhausting RAM/disk (`e2e/load`). | golden VM only |
| **T-DOC** | English-docstring gate for production code (`lib/check_docstrings.py`, `unit/docs`). | CI |

D2 (`test_ecosystem_integrity.sh`) remains the read-only cross-layer gate; the
per-layer modules complement it, they do not replace or weaken it.

## Runner

```bash
tests/integration/run_integrity.sh --profile ci --json report.json
tests/integration/run_integrity.sh --profile vm --layer agora --json -
tests/integration/run_integrity.sh --list --json -
```

Profiles:

- `ci`: fast subset for PR CI without LXD. Tests that require host/VM state are
  reported as `skip` with a reason, not silently ignored.
- `host`: read-only host checks where LXD may be available.
- `vm`: golden VM checks, including later e2e tests.
- `auto`: default. Selects `ci` when LXD is unavailable, otherwise `host`.

Levels:

- `unit`: fast contract checks with synthetic fixtures.
- `integration`: read-only ecosystem checks or medium-weight integration checks.
- `e2e`: mutating golden-path tests for the VM only.

Layers:

- `host`
- `lxd`
- `agora`
- `executor`
- `data`
- `atlas`
- `backups`
- `cross`

New tests should live under a path that mirrors the taxonomy when practical,
for example `tests/integration/integration/agora/test_health_contract.sh`.
The runner discovers every `test_*.sh` under `tests/integration/`; metadata is
the source of truth for selection.

Module map (path → what it asserts):

- `integration/host`: `/srv/laia` operational layout.
- `integration/lxd`: `laia-agora` container and data mount.
- `integration/agora`: health endpoint and `agora.db` integrity.
- `integration/executor`: provisioned `agent-*` containers and workspaces.
- `integration/data`: two-zone data/secrets permissions.
- `integration/atlas`: Atlas reference resolution via `doctor`.
- `integration/cross`: live DB↔FS↔containers reconciliation (T4).
- `integration/data/test_migrate_v1_to_v2_prod_outage_regression.sh`: outage regression (T5).
- `regression/`: one guard per resolved bug (T5) — see `regression/README.md`.
- `unit/backup`: fixture-backed backup contract for CI.
- `unit/cross`: fixture-backed reconciler self-test (T4).
- `unit/docs`: English-docstring gate self-test + real gate (T-DOC).
- `e2e/golden`: golden-path provision→tool-call→deprovision (T3).
- `e2e/load`: N-agent load smoke (T6).

## What runs where (no silent gaps)

- **CI (no LXD)** — `run_integrity.sh --profile ci` runs the unit/fixture and
  read-only-safe tests: D2 (ci mode), `backup_contract_fixture`,
  `cross_consistency_reconciler`, `docstring_gate`,
  `regression_backend_hardcoded_plugin_paths`. The layer contracts and e2e
  flows report `skip` with a reason (profile/requirement), never silently.
- **VM `laia-dev` (with LXD)** — `--profile vm` additionally runs the per-layer
  contracts, the live cross-consistency check, the cutover regression, and the
  e2e flows.
- **Pre-deploy gate** — the cutover/Lead runs the relevant subset before prod.

### Destructive e2e safety

`e2e/golden` and `e2e/load` create and delete containers and host directories.
They are double-gated so they can never touch production by accident:

1. their profile is `vm` only (CI/host never select them), and
2. they refuse to run unless `LAIA_E2E_ALLOW_DESTRUCTIVE=1` is set (otherwise
   they exit `77`/skip with a reason).

Run them on the golden VM with, e.g.:

```bash
LAIA_E2E_ALLOW_DESTRUCTIVE=1 tests/integration/run_integrity.sh --profile vm --level e2e
```

## Metadata

Each test script declares its contract in comments:

```bash
# integrity:id=agora_health_contract
# integrity:name=AGORA health contract
# integrity:level=integration
# integrity:layers=agora,data
# integrity:profiles=ci,host,vm
# integrity:requires=sqlite3
# integrity:timeout=60
```

Requirements are checked by the runner before execution. Prefix a requirement
with `optional_` when the test itself handles skip/degraded behavior, as D2
does for LXD/curl/sqlite/Atlas.

## JSON Report

Track B consumes the report emitted by `--json FILE` or `--json -`.

```json
{
  "schema_version": 1,
  "runner": "tests/integration/run_integrity.sh",
  "profile": "ci",
  "requested_profile": "auto",
  "environment": {
    "ci_env": true,
    "lxd_available": false,
    "curl_available": true,
    "sqlite3_available": true,
    "jq_available": false,
    "python3_available": true,
    "atlas_available": true
  },
  "filters": {
    "level": null,
    "layers": []
  },
  "summary": {
    "total": 1,
    "selected": 1,
    "passed": 1,
    "failed": 0,
    "skipped": 0,
    "runtime_skipped": 0,
    "duration_ms": 123
  },
  "tests": [
    {
      "id": "ecosystem_integrity_d2",
      "name": "D2 ecosystem integrity gate",
      "path": "tests/integration/test_ecosystem_integrity.sh",
      "level": "integration",
      "layers": ["host", "lxd", "agora", "executor", "data", "atlas", "backups"],
      "profiles": ["ci", "host", "vm"],
      "requires": ["optional_lxd"],
      "status": "pass",
      "exit_code": 0,
      "duration_ms": 123,
      "reason": null,
      "stdout": "...",
      "stderr": ""
    }
  ]
}
```

Exit codes:

- `0`: every selected test passed.
- `1`: at least one selected test failed.
- `2`: runner/configuration error, including no selected tests.

Individual test scripts may exit `77` to request an explicit skip after doing
their own applicability checks. The runner records that as `status:"skip"` with
`reason:"test requested skip"`; it is not counted as a pass.

## D2 Migration Status

`test_ecosystem_integrity.sh` remains callable directly for compatibility, but
it now declares taxonomy metadata and is discovered by `run_integrity.sh` as the
cross-layer integration gate. The per-layer modules (T2) and the cross-cutting
slices (T3–T6, T-DOC) live alongside it without removing this top-level gate.

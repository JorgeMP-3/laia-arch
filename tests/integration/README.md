# LAIA integrity regression suite

Track T turns the old D2 integrity gate into a runner-driven regression suite.
T1 defines the taxonomy and report contract; T2 adds dedicated per-layer
invariant modules while keeping D2 as the cross-layer gate.

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

T2 currently provides one module per core layer:

- `integration/host`: `/srv/laia` operational layout.
- `integration/lxd`: `laia-agora` container and data mount.
- `integration/agora`: health endpoint and `agora.db` integrity.
- `integration/executor`: provisioned `agent-*` containers and workspaces.
- `integration/data`: two-zone data/secrets permissions.
- `integration/atlas`: Atlas reference resolution via `doctor`.
- `unit/backup`: fixture-backed backup contract for CI.

`test_ecosystem_integrity.sh` remains the D2 cross-layer gate; these modules do
not replace or weaken it.

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
cross-layer integration gate. T2 will split additional invariants into dedicated
per-layer modules without removing this top-level gate.

# LAIA integrity regression suite

Track T turns the old D2 integrity gate into a runner-driven regression suite.
T1 defines the taxonomy and report contract; later slices add the per-layer
invariants and heavy e2e cases.

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

## D2 Migration Status

`test_ecosystem_integrity.sh` remains callable directly for compatibility, but
it now declares taxonomy metadata and is discovered by `run_integrity.sh` as the
cross-layer integration gate. T2 will split additional invariants into dedicated
per-layer modules without removing this top-level gate.

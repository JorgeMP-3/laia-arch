# tests/installer/

Tests for the installer/cloner/release scripts in `bin/` and helpers in
`infra/installer/lib/`.

Most tests are designed to run **without root, without LXD, without GitHub**:
they exercise flag parsing, help output, library functions, and dry-run paths.
Some tests include guarded host-specific blocks:

- `test_clone_hardening.sh` runs its sudo ownership scenario only when
  `sudo -n true` works; otherwise that block is skipped cleanly. Its
  nonexistent install-root regression runs without sudo.
- `test_install_native_layout.sh` needs the `laia auth` runtime dependencies
  normally provided by a real `/opt/laia/.laia-core/venv`; it is skipped in CI
  via `INSTALLER_SKIP` and covered by VM/host runs with laia-core installed.

The real install paths (`/opt/laia`, systemd, etc.) are covered by the E2E test
in a Multipass VM.

## Running

```bash
# From the LAIA root:
bash tests/installer/test_flags.sh
bash tests/installer/test_lib_common.sh
```

Or both:

```bash
bash tests/installer/run_all.sh
```

To mirror GitHub Actions on a clean runner:

```bash
INSTALLER_SKIP="test_install_native_layout.sh" bash tests/installer/run_all.sh
```

## Conventions

- Each test file is self-contained: it sources helpers from
  `infra/installer/lib/` and uses small `assert_*` helpers defined inline.
- No external test framework (bats, shunit) — keeps zero-deps.
- Test files print `  ✓` / `  ✗` per assertion and exit nonzero if any fail.

## What's not tested here (yet)

| Concern                              | Where it's tested                       |
|--------------------------------------|-----------------------------------------|
| Real install to `/opt/laia-vX.Y.Z/`  | Fase B — Multipass VM E2E               |
| `systemctl restart` + healthcheck    | Fase C — the production migration       |
| Remote SSH + `lxc export`            | Fase E — Multipass VM with LXD nested   |
| Idempotency of repeated installs     | Fase B — VM E2E                         |

# tests/installer/

Tests for the installer/cloner/release scripts in `bin/` and helpers in
`infra/installer/lib/`.

Designed to run **without root, without LXD, without GitHub** — they exercise
flag parsing, help output, library functions, and dry-run paths only. The
"real" install paths (`/opt/laia`, systemd, etc.) are covered by the E2E test
in a Multipass VM (planned for Fase B).

## Running

```bash
# From the LAIA root:
bash tests/installer/test_flags.sh
bash tests/installer/test_lib_common.sh
```

Or both:

```bash
for t in tests/installer/test_*.sh; do
  echo "── $t ──"; bash "$t" || exit 1
done
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

# Legacy systemd units (pre installer-v2)

Archived on 2026-05-21 — these unit files were the dev-machine snapshot with
hardcoded `User=laia-hermes`, `WorkingDirectory=/home/laia-hermes/LAIA/...`,
`EnvironmentFile=-/home/laia-hermes/.laia/.env.paths`, and absolute
`ExecStart=/home/laia-hermes/.../uvicorn ...` paths.

They were superseded by the parameterized templates rendered by
`laia-install` from:

    infra/installer/systemd/agora-backend.service.tmpl
    infra/installer/systemd/laia-gateway.service.tmpl
    infra/installer/systemd/laia-pathd.service.tmpl
    infra/installer/systemd/laia-ui-server.service.tmpl

Each template uses `${LAIA_USER}`, `${LAIA_USER_HOME}`, `${LAIA_HOME}`,
`${LAIA_INSTALL_PREFIX}` placeholders that `systemd.sh::systemd_install_all`
substitutes at install time via `envsubst`. The result lands in
`/etc/systemd/system/` with the correct user / paths for the target host.

**Do not re-introduce these files into `infra/systemd/`.** If you need to
inspect what shipped before installer-v2, look here; if you need to change
a unit, edit the template, not the rendered file.

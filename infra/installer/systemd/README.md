# Systemd unit templates

These `.tmpl` files are rendered by `laia-install` and `laia-release` and
written to `/etc/systemd/system/`. Placeholders are substituted with
`envsubst` (or `sed`) using these variables:

| Placeholder              | Value                                  | Source                |
|--------------------------|----------------------------------------|-----------------------|
| `${LAIA_USER}`           | The LAIA-ARCH admin's username         | `$SUDO_USER` or `id -un` |
| `${LAIA_USER_HOME}`      | That user's `$HOME`                    | `getent passwd`       |
| `${LAIA_HOME}`           | Data directory                         | Default `$HOME/LAIA-ARCH` |
| `${LAIA_INSTALL_PREFIX}` | The `/opt/laia` symlink                | `lib/version.sh`      |

The symlink form (`/opt/laia` not `/opt/laia-vX.Y.Z`) is intentional: when
`laia-release` switches the symlink to a new version, systemd picks up the
change on the next `systemctl restart`, without needing to rewrite the unit
file each time.

## Why templates, not generated-once

Historically these units lived in `infra/systemd/*.service` with hardcoded
paths. That broke on path renames and on hosts with different usernames. The
template approach makes the install both portable across hosts and resilient
to the path-rename audit (Atlas Path Registry).

## Rendering

The installer renders templates with a simple `envsubst` call:

    envsubst '${LAIA_USER} ${LAIA_USER_HOME} ${LAIA_HOME} ${LAIA_INSTALL_PREFIX}' \
        <laia-gateway.service.tmpl \
        >/etc/systemd/system/laia-gateway.service

Note the explicit variable list — `envsubst` without arguments expands every
shell variable in the environment, which is a footgun.

## Status

These are **scaffolds for Fase A**. They're identical in structure to the
current `infra/systemd/*.service` files but with placeholders.

Pending in **Fase B/C**:
- Render logic in `laia-install` and `laia-release`
- Validation that paths exist after substitution
- `daemon-reload` + healthcheck after enabling

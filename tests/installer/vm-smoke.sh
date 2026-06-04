#!/usr/bin/env bash
# Compat shim — vm-smoke.sh moved to infra/dev/ (ARCH-usable S2, 2026-06-04)
# so it ships inside the installed tree (/opt/laia/infra) and `laia diagnose`
# can find it on a real install, not only in a repo checkout.
exec bash "$(dirname "${BASH_SOURCE[0]}")/../../infra/dev/vm-smoke.sh" "$@"

package collect

import (
	"context"
	"fmt"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/run"
)

// SystemdActive runs `systemctl is-active <unit>` and maps the exit
// code to a lifecycle string:
//
//	0  → "ok"      (active)
//	3  → "down"    (inactive)
//	4  → "down"    (failed)
//	*  → "unknown" (not-found, invalid arg, no permission, etc.)
//
// "unknown" is the right choice for "we could not determine liveness"
// rather than "down" — we do not want to alarm because systemctl was
// missing or the user has no access. The evaluator treats unknown
// distinctly from down (down → red, unknown → unknown).
func SystemdActive(ctx context.Context, r run.Runner, unit string) (string, error) {
	if r == nil {
		return "unknown", fmt.Errorf("systemctl is-active: no runner")
	}
	res := r(ctx, "systemctl", "is-active", unit)
	if res.Err != nil {
		// The Runner's error wraps context.DeadlineExceeded on
		// timeout, or "binary not found". The alive value is
		// "unknown" — we already know we could not measure. The
		// returned error is for the caller's logging, not for
		// alarming (the alive value already does that).
		return "unknown", fmt.Errorf("systemctl is-active %s: %w", unit, shortRunnerErr(res.Err))
	}
	switch res.ExitCode {
	case 0:
		return "ok", nil
	case 3, 4:
		return "down", nil
	default:
		return "unknown", nil
	}
}

// LXCSystemdActive is SystemdActive inside an LXD container. We do
// NOT execute the command if the container is not Running — we
// return "unknown" without doing I/O, to avoid poking a stopped
// container (which could trigger side effects or simply waste time).
func LXCSystemdActive(ctx context.Context, r run.Runner, container, unit, containerStatus string) (string, error) {
	if containerStatus != "Running" {
		return "unknown", nil
	}
	if r == nil {
		return "unknown", fmt.Errorf("lxc exec systemctl: no runner")
	}
	res := r(ctx, "lxc", "exec", container, "--", "systemctl", "is-active", unit)
	if res.Err != nil {
		return "unknown", fmt.Errorf("lxc exec systemctl %s in %s: %w", unit, container, shortRunnerErr(res.Err))
	}
	switch res.ExitCode {
	case 0:
		return "ok", nil
	case 3, 4:
		return "down", nil
	default:
		return "unknown", nil
	}
}

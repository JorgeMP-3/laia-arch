package collect

import (
	"context"
	"fmt"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/run"
)

// mapIsActive translates a `systemctl is-active` result into the alive
// vocabulary, by EXIT CODE ONLY — stdout lies: a NONEXISTENT unit
// prints "inactive" with exit 4, byte-identical stdout to a real
// inactive unit (exit 3). Verified on doyouwin-server, 2026-06-03:
//
//	is-active tts-server.service             → "active",   exit 0
//	is-active unidad-inexistente-xyz.service → "inactive", exit 4
//
// Mapping (spec §S4 table):
//
//	0 → ok; 3 → down (inactive AND failed are real, known states);
//	anything else (4 = no such unit; 1/2 = usage/permission) → unknown.
//
// The distinction matters operationally: a typo in a config unit name
// must surface as "could not measure" (unknown), NEVER as a false red
// that pushes a Telegram alarm.
func mapIsActive(code int) string {
	switch code {
	case 0:
		return "ok"
	case 3:
		return "down"
	default:
		return "unknown"
	}
}

// SystemdActive runs `systemctl is-active <unit>` and maps the result
// via mapIsActive (see its comment for the exit-code table and why
// stdout is deliberately ignored).
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
	return mapIsActive(res.ExitCode), nil
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
	return mapIsActive(res.ExitCode), nil
}

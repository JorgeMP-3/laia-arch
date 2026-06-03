// Package run is the testability seam for exec.Command.
//
// Every command the daemon launches goes through here: in production it
// uses Real, in tests a fake is injected that returns stdout/exit from
// a table. This way no collector calls exec.Command directly: the logic
// is tested without a host, in milliseconds, and fake Runners are just
// tables of strings.
//
// The Runner is injected into collectors so their tests do not depend
// on system binaries. Real exists only for the daemon in production;
// its tests are quick smoke tests against /bin/echo and /bin/sleep.
package run

import (
	"context"
	"errors"
	"fmt"
	"os/exec"
	"time"
)

// DefaultTimeout is the per-command timeout Real applies if the caller
// does not pass one. 10s gives room for `curl --max-time 8` or
// `systemctl is-active` without a hung host stalling the tick. Collectors
// can use a smaller timeout (egress uses 8s inside curl and leaves 2s
// for the Runner).
const DefaultTimeout = 10 * time.Second

// Result is the outcome of a command run by a Runner. ExitCode is -1 if
// the process never started (binary missing, permissions, timeout). Err
// describes why; nil if the process ran, EVEN when exit != 0 — collectors
// need to distinguish "the command failed" (exit != 0, mappable via the
// table) from "we could not measure it" (Err != nil).
type Result struct {
	Stdout   string
	ExitCode int
	Err      error
}

// Runner executes a command and returns its result. This is the
// testability seam: in tests, a Runner returning a table of results
// is injected.
type Runner func(ctx context.Context, name string, args ...string) Result

// Real returns a Runner that actually executes with exec.CommandContext
// and applies a per-command timeout (not per-tick: each exec has its own
// clock so one hung command does not stall the rest of the tick). stderr
// is discarded (the logic does not need it; in debug a per-command log
// capture could be added).
func Real(timeout time.Duration) Runner {
	if timeout <= 0 {
		timeout = DefaultTimeout
	}
	return func(ctx context.Context, name string, args ...string) Result {
		// The Runner's context is imposed by us: the caller's ctx may
		// be cancelled by a signal and we want a hard per-command
		// timeout on top.
		cctx, cancel := context.WithTimeout(ctx, timeout)
		defer cancel()

		cmd := exec.CommandContext(cctx, name, args...)
		out, err := cmd.Output() // stdout; stderr goes to /dev/null
		if err == nil {
			return Result{Stdout: string(out), ExitCode: 0}
		}
		// If the context expired it was timeout or cancel: we cannot
		// get a reliable exit code (the process was killed).
		if cerr := cctx.Err(); cerr != nil {
			return Result{ExitCode: -1, Err: fmt.Errorf("%w", cerr)}
		}
		// The process ran and exited != 0: reliable exit code and
		// Err = nil — this is the CONTRACT stated on Result and what
		// every collector is written against ("the command failed" is
		// mappable via ExitCode; Err means "we could not measure").
		// Review finding 2026-06-03: this returned Err here, so with
		// the real Runner a `curl` exit 6 (egress DOWN) or an
		// `is-active` exit 3 (unit down) collapsed into unknown —
		// fake-based tests (Err=nil) masked it.
		var ee *exec.ExitError
		if errors.As(err, &ee) {
			return Result{Stdout: string(out), ExitCode: ee.ExitCode()}
		}
		// Other error: binary not found, EACCES, etc.
		return Result{ExitCode: -1, Err: err}
	}
}

// Package run is the testability seam for exec.Command.
//
// Every lxc/git command dev-run launches goes through here: in
// production it uses Real, in tests a fake is injected that returns
// stdout/exit from a table. No caller touches exec.Command directly,
// so the whole logic is tested without a host, in milliseconds.
//
// This is a deliberate COPY of infra/resourced/internal/run (separate
// modules must not import each other), including the 2026-06-03 review
// fix: a clean non-zero exit returns Err = nil — failures the process
// itself reports are mapped via ExitCode; Err is reserved for "we
// could not run it" (timeout, missing binary, EACCES).
package run

import (
	"context"
	"errors"
	"fmt"
	"os/exec"
	"time"
)

// DefaultTimeout is the per-command timeout Real applies if the caller
// does not pass one. lxc start of a cold container can take a few
// seconds; 30s leaves slack without letting a hung lxd stall forever.
const DefaultTimeout = 30 * time.Second

// Result is the outcome of a command run by a Runner. ExitCode is -1
// if the process never started. Err describes why; nil if the process
// ran, EVEN when exit != 0.
type Result struct {
	Stdout   string
	ExitCode int
	Err      error
}

// Runner executes a command and returns its result. The testability
// seam: tests inject a Runner backed by a table (or a stateful fake).
type Runner func(ctx context.Context, name string, args ...string) Result

// Real returns a Runner that executes with exec.CommandContext and a
// hard per-command timeout. stderr is discarded (callers map outcomes
// from exit codes and stdout).
func Real(timeout time.Duration) Runner {
	if timeout <= 0 {
		timeout = DefaultTimeout
	}
	return func(ctx context.Context, name string, args ...string) Result {
		cctx, cancel := context.WithTimeout(ctx, timeout)
		defer cancel()

		cmd := exec.CommandContext(cctx, name, args...)
		out, err := cmd.Output()
		if err == nil {
			return Result{Stdout: string(out), ExitCode: 0}
		}
		if cerr := cctx.Err(); cerr != nil {
			return Result{ExitCode: -1, Err: fmt.Errorf("%w", cerr)}
		}
		// Clean non-zero exit: reliable code, Err nil (the contract).
		var ee *exec.ExitError
		if errors.As(err, &ee) {
			return Result{Stdout: string(out), ExitCode: ee.ExitCode()}
		}
		return Result{ExitCode: -1, Err: err}
	}
}

package collect

import (
	"context"
	"errors"
	"testing"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/run"
)

const lxdJSON = `[
  {"name": "laia-agora", "status": "Running"},
  {"name": "laia-dev", "status": "Running"},
  {"name": "laia-edge", "status": "Stopped"}
]`

func TestLXCStatesOK(t *testing.T) {
	r := func(_ context.Context, name string, args ...string) run.Result {
		if name != "lxc" {
			return run.Result{ExitCode: -1, Err: errCmd(name)}
		}
		return run.Result{ExitCode: 0, Stdout: lxdJSON}
	}
	got, err := LXCStates(testCtx(), r)
	if err != nil {
		t.Fatalf("LXCStates: %v", err)
	}
	if len(got) != 3 {
		t.Fatalf("got %d entries, want 3", len(got))
	}
	if got["laia-agora"] != "Running" {
		t.Errorf("laia-agora: %q", got["laia-agora"])
	}
	if got["laia-edge"] != "Stopped" {
		t.Errorf("laia-edge: %q", got["laia-edge"])
	}
}

func TestLXCStatesExitError(t *testing.T) {
	r := func(_ context.Context, name string, args ...string) run.Result {
		return run.Result{ExitCode: 1}
	}
	_, err := LXCStates(testCtx(), r)
	if err == nil {
		t.Errorf("expected error for non-zero exit")
	}
}

func TestLXCStatesBadJSON(t *testing.T) {
	r := func(_ context.Context, name string, args ...string) run.Result {
		return run.Result{ExitCode: 0, Stdout: "not json"}
	}
	_, err := LXCStates(testCtx(), r)
	if err == nil {
		t.Errorf("expected parse error")
	}
}

func TestLXCStatesNoRunner(t *testing.T) {
	if _, err := LXCStates(testCtx(), nil); err == nil {
		t.Errorf("expected error for nil runner")
	}
}

func errCmd(name string) error { return errors.New("unexpected cmd: " + name) }

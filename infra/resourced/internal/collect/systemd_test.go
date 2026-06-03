package collect

import (
	"context"
	"errors"
	"testing"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/run"
)

// runTable dispatches a Runner from a table keyed by command name.
type runTable map[string]run.Result

func (t runTable) runner() run.Runner {
	return func(_ context.Context, name string, args ...string) run.Result {
		if r, ok := t[name]; ok {
			return r
		}
		return run.Result{ExitCode: -1, Err: errors.New("unexpected cmd: " + name)}
	}
}

func TestSystemdActiveTabla(t *testing.T) {
	cases := []struct {
		name string
		res  run.Result
		want string
	}{
		{"exit 0 → ok", run.Result{ExitCode: 0, Stdout: "active"}, "ok"},
		{"exit 3 (inactive) → down", run.Result{ExitCode: 3, Stdout: "inactive"}, "down"},
		{"exit 4 (failed) → down", run.Result{ExitCode: 4, Stdout: "failed"}, "down"},
		{"exit 1 (not found) → unknown", run.Result{ExitCode: 1, Stdout: "inactive"}, "unknown"},
		{"exit 2 (invalid) → unknown", run.Result{ExitCode: 2}, "unknown"},
		{"runner timeout → unknown (err logged, not bubbled as fatal)", run.Result{Err: errors.New("timeout")}, "unknown"},
		{"runner binary not found → unknown (err logged, not bubbled as fatal)", run.Result{Err: errors.New("not found")}, "unknown"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			r := runTable{"systemctl": c.res}.runner()
			got, _ := SystemdActive(testCtx(), r, "tts-server.service")
			if got != c.want {
				t.Errorf("got %q want %q", got, c.want)
			}
		})
	}
}

func TestLXCSystemdActiveNoRunning(t *testing.T) {
	// Container is Stopped → must NOT call lxc.
	calls := 0
	r := func(_ context.Context, name string, args ...string) run.Result {
		calls++
		return run.Result{ExitCode: 0, Stdout: "active"}
	}
	got, err := LXCSystemdActive(testCtx(), r, "laia-edge", "cloudflared.service", "Stopped")
	if err != nil {
		t.Fatal(err)
	}
	if got != "unknown" {
		t.Errorf("got %q want unknown (container stopped)", got)
	}
	if calls != 0 {
		t.Errorf("lxc must NOT be called when container is not Running; got %d calls", calls)
	}
}

func TestLXCSystemdActiveRunning(t *testing.T) {
	r := runTable{"lxc": {ExitCode: 0, Stdout: "active"}}.runner()
	got, _ := LXCSystemdActive(testCtx(), r, "laia-edge", "cloudflared.service", "Running")
	if got != "ok" {
		t.Errorf("got %q want ok", got)
	}
}

func TestLXCSystemdActiveDownInRunningContainer(t *testing.T) {
	// cloudflared service is failed inside laia-edge (Running) → down.
	r := runTable{"lxc": {ExitCode: 4, Stdout: "failed"}}.runner()
	got, _ := LXCSystemdActive(testCtx(), r, "laia-edge", "cloudflared.service", "Running")
	if got != "down" {
		t.Errorf("got %q want down", got)
	}
}

package collect

import (
	"context"
	"errors"
	"testing"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/run"
)

// fakeRunner returns a Result by command name. The key is `name`
// ("lxc", "/bin/echo"...). Anything not in the table → the test fails
// (we do not want fake Runners that "swallow" commands silently).
type fakeRunner map[string]run.Result

func (f fakeRunner) runner() run.Runner {
	return func(_ context.Context, name string, args ...string) run.Result {
		r, ok := f[name]
		if !ok {
			return run.Result{ExitCode: -1, Err: errors.New("fakeRunner: command not in table: " + name)}
		}
		return r
	}
}

// TestEgressProbeTable: COMPLETE coverage of the §S1 table. Each row
// is a real scenario an operator will see in production.
func TestEgressProbeTable(t *testing.T) {
	cases := []struct {
		name      string
		res       run.Result
		container string
		want      ProbeOutcome
	}{
		// --- ProbeOK ---
		{"exit 0 + HTTP 200", run.Result{ExitCode: 0, Stdout: "200"}, "laia-edge", ProbeOK},
		{"exit 0 + HTTP 301 (redirect)", run.Result{ExitCode: 0, Stdout: "301"}, "laia-edge", ProbeOK},
		{"exit 0 + HTTP 404 (mirror responded)", run.Result{ExitCode: 0, Stdout: "404"}, "laia-edge", ProbeOK},
		{"exit 0 + HTTP 503 (mirror responded)", run.Result{ExitCode: 0, Stdout: "503"}, "laia-edge", ProbeOK},
		{"exit 0 + stdout with whitespace", run.Result{ExitCode: 0, Stdout: "  200\n"}, "laia-edge", ProbeOK},

		// --- ProbeDown (curl exit 6, 7, 28, 35) ---
		{"curl exit 6 (no DNS)", run.Result{ExitCode: 6}, "laia-edge", ProbeDown},
		{"curl exit 7 (connect refused)", run.Result{ExitCode: 7}, "laia-edge", ProbeDown},
		{"curl exit 28 (timeout)", run.Result{ExitCode: 28}, "laia-edge", ProbeDown},
		{"curl exit 35 (TLS handshake)", run.Result{ExitCode: 35}, "laia-edge", ProbeDown},

		// --- ProbeBroken ---
		{"curl exit 127 (not installed)", run.Result{ExitCode: 127}, "laia-edge", ProbeBroken},
		{"exit 1 (rare)", run.Result{ExitCode: 1}, "laia-edge", ProbeBroken},
		{"exit 5 (rare)", run.Result{ExitCode: 5}, "laia-edge", ProbeBroken},
		{"Runner timeout (Err)", run.Result{Err: errors.New("timeout")}, "laia-edge", ProbeBroken},
		{"Runner binary not found (Err)", run.Result{Err: errors.New("not found")}, "laia-edge", ProbeBroken},
		{"exit 0 code 0 (rare)", run.Result{ExitCode: 0, Stdout: "0"}, "laia-edge", ProbeBroken},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			r := fakeRunner{"lxc": c.res}.runner()
			got := Probe(testCtx(), r, c.container, "http://x")
			if got.Outcome != c.want {
				t.Errorf("Outcome: got %v want %v (Detail: %q)", got.Outcome, c.want, got.Detail)
			}
		})
	}
}

// TestProbeNoRunner: if the caller passes nil, do not crash — return
// Broken. This protects a collector that initializes without DI in an
// error path.
func TestProbeNoRunner(t *testing.T) {
	got := Probe(testCtx(), nil, "laia-edge", "http://x")
	if got.Outcome != ProbeBroken {
		t.Errorf("Outcome: got %v want Broken", got.Outcome)
	}
}

func testCtx() context.Context { return context.Background() }

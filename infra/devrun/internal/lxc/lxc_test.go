package lxc

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"

	"github.com/JorgeMP-3/laia-arch/infra/devrun/internal/run"
)

func testCtx() context.Context { return context.Background() }

// fakeRunner records every invocation and returns results from a
// script (one Result per call, in order). Stateful on purpose:
// WaitReady and the idempotent paths need call sequences, not a
// static table.
type fakeRunner struct {
	calls   [][]string
	script  []run.Result
	fallbck run.Result
}

func (f *fakeRunner) runner() run.Runner {
	return func(_ context.Context, name string, args ...string) run.Result {
		f.calls = append(f.calls, append([]string{name}, args...))
		if len(f.script) > 0 {
			r := f.script[0]
			f.script = f.script[1:]
			return r
		}
		return f.fallbck
	}
}

func (f *fakeRunner) joined() []string {
	out := make([]string, len(f.calls))
	for i, c := range f.calls {
		out[i] = strings.Join(c, " ")
	}
	return out
}

const listJSON = `[
  {"name":"laia-test","status":"Stopped","type":"container"},
  {"name":"laia-dev","status":"Running","type":"virtual-machine"},
  {"name":"laia-finance","status":"Running","type":"container"}
]`

func TestListParsesInstances(t *testing.T) {
	f := &fakeRunner{script: []run.Result{{Stdout: listJSON}}}
	m, err := List(testCtx(), f.runner())
	if err != nil {
		t.Fatal(err)
	}
	if m["laia-test"].Status != "Stopped" || !m["laia-test"].IsContainer() {
		t.Errorf("laia-test: %+v", m["laia-test"])
	}
	if m["laia-dev"].IsContainer() {
		t.Errorf("laia-dev must be a VM")
	}
}

func TestListErrors(t *testing.T) {
	cases := []struct {
		name string
		res  run.Result
	}{
		{"runner error", run.Result{ExitCode: -1, Err: errors.New("no lxc")}},
		{"non-zero exit", run.Result{ExitCode: 1}},
		{"bad json", run.Result{Stdout: "{nope"}},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			f := &fakeRunner{script: []run.Result{c.res}}
			if _, err := List(testCtx(), f.runner()); err == nil {
				t.Errorf("expected error")
			}
		})
	}
}

// shift=true ONLY on containers; never on VMs (virtiofs). Verified on
// the host 2026-06-03 — this is the regression test for that fact.
func TestDeviceAddShiftOnlyContainers(t *testing.T) {
	cont := Instance{Name: "laia-test", Type: "container"}
	vm := Instance{Name: "laia-dev", Type: "virtual-machine"}

	f := &fakeRunner{}
	if err := DeviceAdd(testCtx(), f.runner(), cont, "d", "/src", "/mnt/p"); err != nil {
		t.Fatal(err)
	}
	if got := f.joined()[0]; !strings.Contains(got, "shift=true") {
		t.Errorf("container add must carry shift=true: %q", got)
	}

	f = &fakeRunner{}
	if err := DeviceAdd(testCtx(), f.runner(), vm, "d", "/src", "/mnt/p"); err != nil {
		t.Fatal(err)
	}
	if got := f.joined()[0]; strings.Contains(got, "shift") {
		t.Errorf("VM add must NOT carry shift: %q", got)
	}
}

func TestDeviceRemoveIdempotent(t *testing.T) {
	// Device not present → only the list call, no remove, no error.
	f := &fakeRunner{script: []run.Result{{Stdout: "root\nother\n"}}}
	if err := DeviceRemove(testCtx(), f.runner(), "laia-test", "devrun-x"); err != nil {
		t.Fatal(err)
	}
	if len(f.calls) != 1 {
		t.Errorf("expected 1 call (list only), got %v", f.joined())
	}

	// Device present → list + remove.
	f = &fakeRunner{script: []run.Result{{Stdout: "root\ndevrun-x\n"}, {}}}
	if err := DeviceRemove(testCtx(), f.runner(), "laia-test", "devrun-x"); err != nil {
		t.Fatal(err)
	}
	if len(f.calls) != 2 || !strings.Contains(f.joined()[1], "device remove laia-test devrun-x") {
		t.Errorf("calls: %v", f.joined())
	}
}

func TestWaitReadyPollsUntilOK(t *testing.T) {
	// Fails twice (agent booting), then succeeds. Sleep is injected.
	f := &fakeRunner{script: []run.Result{
		{ExitCode: 1}, {ExitCode: -1, Err: errors.New("agent down")}, {ExitCode: 0},
	}}
	slept := 0
	err := WaitReady(testCtx(), f.runner(), "laia-dev", 5, time.Second, func(time.Duration) { slept++ })
	if err != nil {
		t.Fatal(err)
	}
	if len(f.calls) != 3 || slept != 2 {
		t.Errorf("calls=%d slept=%d", len(f.calls), slept)
	}
}

func TestWaitReadyGivesUp(t *testing.T) {
	f := &fakeRunner{fallbck: run.Result{ExitCode: 1}}
	err := WaitReady(testCtx(), f.runner(), "laia-test", 3, time.Second, func(time.Duration) {})
	if err == nil {
		t.Fatal("expected give-up error")
	}
	if len(f.calls) != 3 {
		t.Errorf("expected exactly 3 attempts, got %d", len(f.calls))
	}
}

func TestStartStopErrors(t *testing.T) {
	f := &fakeRunner{script: []run.Result{{ExitCode: 1}}}
	if err := Start(testCtx(), f.runner(), "laia-test"); err == nil {
		t.Error("start: expected error on exit 1")
	}
	f = &fakeRunner{script: []run.Result{{ExitCode: 0}}}
	if err := Stop(testCtx(), f.runner(), "laia-test"); err != nil {
		t.Errorf("stop: %v", err)
	}
}

package devmode

import (
	"strings"
	"testing"

	"github.com/JorgeMP-3/laia-arch/infra/devrun/internal/run"
)

func TestStatusRendersAndExitCodes(t *testing.T) {
	c := cfg(t) // odoo→laia-test (exists), evil→laia-finance (exists)
	var s [][]string
	f := &fakeRunner{
		script: map[string][]run.Result{
			"lxc list --format": {{Stdout: listRunning}},
		},
		// device list per target: odoo's mount attached on laia-test
		deflt: run.Result{Stdout: "root\ndevrun-odoo\n"},
	}
	d := deps(c, f, &s, false)
	out, code := d.Status(testCtx())
	if code != 0 {
		t.Fatalf("exit: got %d want 0\n%s", code, out)
	}
	for _, want := range []string{"PROYECTO", "odoo", "laia-test", "Running", "sí", "jaula dev: laia-dev, laia-test"} {
		if !strings.Contains(out, want) {
			t.Errorf("missing %q in:\n%s", want, out)
		}
	}
}

func TestStatusMissingTargetExit2(t *testing.T) {
	c := cfg(t)
	var s [][]string
	f := &fakeRunner{
		script: map[string][]run.Result{
			// only laia-finance exists; laia-test (odoo's target) missing
			"lxc list --format": {{Stdout: `[{"name":"laia-finance","status":"Running","type":"container"}]`}},
		},
		deflt: run.Result{Stdout: ""},
	}
	d := deps(c, f, &s, false)
	out, code := d.Status(testCtx())
	if code != 2 {
		t.Fatalf("exit: got %d want 2 (config drift)\n%s", code, out)
	}
	if !strings.Contains(out, "NO EXISTE") {
		t.Errorf("missing NO EXISTE marker:\n%s", out)
	}
}

func TestStatusLXDDownExit2(t *testing.T) {
	c := cfg(t)
	var s [][]string
	f := &fakeRunner{deflt: run.Result{ExitCode: -1, Err: errTest}}
	d := deps(c, f, &s, false)
	out, code := d.Status(testCtx())
	if code != 2 || !strings.Contains(out, "LXD") {
		t.Errorf("exit=%d out=%q", code, out)
	}
}

var errTest = errFake("lxd down")

type errFake string

func (e errFake) Error() string { return string(e) }

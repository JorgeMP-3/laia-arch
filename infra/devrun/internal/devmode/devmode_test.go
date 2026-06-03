package devmode

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/JorgeMP-3/laia-arch/infra/devrun/internal/config"
	"github.com/JorgeMP-3/laia-arch/infra/devrun/internal/lxc"
	"github.com/JorgeMP-3/laia-arch/infra/devrun/internal/run"
)

func testCtx() context.Context { return context.Background() }

// cfg builds a hand-made Config (bypassing Validate on purpose: the
// runtime cage must hold even for configs that never saw Validate).
func cfg(t *testing.T) *config.Config {
	t.Helper()
	return &config.Config{
		DevInstances: []string{"laia-test", "laia-dev"},
		Projects: map[string]config.Project{
			"odoo": {Source: t.TempDir(), DevTarget: "laia-test",
				MountPath: "/mnt/proyecto", TestCmd: "run-tests"},
			"evil": {Source: t.TempDir(), DevTarget: "laia-finance", // NOT whitelisted
				MountPath: "/mnt/x"},
		},
	}
}

// scripted fake runner (same shape as the lxc package tests).
type fakeRunner struct {
	calls  [][]string
	script map[string][]run.Result // key: first 3 tokens joined
	deflt  run.Result
}

func key(name string, args ...string) string {
	all := append([]string{name}, args...)
	if len(all) > 3 {
		all = all[:3]
	}
	return strings.Join(all, " ")
}

func (f *fakeRunner) runner() run.Runner {
	return func(_ context.Context, name string, args ...string) run.Result {
		f.calls = append(f.calls, append([]string{name}, args...))
		k := key(name, args...)
		if rs, ok := f.script[k]; ok && len(rs) > 0 {
			r := rs[0]
			f.script[k] = rs[1:]
			return r
		}
		return f.deflt
	}
}

func (f *fakeRunner) joined() string {
	var b strings.Builder
	for _, c := range f.calls {
		b.WriteString(strings.Join(c, " "))
		b.WriteString("\n")
	}
	return b.String()
}

const listRunning = `[{"name":"laia-test","status":"Running","type":"container"},
{"name":"laia-dev","status":"Running","type":"virtual-machine"},
{"name":"laia-finance","status":"Running","type":"container"}]`

const listStopped = `[{"name":"laia-test","status":"Stopped","type":"container"}]`

func deps(c *config.Config, f *fakeRunner, streamed *[][]string, dry bool) *Deps {
	return &Deps{
		Cfg: c,
		R:   f.runner(),
		Stream: func(name string, args ...string) int {
			*streamed = append(*streamed, append([]string{name}, args...))
			return 0
		},
		DryRun: dry,
		Sleep:  func(time.Duration) {},
	}
}

// THE cage: every dev-mode entry point refuses non-whitelisted targets
// and the message points to deploy. Spec §8(1): inviolable from every
// subcommand.
func TestCageRefusesProdFromEverywhere(t *testing.T) {
	c := cfg(t)
	p := c.Projects["evil"]
	var streamed [][]string
	f := &fakeRunner{deflt: run.Result{Stdout: listRunning}}
	d := deps(c, f, &streamed, false)

	checks := map[string]func() error{
		"EnsureUp":    func() error { _, err := d.EnsureUp(testCtx(), "laia-finance"); return err },
		"EnsureMount": func() error { return d.EnsureMount(testCtx(), "evil", p, instOf("laia-finance")) },
		"Unmount":     func() error { return d.Unmount(testCtx(), "evil", p) },
		"StopTarget":  func() error { return d.StopTarget(testCtx(), p) },
		"RunIn":       func() error { _, err := d.RunIn(testCtx(), "evil", p, "x"); return err },
		"Shell":       func() error { _, err := d.Shell(testCtx(), "evil", p); return err },
	}
	for name, fn := range checks {
		t.Run(name, func(t *testing.T) {
			err := fn()
			if err == nil {
				t.Fatalf("%s: expected cage refusal", name)
			}
			if !strings.Contains(err.Error(), "deploy") {
				t.Errorf("%s: refusal must point to deploy: %v", name, err)
			}
		})
	}
	if len(streamed) != 0 {
		t.Errorf("nothing must ever stream into a prod target: %v", streamed)
	}
	for _, call := range f.calls {
		j := strings.Join(call, " ")
		if strings.Contains(j, "start") || strings.Contains(j, "device add") ||
			strings.Contains(j, "stop") || strings.Contains(j, "exec") {
			t.Errorf("mutating lxc verb reached the runner on a caged path: %q", j)
		}
	}
}

func instOf(name string) lxc.Instance {
	return lxc.Instance{Name: name, Status: "Running", Type: "container"}
}

func TestEnsureUpStartsStoppedAndWaits(t *testing.T) {
	c := cfg(t)
	var streamed [][]string
	f := &fakeRunner{
		script: map[string][]run.Result{
			"lxc list --format":  {{Stdout: listStopped}},
			"lxc exec laia-test": {{ExitCode: 1}, {ExitCode: 0}}, // agent: fail once, then ready
		},
		deflt: run.Result{ExitCode: 0},
	}
	d := deps(c, f, &streamed, false)
	if _, err := d.EnsureUp(testCtx(), "laia-test"); err != nil {
		t.Fatal(err)
	}
	j := f.joined()
	if !strings.Contains(j, "lxc start laia-test") {
		t.Errorf("expected lxc start, calls:\n%s", j)
	}
	if strings.Count(j, "lxc exec laia-test -- true") != 2 {
		t.Errorf("expected 2 readiness polls, calls:\n%s", j)
	}
}

func TestEnsureUpRunningDoesNotStart(t *testing.T) {
	c := cfg(t)
	var streamed [][]string
	f := &fakeRunner{deflt: run.Result{Stdout: listRunning}}
	d := deps(c, f, &streamed, false)
	if _, err := d.EnsureUp(testCtx(), "laia-test"); err != nil {
		t.Fatal(err)
	}
	if strings.Contains(f.joined(), "lxc start") {
		t.Errorf("must not start a running instance:\n%s", f.joined())
	}
}

func TestRunInFullPipelineAndCwd(t *testing.T) {
	c := cfg(t)
	p := c.Projects["odoo"]
	var streamed [][]string
	f := &fakeRunner{
		script: map[string][]run.Result{
			"lxc list --format": {{Stdout: listRunning}},
			"lxc config device": {{Stdout: "root\n"}}, // not mounted yet → add
		},
		deflt: run.Result{ExitCode: 0},
	}
	d := deps(c, f, &streamed, false)
	code, err := d.RunIn(testCtx(), "odoo", p, "run-tests")
	if err != nil || code != 0 {
		t.Fatalf("code=%d err=%v", code, err)
	}
	if !strings.Contains(f.joined(), "device add laia-test devrun-odoo disk source="+p.Source) {
		t.Errorf("mount missing/wrong:\n%s", f.joined())
	}
	if len(streamed) != 1 {
		t.Fatalf("expected 1 streamed exec, got %v", streamed)
	}
	got := strings.Join(streamed[0], " ")
	want := "lxc exec laia-test --cwd /mnt/proyecto -- sh -c run-tests"
	if got != want {
		t.Errorf("exec:\n got  %q\n want %q", got, want)
	}
}

func TestRunInPropagatesExitCode(t *testing.T) {
	c := cfg(t)
	p := c.Projects["odoo"]
	var streamed [][]string
	f := &fakeRunner{
		script: map[string][]run.Result{
			"lxc list --format": {{Stdout: listRunning}},
			"lxc config device": {{Stdout: "devrun-odoo\n"}}, // already mounted
		},
		deflt: run.Result{ExitCode: 0},
	}
	d := deps(c, f, &streamed, false)
	d.Stream = func(string, ...string) int { return 7 }
	code, err := d.RunIn(testCtx(), "odoo", p, "run-tests")
	if err != nil {
		t.Fatal(err)
	}
	if code != 7 {
		t.Errorf("exit code: got %d want 7 (agents script against this)", code)
	}
}

func TestEnsureMountIdempotent(t *testing.T) {
	c := cfg(t)
	p := c.Projects["odoo"]
	var streamed [][]string
	f := &fakeRunner{
		script: map[string][]run.Result{
			"lxc config device": {{Stdout: "root\ndevrun-odoo\n"}},
		},
		deflt: run.Result{ExitCode: 0},
	}
	d := deps(c, f, &streamed, false)
	if err := d.EnsureMount(testCtx(), "odoo", p, instOf("laia-test")); err != nil {
		t.Fatal(err)
	}
	if strings.Contains(f.joined(), "device add") {
		t.Errorf("already mounted: must not add again:\n%s", f.joined())
	}
}

// --dry-run: NOTHING mutating reaches the runner, the streamer is
// never called (spec §8(3): test that fails on mutating verbs).
func TestDryRunNeverMutates(t *testing.T) {
	c := cfg(t)
	p := c.Projects["odoo"]
	var streamed [][]string
	f := &fakeRunner{
		script: map[string][]run.Result{
			"lxc list --format": {{Stdout: listStopped}},
			"lxc config device": {{Stdout: "root\n"}},
		},
		deflt: run.Result{ExitCode: 0},
	}
	d := deps(c, f, &streamed, true)

	if _, err := d.RunIn(testCtx(), "odoo", p, "run-tests"); err != nil {
		t.Fatal(err)
	}
	if err := d.Unmount(testCtx(), "odoo", p); err != nil {
		t.Fatal(err)
	}
	if err := d.StopTarget(testCtx(), p); err != nil {
		t.Fatal(err)
	}

	if len(streamed) != 0 {
		t.Errorf("dry-run streamed something: %v", streamed)
	}
	for _, call := range f.calls {
		j := strings.Join(call, " ")
		for _, verb := range []string{"start", "device add", "device remove", "stop", "file push"} {
			if strings.Contains(j, verb) {
				t.Errorf("dry-run reached mutating verb %q: %q", verb, j)
			}
		}
	}
}

func TestProjectUnknownListsNames(t *testing.T) {
	c := cfg(t)
	var streamed [][]string
	d := deps(c, &fakeRunner{}, &streamed, false)
	_, err := d.Project("nope")
	if err == nil || !strings.Contains(err.Error(), "evil, odoo") {
		t.Errorf("error must list defined projects sorted: %v", err)
	}
}

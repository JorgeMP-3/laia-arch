package deploy

import (
	"context"
	"strings"
	"testing"

	"github.com/JorgeMP-3/laia-arch/infra/devrun/internal/config"
	"github.com/JorgeMP-3/laia-arch/infra/devrun/internal/run"
)

func testCtx() context.Context { return context.Background() }

// seqRunner returns scripted results IN CALL ORDER and records calls.
type seqRunner struct {
	calls  [][]string
	script []run.Result
	deflt  run.Result
}

func (f *seqRunner) runner() run.Runner {
	return func(_ context.Context, name string, args ...string) run.Result {
		f.calls = append(f.calls, append([]string{name}, args...))
		if len(f.script) > 0 {
			r := f.script[0]
			f.script = f.script[1:]
			return r
		}
		return f.deflt
	}
}

func (f *seqRunner) joined() string {
	var b strings.Builder
	for _, c := range f.calls {
		b.WriteString(strings.Join(c, " "))
		b.WriteString("\n")
	}
	return b.String()
}

func project(t *testing.T) config.Project {
	t.Helper()
	return config.Project{
		Source:     t.TempDir(),
		DevTarget:  "laia-test",
		MountPath:  "/mnt/p",
		ProdTarget: "laia-finance",
		DeployCmd:  "bin/deploy.sh",
	}
}

func cfg() *config.Config {
	return &config.Config{DevInstances: []string{"laia-test", "laia-dev"}}
}

// gitOK are the 5 read-only precondition results, in call order:
// status --porcelain (clean), branch (main), HEAD, origin/main (equal),
// short sha.
func gitOK() []run.Result {
	return []run.Result{
		{Stdout: ""},        // porcelain: clean
		{Stdout: "main"},    // branch
		{Stdout: "aaaa111"}, // HEAD
		{Stdout: "aaaa111"}, // origin/main
		{Stdout: "ab12cd3"}, // short sha
	}
}

func deps(f *seqRunner, in string, tty bool, dry bool, streamed *[][]string, code int) *Deps {
	return &Deps{
		Cfg: cfg(),
		R:   f.runner(),
		Stream: func(name string, args ...string) int {
			*streamed = append(*streamed, append([]string{name}, args...))
			return code
		},
		In:     strings.NewReader(in),
		Out:    &strings.Builder{},
		DryRun: dry,
		IsTTY:  func() bool { return tty },
		TmpDir: "",
	}
}

func TestDeployRefusesWithoutProdTarget(t *testing.T) {
	p := project(t)
	p.ProdTarget = ""
	var s [][]string
	_, err := Run(testCtx(), deps(&seqRunner{}, "", true, false, &s, 0), "odoo", p, "")
	if err == nil || !strings.Contains(err.Error(), "prod_target") {
		t.Fatalf("expected prod_target refusal, got %v", err)
	}
}

func TestDeployRefusesProdInsideCage(t *testing.T) {
	p := project(t)
	p.ProdTarget = "laia-test" // inside dev_instances → inconsistent
	var s [][]string
	_, err := Run(testCtx(), deps(&seqRunner{}, "", true, false, &s, 0), "odoo", p, "")
	if err == nil || !strings.Contains(err.Error(), "dev_instances") {
		t.Fatalf("expected cage-consistency refusal, got %v", err)
	}
}

func TestDeployPreconditionsTable(t *testing.T) {
	cases := []struct {
		name    string
		script  []run.Result
		wantErr string
	}{
		{"dirty tree", []run.Result{{Stdout: " M x.py"}}, "sin commitear"},
		{"wrong branch", []run.Result{{Stdout: ""}, {Stdout: "wip/x"}}, "desde main"},
		{"unpushed", []run.Result{{Stdout: ""}, {Stdout: "main"}, {Stdout: "aaa"}, {Stdout: "bbb"}}, "origin/main"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			var s [][]string
			f := &seqRunner{script: c.script}
			_, err := Run(testCtx(), deps(f, "", true, false, &s, 0), "odoo", project(t), "")
			if err == nil || !strings.Contains(err.Error(), c.wantErr) {
				t.Fatalf("got %v, want contains %q", err, c.wantErr)
			}
			if len(s) != 0 {
				t.Errorf("precondition failure must never reach the switch: %v", s)
			}
		})
	}
}

func TestDeployHappyPath(t *testing.T) {
	var s [][]string
	script := append(gitOK(),
		run.Result{ExitCode: 1}, // test -d release dir → missing
		run.Result{},            // git archive
		run.Result{},            // mkdir -p
		run.Result{},            // lxc file push
		run.Result{},            // tar -xzf && rm
	)
	f := &seqRunner{script: script}
	d := deps(f, "laia-finance\n", true, false, &s, 0)
	code, err := Run(testCtx(), d, "odoo", project(t), "")
	if err != nil || code != 0 {
		t.Fatalf("code=%d err=%v", code, err)
	}
	j := f.joined()
	for _, want := range []string{
		"git -C", "archive --format=tar.gz",
		"lxc exec laia-finance -- mkdir -p /srv/deploy/odoo/ab12cd3",
		"lxc file push",
		"tar -xzf /srv/deploy/odoo/ab12cd3.tar.gz -C /srv/deploy/odoo/ab12cd3",
	} {
		if !strings.Contains(j, want) {
			t.Errorf("missing %q in:\n%s", want, j)
		}
	}
	if len(s) != 1 {
		t.Fatalf("expected exactly 1 switch exec, got %v", s)
	}
	sw := strings.Join(s[0], " ")
	if !strings.Contains(sw, "--env DEVRUN_RELEASE_DIR=/srv/deploy/odoo/ab12cd3") ||
		!strings.Contains(sw, "sh -c bin/deploy.sh") || !strings.Contains(sw, "lxc exec laia-finance") {
		t.Errorf("switch exec wrong: %q", sw)
	}
}

func TestDeployWrongConfirmationAborts(t *testing.T) {
	var s [][]string
	script := append(gitOK(), run.Result{ExitCode: 1}, run.Result{}, run.Result{}, run.Result{}, run.Result{})
	f := &seqRunner{script: script}
	_, err := Run(testCtx(), deps(f, "laia-typo\n", true, false, &s, 0), "odoo", project(t), "")
	if err == nil || !strings.Contains(err.Error(), "abortado") {
		t.Fatalf("expected abort, got %v", err)
	}
	if len(s) != 0 {
		t.Errorf("wrong confirmation must never switch: %v", s)
	}
}

func TestDeployNoTTYRefuses(t *testing.T) {
	var s [][]string
	script := append(gitOK(), run.Result{ExitCode: 1}, run.Result{}, run.Result{}, run.Result{}, run.Result{})
	f := &seqRunner{script: script}
	_, err := Run(testCtx(), deps(f, "laia-finance\n", false, false, &s, 0), "odoo", project(t), "")
	if err == nil || !strings.Contains(err.Error(), "desatendido") {
		t.Fatalf("expected TTY refusal, got %v", err)
	}
	if len(s) != 0 {
		t.Errorf("no-TTY must never switch: %v", s)
	}
}

// --sha with the release dir already present: skips PREPARE entirely
// (rollback path) and goes straight to confirm+switch.
func TestDeploySHARollbackSkipsPrepare(t *testing.T) {
	var s [][]string
	f := &seqRunner{script: []run.Result{{ExitCode: 0}}} // test -d → exists
	code, err := Run(testCtx(), deps(f, "laia-finance\n", true, false, &s, 0), "odoo", project(t), "old1234")
	if err != nil || code != 0 {
		t.Fatalf("code=%d err=%v", code, err)
	}
	j := f.joined()
	for _, banned := range []string{"archive", "mkdir", "file push", "tar -xzf", "git"} {
		if strings.Contains(j, banned) {
			t.Errorf("rollback must skip prepare (%q found):\n%s", banned, j)
		}
	}
	if len(s) != 1 || !strings.Contains(strings.Join(s[0], " "), "DEVRUN_RELEASE_DIR=/srv/deploy/odoo/old1234") {
		t.Errorf("switch with wrong release dir: %v", s)
	}
}

func TestDeployExitCodePropagates(t *testing.T) {
	var s [][]string
	f := &seqRunner{script: []run.Result{{ExitCode: 0}}}
	code, err := Run(testCtx(), deps(f, "laia-finance\n", true, false, &s, 9), "odoo", project(t), "old1234")
	if err != nil {
		t.Fatal(err)
	}
	if code != 9 {
		t.Errorf("deploy_cmd exit must propagate: got %d want 9", code)
	}
}

// dry-run: read-only git preconditions may run; NOTHING mutating does
// (no archive/mkdir/push/untar), no prompt, no switch.
func TestDeployDryRunNeverMutates(t *testing.T) {
	var s [][]string
	script := append(gitOK(), run.Result{ExitCode: 1}) // exists-check: missing
	f := &seqRunner{script: script}
	code, err := Run(testCtx(), deps(f, "", false /*no TTY: must not matter*/, true, &s, 0), "odoo", project(t), "")
	if err != nil || code != 0 {
		t.Fatalf("code=%d err=%v", code, err)
	}
	j := f.joined()
	for _, banned := range []string{"archive", "mkdir", "file push", "tar -xzf"} {
		if strings.Contains(j, banned) {
			t.Errorf("dry-run reached mutating step %q:\n%s", banned, j)
		}
	}
	if len(s) != 0 {
		t.Errorf("dry-run must never switch: %v", s)
	}
}

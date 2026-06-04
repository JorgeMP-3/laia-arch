package collect

import (
	"context"
	"errors"
	"strings"
	"testing"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/run"
)

// Real fixture for a laia-dev VM that has no user session, idle CPU,
// and only outgoing connections on 10.123.x (the VM's own interface
// for things like apt updates, snap refresh, etc.). The tailscale
// daemon is also off (no 100.x conns).
const idleFixture = `user1 tty1         2026-06-03 09:00
# users=0
---
0.12 0.17 0.12 1/334 9794
---
ESTAB  0  0  10.123.0.50:50000  5.6.7.8:443
ESTAB  0  0  10.123.0.50:50001  8.9.10.11:443
ESTAB  0  0  10.99.0.1:50002     12.13.14.15:443
`

// Variant: a user just SSH'd in on the tailscale IP. Should count.
const busyFixture = idleFixture + `ESTAB  0  0  100.98.22.53:22  192.168.1.5:50000
`

func TestParseDevActivityIdle(t *testing.T) {
	got, err := parseDevActivity(idleFixture, "100.")
	if err != nil {
		t.Fatalf("parseDevActivity: %v", err)
	}
	if got.SSHUsers != 0 {
		t.Errorf("SSHUsers: got %d want 0", got.SSHUsers)
	}
	if got.TailscaleConns != 0 {
		// 3 conns en 10.123.x → TailscaleConns=0 (spec §S5 test contract)
		t.Errorf("TailscaleConns: got %d want 0 (3 conns on 10.123.x)", got.TailscaleConns)
	}
	if got.Load1 != 0.12 {
		t.Errorf("Load1: got %f want 0.12", got.Load1)
	}
}

func TestParseDevActivityBusy(t *testing.T) {
	got, err := parseDevActivity(busyFixture, "100.")
	if err != nil {
		t.Fatalf("parseDevActivity: %v", err)
	}
	if got.TailscaleConns != 1 {
		t.Errorf("TailscaleConns: got %d want 1 (100.98.22.53:22 should count)", got.TailscaleConns)
	}
}

func TestParseDevActivityUsers2(t *testing.T) {
	fix := strings.Replace(idleFixture, "# users=0", "# users=2", 1)
	got, err := parseDevActivity(fix, "100.")
	if err != nil {
		t.Fatal(err)
	}
	if got.SSHUsers != 2 {
		t.Errorf("SSHUsers: got %d want 2", got.SSHUsers)
	}
}

func TestParseDevActivitySalidaTruncada(t *testing.T) {
	// Only who section, no "---" separators.
	_, err := parseDevActivity("# users=0\n", "100.")
	if err == nil {
		t.Fatalf("expected error for truncated output")
	}
	if !strings.Contains(err.Error(), "expected 3 sections") {
		t.Errorf("error should mention 3 sections, got %q", err.Error())
	}
}

func TestParseDevActivityLoadavgMalo(t *testing.T) {
	fix := strings.Replace(idleFixture, "0.12 0.17 0.12 1/334 9794", "NaN 0.17 0.12 1/334 9794", 1)
	_, err := parseDevActivity(fix, "100.")
	if err == nil {
		t.Fatalf("expected error for bad loadavg")
	}
}

func TestDevActivityFakeRunner(t *testing.T) {
	r := func(_ context.Context, name string, args ...string) run.Result {
		if name != "lxc" {
			return run.Result{ExitCode: -1, Err: errors.New("unexpected: " + name)}
		}
		return run.Result{ExitCode: 0, Stdout: idleFixture}
	}
	got, err := DevActivity(testCtx(), r, "laia-dev", "100.")
	if err != nil {
		t.Fatalf("DevActivity: %v", err)
	}
	if got.SSHUsers != 0 || got.TailscaleConns != 0 {
		t.Errorf("got %+v", got)
	}
}

func TestDevActivityNoRunner(t *testing.T) {
	if _, err := DevActivity(testCtx(), nil, "laia-dev", "100."); err == nil {
		t.Errorf("expected error for nil runner")
	}
}

func TestIsTailscaleOrSSH(t *testing.T) {
	cases := []struct {
		local string
		want  bool
	}{
		{"100.98.22.53:22", true},  // tailscale
		{"100.98.22.53:443", true}, // tailscale any port
		{"192.168.1.5:22", true},   // SSH on any IP
		{"10.123.0.50:22", true},   // 10.123.x:22 — wait, the spec says outgoing on 10.123 doesn't count
		{"10.99.0.1:443", false},
		{"10.123.0.50:50000", false}, // outgoing on 10.123
		{"[::1]:22", true},           // IPv6 SSH
		{"", false},
	}
	for _, c := range cases {
		got := isTailscaleOrSSH(c.local, "100.")
		if got != c.want {
			t.Errorf("local=%q: got %v want %v", c.local, got, c.want)
		}
	}
}

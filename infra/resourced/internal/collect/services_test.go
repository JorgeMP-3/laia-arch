package collect

import (
	"context"
	"testing"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/config"
	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/run"
)

func TestCombineUnitsTabla(t *testing.T) {
	cases := []struct {
		name string
		in   []string
		want string
	}{
		{"all ok", []string{"ok", "ok", "ok"}, "ok"},
		{"one down (rest ok)", []string{"ok", "down", "ok"}, "down"},
		{"one unknown (rest ok)", []string{"ok", "unknown", "ok"}, "unknown"},
		{"down + unknown", []string{"down", "unknown"}, "down"},
		{"all unknown", []string{"unknown", "unknown"}, "unknown"},
		{"empty", []string{}, "ok"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := combineUnits(c.in); got != c.want {
				t.Errorf("got %q want %q", got, c.want)
			}
		})
	}
}

func TestServiceStatesLXC(t *testing.T) {
	svcs := []config.Service{
		{Name: "laia-agora", Class: "critical", Liveness: config.Liveness{Kind: config.LivenessLXC, Container: "laia-agora"}},
		{Name: "laia-edge", Class: "critical", Liveness: config.Liveness{Kind: config.LivenessLXC, Container: "laia-edge"}},
		{Name: "missing", Class: "critical", Liveness: config.Liveness{Kind: config.LivenessLXC, Container: "ghost"}},
	}
	lxcStates := map[string]string{
		"laia-agora": "Running",
		"laia-edge":  "Stopped",
	}
	r := func(_ context.Context, name string, args ...string) run.Result {
		t.Errorf("LXC should not need runner; got call to %s", name)
		return run.Result{}
	}
	got := ServiceStates(testCtx(), r, svcs, lxcStates)
	want := map[string]string{
		"laia-agora": "ok",
		"laia-edge":  "down",
		"missing":    "down", // not in map → down
	}
	if len(got) != len(want) {
		t.Fatalf("len: got %d want %d", len(got), len(want))
	}
	for k, v := range want {
		if got[k] != v {
			t.Errorf("%s: got %q want %q", k, got[k], v)
		}
	}
}

func TestServiceStatesSystemd(t *testing.T) {
	svcs := []config.Service{
		{Name: "nextcloud", Class: "critical", Liveness: config.Liveness{
			Kind:  config.LivenessSystemd,
			Units: []string{"snap.nextcloud.apache.service", "snap.nextcloud.mysql.service", "snap.nextcloud.php-fpm.service"},
		}},
	}
	// 2 ok, 1 down → combined down.
	r := runTable{
		"systemctl": {ExitCode: 0, Stdout: "active"},
	}.runner()
	// Patch: 1 of 3 should be down. Use a per-call Runner.
	callIdx := 0
	r2 := func(_ context.Context, name string, args ...string) run.Result {
		if callIdx == 1 { // 2nd unit is down
			return run.Result{ExitCode: 3, Stdout: "inactive"}
		}
		callIdx++
		return run.Result{ExitCode: 0, Stdout: "active"}
	}
	got := ServiceStates(testCtx(), r2, svcs, map[string]string{})
	if got["nextcloud"] != "down" {
		t.Errorf("nextcloud: got %q want down (1 of 3 units down)", got["nextcloud"])
	}
	_ = r
}

func TestServiceStatesLXCSystemdContainerParado(t *testing.T) {
	svcs := []config.Service{
		{Name: "cloudflared", Class: "critical", Liveness: config.Liveness{
			Kind:      config.LivenessLXCSystemd,
			Container: "laia-edge",
			Units:     []string{"cloudflared.service"},
		}},
	}
	// laia-edge is Stopped → we must NOT call lxc.
	lxcStates := map[string]string{"laia-edge": "Stopped"}
	calls := 0
	r := func(_ context.Context, name string, args ...string) run.Result {
		calls++
		return run.Result{ExitCode: 0, Stdout: "active"}
	}
	got := ServiceStates(testCtx(), r, svcs, lxcStates)
	if got["cloudflared"] != "unknown" {
		t.Errorf("got %q want unknown", got["cloudflared"])
	}
	if calls != 0 {
		t.Errorf("lxc must NOT be called when container is Stopped; got %d calls", calls)
	}
}

func TestServiceStatesLXCSystemdContainerRunningUnitDown(t *testing.T) {
	svcs := []config.Service{
		{Name: "cloudflared", Class: "critical", Liveness: config.Liveness{
			Kind:      config.LivenessLXCSystemd,
			Container: "laia-edge",
			Units:     []string{"cloudflared.service"},
		}},
	}
	lxcStates := map[string]string{"laia-edge": "Running"}
	// systemd reality: a unit in "failed" state exits 3 (exit 4 is
	// "no such unit" → unknown). Verified on the host, 2026-06-03.
	r := runTable{"lxc": {ExitCode: 3, Stdout: "failed"}}.runner()
	got := ServiceStates(testCtx(), r, svcs, lxcStates)
	if got["cloudflared"] != "down" {
		t.Errorf("got %q want down (cloudflared failed in Running container)", got["cloudflared"])
	}
}

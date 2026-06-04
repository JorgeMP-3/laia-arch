package evaluate

import (
	"testing"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/collect"
)

func TestIdleNowTabla(t *testing.T) {
	cases := []struct {
		name      string
		a         collect.Activity
		loadBelow float64
		want      bool
	}{
		{"all zero, loadBelow 0.2 → idle", collect.Activity{SSHUsers: 0, TailscaleConns: 0, Load1: 0.05}, 0.2, true},
		{"load high → not idle", collect.Activity{SSHUsers: 0, TailscaleConns: 0, Load1: 0.5}, 0.2, false},
		{"ssh open → not idle", collect.Activity{SSHUsers: 1, TailscaleConns: 0, Load1: 0.05}, 0.2, false},
		{"tailscale conn → not idle", collect.Activity{SSHUsers: 0, TailscaleConns: 1, Load1: 0.05}, 0.2, false},
		{"all conditions fail → not idle", collect.Activity{SSHUsers: 1, TailscaleConns: 1, Load1: 0.5}, 0.2, false},
		{"load exactly at threshold → not idle (strict less-than)", collect.Activity{SSHUsers: 0, TailscaleConns: 0, Load1: 0.2}, 0.2, false},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := IdleNow(c.a, c.loadBelow); got != c.want {
				t.Errorf("got %v want %v", got, c.want)
			}
		})
	}
}

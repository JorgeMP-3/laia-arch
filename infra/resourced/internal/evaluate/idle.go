package evaluate

import "github.com/JorgeMP-3/laia-arch/infra/resourced/internal/collect"

// IdleNow returns true if the laia-dev container is currently idle:
// no SSH session (who -q), no tailscale/SSH connection (ss filter),
// AND load1 below the configured threshold. PURE: no I/O, no clock.
//
// The "AND" is critical: a VM with low load but an open SSH session
// is NOT idle. A VM with high load but no users is not idle either
// (we want to know why it's busy). The S5 spec calls ssh=0 and
// tailscale=0 "implicit" — they are part of the predicate even
// though they are not in the YAML.
func IdleNow(a collect.Activity, loadBelow float64) bool {
	return a.SSHUsers == 0 && a.TailscaleConns == 0 && a.Load1 < loadBelow
}

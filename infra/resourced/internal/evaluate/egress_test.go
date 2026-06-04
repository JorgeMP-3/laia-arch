package evaluate

import (
	"testing"
	"time"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/collect"
	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/state"
)

func TestEgressEvalTable(t *testing.T) {
	now := time.Unix(1700000000, 0).UTC()
	script := "/opt/laia/current/infra/lxd/scripts/fix-egress-root.sh"
	cases := []struct {
		name  string
		probe collect.EgressProbe
		want  state.Light
	}{
		{"OK → ok", collect.EgressProbe{Outcome: collect.ProbeOK, Detail: "HTTP 200"}, state.LightOK},
		{"Down → red", collect.EgressProbe{Outcome: collect.ProbeDown, Detail: "curl exit 7"}, state.LightRed},
		{"Broken → unknown", collect.EgressProbe{Outcome: collect.ProbeBroken, Detail: "curl not installed"}, state.LightUnknown},
		{"Default (rare) → unknown", collect.EgressProbe{Outcome: collect.ProbeOutcome(99)}, state.LightUnknown},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := Egress(c.probe, now, script)
			if got.Light != c.want {
				t.Errorf("Light: got %q want %q", got.Light, c.want)
			}
			if !got.CheckedAt.Equal(now) {
				t.Errorf("CheckedAt: got %v want %v", got.CheckedAt, now)
			}
		})
	}
}

// TestEgressDownIncludesReapply: the Down Detail MUST mention the
// script; without it the alert is not actionable.
func TestEgressDownIncludesReapply(t *testing.T) {
	got := Egress(collect.EgressProbe{Outcome: collect.ProbeDown}, time.Now(), "/path/to/script.sh")
	if got.Light != state.LightRed {
		t.Errorf("Light: got %q want red", got.Light)
	}
	if got.Detail == "" || !contains(got.Detail, "/path/to/script.sh") {
		t.Errorf("Detail should include the reapply path, got %q", got.Detail)
	}
}

func contains(s, sub string) bool {
	return len(s) >= len(sub) && (s == sub || indexOf(s, sub) >= 0)
}

func indexOf(s, sub string) int {
	for i := 0; i+len(sub) <= len(s); i++ {
		if s[i:i+len(sub)] == sub {
			return i
		}
	}
	return -1
}

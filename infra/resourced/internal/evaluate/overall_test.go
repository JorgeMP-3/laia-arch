package evaluate

import (
	"testing"
	"time"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/state"
)

func dim(light state.Light) state.Dimension {
	return state.Dimension{Light: light, CheckedAt: time.Unix(0, 0).UTC()}
}

func TestOverallTable(t *testing.T) {
	cases := []struct {
		name string
		dims map[string]state.Dimension
		want state.Light
	}{
		{"empty → ok", map[string]state.Dimension{}, state.LightOK},
		{"only dev_idle ok → ok (ignore dev_idle)", map[string]state.Dimension{
			"dev_idle": dim(state.LightOK),
		}, state.LightOK},
		{"dev_idle ok + egress ok → ok", map[string]state.Dimension{
			"egress":   dim(state.LightOK),
			"dev_idle": dim(state.LightOK),
		}, state.LightOK},
		{"egress red → red", map[string]state.Dimension{
			"egress": dim(state.LightRed),
		}, state.LightRed},
		{"egress ok + ram warn → warn", map[string]state.Dimension{
			"egress": dim(state.LightOK),
			"ram":    dim(state.LightWarn),
		}, state.LightWarn},
		{"egress red + ram warn → red (worst wins)", map[string]state.Dimension{
			"egress": dim(state.LightRed),
			"ram":    dim(state.LightWarn),
		}, state.LightRed},
		{"egress unknown + ram ok → unknown (does not mask green)", map[string]state.Dimension{
			"egress": dim(state.LightUnknown),
			"ram":    dim(state.LightOK),
		}, state.LightUnknown},
		{"egress ok + dev_idle red → ok (dev_idle does not count)", map[string]state.Dimension{
			"egress":   dim(state.LightOK),
			"dev_idle": dim(state.LightRed),
		}, state.LightOK},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := Overall(c.dims); got != c.want {
				t.Errorf("got %q want %q", got, c.want)
			}
		})
	}
}

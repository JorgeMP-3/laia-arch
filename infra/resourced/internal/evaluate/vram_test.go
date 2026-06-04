package evaluate

import (
	"testing"
	"time"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/state"
)

func TestVRAMTabla(t *testing.T) {
	now := time.Unix(0, 0).UTC()
	cases := []struct {
		name string
		free int64
		want state.Light
	}{
		{"free above threshold → ok", 5000, state.LightOK},
		{"free at threshold → ok (equal is ok)", 1000, state.LightOK},
		{"free below threshold → warn", 999, state.LightWarn},
		{"free very low → warn (never red in v1)", 0, state.LightWarn},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := VRAM(0, 8192, c.free, 1000, now)
			if got.Light != c.want {
				t.Errorf("Light: got %q want %q", got.Light, c.want)
			}
		})
	}
}

func TestVRAMNeverRedInV1(t *testing.T) {
	// Even with 0 free, the dimension must not be red in v1.
	got := VRAM(8192, 8192, 0, 1000, time.Now())
	if got.Light == state.LightRed {
		t.Errorf("VRAM returned red; v1 contract is warn-or-ok")
	}
}

func TestVRAMUnknown(t *testing.T) {
	got := VRAMUnknown(time.Now(), nil)
	if got.Light != state.LightUnknown {
		t.Errorf("Light: got %q want unknown", got.Light)
	}
	if !contains(got.Detail, "could not read") {
		t.Errorf("Detail should say 'could not read', got %q", got.Detail)
	}
}

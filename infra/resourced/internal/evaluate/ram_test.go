package evaluate

import (
	"errors"
	"testing"
	"time"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/config"
	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/state"
)

func ramBudget() config.Budget {
	// Mirrors the example.yaml: baseline 5000, margin 3000, extra 2000.
	// red threshold = 8000, warn threshold = 10000.
	return config.Budget{
		RamProdBaselineMB: 5000,
		RamSafetyMarginMB: 3000,
		RamWarnExtraMB:    2000,
		VRAMMinFreeMB:     1,
		DiskWarnFreePct:   10,
		DiskRedFreePct:    5,
		DiskPaths:         []string{"/"},
	}
}

func TestRAMEvalTabla(t *testing.T) {
	now := time.Unix(1700000000, 0).UTC()
	b := ramBudget()
	cases := []struct {
		name string
		mb   int64
		want state.Light
	}{
		{"0 MB → red", 0, state.LightRed},
		{"7999 MB → red (just below threshold)", 7999, state.LightRed},
		{"8000 MB → warn (equal is NOT red)", 8000, state.LightWarn},
		{"9999 MB → warn (just below warn threshold)", 9999, state.LightWarn},
		{"10000 MB → ok (equal to warn is ok)", 10000, state.LightOK},
		{"25000 MB → ok", 25000, state.LightOK},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := RAM(c.mb, b, now)
			if got.Light != c.want {
				t.Errorf("Light: got %q want %q", got.Light, c.want)
			}
			if got.Metrics["available_mb"] != c.mb {
				t.Errorf("Metrics: got %d want %d", got.Metrics["available_mb"], c.mb)
			}
			if !got.CheckedAt.Equal(now) {
				t.Errorf("CheckedAt: got %v want %v", got.CheckedAt, now)
			}
		})
	}
}

// TestRAMDetailConNumeros: el Detail SIEMPRE lleva los umbrales y el
// valor medido (sin él la alerta no es accionable).
func TestRAMDetailConNumeros(t *testing.T) {
	got := RAM(9000, ramBudget(), time.Now())
	if got.Detail == "" {
		t.Fatal("Detail empty")
	}
	for _, sub := range []string{"9000", "8000", "10000"} {
		if !contains(got.Detail, sub) {
			t.Errorf("Detail should contain %q, got %q", sub, got.Detail)
		}
	}
}

func TestRAMUnknown(t *testing.T) {
	got := RAMUnknown(time.Now(), errors.New("open /proc/meminfo: permission denied"))
	if got.Light != state.LightUnknown {
		t.Errorf("Light: got %q want unknown", got.Light)
	}
	if !contains(got.Detail, "could not read") {
		t.Errorf("Detail should say 'could not read', got %q", got.Detail)
	}
	if !contains(got.Detail, "permission denied") {
		t.Errorf("Detail should include the error, got %q", got.Detail)
	}
}

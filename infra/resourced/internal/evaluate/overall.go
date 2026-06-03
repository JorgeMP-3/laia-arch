package evaluate

import (
	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/state"
)

// Overall combines the lights of the dimensions into a single host
// verdict. Rules:
//   - If there are no dimensions, return ok (degenerate case).
//   - If the only dimension is dev_idle (informational), return ok.
//   - Otherwise, return the light with the highest severity EXCLUDING
//     dev_idle. The 4th "unknown" light counts toward the max → a
//     measurement failure in a critical dimension is NOT masked by a
//     green.
//
// Why ignore dev_idle? Because it is the v2 shadow: its own definition
// says "never warn/red" (§S5). If Overall included it, an idle VM
// would lower Overall and trigger red alerts — the exact opposite of
// the intent.
func Overall(dims map[string]state.Dimension) state.Light {
	if len(dims) == 0 {
		return state.LightOK
	}
	worst := state.LightOK
	for k, d := range dims {
		if k == "dev_idle" {
			continue // informational: does not affect Overall
		}
		if d.Light.Severity() > worst.Severity() {
			worst = d.Light
		}
	}
	return worst
}

// Package evaluate — PURE evaluators of the watchlist.
//
// Given the raw output of a collector (measurements, lists, maps) and
// the config thresholds, they return a state.Dimension. They do not do
// I/O, do not read the clock (they receive it), and do not import
// collect.X with side effects. This makes them 100% testable with
// tables and fake Runners.
package evaluate

import (
	"time"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/collect"
	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/state"
)

// Egress translates the raw probe into a Dimension. The rule "Broken
// is NOT Red" is the heart of this evaluator: if curl is not in the
// container or lxc failed, we do not know whether there is egress —
// we say "unknown" (better than "all good", worse than "alarm"). The
// operator sees it and decides (reinstall curl, or check if lxd has a
// problem).
//
// Down → red: the container cannot reach the internet, the script must
// be reapplied. The Detail includes the reapply path so the alert is
// actionable without opening an editor.
func Egress(p collect.EgressProbe, now time.Time, reapplyScript string) state.Dimension {
	switch p.Outcome {
	case collect.ProbeOK:
		return state.Dimension{
			Light:     state.LightOK,
			Detail:    "probe " + p.Detail,
			CheckedAt: now,
		}
	case collect.ProbeDown:
		return state.Dimension{
			Light:     state.LightRed,
			Detail:    "containers cannot reach the internet — reapply " + reapplyScript,
			CheckedAt: now,
		}
	case collect.ProbeBroken:
		fallthrough
	default:
		return state.Dimension{
			Light:     state.LightUnknown,
			Detail:    "could not measure egress: " + p.Detail,
			CheckedAt: now,
		}
	}
}

package collect

import (
	"context"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/config"
	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/run"
)

// ServiceStates computes the per-service alive state for every
// service in the policy, by dispatching to the right liveness method.
// It is the orchestration layer between the raw collectors and the
// pure Prod evaluator: given the one-shot LXCStates map and the
// Runner, it produces a name→alive map ready to feed evaluate.Prod.
//
// All state is passed in: no hidden globals, no disk I/O. The function
// is testable with fake Runners and a fixture LXCStates map.
func ServiceStates(ctx context.Context, r run.Runner, services []config.Service, lxcStates map[string]string) map[string]string {
	out := make(map[string]string, len(services))
	for _, s := range services {
		out[s.Name] = serviceAlive(ctx, r, s, lxcStates)
	}
	return out
}

func serviceAlive(ctx context.Context, r run.Runner, s config.Service, lxcStates map[string]string) string {
	// lxcStates == nil means "lxd was unreachable" (lxc list failed):
	// we could not MEASURE, which is unknown — NOT down. Deploy lesson
	// (2026-06-03): the first deployed build conflated both and painted
	// 7 healthy containers red when the unit sandbox blocked the lxc
	// client. A non-nil map where the container is missing is different:
	// lxd answered and the container is gone → down for real.
	switch s.Liveness.Kind {
	case config.LivenessLXC:
		if lxcStates == nil {
			return "unknown"
		}
		// "Running" is the only "ok" state. Missing from the (valid)
		// map, Stopped, Error, Starting, anything else → down. The
		// evaluator maps missing critical → red, which is what we
		// want (a critical container that vanished IS down).
		if lxcStates[s.Liveness.Container] == "Running" {
			return "ok"
		}
		return "down"
	case config.LivenessSystemd:
		return combineUnits(hostUnitStates(ctx, r, s.Liveness.Units))
	case config.LivenessLXCSystemd:
		if lxcStates == nil {
			return "unknown"
		}
		// Short-circuit: do NOT poke a stopped container.
		if lxcStates[s.Liveness.Container] != "Running" {
			return "unknown"
		}
		return combineUnits(lxcUnitStates(ctx, r, s.Liveness.Container, s.Liveness.Units))
	}
	return "unknown"
}

// hostUnitStates calls SystemdActive for each unit (host units, not
// container units). Errors are swallowed — SystemdActive already
// maps them to "unknown".
func hostUnitStates(ctx context.Context, r run.Runner, units []string) []string {
	out := make([]string, 0, len(units))
	for _, u := range units {
		s, _ := SystemdActive(ctx, r, u)
		out = append(out, s)
	}
	return out
}

// lxcUnitStates calls LXCSystemdActive for each unit inside container.
func lxcUnitStates(ctx context.Context, r run.Runner, container string, units []string) []string {
	out := make([]string, 0, len(units))
	for _, u := range units {
		s, _ := LXCSystemdActive(ctx, r, container, u, "Running")
		out = append(out, s)
	}
	return out
}

// combineUnits: "ok" if all units ok, "down" if any down, else
// "unknown". "unknown" is the right answer when we have at least one
// non-ok AND non-down — meaning we could not determine the state
// (tool missing, permission, etc.).
func combineUnits(states []string) string {
	down, unknown := 0, 0
	for _, s := range states {
		switch s {
		case "ok":
			// ok
		case "down":
			down++
		default: // "unknown" or anything else
			unknown++
		}
	}
	switch {
	case down > 0:
		return "down"
	case unknown > 0:
		return "unknown"
	default:
		return "ok"
	}
}

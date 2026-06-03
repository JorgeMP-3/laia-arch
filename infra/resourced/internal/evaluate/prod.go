package evaluate

import (
	"fmt"
	"sort"
	"strings"
	"time"

	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/config"
	"github.com/JorgeMP-3/laia-arch/infra/resourced/internal/state"
)

// ProdInput is the pre-computed per-service liveness. The main loop
// builds this from the liveness kind of each service:
//
//   - lxc         → state from LXCStates map (Running=ok, else=down)
//   - systemd     → combined alive of all units via SystemdActive
//   - lxc_systemd → unknown if container not Running, else combined
//     of LXCSystemdActive per unit
//
// "combined" is: "ok" if all units ok, "down" if any down, "unknown"
// otherwise. Missing in the map = "unknown" (caller decided to
// skip measurement).
type ProdInput struct {
	Services []config.Service
	States   map[string]string // name → "ok" | "down" | "unknown"
}

// Prod computes the prod Dimension (only critical services count
// for the light) and the full Services map (critical + dev). Pure
// function: no I/O, no clock. The dimension's Detail names the
// down services for the operator; the Services map gives the full
// per-service state for `laia-res status`.
func Prod(in ProdInput, now time.Time) (state.Dimension, map[string]state.ServiceState) {
	services := make(map[string]state.ServiceState, len(in.Services))
	var critLights []state.Light
	// var devLights []state.Light // kept for completeness, not used for prod light
	var downCritical []string
	var unknownCritical []string

	for _, s := range in.Services {
		alive := in.States[s.Name]
		if alive == "" {
			alive = "unknown"
		}
		detail := ""
		switch alive {
		case "ok":
			// no detail needed
		case "down":
			detail = "down"
		case "unknown":
			detail = "could not measure"
		}
		services[s.Name] = state.ServiceState{
			Class:  s.Class,
			Alive:  alive,
			Detail: detail,
		}
		if s.Class == "critical" {
			switch alive {
			case "ok":
				critLights = append(critLights, state.LightOK)
			case "down":
				critLights = append(critLights, state.LightRed)
				downCritical = append(downCritical, s.Name)
			case "unknown":
				critLights = append(critLights, state.LightUnknown)
				unknownCritical = append(unknownCritical, s.Name)
			}
		}
	}

	dim := state.Dimension{CheckedAt: now}
	totalCritical := 0
	for _, s := range in.Services {
		if s.Class == "critical" {
			totalCritical++
		}
	}
	okCount := 0
	for _, l := range critLights {
		if l == state.LightOK {
			okCount++
		}
	}
	switch {
	case len(downCritical) > 0:
		dim.Light = state.LightRed
		// Stable order in the detail so tests are deterministic.
		sort.Strings(downCritical)
		dim.Detail = fmt.Sprintf("down: %s", strings.Join(downCritical, ", "))
	case len(unknownCritical) > 0:
		dim.Light = state.LightUnknown
		sort.Strings(unknownCritical)
		dim.Detail = fmt.Sprintf("could not measure: %s", strings.Join(unknownCritical, ", "))
	default:
		dim.Light = state.LightOK
		dim.Detail = fmt.Sprintf("%d/%d critical alive", okCount, totalCritical)
	}
	dim.Metrics = map[string]int64{
		"critical_total":   int64(totalCritical),
		"critical_ok":      int64(okCount),
		"critical_down":    int64(len(downCritical)),
		"critical_unknown": int64(len(unknownCritical)),
	}
	return dim, services
}
